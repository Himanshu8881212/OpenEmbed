import { z } from "zod";
import { audit } from "@/lib/audit";
import { auth } from "@/lib/auth";
import { one, tx } from "@/lib/db";
import { ApiError, body, notFound, route } from "@/lib/http";
import { getStore, storeJson } from "@/lib/stores";

/**
 * Activate a complete index revision. The previous active revision stays `ready` (kept up to date by new imports),
 * so promoting it again is the rollback. Incomplete revisions are refused.
 */
export const POST = route(async (req, { id }) => {
  const p = await auth(req);
  const b = await body(req, z.object({ index_revision: z.string().uuid() }).strict());
  return tx(p.workspaceId, async (db) => {
    const s = await getStore(db, p, id, "source:write");
    await db.query("SELECT 1 FROM stores WHERE id = $1 FOR UPDATE", [id]);
    const r = await one(db, "SELECT * FROM index_revisions WHERE id = $1 AND store_id = $2", [b.index_revision, id]);
    if (!r) throw notFound("Index revision");
    if (r.state === "active") return storeJson(db, s);
    if (r.state !== "ready") throw new ApiError(409, "INDEX_NOT_READY", `Index revision is ${r.state}`);
    const missing = await one(db, `SELECT count(*)::int n FROM kb_store_members($1) m WHERE NOT EXISTS (SELECT 1 FROM segments sg WHERE sg.file_version_id = m.version_id AND sg.profile_id = $2)`, [id, r.profile_id]);
    if (missing.n) throw new ApiError(409, "INDEX_INCOMPLETE", `${missing.n} member(s) have no vectors for this revision`);
    await db.query("UPDATE index_revisions SET state = 'ready' WHERE id = $1", [s.active_revision_id]);
    await db.query("UPDATE index_revisions SET state = 'active', promoted_at = now() WHERE id = $1", [r.id]);
    await db.query("UPDATE stores SET active_revision_id = $2, updated_at = now() WHERE id = $1", [id, r.id]);
    await audit(db, p, "store.promote_index", id, { from: s.active_revision_id, to: r.id, profile_id: r.profile_id });
    return storeJson(db, { ...s, active_revision_id: r.id, profile_id: r.profile_id });
  });
});
