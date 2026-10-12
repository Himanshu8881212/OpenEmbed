import { audit } from "@/lib/audit";
import { auth, require_ } from "@/lib/auth";
import { one, tx } from "@/lib/db";
import { ApiError, notFound, route } from "@/lib/http";

/** Stop syncing. Already imported sources remain in the store. */
export const DELETE = route(async (req, { id }) => {
  const p = await auth(req);
  if (p.kind === "key") throw new ApiError(403, "ACCESS_DENIED", "Human identity required");
  require_(p, "source:write");
  return tx(p.workspaceId, async (db) => {
    if (!(await one(db, "UPDATE connectors SET deleted_at = now() WHERE id = $1 AND deleted_at IS NULL RETURNING id", [id]))) throw notFound("Connector");
    await audit(db, p, "connector.delete", id);
    return new Response(null, { status: 204 });
  });
});
