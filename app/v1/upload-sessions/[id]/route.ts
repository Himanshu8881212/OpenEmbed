import { audit } from "@/lib/audit";
import { auth, require_ } from "@/lib/auth";
import { tx } from "@/lib/db";
import { ApiError, route } from "@/lib/http";
import { abortMultipart, getSession, sessionJson } from "@/lib/uploads";

/** Inspect a session, including which parts were received (used to resume). */
export const GET = route(async (req, { id }) => {
  const p = await auth(req);
  require_(p, "source:write");
  return tx(p.workspaceId, async (db) => sessionJson(db, await getSession(db, p, id)));
});

/** Abandon an open session and discard its partial bytes. */
export const DELETE = route(async (req, { id }) => {
  const p = await auth(req);
  require_(p, "source:write");
  return tx(p.workspaceId, async (db) => {
    const s = await getSession(db, p, id);
    if (s.state !== "open") throw new ApiError(409, "CONFLICT", `Session is ${s.state}`);
    await abortMultipart(db, id);
    await db.query("UPDATE upload_sessions SET state = 'abandoned' WHERE id = $1", [id]);
    await audit(db, p, "upload.abandon", id);
    return new Response(null, { status: 204 });
  });
});
