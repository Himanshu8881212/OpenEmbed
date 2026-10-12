"""Durable preparation/indexing worker (procrastinate on PostgreSQL).

Run: uv run --env-file ../.env python -m kbpy.worker
Guarantees:
  * job rows and queue messages are created in one API transaction;
  * worker heartbeats + `recover_stalled` re-queue tasks of crashed workers (lease expiry);
  * every step is idempotent: segment ids are uuid5(version, profile, ordinal), usage events have unique keys,
    terminal items are skipped on duplicate delivery;
  * publication flips files.current_version_id in one transaction: search sees the old or new complete version.
"""
import contextlib
import datetime as dt
import hashlib
import json
import logging
import os
import tempfile
import uuid

import boto3
import httpx
import procrastinate
import procrastinate.exceptions
import psycopg
from psycopg.rows import dict_row

from .prepare import ItemError, prepare

log = logging.getLogger("kbpy.worker")
DB = os.environ["KB_WORKER_DATABASE_URL"]
BUCKET = os.environ["KB_S3_BUCKET"]
INFERENCE_URL = os.environ.get("KB_INFERENCE_IMPORT_URL") or os.environ["KB_INFERENCE_URL"]
INFERENCE_TOKEN = os.environ["KB_INFERENCE_TOKEN"]
RETENTION = dt.timedelta(seconds=int(os.environ.get("KB_RETENTION_SECONDS", "604800")))
MAX_ATTEMPTS = int(os.environ.get("KB_MAX_ATTEMPTS", "5"))
# Every worker heartbeats every HEARTBEAT s, whatever its lease, so no worker's prune threshold (its LEASE, >= 3x
# HEARTBEAT) can ever remove a healthy peer that happens to use a different lease setting.
HEARTBEAT = 2.0
LEASE = max(float(os.environ.get("KB_LEASE_SECONDS", "30")), 3 * HEARTBEAT)  # a worker silent this long loses its tasks
BATCH = 16
SEG_NS = uuid.UUID("6f1d3c52-7f0e-4a51-9a39-3f2f4c1b8e01")

s3 = boto3.client("s3", endpoint_url=os.environ["KB_S3_ENDPOINT"], region_name=os.environ["KB_S3_REGION"],
                  aws_access_key_id=os.environ["KB_S3_ACCESS_KEY"], aws_secret_access_key=os.environ["KB_S3_SECRET_KEY"])
app = procrastinate.App(connector=procrastinate.PsycopgConnector(conninfo=DB))


@contextlib.contextmanager
def tx(ws: str | None):
    """One transaction as kb_worker with the workspace context set transaction-locally (RLS applies)."""
    with psycopg.connect(DB, row_factory=dict_row) as c:
        with c.transaction():
            if ws:
                c.execute("SELECT set_config('app.workspace_id', %s, true)", (ws,))
            yield c


def one(c, sql, *a):
    return c.execute(sql, a).fetchone()


def job_ws(job_id: str) -> str:
    with tx(None) as c:
        r = one(c, "SELECT kb_job_workspace(%s) ws", job_id)
    if not r or not r["ws"]:
        raise ItemError("NOT_FOUND", "job vanished")
    return str(r["ws"])


def seg_id(version_id, profile_id, ordinal) -> str:
    return str(uuid.uuid5(SEG_NS, f"{version_id}:{profile_id}:{ordinal}"))


def vec(v) -> str:
    return "[" + ",".join(repr(float(x)) for x in v) + "]"


