# Requirements matrix

Source: `docs/source/iso-guide.md` (§ = guide section). Scope: **I** = initial release, **L** = later release (labelled in the guide), **X** = external/process gate (not satisfiable by code).
Status: `todo` · `wip` · `done` (implemented + verified, evidence listed) · `blocked`.
Tests (real Postgres/pgvector, SeaweedFS S3, Keycloak, EmbeddingGemma 2): `tests/security.test.mjs`, `tests/ingest.test.mjs`, `tests/retrieval.test.mjs`, `tests/cli.test.mjs`; unit: `py/tests`.

## Architecture and platform
| ID | § | Scope | Requirement / acceptance | Impl | Evidence | Status |
|---|---|---|---|---|---|---|
| ARCH-01 | 10.4, 11.4, 16.4 | I | Every remote business operation has an HTTP endpoint; core tasks run via HTTP without the CLI. | `app/v1/**` | T:cli journey uses only HTTP; all suites drive HTTP | done |
| ARCH-02 | 1.1, 3.1, 16.4 | I | Hosted EmbeddingGemma 2; clients load no weights. | `py/kbpy/inference.py` | CLI/snippets run with no model deps; retrieval eval | done |
| ARCH-03 | 15.1 | I | Preparation/inference in separate Python processes; no bulk/GPU work inside web requests. | `py/kbpy/worker.py` | ingest suite (worker processes spawned/killed) | done |
| ARCH-04 | 2.2, 15.1 | I | Originals preserved in S3-compatible storage; embeddings never treated as source. | `lib/s3.ts`, worker `verify_upload` | retrieval "original content byte-for-byte" | done |
| ARCH-05 | 15.3 | I | Postgres + pgvector `vector(768)`; profile/workspace/source/published state with each searchable record. | `db/migrations/002_core.sql` | security RLS suite | done |
| OPS-01 | M0 | I | Reproducible dev env, pinned deps, migrations, config validation, `/healthz` `/readyz`, `.env.example` without secrets. | `docker-compose.yml`, `lib/config.ts`, `/readyz`, `scripts/bootstrap.sh`, `scripts/ci.sh` | clean-install CI from fresh copy: 87/87 (2026-10-12); `.env.example` | done |

## API contract
| ID | § | Scope | Requirement / acceptance | Impl | Evidence | Status |
|---|---|---|---|---|---|---|
| API-01 | 11.1 | I | Versioned `/v1`; OpenAPI published at `/v1/openapi.json`, every route documented. | `lib/openapi.ts` | `tests/contract.test.mjs` (routes ⇔ spec) | done |
| API-02 | 11.1 | I | Bearer auth; workspace + store permission on every request. | `lib/auth.ts` | security suite | done |
| API-03 | 11.1 | I | Cursor pagination on lists; UTC ISO timestamps; sizes in bytes. | `lib/http.ts` page/paged | retrieval "cursor pagination walks every file exactly once" | done |
| API-04 | 11.1 | I | Idempotency-Key on job creation and upload commit; same key + different body → 409. | `lib/jobs.ts` | ingest "resumable transfer", "inference outage" (replay + 409) | done |
| API-05 | 11.1, 11.9 | I | Background work → 202 `{job_id,state,status_url}`. | `lib/http.ts` accepted | ingest suite | done |
| API-06 | 11.5 | I | Stable error codes (400/401/403/404/409/413/415/429/503) with message + request_id; concealment policy D24. | `lib/http.ts` | security 401/404; ingest 400/409/413/415/429 | done |

## Identity, access, isolation
| ID | § | Scope | Requirement / acceptance | Impl | Evidence | Status |
|---|---|---|---|---|---|---|
| AUTH-01 | 3.2, 11.2 | I | Device flow: `POST /v1/auth/device-sessions`, `POST /v1/auth/token` (device + refresh grants). | `app/v1/auth/*` | web "device authorization flow … real browser approval" (device → approve → token → /v1/me → refresh) | done |
| AUTH-02 | 11.2 | I | `GET /v1/me`, `GET/POST /v1/workspaces`. | `app/v1/me`, `app/v1/workspaces` | security, cli | done |
| AUTH-03 | 11.2, 14.1 | I | Members list/add/update/remove; roles owner/editor/viewer; owners manage members/keys/plans, editors manage stores/material. | `app/v1/workspaces/[id]/members/*` | security "roles" | done |
| AUTH-04 | 3.3, 14.1, 14.2 | I | API keys: list/create/revoke; scopes `search`, `source:read`, `source:write`, `embeddings`; optional store restriction; search key cannot delete; revocation effective immediately (delay = 0, tested). | `app/v1/api-keys/*` | security "API keys" (revocation delay 0) | done |
| ISO-01 | 14.1, 14.5 | I | Workspace boundary enforced by API and RLS with non-owner `kb_api`/`kb_worker` roles; transaction-local context; pooled-connection reuse cannot leak context; workers preserve boundary. | migrations 002/006, `lib/db.ts` | security "row security with the real service roles" + API isolation | done |

