"""Maintenance / composition jobs: store deletion, source deletion cleanup, merge, reindex, connector sync."""
import hashlib
import json
import os
import tempfile
import urllib.parse

import httpx

from .worker import BUCKET, finalize, gc_workspace, one, s3, tx

TERMINAL = ("completed", "completed_with_errors", "failed", "cancelled")
# Mirrors lib/formats.ts (validated formats). Keep in sync; tests/contract.test.mjs compares them.
FORMATS = {".txt": "text/plain", ".md": "text/markdown", ".markdown": "text/markdown", ".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".jpg": "image/jpeg",
           ".jpeg": "image/jpeg", ".png": "image/png", ".wav": "audio/wav", ".mp3": "audio/mpeg", ".mp4": "video/mp4"}
MAX_FILE = int(os.environ.get("KB_UPLOAD_MAX_FILE_BYTES", str(512 * 1024 * 1024)))


def complete(c, job_id, result: dict, state="completed"):
    c.execute("UPDATE jobs SET state=%s, result=%s, finished_at=now(), updated_at=now() WHERE id=%s", (state, json.dumps(result), job_id))


def defer(c, task, args: list[dict], queue="ingest"):
    if args:
        c.execute("""SELECT procrastinate_defer_jobs_v1(array_agg(ROW(%s::varchar,%s::varchar,0,NULL::text,NULL::text,a,NULL::timestamptz)::procrastinate_job_to_defer_v1))
                     FROM jsonb_array_elements(%s::jsonb) a""", (queue, task, json.dumps(args)))


# ------------------------------------------------------------------ deletion

def store_delete(ws, job):
    """Store already inaccessible (deleted_at set by the API). Remove memberships; optionally delete sources no other live store references."""
    with tx(ws) as c:
        sid = job["store_id"]
        deleted = 0
        if job["params"].get("sources") == "unshared":
            deleted = c.execute("""UPDATE files f SET deleted_at=now() WHERE f.deleted_at IS NULL
                AND EXISTS (SELECT 1 FROM store_files sf WHERE sf.store_id=%s AND sf.file_id=f.id)
                AND NOT EXISTS (SELECT 1 FROM store_files o JOIN stores s ON s.id=o.store_id AND s.deleted_at IS NULL WHERE o.file_id=f.id AND o.store_id<>%s)""",
                                (sid, sid)).rowcount
        removed = c.execute("DELETE FROM store_files WHERE store_id=%s", (sid,)).rowcount
        c.execute("UPDATE index_revisions SET state='retired' WHERE store_id=%s", (sid,))
        c.execute("UPDATE connectors SET deleted_at=now() WHERE store_id=%s AND deleted_at IS NULL", (sid,))
        complete(c, job["id"], {"memberships_removed": removed, "sources_deleted": deleted})
    gc_workspace(ws)


def file_delete(ws, job):
    gc_workspace(ws)
    with tx(ws) as c:
        complete(c, job["id"], {"cleanup": "done"})


# ------------------------------------------------------------------ composition

def missing_vector_items(c, job_id, store_id, profile_id, members_sql, args) -> int:
    """Create one embed item per member version lacking vectors for profile_id; return count."""
    rows = c.execute(f"""INSERT INTO job_items (workspace_id, job_id, path, file_id, file_version_id)
        SELECT kb_ws(), %s, f.path, m.file_id, m.version_id FROM ({members_sql}) m JOIN files f ON f.id=m.file_id
        WHERE NOT EXISTS (SELECT 1 FROM segments s WHERE s.file_version_id=m.version_id AND s.profile_id=%s) RETURNING id""",
                     (job_id, *args, profile_id)).fetchall()
    defer(c, "embed_item", [{"job_id": str(job_id), "item_id": str(r["id"])} for r in rows])
    return len(rows)


MERGE_MEMBERS = """SELECT DISTINCT ON (x.file_id) x.file_id, x.version_id, x.pinned FROM (
        SELECT m.file_id, m.version_id, (s.kind='snapshot') pinned, ord
        FROM unnest(%s::uuid[]) WITH ORDINALITY AS src(id, ord) JOIN stores s ON s.id=src.id AND s.deleted_at IS NULL,
             LATERAL kb_store_members(s.id) m) x ORDER BY x.file_id, x.ord"""