def embed(profile: dict, inputs: list[list[dict]]) -> list[dict]:
    try:
        r = httpx.post(f"{INFERENCE_URL}/embed", timeout=600, headers={"authorization": f"Bearer {INFERENCE_TOKEN}"},
                       json={"profile": {k: profile[k] for k in ("model", "revision", "dtype")}, "inputs": [{"parts": p} for p in inputs],
                             "processing": processing(profile)})
    except httpx.HTTPError:
        raise ItemError("SERVICE_UNAVAILABLE", "embedding service unavailable", retryable=True)
    if r.status_code in (400, 413, 415):
        d = r.json().get("detail", {})
        raise ItemError(d.get("code", "UNREADABLE"), d.get("message", "input rejected by model"))
    if r.status_code != 200:
        raise ItemError("SERVICE_UNAVAILABLE", f"embedding service returned {r.status_code}", retryable=True)
    data = r.json()["data"]
    if len(data) != len(inputs):
        raise ItemError("SERVICE_UNAVAILABLE", "embedding count mismatch", retryable=True)
    return data


def processing(profile: dict) -> dict:
    """Per-modality processor settings that are part of the profile (e.g. sharper video frames)."""
    prep = profile["preparation"]
    return {k: {"max_soft_tokens": prep[k]["max_soft_tokens"]} for k in ("image", "video") if prep.get(k, {}).get("max_soft_tokens")}


def finalize(c, job_id):
    c.execute("SELECT kb_finalize_job(%s)", (job_id,))


def fail_item(ws, job_id, item_id, e: ItemError):
    with tx(ws) as c:
        c.execute("UPDATE job_items SET state='failed', error_code=%s, error_message=%s, retryable=%s, updated_at=now() WHERE id=%s AND state IN ('queued','running')",
                  (e.code, e.message[:500], e.retryable, item_id))
        finalize(c, job_id)
    log.info(json.dumps({"event": "item_failed", "job_id": job_id, "item_id": item_id, "code": e.code}))


def cancelled(c, job_id) -> bool:
    return one(c, "SELECT state FROM jobs WHERE id=%s", job_id)["state"] == "cancel_requested"


# ---------------------------------------------------------------- ingestion

@app.task(name="ingest_item", queue="ingest", pass_context=True,
          retry=procrastinate.RetryStrategy(max_attempts=MAX_ATTEMPTS - 1, exponential_wait=2))
def ingest_item(context, job_id: str, item_id: str):
    ws = job_ws(job_id)
    with tx(ws) as c:
        it = one(c, "SELECT * FROM job_items WHERE id=%s FOR UPDATE", item_id)
        if not it or it["state"] in ("succeeded", "failed", "cancelled"):
            return  # duplicate delivery / already handled
        if cancelled(c, job_id):
            c.execute("UPDATE job_items SET state='cancelled', updated_at=now() WHERE id=%s", (item_id,))
            finalize(c, job_id)
            return
        c.execute("UPDATE job_items SET state='running', attempts=attempts+1, updated_at=now() WHERE id=%s", (item_id,))
        finalize(c, job_id)
    try:
        process_item(ws, job_id, item_id)
    except ItemError as e:
        if e.retryable and e.code != "QUOTA_EXCEEDED" and context.job.attempts + 1 < MAX_ATTEMPTS:
            raise  # transient: procrastinate retries with backoff (quota waits for the user's retry)
        fail_item(ws, job_id, item_id, e)
    except Exception as e:
        log.exception("item error")
        if context.job.attempts + 1 < MAX_ATTEMPTS:
            raise
        fail_item(ws, job_id, item_id, ItemError("INTERNAL_ERROR", f"processing failed: {type(e).__name__}", retryable=True))


