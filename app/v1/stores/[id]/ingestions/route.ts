import { z } from "zod";
import { audit } from "@/lib/audit";
import { auth } from "@/lib/auth";
import { tx } from "@/lib/db";
import { accepted, ApiError, body, route } from "@/lib/http";
import { createIngestJob, idempotencyKey, requestHash } from "@/lib/jobs";
import { getStore } from "@/lib/stores";
import { getSession } from "@/lib/uploads";

/** Import previously committed material into a store (reuses verified bytes; no re-upload). */
export const POST = route(async (req, { id }) => {
  const p = await auth(req);
  const b = await body(req, z.object({ upload_session_id: z.string().uuid() }).strict());
  const key = idempotencyKey(req);
  return tx(p.workspaceId, async (db) => {
    await getStore(db, p, id, "source:write");
    const s = await getSession(db, p, b.upload_session_id);
    if (s.state !== "committed") throw new ApiError(409, "CONFLICT", "Upload session is not committed");
    const job = await createIngestJob(db, p, { kind: "ingest", storeId: id, sessionId: s.id, key, hash: requestHash({ op: "ingest", store: id, ...b }) });
    await audit(db, p, "store.ingest", id, { job_id: job.id });
    return accepted(job);
  });
});