## Stores, uploads, jobs, files
| ID | § | Scope | Requirement / acceptance | Impl | Evidence | Status |
|---|---|---|---|---|---|---|
| STORE-01 | 7.1, 11.3 | I | Create/list/read/rename (PATCH) stores; stable ID; stats. | `app/v1/stores/*` | cli journey, security | done |
| STORE-02 | 7.4, 14.3 | I | Deletion preview + delete; deleted store searches fail immediately; cleanup keeps referenced bytes. | `app/v1/stores/[id]` DELETE, `py/kbpy/jobs.py` | ingest "store deletion" | done |
| UP-01 | 5.3, 11.4 | I | Upload sessions: create/inspect/abandon, PUT parts, commit; resume after interruption; expiry. | `app/v1/upload-sessions/*` | ingest "resumable transfer"; cli resume | done |
| UP-02 | M2 | I | SHA-256 verified per part (optional header) and per file; mismatch → item failure `CHECKSUM_MISMATCH`. | parts route + worker `verify_upload` | ingest "checksum mismatch" | done |
| UP-03 | 1.4, 5.2 | I | CLI uploads real bytes, preserves relative paths, ignores symlinks and reports ignored files; API never accepts a server path. | `cli/kb.ts` scan/upload | cli journey (ignored files listed) | done |
| UP-04 | M3 | I | Limits (file size, files/session, parts) → 413; unsafe paths (`..`, absolute, NUL) → 400; unsupported → 415. | `lib/uploads.ts` SafePath, limits | ingest "upload validation" | done |
| UP-05 | 5.2, 12.3 | I | Unchanged bytes reused within a workspace (content-addressed); counted once in storage. | blobs table + worker | ingest "same bytes twice" | done |
| ING-01 | 11.4 | I | Commit with `store_id` creates import job; `POST /v1/stores/{id}/ingestions` reuses committed material. | commit + `stores/[id]/ingestions` | ingest "membership removal vs source deletion" | done |
| ING-02 | 5.1 | I | Formats advertised only when validated: TXT/MD (passages+offsets), DOCX (passages+offsets+section; added 2026-10-12 on request), text PDF (pages), image PDF (page images), JPEG/PNG, WAV/MP3 (time ranges), MP4 (time ranges, video frames). | `py/kbpy/prepare.py` | py unit tests + retrieval "all advertised formats" | done |
| ING-03 | 5.1, 13.2 | I | No silent truncation: every segment checked against the 8192-token budget; overflow → item error `INPUT_TOO_LARGE`. | inference budget check | retrieval 413 input_too_large; prepare chunk coverage test | done |
| JOB-01 | 5.6, 11.4 | I | Job states queued/running/cancel_requested/completed/completed_with_errors/failed/cancelled; list, status, items. | `lib/jobs.ts`, `kb_finalize_job` | ingest suite | done |
| JOB-02 | 5.4 | I | Retry eligible failed items; no duplicate segments. | `jobs/[id]/retry` | ingest "inference outage" | done |
| JOB-03 | 5.5 | I | Cancel at a safe boundary; already-published items stay. | `jobs/[id]/cancel`, worker batch boundary | ingest "cancellation" | done |
| JOB-04 | 15.6 | I | Jobs survive client exit, worker crash (lease/heartbeat recovery) and duplicate delivery without duplicate vectors or charges. | procrastinate leases, deterministic ids | ingest "worker killed mid-item", "duplicate delivery" | done |
| FILE-01 | 6.1, 11.3 | I | List store files, inspect file (current version, segment count, status), segments, original content (permission + short-lived access). | `app/v1/files/[id]/*` | retrieval, cli inspect | done |
| FILE-02 | 6.2 | I | Metadata PATCH; profile declares representation-affecting fields (initial: none → no re-embedding). | `files/[id]` PATCH | cli tag + filtered search | done |
| FILE-03 | 6.3 | I | Replace via `/files/{id}/revisions`; old version stays current until complete new version publishes. | `files/[id]/revisions`, worker publish | ingest "atomic replacement"; cli replace | done |
| FILE-04 | 6.4, 14.3 | I | Remove membership vs delete source; source deletion has preview + explicit scope; access removed before cleanup. | membership DELETE, files DELETE scope | ingest deletion tests | done |
| DEL-01 | 14.3, 15.6 | I | Cleanup job removes unreferenced segments/blobs per retention; restored backup must not expose deleted material. | worker `gc_workspace`, `lib/ledger.ts`, `scripts/{backup,restore}.sh`, `reapply-deletions.mjs` | ingest cleanup tests; `tests/zz-backup.test.mjs` restore drill | done |