def verify_upload(ws: str, uf: dict) -> str:
    """Verify the whole-file SHA-256 of uploaded bytes, then keep one content-addressed copy per workspace."""
    blob_key = f"ws/{ws}/blobs/{uf['sha256']}"
    if uf["verified_at"]:
        with tx(ws) as c:
            if not one(c, "SELECT 1 FROM blobs WHERE sha256=%s", uf["sha256"]):
                raise ItemError("UPLOAD_MISSING", "verified bytes were removed by retention cleanup; upload the file again")
        return blob_key
    try:
        body = s3.get_object(Bucket=BUCKET, Key=uf["object_key"])["Body"]
    except s3.exceptions.NoSuchKey:
        raise ItemError("UPLOAD_MISSING", "uploaded bytes are no longer available; upload the file again")
    h, n = hashlib.sha256(), 0
    for chunk in body.iter_chunks(1 << 20):
        h.update(chunk)
        n += len(chunk)
    if n != uf["size"] or h.hexdigest() != uf["sha256"]:
        raise ItemError("CHECKSUM_MISMATCH", "uploaded bytes do not match the manifest size/SHA-256; upload the file again")
    with tx(ws) as c:
        if not one(c, "SELECT 1 FROM blobs WHERE sha256=%s", uf["sha256"]):
            s3.copy_object(Bucket=BUCKET, Key=blob_key, CopySource={"Bucket": BUCKET, "Key": uf["object_key"]})
            c.execute("INSERT INTO blobs (workspace_id, sha256, size, object_key) VALUES (kb_ws(), %s, %s, %s) ON CONFLICT DO NOTHING",
                      (uf["sha256"], uf["size"], blob_key))
        c.execute("UPDATE upload_files SET verified_at=now() WHERE id=%s", (uf["id"],))
    s3.delete_object(Bucket=BUCKET, Key=uf["object_key"])
    return blob_key


def resolve_version(ws, job, it, uf) -> tuple[str, str]:
    """Find/create the file and its new (unpublished) version. Idempotent across retries."""
    with tx(ws) as c:
        it = one(c, "SELECT * FROM job_items WHERE id=%s FOR UPDATE", it["id"])
        if it["file_version_id"]:
            return str(it["file_id"]), str(it["file_version_id"])
        file_id = it["file_id"] or uf["replaces_file_id"]
        if not file_id:  # committed material imported again (e.g. into another store): same source
            r = one(c, """SELECT i.file_id FROM job_items i JOIN files f ON f.id=i.file_id AND f.deleted_at IS NULL
                          WHERE i.upload_file_id=%s AND i.state='succeeded' LIMIT 1""", uf["id"])
            file_id = r and r["file_id"]
        if not file_id and job["store_id"]:
            r = one(c, """SELECT f.id FROM store_files sf JOIN files f ON f.id=sf.file_id
                          WHERE sf.store_id=%s AND f.path=%s AND f.deleted_at IS NULL LIMIT 1""", job["store_id"], uf["path"])
            file_id = r and r["id"]
        if file_id:
            f = one(c, "SELECT f.*, v.sha256 cur_sha FROM files f LEFT JOIN file_versions v ON v.id=f.current_version_id WHERE f.id=%s AND f.deleted_at IS NULL FOR UPDATE OF f", file_id)
            if not f:
                raise ItemError("NOT_FOUND", "target file was deleted")
            if f["cur_sha"] == uf["sha256"] and f["current_version_id"]:
                version_id = f["current_version_id"]  # unchanged bytes: reuse the published version
            else:
                version_id = None
        else:
            file_id = one(c, "INSERT INTO files (workspace_id, path) VALUES (kb_ws(), %s) RETURNING id", uf["path"])["id"]
            version_id = None
        if not version_id:
            # hold the blob against concurrent cleanup until this version references it
            if not one(c, "SELECT 1 FROM blobs WHERE sha256=%s FOR KEY SHARE", uf["sha256"]):
                raise ItemError("UPLOAD_MISSING", "verified bytes were removed by retention cleanup; upload the file again")
            no = one(c, "SELECT coalesce(max(version_no),0)+1 n FROM file_versions WHERE file_id=%s", file_id)["n"]
            version_id = one(c, """INSERT INTO file_versions (workspace_id, file_id, version_no, sha256, size, filename, media_type)
                                   VALUES (kb_ws(), %s, %s, %s, %s, %s, %s) RETURNING id""",
                             file_id, no, uf["sha256"], uf["size"], os.path.basename(uf["path"]), uf["media_type"])["id"]
        c.execute("UPDATE job_items SET file_id=%s, file_version_id=%s WHERE id=%s", (file_id, version_id, it["id"]))
        return str(file_id), str(version_id)


