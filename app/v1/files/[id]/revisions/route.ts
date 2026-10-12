import { z } from "zod";
import { audit } from "@/lib/audit";
import { auth } from "@/lib/auth";
import { all, tx } from "@/lib/db";
import { accepted, ApiError, body, route } from "@/lib/http";
import { createIngestJob, idempotencyKey, requestHash } from "@/lib/jobs";
import { getFile } from "@/lib/stores";
import { getSession } from "@/lib/uploads";

/** Replace content with a committed single-file upload. The current version stays searchable until the new one publishes. */
export const POST = route(async (req, { id }) => {
  const p = await auth(req);
  const b = await body(req, z.object({ upload_session_id: z.string().uuid() }).strict());
  const key = idempotencyKey(req);
  return tx(p.workspaceId, async (db) => {
    await getFile(db, p, id, "source:write");
    const s = await getSession(db, p, b.upload_session_id);
    if (s.state !== "committed") throw new ApiError(409, "CONFLICT", "Upload session is not committed");
    if ((await all(db, "SELECT 1 FROM upload_files WHERE session_id = $1", [s.id])).length !== 1) throw new ApiError(400, "INVALID_REQUEST", "A revision upload must contain exactly one file");
    const job = await createIngestJob(db, p, { kind: "revision", storeId: null, sessionId: s.id, fileId: id, key, hash: requestHash({ op: "revision", file: id, ...b }) });
    await audit(db, p, "file.revision", id, { job_id: job.id });
    return accepted(job);
  });
});