## Retrieval and embeddings
| ID | § | Scope | Requirement / acceptance | Impl | Evidence | Status |
|---|---|---|---|---|---|---|
| SRCH-01 | 8.1, 8.2 | I | `POST /v1/stores/{id}/search` text query; active profile auto-selected; fields request_id, store_id, index_revision, profile_id, segment_id, score, content, source{file_id, version_id, filename, location}. | `lib/search.ts` | retrieval eval + field assertions | done |
| SRCH-02 | 8.1, 13.3 | I | Metadata filters; approximate results match exact baseline under selective filters; workspace/membership applied before and after candidate selection. | `lib/search.ts` iterative scan | retrieval "exact vs approximate" | done |
| SRCH-03 | 8.4 | I | Labelled real-model retrieval evaluation (recall@5 ≥ 0.9 on fixture set). | `tests/fixtures/eval.json` | hit@5=1.000, MRR=0.967 (n=15, threshold 0.9) | done |
| CONN-01 | 9.1–9.5 | I | `GET /v1/stores/{id}/connection` → python/javascript/curl, base URL, store ID, query alias; generated snippets run against service. | `stores/[id]/connection` | cli journey runs python/js/curl + embeddings snippet | done |
| EMB-01 | 11.6, 11.8 | I | `GET /v1/models` list envelope; immutable purpose-specific aliases. `GET /v1/embedding-profiles`. | `app/v1/models`, `embedding-profiles` | retrieval "models list envelope" | done |
| EMB-02 | 11.6 | I | `POST /v1/embeddings`: string/list, ordered `index`, float/base64, measured Gemma token usage, `dimensions` only = 768, token-ID input rejected, unknown params rejected, OpenAI error envelope; official `openai` SDK tested. | `app/v1/embeddings` | retrieval contract + openai JS 7.32.0 + Python 3.29.0 | done |
| EMB-03 | 11.7 | I | `POST /v1/multimodal-embeddings` with ordered parts referencing query assets. | `app/v1/multimodal-embeddings` | retrieval "multimodal extension" | done |
| EMB-04 | 11.4 | I | `POST /v1/stores/{id}/query-embeddings` uses store's active query profile. | `stores/[id]/query-embeddings` | retrieval (matches query alias) | done |
| EMB-05 | 15.4, 15.5 | I | Profiles immutable (DB-enforced), pin revision/dims/normalization/prompts/preparation/dtype; non-finite vectors rejected. | profile rows + triggers + inference checks | security "immutable"; retrieval norms | done |
| QA-01 | 8.3, 11.4 | I | `POST/DELETE /v1/query-assets`; expiry; workspace access validated. | `app/v1/query-assets/*`, `lib/assets.ts` | security cross-ws asset; retrieval expiry 410 | done |

## Control
| ID | § | Scope | Requirement / acceptance | Impl | Evidence | Status |
|---|---|---|---|---|---|---|
| USE-01 | 12, 15.6 | I | `GET /v1/usage`, `GET /v1/subscription`: storage bytes by category + GiB-month (hourly samples), text/media tokens; replay-safe events; hard caps → 429; bounded per-workspace queue (`KB_MAX_QUEUED_ITEMS`). | `lib/usage.ts`, `app/v1/usage` | ingest "usage reconciles…", "GiB-month", "queue is bounded" | done |
| AUD-01 | 11.2 | I | `GET /v1/audit-events` for key, member, store, delete actions. | `app/v1/audit-events` | ingest "audit events" | done |
| DATA-01 | 14.4 | I | Customer content excluded from logs; source URLs short-lived with access recheck. | error logs exclude content; content streamed with per-request access check | ingest "log hygiene" (worker INFO logs) + grep of API/inference logs: 0 hits | done |
| CLI-01 | 10 | I | Commands of §10.1; `--json` on stdout, progress on stderr; `--wait` nonzero exit on failure/partial; top-level and command help. | `cli/kb.ts` | cli journey (exit 0/1/3, --json, help) | done |

