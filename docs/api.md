# API reference (v1)

Machine-readable contract: `GET /v1/openapi.json` (OpenAPI 3.1). `tests/contract.test.mjs` checks that it matches the implemented routes exactly. This page covers the conventions that the schema alone does not express.

## Conventions
- **Base URL**: your deployment (`KB_PUBLIC_BASE_URL`). All paths are under `/v1`. Use HTTPS in production (terminate TLS in front of the API).
- **Authentication**: `Authorization: Bearer <token>`.
  - Humans: OIDC access token (device flow via `POST /v1/auth/device-sessions` + `POST /v1/auth/token`, or browser code+PKCE). If you belong to several workspaces, send `X-Workspace-Id`.
  - Applications: API key `kb_…` (one workspace; optional store restriction).
- **Scopes** (keys): `search` (search, query embeddings, connection details, store read), `source:read` (files, segments, original content, jobs), `source:write` (uploads, ingestion, metadata, replacement, membership removal, retry/cancel; store-restricted keys only), `embeddings` (`/v1/embeddings`, `/v1/multimodal-embeddings`, query assets; `search` also allows these). No key can delete stores or sources, manage keys or members, or read usage. Those are human-only.
- **Roles** (humans): `owner` (everything, incl. members, audit), `editor` (material, stores, keys, deletion), `viewer` (read and search).
- **Revocation delay**: 0. Keys and memberships are checked on every request.
- **IDs** are UUIDs. Store paths take IDs only (names can change). `GET /v1/stores?name=` resolves a name.
- **Lists**: `?limit=` (1–200) and `?cursor=` from `next_cursor`. **Timestamps**: ISO 8601 UTC. **Sizes**: bytes.
- **Idempotency**: `Idempotency-Key` on upload commit, ingestions, revisions, retries, reindex and merges. A replay with the same body returns the original result. The same key with a different body returns `409 IDEMPOTENCY_KEY_REUSED`.
- **Background work** returns `202 {"job_id","state","status_url"}`. Accepted is not the same as published: poll `GET /v1/jobs/{id}` and read `GET /v1/jobs/{id}/items` for per-file results.
- **Diagnostics**: every response carries `x-request-id`. Business errors also include it in the body.

## Errors
Business endpoints: `{"error":{"code","message","request_id","param"?}}`.

| Status | Codes |
|---|---|
| 400 | `INVALID_REQUEST`, `CHECKSUM_MISMATCH`, `AUTHORIZATION_PENDING`, `SLOW_DOWN`, `EXPIRED_TOKEN` |
| 401 | `AUTHENTICATION_REQUIRED` |
| 403 | `ACCESS_DENIED` (visible resource, missing role/scope) |
| 404 | `RESOURCE_NOT_FOUND`: absent, in another workspace, or outside a key's stores (one concealment policy) |
| 409 | `PROFILE_INCOMPATIBLE`, `CONFLICT`, `IDEMPOTENCY_KEY_REUSED`, `UPLOAD_INCOMPLETE`, `NOTHING_TO_RETRY`, `INDEX_NOT_READY`, `INDEX_INCOMPLETE` |
| 410 | `SESSION_EXPIRED`, `ASSET_EXPIRED` |
| 413 | `INPUT_TOO_LARGE` (file/part/session limits, or input over the 8,192-token model budget) |
| 415 | `FORMAT_UNSUPPORTED` |
| 429 | `QUOTA_EXCEEDED` (hard caps, full queue), `RATE_LIMITED` (requests/minute; `Retry-After`, `X-RateLimit-Limit`) |
| 503 | `SERVICE_UNAVAILABLE` (inference/IdP unavailable) |

Per-item job errors: `CHECKSUM_MISMATCH`, `UNREADABLE` (incl. encrypted PDF), `EMPTY_CONTENT`, `FORMAT_UNSUPPORTED`, `INPUT_TOO_LARGE`, `UPLOAD_MISSING` (not retryable: correct and re-upload); `SERVICE_UNAVAILABLE`, `QUOTA_EXCEEDED`, `INTERNAL_ERROR` (retryable via `POST /v1/jobs/{id}/retry`).

## Formats and limits (validated)
| Type | Extensions | Segments and locations |
|---|---|---|
| Text | `.txt`, `.md`, `.markdown` (UTF-8) | ≤1,600-char passages, 200 overlap; `{start,end}` char offsets |
| Word | `.docx` (Office Open XML) | body paragraphs and tables in order → passages `{start,end,section}` (nearest heading); headers/footers, comments, text boxes not extracted; encrypted/damaged → `UNREADABLE`. Legacy `.doc` is not supported. |
| PDF | `.pdf` | text pages → passages `{page,start,end}`; pages with < 20 chars of text → rendered page image `{page}` and (p4) OCR text passages `{page,kind:"ocr"}`; encrypted → `UNREADABLE` |
| Image | `.jpg`, `.jpeg`, `.png` | whole image (280 soft tokens) |
| Audio | `.wav`, `.mp3` | 30 s windows (5 s overlap in p3/p4), 16 kHz mono `{start_seconds,end_seconds}`; p4 adds speech transcript passages `{start_seconds,end_seconds,kind:"transcript"}` |
| Video | `.mp4` | p4: 20 s windows (4 s overlap), 720p frames at 1 fps with 280 tokens/frame; soundtrack audio windows `{kind:"soundtrack"}` and transcript passages `{kind:"transcript"}`. p1–p3: 30 s visual windows at 480p |