def needed_profiles(c, store_id, file_id) -> list[dict]:
    """Profiles of every live (active/building/ready) index that will contain this file, including live views over its stores."""
    return c.execute("""
        WITH direct AS (SELECT %s::uuid AS sid UNION SELECT store_id FROM store_files WHERE file_id=%s)
        SELECT DISTINCT p.* FROM index_revisions r JOIN embedding_profiles p ON p.id=r.profile_id
         JOIN stores s ON s.id=r.store_id AND s.deleted_at IS NULL
         WHERE r.state IN ('active','building','ready')
           AND (r.store_id IN (SELECT sid FROM direct)
                OR (s.kind='view' AND EXISTS (SELECT 1 FROM direct d WHERE s.definition->'parents' ? d.sid::text)))""", (store_id, file_id)).fetchall()


def index_quota_ok(c) -> bool:
    r = one(c, """SELECT w.plan, coalesce((SELECT sum(quantity) FROM usage_events WHERE kind LIKE 'index_%%'
                    AND created_at >= date_trunc('month', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'),0) used FROM workspaces w WHERE w.id=kb_ws()""")
    return r["plan"].get("allow_excess") or r["used"] < r["plan"]["limits"]["index_tokens_month"]


def embed_version(ws, job_id, version_id, profile, path_on_disk, v):
    """Build all segments of (version, profile) and insert them in one transaction (existence => complete)."""
    with tx(ws) as c:
        if one(c, "SELECT 1 FROM segments WHERE file_version_id=%s AND profile_id=%s LIMIT 1", version_id, profile["id"]):
            return
        # identical bytes + filename already embedded for this profile: copy vectors, no inference, no charge
        src = one(c, """SELECT s.file_version_id FROM segments s JOIN file_versions o ON o.id=s.file_version_id
                        WHERE o.sha256=%s AND o.filename=%s AND s.profile_id=%s AND o.id<>%s LIMIT 1""", v["sha256"], v["filename"], profile["id"], version_id)
        if src:
            rows = c.execute("SELECT * FROM segments WHERE file_version_id=%s AND profile_id=%s", (src["file_version_id"], profile["id"])).fetchall()
            for r in rows:
                c.execute("""INSERT INTO segments (id, workspace_id, file_version_id, profile_id, ordinal, modality, location, content, token_count, embedding)
                             VALUES (%s, kb_ws(), %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""",
                          (seg_id(version_id, profile["id"], r["ordinal"]), version_id, profile["id"], r["ordinal"], r["modality"],
                           json.dumps(r["location"]), r["content"], r["token_count"], r["embedding"]))
            return
        # same model/runtime + identical preparation for this media type → vectors are identical: copy, don't recompute
        mod = MEDIA_PREP_KEY.get(v["media_type"])
        if mod:
            twin = one(c, """SELECT s.profile_id FROM segments s JOIN embedding_profiles p ON p.id = s.profile_id
                             WHERE s.file_version_id=%s AND p.model=%s AND p.revision=%s AND p.dtype=%s
                               AND p.preparation->%s = %s::jsonb AND p.id <> %s LIMIT 1""",
                       version_id, profile["model"], profile["revision"], profile["dtype"], mod, json.dumps(profile["preparation"][mod]), profile["id"])
            if twin:
                for r in c.execute("SELECT * FROM segments WHERE file_version_id=%s AND profile_id=%s", (version_id, twin["profile_id"])).fetchall():
                    c.execute("""INSERT INTO segments (id, workspace_id, file_version_id, profile_id, ordinal, modality, location, content, token_count, embedding)
                                 VALUES (%s, kb_ws(), %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""",
                              (seg_id(version_id, profile["id"], r["ordinal"]), version_id, profile["id"], r["ordinal"], r["modality"],
                               json.dumps(r["location"]), r["content"], r["token_count"], r["embedding"]))
                return
        if not index_quota_ok(c):
            raise ItemError("QUOTA_EXCEEDED", "monthly indexing allowance exhausted", retryable=True)
    segs = prepare(path_on_disk, v["media_type"], profile["preparation"])
    title = v["filename"]
    vectors = []
    for i in range(0, len(segs), BATCH):
        with tx(ws) as c:  # safe cancellation boundary between batches
            if cancelled(c, job_id):
                raise Cancelled()
        batch = segs[i:i + BATCH]
        inputs = [[{**p, "text": profile["document_template"].replace("{title}", context_title(profile, title, s)).replace("{content}", p["text"])} if p["type"] == "text" else p
                   for p in s["parts"]] for s in batch]
        vectors += embed(profile, inputs)
    text_tokens = sum(r["tokens"] for s, r in zip(segs, vectors) if s["modality"] == "text")
    media_tokens = sum(r["tokens"] for s, r in zip(segs, vectors) if s["modality"] != "text")
    with tx(ws) as c:
        for n, (s, r) in enumerate(zip(segs, vectors)):
            c.execute("""INSERT INTO segments (id, workspace_id, file_version_id, profile_id, ordinal, modality, location, content, token_count, embedding)
                         VALUES (%s, kb_ws(), %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""",
                      (seg_id(version_id, profile["id"], n), version_id, profile["id"], n, s["modality"], json.dumps(s["location"]),
                       s["content"], r["tokens"], vec(r["embedding"])))
        for kind, q in (("index_text_tokens", text_tokens), ("index_media_tokens", media_tokens)):
            if q:
                c.execute("INSERT INTO usage_events (workspace_id, kind, quantity, idem_key) VALUES (kb_ws(), %s, %s, %s) ON CONFLICT DO NOTHING",
                          (kind, q, f"{kind}:{version_id}:{profile['id']}"))


