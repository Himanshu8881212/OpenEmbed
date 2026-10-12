import { z } from "zod";
import { audit } from "@/lib/audit";
import { auth } from "@/lib/auth";
import { one, tx } from "@/lib/db";
import { accepted, ApiError, body, invalid, route } from "@/lib/http";
import { idempotencyKey, replay, requestHash } from "@/lib/jobs";
import { defer } from "@/lib/queue";
import { getStore } from "@/lib/stores";

/** Build a separate index revision for another profile from retained sources. Searches keep using the active one until promotion. */
export const POST = route(async (req, { id }) => {
  const p = await auth(req);
  const b = await body(req, z.object({ profile_id: z.string() }).strict());
  const key = idempotencyKey(req);
  const hash = requestHash({ op: "reindex", store: id, ...b });
  return tx(p.workspaceId, async (db) => {
    const s = await getStore(db, p, id, "source:write");
    const prev = await replay(db, key, hash);
    if (prev) return accepted(prev);
    if (!(await one(db, "SELECT 1 FROM embedding_profiles WHERE id = $1", [b.profile_id]))) throw invalid("Unknown profile", "profile_id");
    if (b.profile_id === s.profile_id) throw new ApiError(409, "CONFLICT", "The store already uses this profile");
    if (await one(db, "SELECT 1 FROM index_revisions WHERE store_id = $1 AND profile_id = $2 AND state = 'building'", [id, b.profile_id])) throw new ApiError(409, "CONFLICT", "A build for this profile is already running");
    const r = await one(db, "INSERT INTO index_revisions (workspace_id, store_id, profile_id, state) VALUES (kb_ws(), $1, $2, 'building') RETURNING id", [id, b.profile_id]);
    const job = await one(db, "INSERT INTO jobs (workspace_id, store_id, kind, params, idempotency_key, request_hash, created_by) VALUES (kb_ws(), $1, 'reindex', $2, $3, $4, $5) RETURNING id, state",
      [id, { revision_id: r.id, profile_id: b.profile_id }, key, hash, p.actor]);
    await defer(db, "run_job", [{ job_id: job.id }], "maintenance");
    await audit(db, p, "store.reindex", id, { revision_id: r.id, profile_id: b.profile_id });
    return Response.json({ job_id: job.id, state: job.state, status_url: `/v1/jobs/${job.id}`, index_revision: r.id }, { status: 202 });
  });
});
