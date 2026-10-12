import { z } from "zod";
import { audit } from "@/lib/audit";
import { auth } from "@/lib/auth";
import { one, tx } from "@/lib/db";
import { accepted, ApiError, body, invalid, route } from "@/lib/http";
import { StoreName } from "@/lib/names";
import { defer } from "@/lib/queue";
import { getStore, storeJson } from "@/lib/stores";
import { ledger } from "@/lib/ledger";

export const GET = route(async (req, { id }) => {
  const p = await auth(req);
  return tx(p.workspaceId, async (db) => storeJson(db, await getStore(db, p, id, "search")));
});

/** Rename. The ID is stable, so application connections are unaffected. */
export const PATCH = route(async (req, { id }) => {
  const p = await auth(req);
  const b = await body(req, z.object({ name: StoreName }).strict());
  return tx(p.workspaceId, async (db) => {
    const s = await getStore(db, p, id, "source:write");
    if (p.kind === "key") throw new ApiError(403, "ACCESS_DENIED", "API keys cannot rename stores");
    if (await one(db, "SELECT 1 FROM stores WHERE deleted_at IS NULL AND lower(name) = lower($1) AND id <> $2", [b.name, id])) throw new ApiError(409, "CONFLICT", "A store with this name already exists");
    await db.query("UPDATE stores SET name = $2, updated_at = now() WHERE id = $1", [id, b.name]);
    await audit(db, p, "store.rename", id, { from: s.name, to: b.name });
    return storeJson(db, { ...s, name: b.name });
  });
});

/**
 * Delete a store. Scope (required): `sources=unshared` also deletes sources referenced by no other store;
 * `sources=keep` keeps every source in the workspace. The store is inaccessible immediately; cleanup runs as a job.
 */
export const DELETE = route(async (req, { id }) => {
  const p = await auth(req);
  const scope = req.nextUrl.searchParams.get("sources");
  if (scope !== "unshared" && scope !== "keep") throw invalid("Choose the deletion scope: sources=unshared or sources=keep (see the deletion preview)", "sources");
  return tx(p.workspaceId, async (db) => {
    await getStore(db, p, id, "delete");
    await db.query("UPDATE stores SET deleted_at = now(), updated_at = now() WHERE id = $1", [id]);
    const job = await one(db, "INSERT INTO jobs (workspace_id, store_id, kind, params, created_by) VALUES (kb_ws(), $1, 'store_delete', $2, $3) RETURNING id, state", [id, { sources: scope }, p.actor]);
    await defer(db, "run_job", [{ job_id: job.id }], "maintenance");
    await audit(db, p, "store.delete", id, { sources: scope, job_id: job.id });
    const unshared = scope === "unshared" ? (await db.query(`SELECT sf.file_id FROM store_files sf WHERE sf.store_id = $1 AND NOT EXISTS
      (SELECT 1 FROM store_files o JOIN stores os ON os.id = o.store_id AND os.deleted_at IS NULL WHERE o.file_id = sf.file_id AND o.store_id <> $1)`, [id])).rows.map((r) => r.file_id) : [];
    await ledger("store.delete", p.workspaceId, id, { sources: scope, file_ids: unshared });
    return accepted(job);
  });
});
