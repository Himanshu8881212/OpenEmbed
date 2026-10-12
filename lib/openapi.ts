// OpenAPI 3.1 description of the /v1 contract. Served at GET /v1/openapi.json; tests/contract.test.mjs checks that
// every route file is documented and vice versa. OpenAPI documents the contract; "OpenAI-compatible" is only the
// /v1/embeddings + /v1/models subset described in docs/api.md.
const ref = (n: string) => ({ $ref: `#/components/schemas/${n}` });
const json = (schema: unknown) => ({ content: { "application/json": { schema } } });
const err = (codes: number[]) => Object.fromEntries(codes.map((c) => [String(c), { description: "Error", ...json(ref("Error")) }]));
const COMMON = [400, 401, 403, 404];
const op = (summary: string, o: { body?: unknown; ok?: [number, unknown] | [number]; errors?: number[]; params?: unknown[]; tag: string; security?: boolean; headers?: string[]; raw?: string }) => ({
  summary, tags: [o.tag],
  ...(o.security === false ? { security: [] } : {}),
  parameters: [...(o.params ?? []), ...(o.headers ?? []).map((h) => ({ $ref: `#/components/parameters/${h}` }))],
  ...(o.body ? { requestBody: { required: true, ...json(o.body) } } : {}),
  ...(o.raw ? { requestBody: { required: true, content: { [o.raw]: { schema: { type: "string", format: "binary" } } } } } : {}),
  responses: { [String(o.ok?.[0] ?? 200)]: { description: "Success", ...(o.ok?.[1] ? json(o.ok[1]) : {}) }, ...err(o.errors ?? COMMON) },
});
const path = (n: string) => ({ name: n, in: "path", required: true, schema: { type: "string", format: "uuid" } });
const q = (n: string, schema: unknown = { type: "string" }, required = false) => ({ name: n, in: "query", required, schema });
const page = [q("limit", { type: "integer", minimum: 1, maximum: 200 }), q("cursor")];
const list = (item: string) => ({ type: "object", properties: { data: { type: "array", items: ref(item) }, next_cursor: { type: ["string", "null"] } } });