## V1 additions (data freedom and hardening, from the 2026-10-12 review)
| ID | Source | Scope | Requirement / acceptance | Impl | Evidence | Status |
|---|---|---|---|---|---|---|
| V1-EXPORT | goal: "complete freedom over their data and embeddings" | I | Export a store's segments (source, location, text, 768-d embedding) as NDJSON; access rechecked per batch; `source:read` only. | `app/v1/stores/[id]/export` | v1 "embedding export" (vectors match search) | done |
| V1-SPLIT | §7.3 reuse | I | Split a store by metadata field into live views or snapshots in one call (≤50 values, no overwrite). | `app/v1/stores/[id]/splits`, `lib/derive.ts` | v1 "split by field" | done |
| V1-PROFILE | §15.4–15.5, goal | I | Workspace-defined immutable chunking profiles (text chars/overlap, audio/video window) within model limits; private to workspace; usable for new stores and reindex. | `POST /v1/embedding-profiles`, migration 010 | v1 "custom chunking profiles" | done |
| V1-NEST | §7.3 | I | Live views over views (depth ≤ 3), recursive membership, snapshots of views. | migrations 010/012, `lib/derive.ts` | v1 "nested live views"; composition | done |
| V1-RATE | §11.5 (429 "plan or rate limit") | I | Per-principal per-workspace requests/minute (plan `requests_per_minute`, default `KB_RATE_LIMIT_PER_MINUTE`), 429 `RATE_LIMITED` + `Retry-After`. | `lib/auth.ts`, `kb_rate_hit` | v1 "per-principal rate limit" | done |
| V1-OBS | §15.6 operations | I | `/metrics` (Prometheus, token-protected, no identifiers), JSON access logs without content. | `app/metrics`, `lib/http.ts` | v1 "/metrics"; ingest "log hygiene" | done |
| V1-HEADERS | §14.4 | I | CSP, frame-ancestors none, nosniff, no-referrer, HSTS, permissions policy. | `next.config.ts` | v1 "security headers" | done |
| V1-SPEED | review: "jobs fast" | I | Inference device `auto` (CUDA → Apple GPU → CPU) at the profile's fp32 precision behind an equivalence gate (CPU-reference cosine ≥ 0.9999, else refuse to start); identical media vectors reused across profiles; one-pass reindex. Measured: image 1.44→0.82 s, video 30 s 21.3→14.3 s; DUNE 378-file reindex 24 s. | `py/kbpy/inference.py`, worker `MEDIA_PREP_KEY` | readyz `equivalence`; retrieval "image vectors are reused"; operations.md table | done |
| V1-CHUNK | §5.1, review: "high-quality chunking" | I | Profile `p3` (provider default for new stores): heading-aware sections, sentence packing/overlap, tiny-tail merge, table header repeat, contextual title (file › section · page); audio/video 30 s windows with 5 s overlap. p1/p2 unchanged. | `py/kbpy/prepare.py`, migration 013 | py unit `StructureChunking`; retrieval "chunking quality" (answer@1); DUNE answer@1 0.2→0.7 | done |
| V1-HYBRID | §8.4 | I | Hybrid search (default for text queries): RRF of vectors and selective identifier keywords (English tsvector, tokens with digits/acronyms present in ≤10% of passages); `mode: vector` available. Never worse than vector on both evals. | `lib/search.ts`, migrations 013/014 | retrieval "hybrid is at least as good"; corpus MRR 0.885→0.975 | done |
| V1-MULTIMODAL | review: "search returns only text" | I | `balance` ranks within each modality and interleaves (modality gap); `modalities` filter; workbench format chips, image thumbnails, playable audio/video segments at the matched time. | `lib/search.ts`, store page | manual DUNE check; web suite | done |
| V1-ACCOUNTS | review | I | Self-registration with email verification (provider policy: 12+ chars), first screen is the themed sign-in form (original product panel), RP-initiated sign-out, generated readable names, chunking hidden from customers (plan feature `custom_profiles`). | `infra/keycloak-theme`, `lib/web/session.ts`, `lib/names.ts` | web "self-registration…", "weak passwords…", "first screen…" | done |
| V1-MONITOR | §15.6 | I | Metrics operational: Prometheus scrapes API + inference, 9 alert rules (unit-tested), Alertmanager e-mail, Grafana dashboard. | `infra/observability/*` | `tests/observability.test.mjs` (live outage fires + resolves; e-mail delivered) | done |
| V1-RICH | review: "multimodal" | I | Profile `p4` (provider default): speech transcripts for audio and video soundtracks (faster-whisper base, pinned revision; VAD, no hallucinated text on silence/tones), OCR text for scanned PDF pages (RapidOCR) beside the page image, sharper video (720p, 280 soft tokens/frame, 20 s windows / 4 s overlap) plus soundtrack audio windows. Text is embedded by EmbeddingGemma 2 only. | `py/kbpy/prepare.py`, migration 015, inference `processing` | py `RichMedia` (4); eval 22 queries p1 0.955/0.932 → p4 1.000/0.970; DUNE cross-modal 15/16 → 16/16 | done |
| V1-UI | M6 review | I | Premium workbench ("Ink & Paper"): shell + workspace switcher, ⌘K palette, toasts, search evidence cards, drawer inspector, drag-and-drop import with steps, jobs timeline, connect stepper with copy, usage dashboard, split/export/profile UI, dark mode, reduced motion, responsive. | `app/**`, `lib/web/*`, `docs/ui-plan.md` | web suite 11/11 incl. axe on 7 views | done |

