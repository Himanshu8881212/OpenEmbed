import { z } from "zod";
import { audit } from "@/lib/audit";
import { one, tx } from "@/lib/db";
import { ApiError, body, notFound, route } from "@/lib/http";
import { memberJson, workspaceAdmin } from "@/lib/members";
import { ledger } from "@/lib/ledger";

async function guardLastOwner(db: any, memberId: string) {
  const r = await one(db, "SELECT count(*) FILTER (WHERE role='owner' AND identity_id IS NOT NULL)::int owners, bool_or(id = $1 AND role = 'owner') target FROM members", [memberId]);
  if (r.target && r.owners <= 1) throw new ApiError(409, "CONFLICT", "A workspace must keep at least one active owner");
}

export const PATCH = route(async (req, { id, member_id }) => {
  const p = await workspaceAdmin(req, id);
  const b = await body(req, z.object({ role: z.enum(["owner", "editor", "viewer"]) }).strict());
  return tx(id, async (db) => {
    if (b.role !== "owner") await guardLastOwner(db, member_id);
    const m = await one(db, "UPDATE members SET role = $2 WHERE id = $1 RETURNING *", [member_id, b.role]);
    if (!m) throw notFound("Member");
    await audit(db, p, "member.update", member_id, { role: b.role });
    return memberJson(m);
  });
});

export const DELETE = route(async (req, { id, member_id }) => {
  const p = await workspaceAdmin(req, id);
  return tx(id, async (db) => {
    await guardLastOwner(db, member_id);
    const m = await one(db, "DELETE FROM members WHERE id = $1 RETURNING id", [member_id]);
    if (!m) throw notFound("Member");
    await audit(db, p, "member.remove", member_id);
    await ledger("member.remove", id, member_id);
    return new Response(null, { status: 204 });
  });
});
