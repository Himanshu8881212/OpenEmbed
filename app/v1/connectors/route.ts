import { z } from "zod";
import { audit } from "@/lib/audit";
import { auth } from "@/lib/auth";
import { all, one, tx } from "@/lib/db";
import { ApiError, body, invalid, iso, route } from "@/lib/http";
import { getStore } from "@/lib/stores";

const json = (c: any) => ({ id: c.id, store_id: c.store_id, type: c.type, url: c.config.url, interval_minutes: c.interval_minutes, next_run_at: iso(c.next_run_at), last_job_id: c.last_job_id, created_at: iso(c.created_at) });
const allowedHosts = () => (process.env.KB_CONNECTOR_ALLOWED_HOSTS ?? "").split(",").map((h) => h.trim().toLowerCase()).filter(Boolean);

export const GET = route(async (req) => {
  const p = await auth(req);
  if (p.kind === "key") throw new ApiError(403, "ACCESS_DENIED", "Human identity required");
  return tx(p.workspaceId, async (db) => ({ data: (await all(db, "SELECT * FROM connectors WHERE deleted_at IS NULL ORDER BY created_at DESC")).map(json), next_cursor: null }));
});

/**
 * Scheduled sync from an HTTP(S) JSON manifest {"files":[{"path","url"}]}. The store mirrors the manifest:
 * new/changed files are imported, unchanged skipped, files removed from the manifest leave the store.
 * Only hosts in KB_CONNECTOR_ALLOWED_HOSTS may be fetched (prevents server-side request forgery).
 */
export const POST = route(async (req) => {
  const p = await auth(req);
  if (p.kind === "key") throw new ApiError(403, "ACCESS_DENIED", "Human identity required");
  const b = await body(req, z.object({ store_id: z.string().uuid(), type: z.literal("http_manifest"), url: z.string().url(), interval_minutes: z.number().int().min(5).max(10080).default(60) }).strict());
  const u = new URL(b.url);
  if (!["http:", "https:"].includes(u.protocol) || !allowedHosts().includes(u.host.toLowerCase())) throw invalid(`Host ${u.host} is not in the connector allowlist (KB_CONNECTOR_ALLOWED_HOSTS)`, "url");
  return tx(p.workspaceId, async (db) => {
    const s = await getStore(db, p, b.store_id, "source:write");
    if (s.kind !== "material") throw new ApiError(409, "CONFLICT", "Connectors sync into material stores only");
    const c = await one(db, "INSERT INTO connectors (workspace_id, store_id, type, config, interval_minutes, created_by) VALUES (kb_ws(), $1, $2, $3, $4, $5) RETURNING *", [s.id, b.type, { url: b.url }, b.interval_minutes, p.actor]);
    await audit(db, p, "connector.create", c.id, { store_id: s.id, host: u.host });
    return Response.json(json(c), { status: 201 });
  });
});
