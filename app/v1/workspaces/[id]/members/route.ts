import { z } from "zod";
import { audit } from "@/lib/audit";
import { auth } from "@/lib/auth";
import { memberJson, workspaceAdmin } from "@/lib/members";
import { all, one, tx } from "@/lib/db";
import { ApiError, body, notFound, route } from "@/lib/http";

export const GET = route(async (req, { id }) => {
  const p = await auth(req);
  if (p.workspaceId !== id || p.kind !== "user") throw notFound("Workspace");
  return tx(id, async (db) => ({ data: (await all(db, "SELECT * FROM members ORDER BY created_at")).map(memberJson), next_cursor: null }));
});

/** Invite by verified email; the membership activates when that identity signs in. */
export const POST = route(async (req, { id }) => {
  const p = await workspaceAdmin(req, id);
  const b = await body(req, z.object({ email: z.string().email().transform((s) => s.toLowerCase()), role: z.enum(["owner", "editor", "viewer"]) }).strict());
  return tx(id, async (db) => {
    if (await one(db, "SELECT 1 FROM members WHERE email = $1", [b.email])) throw new ApiError(409, "CONFLICT", "This email is already a member");
    const m = await one(db, "INSERT INTO members (workspace_id, email, role) VALUES ($1,$2,$3) RETURNING *", [id, b.email, b.role]);
    await audit(db, p, "member.add", m.id, { role: b.role });
    return Response.json(memberJson(m), { status: 201 });
  });
});
