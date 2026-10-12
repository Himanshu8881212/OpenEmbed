import { audit } from "@/lib/audit";
import { auth, require_ } from "@/lib/auth";
import { all, one, tx } from "@/lib/db";
import { accepted, ApiError, route } from "@/lib/http";
import { getJob, idempotencyKey, replay, requestHash, TERMINAL } from "@/lib/jobs";
import { defer } from "@/lib/queue";

/** Retry retryable failed items of a finished job as a new job. Published items are untouched; segment IDs are deterministic. */
export const POST = route(async (req, { id }) => {
  const p = await auth(req);
  const key = idempotencyKey(req);
  const hash = requestHash({ op: "retry", job: id });
  return tx(p.workspaceId, async (db) => {
    const j = await getJob(db, p, id);
    require_(p, "source:write", j.store_id ?? undefined);
    const prev = await replay(db, key, hash);
    if (prev) return accepted(prev);
    if (!TERMINAL.includes(j.state)) throw new ApiError(409, "CONFLICT", "Wait until the job finishes before retrying");
    const failed = await all(db, "SELECT * FROM job_items WHERE job_id = $1 AND state = 'failed' AND retryable", [id]);
    if (!failed.length) throw new ApiError(409, "NOTHING_TO_RETRY", "The job has no retryable failed items");
    const nj = await one(db, `INSERT INTO jobs (workspace_id, store_id, kind, params, idempotency_key, request_hash, created_by)
      VALUES (kb_ws(), $1, $2, $3, $4, $5, $6) RETURNING id, state`, [j.store_id, j.kind, { ...j.params, retry_of: id }, key, hash, p.actor]);
    const items = await all(db, `INSERT INTO job_items (workspace_id, job_id, path, upload_file_id, file_id, file_version_id)
      SELECT kb_ws(), $1, path, upload_file_id, file_id, file_version_id FROM job_items WHERE id = ANY($2) RETURNING id`, [nj.id, failed.map((i) => i.id)]);
    await defer(db, "ingest_item", items.map((i) => ({ job_id: nj.id, item_id: i.id })));
    await audit(db, p, "job.retry", id, { new_job_id: nj.id, items: items.length });
    return accepted(nj);
  });
});
