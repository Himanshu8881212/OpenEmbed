import { z } from "zod";
import { audit } from "@/lib/audit";
import { auth, require_ } from "@/lib/auth";
import { one, tx } from "@/lib/db";
import { accepted, ApiError, body, invalid, route } from "@/lib/http";
import { idempotencyKey, replay, requestHash } from "@/lib/jobs";
import { StoreName } from "@/lib/names";
import { defer } from "@/lib/queue";
import { getStore } from "@/lib/stores";

/**
 * Merge stores into a new material store. Default: profiles must match (matching dimensions are not enough) and
 * existing vectors are reused. mode=rebuild + profile_id embeds every member for that profile from retained sources
 * before the target's membership is published.
 */
export const POST = route(async (req) => {
  const p = await auth(req);
  require_(p, "source:write");
  if (p.kind === "key") throw new ApiError(403, "ACCESS_DENIED", "API keys cannot create stores");
  const b = await body(req, z.object({ sources: z.array(z.string().uuid()).min(2).max(20), target_name: StoreName, mode: z.enum(["compatible", "rebuild"]).default("compatible"), profile_id: z.string().optional() }).strict());
  const key = idempotencyKey(req);
  const hash = requestHash({ op: "merge", ...b });
  return tx(p.workspaceId, async (db) => {
    const prev = await replay(db, key, hash);
    if (prev) return accepted(prev);
    const stores = await Promise.all([...new Set(b.sources)].map((id) => getStore(db, p, id, "search")));
    const profiles = new Set(stores.map((s) => s.profile_id));
    let profile = stores[0].profile_id;
    if (b.mode === "rebuild") {
      if (!b.profile_id || !(await one(db, "SELECT 1 FROM embedding_profiles WHERE id = $1", [b.profile_id]))) throw invalid("mode=rebuild requires a valid profile_id", "profile_id");
      profile = b.profile_id;
    } else if (profiles.size > 1) {
      throw new ApiError(409, "PROFILE_INCOMPATIBLE", `Source stores use different embedding profiles (${[...profiles].join(", ")}); use mode=rebuild with a profile_id`);
    }
    if (await one(db, "SELECT 1 FROM stores WHERE deleted_at IS NULL AND lower(name) = lower($1)", [b.target_name])) throw new ApiError(409, "CONFLICT", "A store with this name already exists");
    const t = await one(db, "INSERT INTO stores (workspace_id, name, definition, created_by) VALUES (kb_ws(), $1, $2, $3) RETURNING id", [b.target_name, { merged_from: stores.map((s) => s.id) }, p.actor]);
    const r = await one(db, "INSERT INTO index_revisions (workspace_id, store_id, profile_id, state, promoted_at) VALUES (kb_ws(), $1, $2, 'active', now()) RETURNING id", [t.id, profile]);
    await db.query("UPDATE stores SET active_revision_id = $2 WHERE id = $1", [t.id, r.id]);
    const job = await one(db, `INSERT INTO jobs (workspace_id, store_id, kind, params, idempotency_key, request_hash, created_by)
      VALUES (kb_ws(), $1, 'merge', $2, $3, $4, $5) RETURNING id, state`, [t.id, { sources: stores.map((s) => s.id), mode: b.mode, profile_id: profile }, key, hash, p.actor]);
    await defer(db, "run_job", [{ job_id: job.id }], "maintenance");
    await audit(db, p, "store.merge", t.id, { sources: stores.map((s) => s.id), mode: b.mode });
    return Response.json({ job_id: job.id, state: job.state, status_url: `/v1/jobs/${job.id}`, target_store_id: t.id }, { status: 202 });
  });
});
