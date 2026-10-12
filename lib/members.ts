import type { NextRequest } from "next/server";
import { auth, require_ } from "./auth";
import { iso, notFound } from "./http";

export const memberJson = (m: any) => ({ id: m.id, email: m.email, role: m.role, status: m.identity_id ? "active" : "invited", created_at: iso(m.created_at) });

export async function workspaceAdmin(req: NextRequest, id: string) {
  const p = await auth(req);
  if (p.workspaceId !== id) throw notFound("Workspace");
  require_(p, "admin");
  return p;
}
