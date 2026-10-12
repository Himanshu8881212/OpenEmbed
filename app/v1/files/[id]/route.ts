import { z } from "zod";
import { audit } from "@/lib/audit";
import { auth } from "@/lib/auth";
import { one, tx } from "@/lib/db";
import { fileJson } from "@/lib/files";
import { accepted, body, invalid, route } from "@/lib/http";
import { defer } from "@/lib/queue";
import { getFile } from "@/lib/stores";
import { ledger } from "@/lib/ledger";

export const GET = route(async (req, { id }) => {
  const p = await auth(req);
  return tx(p.workspaceId, async (db) => fileJson(db, await getFile(db, p, id, "source:read")));
});

const Value = z.union([z.string().max(1000), z.number(), z.boolean()]);
/** Merge-patch metadata (null removes a key). No embedded_metadata_fields in the initial profile, so no re-embedding. */
export const PATCH = route(async (req, { id }) => {
  const p = await auth(req);
  const b = await body(req, z.object({ metadata: z.record(z.string().min(1).max(100), Value.nullable()) }).strict());
  return tx(p.workspaceId, async (db) => {
    const f = await getFile(db, p, id, "source:write");
    const set = Object.fromEntries(Object.entries(b.metadata).filter(([, v]) => v !== null));
    const unset = Object.keys(b.metadata).filter((k) => b.metadata[k] === null);
    const merged = { ...f.metadata, ...set };
    for (const k of unset) delete merged[k];
    if (JSON.stringify(merged).length > 16384) throw invalid("Metadata exceeds 16 KiB", "metadata");
    const nf = await one(db, "UPDATE files SET metadata = $2, updated_at = now() WHERE id = $1 RETURNING *", [id, merged]);
    const affecting = (await one(db, `SELECT coalesce(array_agg(DISTINCT x), '{}') f FROM segments s JOIN embedding_profiles ep ON ep.id = s.profile_id, unnest(ep.embedded_metadata_fields) x WHERE s.file_version_id = $1`, [f.current_version_id])).f as string[];
    await audit(db, p, "file.metadata", id, { keys: Object.keys(b.metadata) });
    return { ...(await fileJson(db, nf)), reprocessing_required: Object.keys(b.metadata).some((k) => affecting.includes(k)) };
  });
});

/** Delete a source everywhere (scope=workspace, incl. snapshots). Access is removed now; cleanup follows retention. */
export const DELETE = route(async (req, { id }) => {
  const p = await auth(req);
  if (req.nextUrl.searchParams.get("scope") !== "workspace") throw invalid("Set scope=workspace after reviewing POST /v1/files/{id}/deletion-previews; to remove from one store use DELETE /v1/stores/{id}/files/{file_id}", "scope");
  return tx(p.workspaceId, async (db) => {
    await getFile(db, p, id, "delete");
    await db.query("UPDATE files SET deleted_at = now(), updated_at = now() WHERE id = $1", [id]);
    await db.query("UPDATE job_items SET state = 'cancelled', updated_at = now() WHERE file_id = $1 AND state = 'queued'", [id]);
    const job = await one(db, "INSERT INTO jobs (workspace_id, kind, params, created_by) VALUES (kb_ws(), 'file_delete', $1, $2) RETURNING id, state", [{ file_id: id }, p.actor]);
    await defer(db, "run_job", [{ job_id: job.id }], "maintenance");
    await audit(db, p, "file.delete", id, { scope: "workspace", job_id: job.id });
    await ledger("file.delete", p.workspaceId, id);
    return accepted(job);
  });
});
