import { audit } from "@/lib/audit";
import { auth, require_ } from "@/lib/auth";
import { one, tx } from "@/lib/db";
import { accepted, ApiError, notFound, route } from "@/lib/http";
import { defer } from "@/lib/queue";

/** Run a sync now (the scheduler also runs it every interval_minutes). */
export const POST = route(async (req, { id }) => {
  const p = await auth(req);
  if (p.kind === "key") throw new ApiError(403, "ACCESS_DENIED", "Human identity required");
  require_(p, "source:write");
  return tx(p.workspaceId, async (db) => {
    const c = await one(db, "SELECT * FROM connectors WHERE id = $1 AND deleted_at IS NULL FOR UPDATE", [id]);
    if (!c) throw notFound("Connector");
    const job = await one(db, "INSERT INTO jobs (workspace_id, store_id, kind, params, created_by) VALUES (kb_ws(), $1, 'connector_sync', $2, $3) RETURNING id, state", [c.store_id, { connector_id: id }, p.actor]);
    await db.query("UPDATE connectors SET last_job_id = $2, next_run_at = now() + make_interval(mins => interval_minutes) WHERE id = $1", [id, job.id]);
    await defer(db, "run_job", [{ job_id: job.id }], "maintenance");
    await audit(db, p, "connector.sync", id, { job_id: job.id });
    return accepted(job);
  });
});
