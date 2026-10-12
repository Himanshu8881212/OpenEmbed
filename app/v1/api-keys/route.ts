import { randomBytes } from "node:crypto";
import { z } from "zod";
import { audit } from "@/lib/audit";
import { auth, hashKey, require_ } from "@/lib/auth";
import { all, tx } from "@/lib/db";
import { body, invalid, iso, page, paged, route } from "@/lib/http";
import { getStore } from "@/lib/stores";

const keyJson = (k: any) => ({ id: k.id, name: k.name, prefix: k.prefix, scopes: k.scopes, store_ids: k.store_ids, created_at: iso(k.created_at), revoked_at: iso(k.revoked_at), last_used_at: iso(k.last_used_at) });
const Scope = z.enum(["search", "source:read", "source:write", "embeddings"]);

export const GET = route(async (req) => {
  const p = await auth(req);
  require_(p, "keys");
  const { limit, after } = page(req);
  return tx(p.workspaceId, async (db) => paged(await all(db,
    `SELECT * FROM api_keys WHERE ($1::timestamptz IS NULL OR (created_at, id) < ($1, $2::uuid)) ORDER BY created_at DESC, id DESC LIMIT $3`,
    [after?.[0] ?? null, after?.[1] ?? null, limit + 1]), limit, keyJson));
});

/** Creates a scoped key. The secret is returned once; only its SHA-256 hash is stored. */
export const POST = route(async (req) => {
  const p = await auth(req);
  require_(p, "keys");
  const b = await body(req, z.object({ name: z.string().trim().min(1).max(100), scopes: z.array(Scope).min(1), stores: z.array(z.string()).min(1).optional() }).strict());
  return tx(p.workspaceId, async (db) => {
    const storeIds = b.stores ? [...new Set(await Promise.all(b.stores.map(async (s) => (await getStore(db, p, s, "search")).id)))] : null;
    if (!storeIds && b.scopes.includes("source:write")) throw invalid("source:write keys must be restricted to stores", "stores");
    const secret = "kb_" + randomBytes(32).toString("base64url");
    const { rows: [k] } = await db.query(
      "INSERT INTO api_keys (workspace_id, name, prefix, token_hash, scopes, store_ids, created_by) VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING *",
      [p.workspaceId, b.name, secret.slice(0, 10), hashKey(secret), [...new Set(b.scopes)], storeIds, p.identityId]);
    await audit(db, p, "api_key.create", k.id, { scopes: k.scopes, store_ids: storeIds });
    return Response.json({ ...keyJson(k), secret }, { status: 201 });
  });
});