def merge(ws, job):
    """Plan membership; embed missing vectors first (rebuild); publish all memberships in one transaction."""
    p = job["params"]
    with tx(ws) as c:
        n = missing_vector_items(c, job["id"], job["store_id"], p["profile_id"], MERGE_MEMBERS, (p["sources"],))
        if n == 0:
            publish_merge(c, job)


def publish_merge(c, job):
    p = job["params"]
    members = c.execute(MERGE_MEMBERS, (p["sources"],)).fetchall()
    seen, inserted, dup = set(), 0, 0
    for m in members:
        v = one(c, "SELECT sha256, f.path FROM file_versions v JOIN files f ON f.id=v.file_id WHERE v.id=%s", m["version_id"])
        k = (v["path"], v["sha256"])
        if k in seen:  # same path + same bytes from different sources: one membership
            dup += 1
            continue
        seen.add(k)
        if not one(c, "SELECT 1 FROM segments WHERE file_version_id=%s AND profile_id=%s LIMIT 1", m["version_id"], p["profile_id"]):
            continue  # its vector build failed; reported by the job items
        inserted += c.execute("""INSERT INTO store_files (workspace_id, store_id, file_id, pinned_version_id) VALUES (kb_ws(), %s, %s, %s)
                                 ON CONFLICT DO NOTHING""", (job["store_id"], m["file_id"], m["version_id"] if m["pinned"] else None)).rowcount
    total_refs = one(c, "SELECT count(*)::int n FROM unnest(%s::uuid[]) sid, LATERAL kb_store_members(sid) m", p["sources"])["n"]
    state = one(c, "SELECT state FROM jobs WHERE id=%s", job["id"])["state"]
    result = {"source_references": total_refs, "memberships": inserted,
              "duplicates_removed": (total_refs - len(members)) + dup,  # same source in several parents + same path/bytes
              "reembedded_items": one(c, "SELECT count(*)::int n FROM job_items WHERE job_id=%s AND state='succeeded'", job["id"])["n"]}
    complete(c, job["id"], result, state if state in TERMINAL else "completed")


def reindex(ws, job):
    p = job["params"]
    with tx(ws) as c:
        n = missing_vector_items(c, job["id"], job["store_id"], p["profile_id"], "SELECT * FROM kb_store_members(%s)", (job["store_id"],))
        if n == 0:
            c.execute("UPDATE index_revisions SET state='ready' WHERE id=%s AND state='building'", (p["revision_id"],))
            complete(c, job["id"], {"index_revision": p["revision_id"], "embedded_items": 0})


def after_items(c, job_id):
    """Called after an embed item reaches a terminal state: completes composition jobs once all items are done."""
    job = one(c, "SELECT * FROM jobs WHERE id=%s FOR UPDATE", job_id)
    if job["state"] not in TERMINAL or job["result"] is not None:
        return
    if job["kind"] == "reindex":
        ok = job["state"] == "completed"
        c.execute("UPDATE index_revisions SET state=%s WHERE id=%s AND state='building'", ("ready" if ok else "failed", job["params"]["revision_id"]))
        n = one(c, "SELECT count(*)::int n FROM job_items WHERE job_id=%s AND state='succeeded'", job_id)["n"]
        complete(c, job_id, {"index_revision": job["params"]["revision_id"], "embedded_items": n}, job["state"])
    elif job["kind"] == "merge":
        publish_merge(c, job)


# ------------------------------------------------------------------ connectors

def _allowed(url: str) -> bool:
    u = urllib.parse.urlsplit(url)
    hosts = [h.strip().lower() for h in os.environ.get("KB_CONNECTOR_ALLOWED_HOSTS", "").split(",") if h.strip()]
    return u.scheme in ("http", "https") and u.netloc.lower() in hosts


def _get(url: str, limit: int) -> bytes:
    if not _allowed(url):
        raise ValueError(f"host not allowed: {urllib.parse.urlsplit(url).netloc}")
    with httpx.stream("GET", url, timeout=60, follow_redirects=False) as r:
        if r.status_code != 200:
            raise ValueError(f"HTTP {r.status_code} for {url}")
        buf = bytearray()
        for chunk in r.iter_bytes():
            buf += chunk
            if len(buf) > limit:
                raise ValueError(f"{url} exceeds {limit} bytes")
        return bytes(buf)


