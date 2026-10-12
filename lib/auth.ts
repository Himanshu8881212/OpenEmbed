import { createHash } from "node:crypto";
import { createRemoteJWKSet, jwtVerify } from "jose";
import type { NextRequest } from "next/server";
import { config } from "./config";
import { pool } from "./db";
import { ApiError, denied, invalid } from "./http";

export type Role = "owner" | "editor" | "viewer";
export type Scope = "search" | "source:read" | "source:write" | "embeddings";
export type Principal = {
  kind: "user" | "key";
  actor: string;                // "user:<identity>" | "key:<id>" — for audit, never a secret
  identityId: string | null;
  keyId: string | null;
  workspaceId: string;
  role: Role | null;            // users
  scopes: Scope[] | null;       // keys
  storeIds: string[] | null;    // keys restricted to stores (null = all)
};
export type User = { identityId: string; email: string | null; memberships: { workspace_id: string; workspace_name: string; role: Role }[] };

const unauth = (m = "The credential is missing or invalid") => new ApiError(401, "AUTHENTICATION_REQUIRED", m);
export const hashKey = (token: string) => createHash("sha256").update(token).digest();

let jwks: ReturnType<typeof createRemoteJWKSet> | undefined;
async function verifyJwt(token: string) {
  const c = config();
  jwks ??= createRemoteJWKSet(new URL(`${c.KB_OIDC_ISSUER}/protocol/openid-connect/certs`));
  try {
    const { payload } = await jwtVerify(token, jwks, { issuer: c.KB_OIDC_ISSUER });
    const client = (payload.azp ?? payload.client_id) as string | undefined;
    if (!client || !c.KB_OIDC_ALLOWED_CLIENTS.includes(client)) throw unauth("Token was issued to an unknown client");
    if (payload.email && payload.email_verified === false) throw unauth("Email not verified");
    return payload;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    throw unauth("The token is invalid or expired");
  }
}

function bearer(req: NextRequest) {
  const h = req.headers.get("authorization") ?? "";
  const m = /^Bearer\s+(\S+)$/i.exec(h);
  if (!m) throw unauth();
  return m[1];
}

/** Human identity (no workspace needed): /v1/me, /v1/workspaces. */
export async function authUser(req: NextRequest): Promise<User> {
  const token = bearer(req);
  if (token.startsWith("kb_")) throw denied("This operation requires a human identity, not an API key");
  const p = await verifyJwt(token);
  const email = typeof p.email === "string" ? p.email : null;
  const { rows: [{ id }] } = await pool.query("SELECT kb_login($1,$2,$3) AS id", [p.iss, p.sub, email]);
  const { rows } = await pool.query("SELECT * FROM kb_memberships($1)", [id]);
  return { identityId: id, email, memberships: rows };
}

/** Workspace-scoped principal from a bearer JWT (+ X-Workspace-Id) or an API key. Revocation takes effect immediately: no cache. */
export async function auth(req: NextRequest): Promise<Principal> {
  const p = await resolvePrincipal(req);
  await rateLimit(p);
  return p;
}

/** Fixed one-minute window per principal and workspace; limit = plan.limits.requests_per_minute or KB_RATE_LIMIT_PER_MINUTE. */
async function rateLimit(p: Principal) {
  const { rows: [r] } = await pool.query("SELECT * FROM kb_rate_hit($1, $2, $3)", [p.workspaceId, `${p.actor}:${p.workspaceId}`, Number(process.env.KB_RATE_LIMIT_PER_MINUTE ?? 600)]);
  if (!r.allowed) throw new ApiError(429, "RATE_LIMITED", `Rate limit of ${r.lim} requests per minute reached; retry in ${r.reset_seconds}s`, undefined,
    { "retry-after": String(r.reset_seconds), "x-ratelimit-limit": String(r.lim), "x-ratelimit-remaining": "0" });
}

async function resolvePrincipal(req: NextRequest): Promise<Principal> {
  const token = bearer(req);
  if (token.startsWith("kb_")) {
    const { rows: [k] } = await pool.query("SELECT * FROM kb_lookup_api_key($1)", [hashKey(token)]);
    if (!k) throw unauth("The API key is invalid or revoked");
    return { kind: "key", actor: `key:${k.id}`, identityId: null, keyId: k.id, workspaceId: k.workspace_id, role: null, scopes: k.scopes, storeIds: k.store_ids };
  }
  const u = await authUser(req);
  const want = req.headers.get("x-workspace-id");
  const m = want ? u.memberships.find((x) => x.workspace_id === want) : u.memberships.length === 1 ? u.memberships[0] : undefined;
  if (!m) {
    if (want) throw new ApiError(404, "RESOURCE_NOT_FOUND", "Workspace not found");
    throw invalid(u.memberships.length ? "Select a workspace with the X-Workspace-Id header" : "The identity has no workspace; create one with POST /v1/workspaces", "x-workspace-id");
  }
  return { kind: "user", actor: `user:${u.identityId}`, identityId: u.identityId, keyId: null, workspaceId: m.workspace_id, role: m.role, scopes: null, storeIds: null };
}

/**
 * Permission check.
 *  search        — search, query embeddings, connection details, store read
 *  source:read   — files, segments, original content, jobs read
 *  source:write  — uploads, ingestion, metadata, replace, membership removal, retry/cancel, store create/rename
 *  embeddings    — /v1/embeddings, /v1/multimodal-embeddings (keys: `embeddings` or `search` scope)
 *  delete        — store and source deletion: human owner/editor only (no API key may delete)
 *  keys          — create/list/revoke API keys: owner/editor
 *  admin         — members, plan, audit: owner
 *  usage         — usage read: any member
 */
export type Perm = Scope | "delete" | "keys" | "admin" | "usage";
export function can(p: Principal, perm: Perm, storeId?: string): boolean {
  if (p.kind === "user") {
    if (perm === "admin") return p.role === "owner";
    if (perm === "source:write" || perm === "delete" || perm === "keys") return p.role === "owner" || p.role === "editor";
    return true;
  }
  if (storeId && p.storeIds && !p.storeIds.includes(storeId)) return false;
  if (perm === "embeddings") return p.scopes!.includes("embeddings") || p.scopes!.includes("search");
  if (perm === "delete" || perm === "keys" || perm === "admin" || perm === "usage") return false;
  return p.scopes!.includes(perm);
}
export function require_(p: Principal, perm: Perm, storeId?: string) {
  if (!can(p, perm, storeId)) throw denied();
}
/** Keys restricted to stores cannot use workspace-wide listings. */
export function storeFilter(p: Principal): string[] | null {
  return p.kind === "key" ? p.storeIds : null;
}