export const openapi = {
  openapi: "3.1.0",
  info: { title: "Multimodal Knowledge Store API", version: "0.1.0", description: "Store, prepare, index and search company material with hosted EmbeddingGemma 2. Every remote business operation is available here; the kb CLI and web workbench are clients of this API." },
  servers: [{ url: "{base}", variables: { base: { default: "http://localhost:3000" } } }],
  security: [{ bearer: [] }],
  tags: ["auth", "workspaces", "keys", "models", "stores", "uploads", "jobs", "files", "search", "embeddings", "usage", "composition"].map((name) => ({ name })),
  paths: {
    "/v1/auth/device-sessions": { post: op("Start a device authorization (RFC 8628) with the identity provider", { tag: "auth", security: false, ok: [200, ref("DeviceSession")], errors: [503] }) },
    "/v1/auth/token": { post: op("Exchange a device code or refresh token for tokens", { tag: "auth", security: false, body: ref("TokenRequest"), ok: [200, ref("Tokens")], errors: [400, 401, 503] }) },
    "/v1/me": { get: op("Current identity (user or API key)", { tag: "auth" }) },
    "/v1/workspaces": {
      get: op("List accessible workspaces (human identities)", { tag: "workspaces" }),
      post: op("Create a workspace; caller becomes owner", { tag: "workspaces", body: { type: "object", required: ["name"], properties: { name: { type: "string" } }, additionalProperties: false }, ok: [201] }),
    },
    "/v1/workspaces/{id}/members": {
      get: op("List members", { tag: "workspaces", params: [path("id")] }),
      post: op("Invite a member by verified email (owner)", { tag: "workspaces", params: [path("id")], body: { type: "object", required: ["email", "role"], properties: { email: { type: "string", format: "email" }, role: ref("Role") } }, ok: [201], errors: [...COMMON, 409] }),
    },
    "/v1/workspaces/{id}/members/{member_id}": {
      patch: op("Change a member's role (owner)", { tag: "workspaces", params: [path("id"), path("member_id")], body: { type: "object", required: ["role"], properties: { role: ref("Role") } }, errors: [...COMMON, 409] }),
      delete: op("Remove a member (owner)", { tag: "workspaces", params: [path("id"), path("member_id")], ok: [204], errors: [...COMMON, 409] }),
    },
    "/v1/api-keys": {
      get: op("List API keys (no secrets)", { tag: "keys", params: page }),
      post: op("Create a scoped key; secret returned once", { tag: "keys", body: ref("ApiKeyCreate"), ok: [201] }),
    },
    "/v1/api-keys/{id}": { delete: op("Revoke a key (effective on the next request)", { tag: "keys", params: [path("id")], ok: [204] }) },
    "/v1/models": { get: op("OpenAI-style list of immutable, purpose-specific embedding aliases", { tag: "models", ok: [200, ref("ModelList")] }) },
    "/v1/embedding-profiles": {
      get: op("Validated profiles (global + this workspace's), supported formats and upload limits", { tag: "models" }),
      post: op("Create an immutable workspace profile with custom segmentation", { tag: "models", body: ref("ProfileCreate"), ok: [201] }),
    },
    "/v1/usage": { get: op("Storage and monthly indexing/query use against allowances", { tag: "usage" }) },
    "/v1/subscription": { get: op("Plan and allowances (no payment provider configured)", { tag: "usage" }) },
    "/v1/audit-events": { get: op("Audit events (owner)", { tag: "usage", params: page }) },
    "/v1/stores": {
      get: op("List stores", { tag: "stores", params: [...page, q("name")], ok: [200, list("Store")] }),
      post: op("Create an empty material store", { tag: "stores", body: { type: "object", required: ["name"], properties: { name: { type: "string", pattern: "^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$" }, profile_id: { type: "string" } }, additionalProperties: false }, ok: [201, ref("Store")], errors: [...COMMON, 409] }),
    },
    "/v1/stores/{id}": {
      get: op("Read a store", { tag: "stores", params: [path("id")], ok: [200, ref("Store")] }),
      patch: op("Rename a store (ID unchanged)", { tag: "stores", params: [path("id")], body: { type: "object", required: ["name"], properties: { name: { type: "string" } } }, ok: [200, ref("Store")], errors: [...COMMON, 409] }),
      delete: op("Delete a store with an explicit source scope", { tag: "stores", params: [path("id"), q("sources", { enum: ["unshared", "keep"] }, true)], ok: [202, ref("Accepted")] }),
    },
    "/v1/stores/{id}/deletion-previews": { post: op("Preview memberships, shared sources, views and keys affected by deletion", { tag: "stores", params: [path("id")] }) },
    "/v1/stores/{id}/stats": { get: op("Store statistics", { tag: "stores", params: [path("id")] }) },
    "/v1/stores/{id}/files": { get: op("List sources in the store's resolved membership", { tag: "files", params: [path("id"), ...page] }) },
    "/v1/stores/{id}/files/{file_id}": { delete: op("Remove a source from this store only", { tag: "files", params: [path("id"), path("file_id")], ok: [204], errors: [...COMMON, 409] }) },
    "/v1/stores/{id}/ingestions": { post: op("Import committed upload material into a store", { tag: "uploads", params: [path("id")], headers: ["IdempotencyKey"], body: { type: "object", required: ["upload_session_id"], properties: { upload_session_id: { type: "string", format: "uuid" } } }, ok: [202, ref("Accepted")], errors: [...COMMON, 409] }) },
    "/v1/stores/{id}/search": { post: op("Search a store (active profile chosen automatically)", { tag: "search", params: [path("id"), q("exact", { enum: ["true", "false"] })], body: ref("SearchRequest"), ok: [200, ref("SearchResponse")], errors: [...COMMON, 410, 413, 415, 429, 503] }) },
    "/v1/stores/{id}/connection": { get: op("Connection details and runnable code (python, javascript, curl)", { tag: "search", params: [path("id")] }) },
    "/v1/stores/{id}/query-embeddings": { post: op("Query vector for the store's active profile", { tag: "embeddings", params: [path("id")], body: { type: "object", properties: { query: ref("Query") } }, errors: [...COMMON, 429, 503] }) },
    "/v1/stores/{id}/derivations": { post: op("Create a live view or snapshot over parent stores (composition release)", { tag: "composition", params: [path("id")], body: ref("DeriveRequest"), ok: [201, ref("Store")], errors: [...COMMON, 409] }) },
    "/v1/stores/{id}/splits": { post: op("Split a store into one live view or snapshot per value of a metadata field", { tag: "composition", params: [path("id")], body: { type: "object", required: ["field"], properties: { field: { type: "string" }, mode: { enum: ["view", "snapshot"] }, prefix: { type: "string" } } }, ok: [201], errors: [...COMMON, 409] }) },
    "/v1/stores/{id}/export": { get: op("Export indexed segments (source, location, text, embedding) as NDJSON", { tag: "search", params: [path("id"), q("include", { type: "string", description: "comma list: embedding, content" })] }) },
    "/v1/stores/{id}/reindex-jobs": { post: op("Build an index for another profile (not active until promoted)", { tag: "composition", params: [path("id")], headers: ["IdempotencyKey"], body: { type: "object", required: ["profile_id"], properties: { profile_id: { type: "string" } } }, ok: [202, ref("Accepted")], errors: [...COMMON, 409] }) },
    "/v1/stores/{id}/index-promotions": { post: op("Activate a ready index revision (promotion or rollback)", { tag: "composition", params: [path("id")], body: { type: "object", required: ["index_revision"], properties: { index_revision: { type: "string", format: "uuid" } } }, ok: [200, ref("Store")], errors: [...COMMON, 409] }) },
    "/v1/store-merges": { post: op("Merge compatible stores into a new store without re-embedding", { tag: "composition", headers: ["IdempotencyKey"], body: { type: "object", required: ["sources", "target_name"], properties: { sources: { type: "array", items: { type: "string", format: "uuid" }, minItems: 2 }, target_name: { type: "string" } } }, ok: [202, ref("Accepted")], errors: [...COMMON, 409] }) },
    "/v1/connectors": {
      get: op("List source connectors", { tag: "composition" }),
      post: op("Create a scheduled sync connector (supported type: http_manifest)", { tag: "composition", body: ref("ConnectorCreate"), ok: [201], errors: [...COMMON, 409] }),
    },
    "/v1/connectors/{id}": { delete: op("Delete a connector (synced sources stay)", { tag: "composition", params: [path("id")], ok: [204] }) },
    "/v1/connectors/{id}/syncs": { post: op("Run a sync now", { tag: "composition", params: [path("id")], ok: [202, ref("Accepted")] }) },
    "/v1/files/{id}": {
      get: op("Inspect a source: current version, status, segment count, stores", { tag: "files", params: [path("id")] }),
      patch: op("Merge-patch metadata (null removes a key)", { tag: "files", params: [path("id")], body: { type: "object", required: ["metadata"], properties: { metadata: { type: "object", additionalProperties: { type: ["string", "number", "boolean", "null"] } } } } }),
      delete: op("Delete the source everywhere (scope=workspace, includes snapshots)", { tag: "files", params: [path("id"), q("scope", { enum: ["workspace"] }, true)], ok: [202, ref("Accepted")] }),
    },
    "/v1/files/{id}/deletion-previews": { post: op("Stores, snapshots and views that reference the source", { tag: "files", params: [path("id")] }) },
    "/v1/files/{id}/revisions": { post: op("Replace content with a committed single-file upload", { tag: "files", params: [path("id")], headers: ["IdempotencyKey"], body: { type: "object", required: ["upload_session_id"], properties: { upload_session_id: { type: "string", format: "uuid" } } }, ok: [202, ref("Accepted")], errors: [...COMMON, 409] }) },
    "/v1/files/{id}/segments": { get: op("Prepared segments (location, text) of a version", { tag: "files", params: [path("id"), q("version_id"), q("limit", { type: "integer" }), q("cursor")] }) },
    "/v1/files/{id}/content": { get: op("Original bytes (access rechecked per request)", { tag: "files", params: [path("id"), q("version_id")] }) },
    "/v1/upload-sessions": { post: op("Create a resumable upload session from a manifest (client sends bytes)", { tag: "uploads", body: ref("UploadSessionCreate"), ok: [201, ref("UploadSession")], errors: [...COMMON, 413, 415, 429] }) },
    "/v1/upload-sessions/{id}": {
      get: op("Inspect a session including received parts (resume)", { tag: "uploads", params: [path("id")], ok: [200, ref("UploadSession")] }),
      delete: op("Abandon an open session", { tag: "uploads", params: [path("id")], ok: [204], errors: [...COMMON, 409] }),
    },
    "/v1/upload-sessions/{id}/files/{file_id}/parts/{part}": { put: op("Upload part n (exactly part_bytes except the last); optional x-part-sha256", { tag: "uploads", params: [path("id"), path("file_id"), { name: "part", in: "path", required: true, schema: { type: "integer", minimum: 1 } }, { name: "x-part-sha256", in: "header", schema: { type: "string" } }], raw: "application/octet-stream", errors: [...COMMON, 409, 410, 413] }) },
    "/v1/upload-sessions/{id}/commit": { post: op("Commit a fully transferred session; with a store, start import (202)", { tag: "uploads", params: [path("id")], headers: ["IdempotencyKey"], body: { type: "object", properties: { store_id: { type: "string", format: "uuid" } } }, ok: [202, ref("Accepted")], errors: [...COMMON, 409, 410] }) },
    "/v1/jobs": { get: op("List jobs", { tag: "jobs", params: [...page, q("store_id"), q("state")] }) },
    "/v1/jobs/{id}": { get: op("Job state and item counts", { tag: "jobs", params: [path("id")], ok: [200, ref("Job")] }) },
    "/v1/jobs/{id}/items": { get: op("Per-file results", { tag: "jobs", params: [path("id"), ...page, q("state")] }) },
    "/v1/jobs/{id}/cancel": { post: op("Request safe cancellation", { tag: "jobs", params: [path("id")], ok: [202, ref("Job")], errors: [...COMMON, 409] }) },
    "/v1/jobs/{id}/retry": { post: op("Retry retryable failed items as a new job", { tag: "jobs", params: [path("id")], headers: ["IdempotencyKey"], ok: [202, ref("Accepted")], errors: [...COMMON, 409] }) },
    "/v1/query-assets": { post: op("Upload a temporary media query asset (raw body)", { tag: "search", raw: "image/png", ok: [201], errors: [...COMMON, 413, 415] }) },
    "/v1/query-assets/{id}": { delete: op("Delete a query asset", { tag: "search", params: [path("id")], ok: [204] }) },
    "/v1/embeddings": { post: op("OpenAI-compatible text embeddings subset", { tag: "embeddings", body: ref("EmbeddingsRequest"), ok: [200, ref("EmbeddingsResponse")], errors: [400, 401, 403, 404, 413, 429, 503] }) },
    "/v1/multimodal-embeddings": { post: op("Platform extension: ordered text/media parts", { tag: "embeddings", body: ref("MultimodalRequest"), errors: [...COMMON, 410, 413, 415, 429, 503] }) },
    "/v1/openapi.json": { get: op("This document", { tag: "models", security: false }) },
  },
  components: {
    securitySchemes: { bearer: { type: "http", scheme: "bearer", description: "OIDC access token (humans; send X-Workspace-Id when you belong to several workspaces) or API key `kb_…` (applications)." } },
    parameters: { IdempotencyKey: { name: "Idempotency-Key", in: "header", schema: { type: "string", maxLength: 200 }, description: "Replays with the same body return the original result; a different body returns 409." } },
    schemas: {
      Error: { type: "object", description: "Business endpoints. /v1/embeddings and /v1/models use the OpenAI envelope {error:{message,type,param,code}}.", properties: { error: { type: "object", required: ["code", "message", "request_id"], properties: { code: { enum: ["INVALID_REQUEST", "AUTHENTICATION_REQUIRED", "ACCESS_DENIED", "RESOURCE_NOT_FOUND", "PROFILE_INCOMPATIBLE", "RATE_LIMITED", "INPUT_TOO_LARGE", "FORMAT_UNSUPPORTED", "QUOTA_EXCEEDED", "SERVICE_UNAVAILABLE", "CONFLICT", "IDEMPOTENCY_KEY_REUSED", "UPLOAD_INCOMPLETE", "CHECKSUM_MISMATCH", "SESSION_EXPIRED", "ASSET_EXPIRED", "NOTHING_TO_RETRY", "AUTHORIZATION_PENDING", "SLOW_DOWN", "EXPIRED_TOKEN", "INTERNAL_ERROR"] }, message: { type: "string" }, request_id: { type: "string" }, param: { type: "string" } } } } },
      Role: { enum: ["owner", "editor", "viewer"] },
      DeviceSession: { type: "object", properties: { device_code: { type: "string" }, user_code: { type: "string" }, verification_uri: { type: "string" }, verification_uri_complete: { type: "string" }, expires_in: { type: "integer" }, interval: { type: "integer" } } },
      TokenRequest: { oneOf: [{ type: "object", required: ["grant_type", "device_code"], properties: { grant_type: { const: "device_code" }, device_code: { type: "string" } } }, { type: "object", required: ["grant_type", "refresh_token"], properties: { grant_type: { const: "refresh_token" }, refresh_token: { type: "string" } } }] },
      Tokens: { type: "object", properties: { access_token: { type: "string" }, refresh_token: { type: "string" }, token_type: { const: "Bearer" }, expires_in: { type: "integer" } } },
      ApiKeyCreate: { type: "object", required: ["name", "scopes"], properties: { name: { type: "string" }, scopes: { type: "array", items: { enum: ["search", "source:read", "source:write", "embeddings"] } }, stores: { type: "array", items: { type: "string", format: "uuid" }, description: "Restrict to stores (required for source:write)." } } },
      ModelList: { type: "object", properties: { object: { const: "list" }, data: { type: "array", items: { type: "object", properties: { id: { type: "string" }, object: { const: "model" }, created: { type: "integer" }, owned_by: { type: "string" }, purpose: { enum: ["query", "document"] }, profile_id: { type: "string" } } } } } },
      Store: { type: "object", properties: { id: { type: "string", format: "uuid" }, name: { type: "string" }, kind: { enum: ["material", "view", "snapshot"] }, profile_id: { type: "string" }, index_revision: { type: "string", format: "uuid" }, query_model: { type: "string" }, file_count: { type: "integer" }, segment_count: { type: "integer" }, state: { enum: ["empty", "ready"] }, created_at: { type: "string", format: "date-time" } } },
      Accepted: { type: "object", required: ["job_id", "state", "status_url"], properties: { job_id: { type: "string", format: "uuid" }, state: { type: "string" }, status_url: { type: "string" } } },
      Job: { type: "object", properties: { id: { type: "string" }, kind: { type: "string" }, state: { enum: ["queued", "running", "cancel_requested", "completed", "completed_with_errors", "failed", "cancelled"] }, items: { type: "object" }, result: {}, status_url: { type: "string" } } },
      UploadSessionCreate: { type: "object", required: ["files"], additionalProperties: false, properties: { store_id: { type: "string", format: "uuid" }, files: { type: "array", minItems: 1, items: { type: "object", required: ["path", "size", "sha256"], additionalProperties: false, properties: { path: { type: "string", description: "Relative POSIX path inside the uploaded folder." }, size: { type: "integer", minimum: 1 }, sha256: { type: "string", pattern: "^[0-9a-f]{64}$" }, replaces_file_id: { type: "string", format: "uuid" } } } } } },
      UploadSession: { type: "object", properties: { id: { type: "string" }, state: { enum: ["open", "committed", "abandoned", "expired"] }, part_bytes: { type: "integer" }, expires_at: { type: "string" }, files: { type: "array", items: { type: "object", properties: { id: { type: "string" }, path: { type: "string" }, parts: { type: "integer" }, parts_received: { type: "array", items: { type: "integer" } }, part_url_template: { type: "string" } } } } } },
      Query: { type: "object", properties: { text: { type: "string" }, asset_id: { type: "string", format: "uuid" } } },
      Filter: { type: "object", additionalProperties: false, properties: { metadata: { type: "object", additionalProperties: { type: ["string", "number", "boolean"] } }, path_prefix: { type: "string" }, media_types: { type: "array", items: { type: "string" } } } },
      SearchRequest: { type: "object", required: ["query"], properties: { query: ref("Query"), limit: { type: "integer", minimum: 1, maximum: 50, default: 10 }, filter: ref("Filter"), modalities: { type: "array", items: { enum: ["text", "image", "audio", "video"] } }, balance: { type: "boolean", default: false, description: "Rank within each modality and interleave (multimodal results despite the modality gap)." }, mode: { enum: ["hybrid", "vector"], default: "hybrid", description: "hybrid = vector + full-text fused by reciprocal rank (text queries); vector = embeddings only." } } },
      SearchResponse: { type: "object", properties: { request_id: { type: "string" }, store_id: { type: "string" }, index_revision: { type: "string" }, profile_id: { type: "string" }, results: { type: "array", items: { type: "object", properties: { segment_id: { type: "string" }, score: { type: "number", description: "Cosine similarity rank value; not answer confidence." }, content: {}, source: { type: "object", properties: { file_id: { type: "string" }, version_id: { type: "string" }, filename: { type: "string" }, path: { type: "string" }, location: { type: "object" } } } } } } } },
      ProfileCreate: { type: "object", required: ["name", "text"], properties: { name: { type: "string" }, base_profile_id: { type: "string" }, text: { type: "object", properties: { max_chars: { type: "integer", minimum: 200, maximum: 6000 }, overlap_chars: { type: "integer", minimum: 0 } } }, audio: { type: "object", properties: { segment_seconds: { type: "integer", minimum: 5, maximum: 300 } } }, video: { type: "object", properties: { segment_seconds: { type: "integer", minimum: 5, maximum: 32 } } } } },
      DeriveRequest: { type: "object", required: ["name", "mode"], properties: { name: { type: "string" }, mode: { enum: ["view", "snapshot"] }, parents: { type: "array", items: { type: "string", format: "uuid" } }, filter: ref("Filter") } },
      ConnectorCreate: { type: "object", required: ["store_id", "type", "url"], properties: { store_id: { type: "string", format: "uuid" }, type: { const: "http_manifest" }, url: { type: "string", format: "uri" }, interval_minutes: { type: "integer", minimum: 5 } } },
      EmbeddingsRequest: { type: "object", required: ["model", "input"], additionalProperties: false, properties: { model: { type: "string" }, input: { oneOf: [{ type: "string" }, { type: "array", items: { type: "string" }, minItems: 1, maxItems: 256 }] }, encoding_format: { enum: ["float", "base64"] }, dimensions: { const: 768 }, user: { type: "string" } } },
      EmbeddingsResponse: { type: "object", properties: { object: { const: "list" }, model: { type: "string" }, data: { type: "array", items: { type: "object", properties: { object: { const: "embedding" }, index: { type: "integer" }, embedding: { oneOf: [{ type: "array", items: { type: "number" } }, { type: "string", description: "base64 little-endian float32" }] } } } }, usage: { type: "object", properties: { prompt_tokens: { type: "integer" }, total_tokens: { type: "integer" } } } } },
      MultimodalRequest: { type: "object", required: ["profile_id", "purpose", "inputs"], properties: { profile_id: { type: "string" }, purpose: { enum: ["query", "document"] }, encoding_format: { enum: ["float", "base64"] }, inputs: { type: "array", items: { type: "object", properties: { parts: { type: "array", items: { oneOf: [{ type: "object", properties: { type: { const: "text" }, text: { type: "string" } } }, { type: "object", properties: { type: { enum: ["image", "audio", "video"] }, asset_id: { type: "string", format: "uuid" } } }] } } } } } } },
    },
  },
};
