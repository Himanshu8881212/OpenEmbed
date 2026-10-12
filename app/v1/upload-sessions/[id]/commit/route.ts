import { CompleteMultipartUploadCommand, HeadObjectCommand } from "@aws-sdk/client-s3";
import { NextResponse } from "next/server";
import { z } from "zod";
import { audit } from "@/lib/audit";
import { auth, require_ } from "@/lib/auth";
import { all, one, tx } from "@/lib/db";
import { accepted, ApiError, body, route } from "@/lib/http";
import { createIngestJob, idempotencyKey, requestHash } from "@/lib/jobs";
import { bucket, s3 } from "@/lib/s3";
import { getStore } from "@/lib/stores";
import { getSession, sessionJson } from "@/lib/uploads";

/**
 * Commit a fully transferred session. With a store (from the session or body) an import job is created → 202.
 * Replays (same body / Idempotency-Key) return the same result; a different body after commit → 409.
 * Whole-file SHA-256 is verified by the worker before any content is published.
 */
export const POST = route(async (req, { id }) => {
  const p = await auth(req);
  require_(p, "source:write");
  const b = await body(req, z.object({ store_id: z.string().uuid().optional() }).strict());
  const key = idempotencyKey(req);
  const hash = requestHash({ op: "commit", session: id, ...b });
  return tx(p.workspaceId, async (db) => {
    const s = await getSession(db, p, id);
    await db.query("SELECT 1 FROM upload_sessions WHERE id = $1 FOR UPDATE", [id]);
    const storeId = b.store_id ?? s.store_id;
    if (s.state === "committed") {
      if (s.commit_request_hash !== hash) throw new ApiError(409, "IDEMPOTENCY_KEY_REUSED", "Session already committed with a different request");
      if (s.job_id) return accepted((await one(db, "SELECT id, state FROM jobs WHERE id = $1", [s.job_id]))!);
      return NextResponse.json(await sessionJson(db, s));
    }
    if (s.state !== "open") throw new ApiError(409, "CONFLICT", `Session is ${s.state}`);
    if (new Date(s.expires_at) < new Date()) throw new ApiError(410, "SESSION_EXPIRED", "The upload session expired; create a new session");
    if (storeId) await getStore(db, p, storeId, "source:write");
    const files = await all(db, `SELECT f.*, (SELECT jsonb_agg(jsonb_build_object('PartNumber', part_no, 'ETag', etag) ORDER BY part_no) FROM upload_parts WHERE upload_file_id = f.id) parts
      FROM upload_files f WHERE session_id = $1`, [id]);
    const missing = files.filter((f) => (f.parts?.length ?? 0) !== Math.ceil(Number(f.size) / f.part_size)).map((f) => f.path);
    if (missing.length) throw new ApiError(409, "UPLOAD_INCOMPLETE", `Missing parts for ${missing.length} file(s): ${missing.slice(0, 5).join(", ")}`);
    for (const f of files) {
      try {
        await s3.send(new CompleteMultipartUploadCommand({ Bucket: bucket(), Key: f.object_key, UploadId: f.s3_upload_id, MultipartUpload: { Parts: f.parts } }));
      } catch (e) {
        // A previous commit attempt may have completed it before failing; accept only if the object is whole.
        const h = await s3.send(new HeadObjectCommand({ Bucket: bucket(), Key: f.object_key })).catch(() => null);
        if (!h || Number(h.ContentLength) !== Number(f.size)) throw e;
      }
    }
    await db.query("UPDATE upload_files SET s3_upload_id = NULL WHERE session_id = $1", [id]);
    let job = null;
    if (storeId) job = await createIngestJob(db, p, { kind: "ingest", storeId, sessionId: id, key, hash });
    await db.query("UPDATE upload_sessions SET state = 'committed', commit_request_hash = $2, job_id = $3, store_id = coalesce(store_id, $4) WHERE id = $1", [id, hash, job?.id ?? null, storeId ?? null]);
    await audit(db, p, "upload.commit", id, { files: files.length, job_id: job?.id ?? null });
    return job ? accepted(job) : NextResponse.json(await sessionJson(db, { ...s, state: "committed" }));
  });
});
