import { auth, require_ } from "@/lib/auth";
import { all, tx } from "@/lib/db";
import { iso, page, route } from "@/lib/http";

export const GET = route(async (req) => {
  const p = await auth(req);
  require_(p, "admin");
  const { limit, after } = page(req);
  return tx(p.workspaceId, async (db) => {
    const rows = await all(db, `SELECT * FROM audit_events WHERE ($1::bigint IS NULL OR id < $1) ORDER BY id DESC LIMIT $2`, [after?.[1] ?? null, limit + 1]);
    const more = rows.length > limit, data = rows.slice(0, limit);
    return {
      data: data.map((e) => ({ id: String(e.id), actor: e.actor, action: e.action, target: e.target, data: e.data, created_at: iso(e.created_at) })),
      next_cursor: more ? Buffer.from(JSON.stringify(["", String(data[data.length - 1].id)])).toString("base64url") : null,
    };
  });
});
