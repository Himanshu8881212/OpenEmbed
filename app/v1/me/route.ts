import { auth, authUser } from "@/lib/auth";
import { route } from "@/lib/http";

export const GET = route(async (req) => {
  if ((req.headers.get("authorization") ?? "").includes(" kb_")) {
    const p = await auth(req);
    return { kind: "api_key", key_id: p.keyId, workspace_id: p.workspaceId, scopes: p.scopes, store_ids: p.storeIds };
  }
  const u = await authUser(req);
  return { kind: "user", identity_id: u.identityId, email: u.email, workspaces: u.memberships.map((m) => ({ id: m.workspace_id, name: m.workspace_name, role: m.role })) };
});