def connector_sync(ws, job):
    """Mirror an http_manifest into the store through the normal verified import path (one ingest item per new/changed file)."""
    cid = job["params"]["connector_id"]
    with tx(ws) as c:
        con = one(c, "SELECT * FROM connectors WHERE id=%s", cid)
    try:
        manifest = json.loads(_get(con["config"]["url"], 5 * 1024 * 1024))
        entries = manifest["files"]
        assert isinstance(entries, list)
    except Exception as e:
        with tx(ws) as c:
            complete(c, job["id"], {"error": f"manifest unavailable or invalid: {str(e)[:200]}"}, "failed")
        return
    added = unchanged = skipped = 0
    errors = []
    paths = set()
    with tx(ws) as c:
        session = one(c, "INSERT INTO upload_sessions (workspace_id, store_id, created_by, state, expires_at) VALUES (kb_ws(), %s, %s, 'committed', now()) RETURNING id",
                      job["store_id"], f"connector:{cid}")["id"]
    for e in entries:
        path = str(e.get("path", ""))
        ext = os.path.splitext(path.lower())[1]
        if not path or path.startswith("/") or ".." in path.split("/") or "\\" in path or ext not in FORMATS:
            skipped += 1
            errors.append({"path": path, "error": "unsafe path or unsupported format"})
            continue
        paths.add(path)
        try:
            data = _get(urllib.parse.urljoin(con["config"]["url"], e["url"]), MAX_FILE)
        except Exception as ex:
            errors.append({"path": path, "error": str(ex)[:200]})
            continue
        digest = hashlib.sha256(data).hexdigest()
        with tx(ws) as c:
            cur = one(c, """SELECT v.sha256 FROM store_files sf JOIN files f ON f.id=sf.file_id AND f.deleted_at IS NULL
                            JOIN file_versions v ON v.id=f.current_version_id WHERE sf.store_id=%s AND f.path=%s""", job["store_id"], path)
            if cur and cur["sha256"] == digest:
                unchanged += 1
                continue
            key = f"ws/{ws}/blobs/{digest}"
            if not one(c, "SELECT 1 FROM blobs WHERE sha256=%s", digest):
                s3.put_object(Bucket=BUCKET, Key=key, Body=data)
                c.execute("INSERT INTO blobs (workspace_id, sha256, size, object_key) VALUES (kb_ws(), %s, %s, %s) ON CONFLICT DO NOTHING", (digest, len(data), key))
            uf = one(c, """INSERT INTO upload_files (workspace_id, session_id, path, size, sha256, media_type, part_size, object_key, verified_at)
                           VALUES (kb_ws(), %s, %s, %s, %s, %s, %s, %s, now()) RETURNING id""", session, path, len(data), digest, FORMATS[ext], len(data), key)
            it = one(c, "INSERT INTO job_items (workspace_id, job_id, path, upload_file_id) VALUES (kb_ws(), %s, %s, %s) RETURNING id", job["id"], path, uf["id"])
            defer(c, "ingest_item", [{"job_id": str(job["id"]), "item_id": str(it["id"])}])
            added += 1
    with tx(ws) as c:
        removed = c.execute("""DELETE FROM store_files sf USING files f WHERE sf.file_id=f.id AND sf.store_id=%s
                               AND f.metadata->>'connector_id'=%s AND NOT (f.path = ANY(%s))""", (job["store_id"], cid, list(paths))).rowcount
        c.execute("UPDATE jobs SET result=%s WHERE id=%s", (json.dumps({"imported": added, "unchanged": unchanged, "removed": removed, "skipped": skipped, "errors": errors[:50]}), job["id"]))
        finalize(c, job["id"])  # zero items → completed now; otherwise items finalize it


KINDS = {"store_delete": store_delete, "file_delete": file_delete, "merge": merge, "reindex": reindex, "connector_sync": connector_sync}


def run(ws, job_id):
    with tx(ws) as c:
        job = one(c, "SELECT * FROM jobs WHERE id=%s", job_id)
        if job["state"] in TERMINAL or one(c, "SELECT 1 FROM job_items WHERE job_id=%s LIMIT 1", job_id):
            return  # finished, or already planned (duplicate delivery)
        c.execute("UPDATE jobs SET state='running', updated_at=now() WHERE id=%s AND state='queued'", (job_id,))
    KINDS[job["kind"]](ws, job)
