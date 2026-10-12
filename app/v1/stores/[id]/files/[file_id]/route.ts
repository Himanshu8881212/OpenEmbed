import { audit } from "@/lib/audit";
import { auth } from "@/lib/auth";
import { one, tx } from "@/lib/db";
import { ApiError, notFound, route } from "@/lib/http";
import { getStore } from "@/lib/stores";

/** Remove a source from this store only. Other stores keep their references. Effective immediately. */
export const DELETE = route(async (req, { id, file_id }) => {
  const p = await auth(req);
  return tx(p.workspaceId, async (db) => {
    const s = await getStore(db, p, id, "source:write");
    if (s.kind === "view") throw new ApiError(409, "CONFLICT", "Live view membership follows its filter; change the filter or the parent store");
    const r = await one(db, "DELETE FROM store_files WHERE store_id = $1 AND file_id = $2 RETURNING file_id", [id, file_id]);
    if (!r) throw notFound("Store membership");
    await audit(db, p, "store.remove_file", id, { file_id });
    return new Response(null, { status: 204 });
  });
});