## Later release
| ID | § | Scope | Requirement / acceptance | Status |
|---|---|---|---|---|
| L-MERGE | 7.2 | L | `POST /v1/store-merges`: compatible profiles only (409 otherwise), dedup membership, no re-embedding; explicit `mode=rebuild`. Impl `app/v1/store-merges`, `py/kbpy/jobs.py`. Evidence: composition "store merges". | done |
| L-DERIVE | 7.3, 2.3 | L | `POST /v1/stores/{id}/derivations`: live view (follows parent metadata/versions/membership/deletion) and snapshot (pinned versions survive replacement, parent removal and GC; removed only by global source deletion). Evidence: composition "live views and snapshots". | done |
| L-MEDIAQ | 8.3 | L | Store search with query asset (image/audio/video) + optional text; expiry rechecked. Evidence: retrieval "media query". | done |
| L-REINDEX | 11.3, 15.5 | L | `reindex-jobs` builds a separate revision; `index-promotions` refuses incomplete builds, switches profile + query alias; previous revision stays `ready` (kept current) for rollback; aliases immutable. Evidence: composition "reindex, promotion and rollback". | done |
| L-HYBRID | 8.4 | L | Hybrid search, justified by evaluation (V1-HYBRID). | done |
| L-CONNECT | 16.2 | L | One concrete connector type `http_manifest` (host allowlist, no redirects) + scheduled sync (mirror semantics). Other connector types (SharePoint, Drive, S3…) are not implemented. Evidence: composition "connectors and scheduled sync". | done |
| L-WEB | 9.1, M6 | L | React/Next.js workbench on the shared /v1 API: stores, folder import (resume by re-selecting folder), job progress/retry/cancel, files/metadata/replace/delete, search with locations + media query, usage, keys, members, audit, composition, connection modal. OIDC code+PKCE; no permanent keys in browser. Evidence: `tests/web.test.mjs` (Chromium + axe WCAG 2.1 AA: no serious/critical). | done |
| L-DEPLOY | 16.2 | L | Self-hosted container option: `deploy/{api,py}.Dockerfile`, `deploy/compose.yml`, `deploy/README.md`. Evidence: `deploy/smoke.sh` (stack from images, CLI ingest+search via containers) passed locally on linux/arm64. Self-service provisioning portal not built. | done (minimal) |
| L-PGDIRECT | 9.6 | L | Direct PostgreSQL access (advanced). Not implemented (D42); the NDJSON embedding export (V1-EXPORT) covers bulk vector access. | deferred |

## External / process gates (not code)
| ID | § | Gate |
|---|---|---|
| X-G01..G10 | 18.2 | Publication gates: technical baseline, clean install, user task tests, recovery, permissions, examples, navigation, accessibility, owners, ISO assessment. |
| X-USER | 17.2 | User interviews / observation. |
| X-PILOT | 16.3 | Controlled customer pilot and cost measurement. |
| X-COMM | 12, 20.2 | Prices, plan terms, payment provider, hosting region, retention periods, support channel, legal. |
