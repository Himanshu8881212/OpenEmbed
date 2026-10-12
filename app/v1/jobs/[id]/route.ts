import { auth, require_ } from "@/lib/auth";
import { tx } from "@/lib/db";
import { route } from "@/lib/http";
import { getJob, jobJson } from "@/lib/jobs";

export const GET = route(async (req, { id }) => {
  const p = await auth(req);
  require_(p, "source:read");
  return tx(p.workspaceId, async (db) => jobJson(db, await getJob(db, p, id)));
});
