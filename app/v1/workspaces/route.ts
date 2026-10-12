import { z } from "zod";
import { authUser } from "@/lib/auth";
import { config } from "@/lib/config";
import { pool, tx } from "@/lib/db";
import { body, route } from "@/lib/http";
import { randomWorkspaceName } from "@/lib/names";

export const GET = route(async (req) => {
  const u = await authUser(req);
  return { data: u.memberships.map((m) => ({ id: m.workspace_id, name: m.workspace_name, role: m.role })), next_cursor: null };
});

export const POST = route(async (req) => {
  const u = await authUser(req);
  const b = await body(req, z.object({ name: z.string().trim().min(1).max(100).optional() }).strict());
  const name = b.name ?? randomWorkspaceName();
  const { rows: [{ id }] } = await pool.query("SELECT kb_create_workspace($1,$2,$3) id", [u.identityId, name, config().KB_DEFAULT_PLAN]);
  await tx(id, (db) => db.query("INSERT INTO audit_events (workspace_id, actor, action, target) VALUES ($1::uuid,$2,'workspace.create',$1::text)", [id, `user:${u.identityId}`]));
  return Response.json({ id, name, role: "owner" }, { status: 201 });
});
