import { createHash } from "node:crypto";
import type { NextRequest } from "next/server";
import type { Principal } from "./auth";
import { all, one, type Db } from "./db";
import { ApiError, iso, notFound } from "./http";
import { defer } from "./queue";

export const TERMINAL = ["completed", "completed_with_errors", "failed", "cancelled"];

export const requestHash = (v: unknown) => createHash("sha256").update(JSON.stringify(v)).digest("hex");

export function idempotencyKey(req: NextRequest) {
  const k = req.headers.get("idempotency-key");
  if (k && (k.length > 200 || !/^[\x21-\x7e]+$/.test(k))) throw new ApiError(400, "INVALID_REQUEST", "Idempotency-Key must be 1-200 visible ASCII characters", "idempotency-key");
  return k;
}

/** Returns an existing job for a replayed idempotency key (same body), throws 409 if the body differs. */
export async function replay(db: Db, key: string | null, hash: string) {
  if (!key) return null;
  const j = await one(db, "SELECT id, state, request_hash FROM jobs WHERE idempotency_key = $1", [key]);
  if (!j) return null;
  if (j.request_hash !== hash) throw new ApiError(409, "IDEMPOTENCY_KEY_REUSED", "This Idempotency-Key was used with a different request body");
  return j;
}

/** Create an import job over the committed files of an upload session; one queue task per item. */
export async function createIngestJob(db: Db, p: Principal, opts: { kind: "ingest" | "revision"; storeId: string | null; sessionId: string; fileId?: string; key: string | null; hash: string }) {
  const prev = await replay(db, opts.key, opts.hash);
  if (prev) return prev;
  const files = await all(db, "SELECT id, path FROM upload_files WHERE session_id = $1 ORDER BY path", [opts.sessionId]);
  const queued = (await one(db, "SELECT count(*)::int n FROM job_items WHERE state IN ('queued','running')"))!.n;
  const cap = Number(process.env.KB_MAX_QUEUED_ITEMS ?? 20000);
  if (queued + files.length > cap) throw new ApiError(429, "QUOTA_EXCEEDED", `Workspace queue is full (${queued} items pending, limit ${cap}); wait for running imports to finish`);
  const job = await one(db,
    `INSERT INTO jobs (workspace_id, store_id, kind, params, idempotency_key, request_hash, created_by)
     VALUES (kb_ws(), $1, $2, $3, $4, $5, $6) RETURNING id, state`,
    [opts.storeId, opts.kind, { upload_session_id: opts.sessionId, file_id: opts.fileId ?? null }, opts.key, opts.hash, p.actor]);
  const items = await all(db,
    `INSERT INTO job_items (workspace_id, job_id, path, upload_file_id, file_id)
     SELECT kb_ws(), $1, x.path, x.id, $3 FROM jsonb_to_recordset($2) x(id uuid, path text) RETURNING id`,
    [job.id, JSON.stringify(files), opts.fileId ?? null]);
  await defer(db, "ingest_item", items.map((i) => ({ job_id: job.id, item_id: i.id })));
  return job;
}

export async function getJob(db: Db, p: Principal, id: string) {
  const j = await one(db, "SELECT * FROM jobs WHERE id = $1", [id]);
  if (!j) throw notFound("Job");
  if (p.kind === "key" && p.storeIds && !(j.store_id && p.storeIds.includes(j.store_id))) throw notFound("Job");
  return j;
}

export async function jobJson(db: Db, j: any) {
  const c = await one(db, `SELECT count(*)::int total,
      count(*) FILTER (WHERE state='queued')::int queued, count(*) FILTER (WHERE state='running')::int running,
      count(*) FILTER (WHERE state='succeeded')::int succeeded, count(*) FILTER (WHERE state='failed')::int failed,
      count(*) FILTER (WHERE state='cancelled')::int cancelled,
      count(*) FILTER (WHERE state='failed' AND retryable)::int retryable
    FROM job_items WHERE job_id = $1`, [j.id]);
  return { id: j.id, object: "job", kind: j.kind, state: j.state, store_id: j.store_id, params: j.params, result: j.result, items: c,
    created_at: iso(j.created_at), updated_at: iso(j.updated_at), finished_at: iso(j.finished_at), status_url: `/v1/jobs/${j.id}` };
}

export const itemJson = (i: any) => ({ id: i.id, path: i.path, state: i.state, file_id: i.file_id, file_version_id: i.file_version_id,
  attempts: i.attempts, retryable: i.retryable, error: i.error_code ? { code: i.error_code, message: i.error_message } : null, updated_at: iso(i.updated_at) });
