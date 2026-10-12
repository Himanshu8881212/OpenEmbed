import { auth } from "@/lib/auth";
import { all, one, tx } from "@/lib/db";
import { route } from "@/lib/http";
import { getStore } from "@/lib/stores";

/** What a store deletion affects: memberships, sources shared with other stores, dependent views, restricted keys. */
export const POST = route(async (req, { id }) => {
  const p = await auth(req);
  return tx(p.workspaceId, async (db) => {
    const s = await getStore(db, p, id, "delete");
    const counts = await one(db, `
      SELECT count(*)::int memberships,
             count(*) FILTER (WHERE EXISTS (SELECT 1 FROM store_files o JOIN stores os ON os.id = o.store_id AND os.deleted_at IS NULL WHERE o.file_id = sf.file_id AND o.store_id <> sf.store_id))::int shared_sources
        FROM store_files sf WHERE sf.store_id = $1`, [id]);
    const views = await all(db, "SELECT id, name FROM stores WHERE deleted_at IS NULL AND kind = 'view' AND definition->'parents' ? $1::text", [id]);
    const keys = await all(db, "SELECT id, name FROM api_keys WHERE revoked_at IS NULL AND $1 = ANY(store_ids)", [id]);
    return {
      store_id: s.id, name: s.name, memberships: counts.memberships,
      sources_shared_with_other_stores: counts.shared_sources,
      sources_deleted_with_scope_unshared: counts.memberships - counts.shared_sources,
      dependent_views: views, restricted_api_keys: keys,
      scopes: ["unshared", "keep"], delete_endpoint: `DELETE /v1/stores/${s.id}?sources=unshared|keep`,
    };
  });
});