# media types whose segments depend only on one preparation key (PDF can mix text and page images: not reusable)
MEDIA_PREP_KEY = {"image/jpeg": "image", "image/png": "image", "audio/wav": "audio", "audio/mpeg": "audio", "video/mp4": "video"}


def context_title(profile: dict, filename: str, seg: dict) -> str:
    """Profiles with text.contextual_title embed each passage with its place in the document (file › section · page)."""
    if not profile["preparation"].get("text", {}).get("contextual_title"):
        return filename
    loc = seg["location"]
    t = filename + (f" › {loc['section']}" if loc.get("section") else "") + (f" · p. {loc['page']}" if loc.get("page") else "")
    return t.replace("|", "/")[:300]


class Cancelled(Exception):
    pass


def process_item(ws, job_id, item_id):
    with tx(ws) as c:
        job = one(c, "SELECT * FROM jobs WHERE id=%s", job_id)
        it = one(c, "SELECT * FROM job_items WHERE id=%s", item_id)
        uf = one(c, "SELECT * FROM upload_files WHERE id=%s", it["upload_file_id"]) if it["upload_file_id"] else None
    if not uf:
        raise ItemError("UPLOAD_MISSING", "upload record is gone; upload the file again")
    blob_key = verify_upload(ws, uf)
    file_id, version_id = resolve_version(ws, job, it, uf)
    with tx(ws) as c:
        v = one(c, "SELECT * FROM file_versions WHERE id=%s", version_id)
        profiles = needed_profiles(c, job["store_id"], file_id)
    try:
        with tempfile.NamedTemporaryFile() as tmp:
            downloaded = False
            for p in profiles:
                with tx(ws) as c:
                    done = one(c, "SELECT 1 FROM segments WHERE file_version_id=%s AND profile_id=%s LIMIT 1", version_id, p["id"])
                if done:
                    continue
                if not downloaded:
                    s3.download_fileobj(BUCKET, blob_key, tmp)
                    tmp.flush()
                    downloaded = True
                embed_version(ws, job_id, version_id, p, tmp.name, v)
    except Cancelled:
        with tx(ws) as c:
            c.execute("UPDATE job_items SET state='cancelled', updated_at=now() WHERE id=%s AND state='running'", (item_id,))
            finalize(c, job_id)
        return
    publish(ws, job, item_id, file_id, version_id)


