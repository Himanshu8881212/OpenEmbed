import { auth } from "@/lib/auth";
import { all, tx } from "@/lib/db";
import { route } from "@/lib/http";
import { getFile } from "@/lib/stores";

/** Stores, views and snapshots that currently reference the source. */
export const POST = route(async (req, { id }) => {
  const p = await auth(req);
  return tx(p.workspaceId, async (db) => {
    const f = await getFile(db, p, id, "delete");
    const direct = await all(db, "SELECT s.id, s.name, s.kind, sf.pinned_version_id FROM store_files sf JOIN stores s ON s.id = sf.store_id AND s.deleted_at IS NULL WHERE sf.file_id = $1", [id]);
    const views = await all(db, "SELECT s.id, s.name FROM stores s WHERE s.deleted_at IS NULL AND s.kind = 'view' AND EXISTS (SELECT 1 FROM kb_store_members(s.id) m WHERE m.file_id = $1)", [id]);
    return { file_id: f.id, path: f.path, stores: direct.filter((s) => s.kind === "material"), snapshots: direct.filter((s) => s.kind === "snapshot"), live_views: views,
      scopes: ["workspace"], delete_endpoint: `DELETE /v1/files/${id}?scope=workspace`, membership_removal_endpoint: "DELETE /v1/stores/{store_id}/files/" + id };
  });
});
