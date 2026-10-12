import { audit } from "@/lib/audit";
import { auth, require_ } from "@/lib/auth";
import { one, tx } from "@/lib/db";
import { ApiError, route } from "@/lib/http";
import { getJob, jobJson, TERMINAL } from "@/lib/jobs";

/** Request safe cancellation: queued items stop now; running items stop at their next safe boundary (never mid-publication). */
export const POST = route(async (req, { id }) => {
  const p = await auth(req);
  return tx(p.workspaceId, async (db) => {
    const j = await getJob(db, p, id);
    require_(p, "source:write", j.store_id ?? undefined);
    await db.query("SELECT 1 FROM jobs WHERE id = $1 FOR UPDATE", [id]);
    const cur = await one(db, "SELECT state FROM jobs WHERE id = $1", [id]);
    if (TERMINAL.includes(cur.state)) throw new ApiError(409, "CONFLICT", `Job is already ${cur.state}`);
    await db.query("UPDATE jobs SET state = 'cancel_requested', updated_at = now() WHERE id = $1", [id]);
    await db.query("UPDATE job_items SET state = 'cancelled', updated_at = now() WHERE job_id = $1 AND state = 'queued'", [id]);
    await db.query("SELECT kb_finalize_job($1)", [id]);
    await audit(db, p, "job.cancel", id);
    return Response.json(await jobJson(db, await one(db, "SELECT * FROM jobs WHERE id = $1", [id])), { status: 202 });
  });
});