def publish(ws, job, item_id, file_id, version_id):
    """Atomic publication: membership + current version flip + item success in one transaction."""
    with tx(ws) as c:
        it = one(c, "SELECT state FROM job_items WHERE id=%s FOR UPDATE", item_id)
        if it["state"] != "running":
            return
        if cancelled(c, job["id"]):
            c.execute("UPDATE job_items SET state='cancelled', updated_at=now() WHERE id=%s", (item_id,))
            finalize(c, job["id"])
            return
        f = one(c, "SELECT f.deleted_at, cv.version_no cur FROM files f LEFT JOIN file_versions cv ON cv.id=f.current_version_id WHERE f.id=%s FOR UPDATE OF f", file_id)
        if f["deleted_at"]:
            raise ItemError("NOT_FOUND", "the source was deleted during processing")
        if job["store_id"] and one(c, "SELECT deleted_at FROM stores WHERE id=%s", job["store_id"])["deleted_at"]:
            raise ItemError("NOT_FOUND", "the store was deleted during processing")
        new_no = one(c, "SELECT version_no FROM file_versions WHERE id=%s", version_id)["version_no"]
        if f["cur"] is None or new_no >= f["cur"]:  # never let an older job overwrite a newer published version
            c.execute("UPDATE files SET current_version_id=%s, updated_at=now() WHERE id=%s", (version_id, file_id))
        if job["store_id"]:
            c.execute("INSERT INTO store_files (workspace_id, store_id, file_id) VALUES (kb_ws(), %s, %s) ON CONFLICT DO NOTHING", (job["store_id"], file_id))
        if job["params"].get("connector_id"):
            c.execute("UPDATE files SET metadata = metadata || jsonb_build_object('connector_id', %s::text) WHERE id=%s", (job["params"]["connector_id"], file_id))
        c.execute("UPDATE job_items SET state='succeeded', error_code=NULL, error_message=NULL, updated_at=now() WHERE id=%s", (item_id,))
        finalize(c, job["id"])


# ---------------------------------------------------------------- recovery and maintenance

@app.periodic(cron="* * * * * */10")
@app.task(name="recover_stalled", queue="maintenance", queueing_lock="recover_stalled", pass_context=True)
async def recover_stalled(context, timestamp: int):
    """Lease expiry: tasks held by workers without a heartbeat for LEASE seconds go back to the queue."""
    for job in await context.app.job_manager.get_stalled_jobs(seconds_since_heartbeat=LEASE):
        log.warning(json.dumps({"event": "lease_expired", "task": job.task_name, "job": job.id}))
        await context.app.job_manager.retry_job(job)


@app.periodic(cron="*/5 * * * *")
@app.task(name="gc", queue="maintenance", queueing_lock="gc")
def gc(timestamp: int):
    run_gc()


def workspaces() -> list[str]:
    with psycopg.connect(DB, row_factory=dict_row) as c:
        return [str(r["id"]) for r in c.execute("SELECT kb_maintenance_workspaces() id").fetchall()]


def run_gc():
    for ws in workspaces():
        gc_workspace(ws)


