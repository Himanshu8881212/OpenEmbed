import { audit } from "@/lib/audit";
import { auth, require_ } from "@/lib/auth";
import { one, tx } from "@/lib/db";
import { notFound, route } from "@/lib/http";
import { ledger } from "@/lib/ledger";

/** Revocation is effective for the next request (keys are looked up on every request; no cache). */
export const DELETE = route(async (req, { id }) => {
  const p = await auth(req);
  require_(p, "keys");
  return tx(p.workspaceId, async (db) => {
    const k = await one(db, "UPDATE api_keys SET revoked_at = coalesce(revoked_at, now()) WHERE id = $1 RETURNING id", [id]);
    if (!k) throw notFound("API key");
    await audit(db, p, "api_key.revoke", id);
    await ledger("api_key.revoke", p.workspaceId, id);
    return new Response(null, { status: 204 });
  });
});