Limits (configurable): 512 MiB per file, 1,000 files per session, 8 MiB parts, sessions expire after 24 h, query assets are ≤ 20 MiB and expire after 1 h. Nothing is truncated silently. Over-budget inputs fail explicitly. `GET /v1/embedding-profiles` publishes the live values.

## Uploads (resumable)
1. `POST /v1/upload-sessions {store_id?, files:[{path,size,sha256,replaces_file_id?}]}`. Paths are relative POSIX paths inside the uploaded folder. Absolute paths, `..`, backslashes, drive letters and control characters are rejected. The server never reads client paths.
2. `PUT /v1/upload-sessions/{id}/files/{file_id}/parts/{n}` with raw bytes. Every part except the last must be exactly `part_bytes`. The optional `x-part-sha256` header is verified. Re-sending a part is safe.
3. To resume, call `GET /v1/upload-sessions/{id}`, which lists `parts_received` per file, then send the rest.
4. `POST /v1/upload-sessions/{id}/commit` (Idempotency-Key). With a store this returns 202 and starts the import job. Before publishing, the worker verifies the whole-file SHA-256 and keeps one content-addressed copy per workspace.

## Search
`POST /v1/stores/{id}/search {query:{text?, asset_id?}, limit (1–50), filter?:{metadata:{k:v}, path_prefix, media_types}, mode?: "hybrid"|"vector" (default hybrid), modalities?: ["text","image","audio","video"], balance?: boolean}`.
- `mode: hybrid` fuses vector ranks with selective identifier keyword ranks (tokens with digits or acronyms that occur in ≤10% of the store's passages, e.g. `PS-400`, `ISO VG 46`). Results show `match: {keyword_rank, vector_rank}`. Media-only queries are vector.
- `balance: true` returns the best matches of each format, interleaved (`modality_rank`). Without it, ordering follows the score, and text usually outranks media for text queries. The store's active profile is used automatically. Each result carries `request_id, store_id, index_revision, profile_id, segment_id, score, content, source{file_id, version_id, version_no, filename, path, location, metadata}`. Text segments return the passage. Media segments return `{type, media_url, location}`. The score is cosine similarity: it ranks results and is not answer confidence. `?exact=true` runs an exact scan, for diagnosing approximate search under selective filters.

## OpenAI-compatible embeddings subset
`GET /v1/models`, `POST /v1/embeddings`. This is compatibility with the HTTP shape of OpenAI's embeddings API, not an implementation of every OpenAI endpoint.

- Supported: `model` (an alias from `/v1/models`), `input` (string or array of up to 256 non-empty strings), `encoding_format` (`float` | `base64`, little-endian float32), `dimensions` (only 768), `user` (ignored).
- Response: `{object:"list", model, data:[{object:"embedding", index, embedding}], usage:{prompt_tokens,total_tokens}}`. Data is in input order. Usage counts measured EmbeddingGemma 2 tokens, including the instruction prefix.
- Aliases are immutable and purpose-specific: `…-query` applies `task: search result | query: `, and `…-document` applies `title: none | text: `. Use the alias returned by `GET /v1/stores/{id}/connection`. After a store's index is promoted to a new profile, its connection returns the new alias.
- Rejected explicitly: token-ID arrays (`unsupported_input`), media objects (use the extension), other dimensions (`unsupported_dimensions`), unknown parameters (`unsupported_parameter`), unknown or OpenAI model names (`404 model_not_found`).
- Errors use the OpenAI envelope `{"error":{"message","type","param","code"}}`, with the request id in the `x-request-id` header.
- Tested SDKs: `openai` JS 7.32.0 (default base64 encoding) and `openai` Python 3.29.0.

## Multimodal extension (platform-specific)
Upload media with `POST /v1/query-assets` (raw body; `Content-Type` image/png, image/jpeg, audio/wav, audio/mpeg, video/mp4). Then call `POST /v1/multimodal-embeddings {profile_id, purpose:"query"|"document", encoding_format?, inputs:[{parts:[{type:"text",text}|{type:"image"|"audio"|"video",asset_id}]}]}`, which returns one vector per input, with parts interleaved in order. Unmodified OpenAI SDKs cannot send these objects. Store search accepts `query.asset_id` directly.

## Data freedom
- **Export:** `GET /v1/stores/{id}/export[?include=embedding,content]` streams NDJSON, one line per indexed segment: `{segment_id, store_id, profile_id, index_revision, modality, ordinal, token_count, source{file_id, version_id, version_no, path, filename, media_type, sha256, metadata, location}, content, embedding[768]}`. Requires `source:read`.
- **Split:** `POST /v1/stores/{id}/splits {field, mode: view|snapshot, prefix?}` creates one derived store per distinct value (≤ 50) named `<prefix>-<value>`. Existing names are skipped and reported.
- **Custom chunking:** `POST /v1/embedding-profiles {name, base_profile_id?, text:{max_chars 200–6000, overlap_chars < max/2}, audio?:{segment_seconds 5–300}, video?:{segment_seconds 5–32}}` creates an immutable workspace profile with `…-query`/`…-document` aliases. Use it in `POST /v1/stores {profile_id}` or `reindex-jobs`.
- **Nested views:** `derivations` accepts views as parents (depth ≤ 3).

## Operations endpoints
`GET /healthz`, `GET /readyz`, `GET /metrics` (Prometheus; `Authorization: Bearer $KB_METRICS_TOKEN`, 404 otherwise).