def gc_workspace(ws: str):
    cutoff = dt.datetime.now(dt.timezone.utc) - RETENTION
    with tx(ws) as c:
        # expired upload sessions: abort multipart uploads, drop unverified bytes
        for f in c.execute("""SELECT f.object_key, f.s3_upload_id FROM upload_files f JOIN upload_sessions s ON s.id=f.session_id
                              WHERE s.state='open' AND s.expires_at < now()""").fetchall():
            if f["s3_upload_id"]:
                with contextlib.suppress(Exception):
                    s3.abort_multipart_upload(Bucket=BUCKET, Key=f["object_key"], UploadId=f["s3_upload_id"])
        c.execute("UPDATE upload_sessions SET state='expired' WHERE state='open' AND expires_at < now()")
        for a in c.execute("DELETE FROM query_assets WHERE expires_at < now() RETURNING object_key").fetchall():
            s3.delete_object(Bucket=BUCKET, Key=a["object_key"])
        # deleted sources past retention: drop memberships, versions (segments cascade)
        c.execute("DELETE FROM store_files WHERE file_id IN (SELECT id FROM files WHERE deleted_at < %s)", (cutoff,))
        c.execute("UPDATE files SET current_version_id=NULL WHERE deleted_at < %s", (cutoff,))
        c.execute("DELETE FROM files WHERE deleted_at < %s", (cutoff,))
        # superseded versions not pinned by a snapshot and not in-flight
        c.execute("""DELETE FROM file_versions v WHERE v.created_at < %s
                       AND NOT EXISTS (SELECT 1 FROM files f WHERE f.current_version_id=v.id)
                       AND NOT EXISTS (SELECT 1 FROM store_files sf WHERE sf.pinned_version_id=v.id)
                       AND NOT EXISTS (SELECT 1 FROM job_items i WHERE i.file_version_id=v.id AND i.state IN ('queued','running'))""", (cutoff,))
        # unreferenced blobs
        # unreferenced blobs, except bytes an in-flight import is about to publish (verified but no version yet)
        orphans = c.execute("""DELETE FROM blobs b WHERE b.created_at < %s
                                 AND NOT EXISTS (SELECT 1 FROM file_versions v WHERE v.sha256=b.sha256)
                                 AND NOT EXISTS (SELECT 1 FROM job_items i JOIN upload_files uf ON uf.id=i.upload_file_id
                                                 WHERE uf.sha256=b.sha256 AND i.state IN ('queued','running'))
                               RETURNING object_key""", (cutoff,)).fetchall()
    for o in orphans:
        s3.delete_object(Bucket=BUCKET, Key=o["object_key"])


@app.periodic(cron="0 * * * *")
@app.task(name="sample_storage", queue="maintenance", queueing_lock="sample_storage")
def sample_storage(timestamp: int):
    """Hourly storage sample per workspace (originals once + prepared text + vectors + metadata), for GiB-month."""
    for ws in workspaces():
        with tx(ws) as c:
            c.execute("""INSERT INTO storage_samples (workspace_id, bytes) SELECT kb_ws(),
                (SELECT coalesce(sum(size),0) FROM blobs) + (SELECT coalesce(sum(octet_length(coalesce(content,''))),0) FROM segments)
                + (SELECT count(*) FROM segments) * 3072 + (SELECT coalesce(sum(octet_length(metadata::text)),0) FROM files)""")


@app.task(name="embed_item", queue="ingest", pass_context=True,
          retry=procrastinate.RetryStrategy(max_attempts=MAX_ATTEMPTS - 1, exponential_wait=2))
