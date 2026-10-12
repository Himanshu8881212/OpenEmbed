import type { Principal } from "./auth";
import { one, type Db } from "./db";
import { ApiError, invalid } from "./http";
import type { Filter } from "./search";
import { getStore, type Store } from "./stores";

export const MAX_VIEW_DEPTH = 3;

/**
 * Create a live view or snapshot over parent stores. Parents may be material stores, snapshots or views
 * (view depth ≤ MAX_VIEW_DEPTH). All parents must share one profile; the creator must be able to edit each parent.
 */
export async function createDerived(db: Db, p: Principal, parentIds: string[], name: string, mode: "view" | "snapshot", filter: Filter) {
  if (p.kind === "key") throw new ApiError(403, "ACCESS_DENIED", "API keys cannot create stores");
  const parents: Store[] = await Promise.all([...new Set(parentIds)].map((x) => getStore(db, p, x, "source:write")));
  const profiles = new Set(parents.map((s) => s.profile_id));
  if (profiles.size > 1) throw new ApiError(409, "PROFILE_INCOMPATIBLE", "Parent stores use different embedding profiles");
  const depth = 1 + Math.max(...parents.map((s) => (s.kind === "view" ? Number(s.definition?.depth ?? 1) : 0)));
  if (depth > MAX_VIEW_DEPTH) throw invalid(`Views can be nested at most ${MAX_VIEW_DEPTH} levels deep`, "parents");
  if (await one(db, "SELECT 1 FROM stores WHERE deleted_at IS NULL AND lower(name) = lower($1)", [name])) throw new ApiError(409, "CONFLICT", `A store named ${name} already exists`);
  const f = { ...(filter.metadata ? { metadata: filter.metadata } : {}), ...(filter.path_prefix ? { path_prefix: filter.path_prefix } : {}), ...(filter.media_types ? { media_types: filter.media_types } : {}) };
  const def = { parents: parents.map((s) => s.id), filter: f, depth };
  const s = await one(db, "INSERT INTO stores (workspace_id, name, kind, definition, created_by) VALUES (kb_ws(), $1, 'view', $2, $3) RETURNING id", [name, def, p.actor]);
  const r = await one(db, "INSERT INTO index_revisions (workspace_id, store_id, profile_id, state, promoted_at) VALUES (kb_ws(), $1, $2, 'active', now()) RETURNING id", [s.id, parents[0].profile_id]);
  await db.query("UPDATE stores SET active_revision_id = $2 WHERE id = $1", [s.id, r.id]);
  if (mode === "snapshot") {
    // materialise the view's current resolution with pinned versions, then freeze it
    const n = await db.query("INSERT INTO store_files (workspace_id, store_id, file_id, pinned_version_id) SELECT kb_ws(), $1, file_id, version_id FROM kb_store_members($1)", [s.id]);
    await db.query("UPDATE stores SET kind = 'snapshot', definition = definition || jsonb_build_object('pinned_at', now(), 'members', $2::int) WHERE id = $1", [s.id, n.rowCount]);
  }
  return (await one<Store>(db, "SELECT s.*, r.profile_id FROM stores s JOIN index_revisions r ON r.id = s.active_revision_id WHERE s.id = $1", [s.id]))!;
}