def embed_item(context, job_id: str, item_id: str):
    """Ensure vectors for one existing file version and the job's profile (reindex / rebuild merge)."""
    from . import jobs
    ws = job_ws(job_id)
    with tx(ws) as c:
        it = one(c, "SELECT * FROM job_items WHERE id=%s FOR UPDATE", item_id)
        if not it or it["state"] in ("succeeded", "failed", "cancelled"):
            return
        if cancelled(c, job_id):
            c.execute("UPDATE job_items SET state='cancelled', updated_at=now() WHERE id=%s", (item_id,))
            finalize(c, job_id)
            jobs.after_items(c, job_id)
            return
        c.execute("UPDATE job_items SET state='running', attempts=attempts+1, updated_at=now() WHERE id=%s", (item_id,))
        finalize(c, job_id)
        job = one(c, "SELECT * FROM jobs WHERE id=%s", job_id)
        v = one(c, "SELECT v.*, b.object_key FROM file_versions v JOIN blobs b ON b.workspace_id=v.workspace_id AND b.sha256=v.sha256 WHERE v.id=%s", it["file_version_id"])
        profile = one(c, "SELECT * FROM embedding_profiles WHERE id=%s", job["params"]["profile_id"])
    try:
        if not v:
            raise ItemError("NOT_FOUND", "source version no longer exists")
        with tempfile.NamedTemporaryFile() as tmp:
            s3.download_fileobj(BUCKET, v["object_key"], tmp)
            tmp.flush()
            embed_version(ws, job_id, str(v["id"]), profile, tmp.name, v)
        with tx(ws) as c:
            c.execute("UPDATE job_items SET state='succeeded', updated_at=now() WHERE id=%s AND state='running'", (item_id,))
            finalize(c, job_id)
            jobs.after_items(c, job_id)
    except Cancelled:
        with tx(ws) as c:
            c.execute("UPDATE job_items SET state='cancelled', updated_at=now() WHERE id=%s", (item_id,))
            finalize(c, job_id)
            jobs.after_items(c, job_id)
    except ItemError as e:
        if e.retryable and e.code != "QUOTA_EXCEEDED" and context.job.attempts + 1 < MAX_ATTEMPTS:
            raise
        fail_item(ws, job_id, item_id, e)
        with tx(ws) as c:
            jobs.after_items(c, job_id)


@app.periodic(cron="* * * * *")
@app.task(name="schedule_connectors", queue="maintenance", queueing_lock="schedule_connectors")
def schedule_connectors(timestamp: int):
    """Scheduled sync: start a sync job for each due connector (inside its tenant context)."""
    with psycopg.connect(DB, row_factory=dict_row) as c:
        due = c.execute("SELECT * FROM kb_due_connectors()").fetchall()
    for d in due:
        with tx(str(d["workspace_id"])) as c:
            con = one(c, "SELECT * FROM connectors WHERE id=%s AND next_run_at <= now() AND deleted_at IS NULL FOR UPDATE SKIP LOCKED", d["id"])
            if not con:
                continue
            job = one(c, "INSERT INTO jobs (workspace_id, store_id, kind, params, created_by) VALUES (kb_ws(), %s, 'connector_sync', %s, 'scheduler') RETURNING id",
                      con["store_id"], json.dumps({"connector_id": str(con["id"])}))
            c.execute("UPDATE connectors SET last_job_id=%s, next_run_at=now() + make_interval(mins => interval_minutes) WHERE id=%s", (job["id"], con["id"]))
            c.execute("SELECT procrastinate_defer_jobs_v1(ARRAY[ROW('maintenance','run_job',0,NULL,NULL,%s::jsonb,NULL)::procrastinate_job_to_defer_v1])",
                      (json.dumps({"job_id": str(job["id"])}),))


@app.task(name="run_job", queue="maintenance", retry=procrastinate.RetryStrategy(max_attempts=MAX_ATTEMPTS - 1, exponential_wait=2))
def run_job(job_id: str):
    from . import jobs  # store deletion, source deletion, merge, derive, reindex
    ws = job_ws(job_id)
    jobs.run(ws, job_id)


def main():
    """Run the worker; on database/registration failures (e.g. pruned by a peer, DB restart) re-register and continue."""
    import time
    logging.basicConfig(level=os.environ.get("KB_LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
    backoff = 1.0
    while True:
        started = time.monotonic()
        try:
            with app.open():
                app.run_worker(queues=os.environ.get("KB_WORKER_QUEUES", "ingest,maintenance").split(","),
                               concurrency=int(os.environ.get("KB_WORKER_CONCURRENCY", "2")), wait=True,
                               update_heartbeat_interval=HEARTBEAT, stalled_worker_timeout=LEASE)
            return  # clean shutdown (signal)
        except (procrastinate.exceptions.ConnectorException, psycopg.OperationalError) as e:
            log.warning(json.dumps({"event": "worker_restart", "reason": type(e).__name__}))
            backoff = 1.0 if time.monotonic() - started > 60 else min(backoff * 2, 30.0)
            time.sleep(backoff)


if __name__ == "__main__":
    main()
