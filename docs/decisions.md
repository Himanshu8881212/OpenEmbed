# Decisions

Format: ID — decision. Reason. Tradeoff / upgrade path.

## Source
- D01 — Authoritative source: `Multimodal_Knowledge_Store_ISO26514_User_Guide.docx` (only copy found), v1.0, 6 Oct 2026, SHA-256 `d13feca66cd1ff44817833cb382466716b5cd43e46d21a193d78fc72bb6c716e`. Extracted with pandoc 3.9 (pypandoc_binary) to `docs/source/iso-guide.md` + `docs/source/media/image1.png`. Completeness check: 1216/1218 non-empty XML paragraphs present; the 2 missing are the cover title text box ("Multimodal Knowledge Store Platform", "User and API guide") and are noted at the top of the extract. 30 tables and 7 hyperlinks were checked and are present. Header and footer text is also noted.
- D02 — Guide placeholders (`api.example.com`, `store_abc123`, `eg2-profile_abc123-query`, prices, CLI package name) are not used as config. Real IDs are UUIDs. Base URL comes from `KB_PUBLIC_BASE_URL`.

## Model (verified 2026-10-12)
- D10 — Model: `google/embeddinggemma-2`, HF revision `914f7f89142e33e77833254d9c9b90c3cef7303b`, Apache-2.0, ungated. Card: https://ai.google.dev/gemma/docs/embeddinggemma/model_card_2. Multimodal guide: https://ai.google.dev/gemma/docs/embeddinggemma/multimodal-embeddinggemma-with-sentence-transformers. It has 740M params, a 768-d native output (MRL 512/256/128), mean pooling plus Normalize, and an 8192-token context shared by all modalities. Image costs 280 tok, video 140 tok/frame at 1 fps, audio 25 tok/s at 16 kHz mono. Supported precision is fp32 or bf16; fp16 is forbidden.
- D11 — Runtime pins: torch 2.14.1, torchvision 0.29.1, torchcodec 0.17.0, transformers 5.19.0, sentence-transformers 6.1.0 (the card requires >=6.1.0), Python 3.12. torchvision is required but undeclared by the card (the processor import fails without it).
- D12 — Default precision is CPU float32. It is deterministic, recommended for CPUs, and verified. MPS bf16 also works (cos 1.003 vs fp32, norm 1.0025). Precision is part of profile identity, so the inference service refuses a profile whose dtype differs from its own. The service re-normalizes in fp32 and rejects non-finite output.
- D13 — Prompts follow the card. Query: `task: search result | query: `. Document text: `title: {filename} | text: {content}`. Media gets no prefix, per the card.
- D14 — Only 768-d profiles exist initially (`vector(768)`). MRL truncation is not offered; add a new profile plus column when needed.
- D15 — Not substituted: original EmbeddingGemma and Gemini Embedding are never used.

## Architecture
- D20 — Fewest services. Infra (docker compose): pgvector/pgvector:0.8.1-pg18, SeaweedFS 4.26 (S3 API, Apache-2.0, already local), Keycloak 26.4 (OIDC with device grant, dev IdP only). App processes: Next.js API (`npm run dev`), Python inference (`kbpy.inference`), Python worker (`kbpy.worker`).
- D21 — Queue: procrastinate 3.10 (maintained, PostgreSQL-backed). It provides retries, worker heartbeats, and stalled-job recovery, and is durable in the same DB. The API enqueues inside its business transaction via procrastinate's SQL function. That makes the job row and queue message atomic, with no outbox needed. Tradeoff: we depend on procrastinate's SQL function signature, pinned by version and covered by integration tests.
- D22 — Identity: generic OIDC, Keycloak in dev. `/v1/auth/device-sessions` and `/v1/auth/token` proxy the IdP device grant (RFC 8628). The API verifies JWTs via JWKS (`jose`). We built no custom crypto. API keys are 256-bit random tokens stored as SHA-256 hashes, the standard practice for high-entropy tokens.
- D23 — Workspace isolation is enforced by the API (role/scope checks) plus PostgreSQL RLS. The `kb_api` and `kb_worker` login roles are non-owners. Each transaction sets `app.workspace_id` with `set_config(...,true)` (transaction-local, so it is safe with pooling). Cross-workspace lookups (key hash → workspace, identity → memberships) go through narrow SECURITY DEFINER functions.
- D24 — Concealment policy: a resource in another workspace, or one that does not exist, returns 404 RESOURCE_NOT_FOUND. A visible resource without permission returns 403.
- D25 — Uploads: S3 multipart, one multipart upload per manifest file, part size 8 MiB. The API records parts in `upload_parts`, so resume = GET the session and PUT the missing parts. An optional per-part `x-part-sha256` header is verified at the API. The worker verifies the whole-file SHA-256 before preparation, then server-side copies the object into content-addressed `ws/{ws}/blobs/{sha256}` (per-workspace dedup).
- D26 — Atomic publication: segments for a new file version are written first but stay invisible. Search joins `files.current_version_id`. One transaction flips `current_version_id`, so search sees the old or new complete version, never a mix. Segment IDs are uuid5(version, profile, ordinal), so retries and duplicate delivery hit ON CONFLICT DO NOTHING.
- D27 — Segments belong to (file_version, profile) because preparation is part of the profile. A store's active index revision points at one profile. Reindex builds segments for the new profile. Promotion and rollback swap the pointer and keep the old vectors.
- D28 — Filters: JSON object equality on file metadata (`metadata @> filter`), plus optional `path_prefix` and `media_types`. Search uses HNSW cosine with `hnsw.iterative_scan=relaxed_order` and verifies results against an exact scan.
- D29 — Migrations are plain SQL files plus a ~30-line runner (`scripts/migrate.mjs`) with a `schema_migrations` table. Procrastinate schema is applied by its own CLI at the pinned version.
- D30 — CLI: `cli/kb.ts`, run directly by Node ≥23 type stripping, using only `node:util.parseArgs` and global fetch. It has zero dependencies. Human tokens go in `~/.config/kb/credentials.json` (0600). Scripts use the `KB_API_KEY` env var.
- D31 — Usage: an append-only `usage_events` table with a unique idempotency key, so replays never double count. Storage is computed from blobs (bytes counted once per workspace). Hard caps come from `workspaces.plan` limits and return 429 QUOTA_EXCEEDED. Prices and payments are not implemented (no provider configured).

## Retrieval and composition
- D40 — Retrieval evaluation metric is predeclared: hit@5 ≥ 0.9 on `tests/fixtures/eval.json` (15 labelled queries over 18 mixed-format files, incl. exact identifiers, image and spoken audio). Distinct topics mean a working model should find nearly all; 0.9 allows one paraphrase miss. MRR is reported. Mocks are never used for this.
- D41 — Hybrid search is deferred: the evaluation, including exact-identifier queries, shows no dense-retrieval misses (hit@5 = 1.0). Revisit when customer evaluations show identifier misses.
- D42 — Direct PostgreSQL access (guide 9.6, "advanced later") is not implemented. It needs per-customer roles and views enforcing membership, and it widens the attack surface. The HTTP search and query-embedding endpoints cover the use case.
- D43 — Views are live and parents must be material stores or snapshots (no view-of-view). Snapshots pin versions at creation, and GC never removes pinned versions. Only global source deletion (`scope=workspace`) removes a source from snapshots. Parent store deletion empties dependent views but leaves snapshots intact.
- D44 — Promotion keeps the previous revision `ready`, and new imports keep embedding for it, so rollback is an instant pointer swap. Promoting an incomplete revision returns 409.
- D45 — The connector is `http_manifest` only. The server fetches only from hosts in `KB_CONNECTOR_ALLOWED_HOSTS` and does not follow redirects (prevents SSRF). Sync mirrors the manifest: changed files become new versions through the normal verified ingest path, and removed entries leave the store (membership only). If a sync crashes mid-plan, the next scheduled run completes the mirror.
- D46 — The second profile `eg2-914f7f8-fp32-p2` (same pinned model, 800-char passages) exists to exercise reindex/promotion with a genuinely different, validated preparation.

## Release
- D47 — The deployment option is one Docker host running images (`deploy/compose.yml`) with an external OIDC provider. Managed PostgreSQL/S3 can replace the bundled services through env vars. No Kubernetes charts: nobody asked for them, and they can be added when a customer needs them.
- D48 — CI is GitHub Actions calling `scripts/ci.sh`, the same script verified locally on a clean copy. It was not run remotely, because pushing was not authorised.
- D49 — Backups never restore the `ledger/` prefix. The restore procedure replays it (F11).

## V1
- D50 — Rate limiting uses fixed one-minute windows in PostgreSQL (`kb_rate_hit`), keyed per principal and workspace. Plan `requests_per_minute` overrides `KB_RATE_LIMIT_PER_MINUTE` (default 600). This costs one extra round trip per request. ponytail: move counters to Redis if request volume makes this hot.
- D51 — Custom profiles copy the base profile's model, revision, precision and instructions, and change only segmentation. That way the hosted model can always serve them, and vector spaces stay within the same model. Bounds keep every segment inside the 8,192-token budget.
- D52 — Nested views are a DAG by construction, since a definition only references existing stores and definitions are immutable. Depth is limited to 3. Membership is a PL/pgSQL function: SQL-function inlining recursed at plan time (F15).
- D53 — Export is NDJSON streamed in keyset batches of 500. Each batch rechecks access, so revoking a key stops an export mid-stream.
- D54 — The CSP allows `'unsafe-inline'` scripts because of the Next.js bootstrap; there are no third-party scripts. Nonce-based CSP is the upgrade path.
- D55 — The UI direction is "Ink & Paper" (`docs/ui-plan.md`): paper canvas, ink sidebar, vermilion accent, with Fraunces / Instrument Sans / JetBrains Mono self-hosted via `next/font`. Evidence cards are the signature element.

- D56 — DOCX uses python-docx 1.2.0 (MIT, maintained). It extracts body paragraphs and tables in document order. Table rows become `a | b`, and merged cells are deduplicated. Each segment records its nearest preceding heading as `section`. Headers/footers, comments and text boxes are skipped (documented). Legacy `.doc` (binary) is not supported.

## Speed, chunking, retrieval (2026-10-12)
- D57 — The device is not part of profile identity, but the inference service proves it at start-up. Probe vectors (text and image) must match the committed CPU-fp32 reference with cosine ≥ 0.9999, or the service exits. On Apple GPU (MPS) every modality measured cosine 1.000000. fp16 stays forbidden.
- D58 — Batching media on CPU was slower, and 8 CPU threads were no faster than 4. GPU (MPS/CUDA) is the throughput lever; video is the costliest modality (14 s per 30 s segment on MPS).
- D59 — `p3` is the default for new stores (`KB_DEFAULT_PROFILE`). Existing stores keep their profile until reindexed and promoted. Preparation changes are always new profiles (immutability).
- D60 — Cross-profile reuse requires the same model, revision and dtype plus identical preparation for that media type. PDFs are excluded because they mix text and page images.
- D61 — Hybrid keyword matching uses only selective identifier tokens. Any-term keyword matching measurably hurt (DUNE answer@1 0.7 → 0.3) by promoting chunks that share common words. RRF k = 60.
- D62 — Balanced multimodal ranking exists because cross-modal cosine sits lower than text-to-text. Raw scores are kept, and ordering is rank-within-modality.
- D63 — Workers all heartbeat every 2 s, with a lease of at least 6 s. A worker that loses its registration re-registers (F19).
- D64 — Accounts: email is the username. Self-registration requires email verification (Mailpit in dev) and a 12-character password policy. Seeded dev users have fixed IDs, and Keycloak data persists, so identities stay stable.
- D65 — Observability: Prometheus + Alertmanager + Grafana in compose. Alerts go by email, and every rule names an action.

- D66 — Transcripts and OCR are preparation, not embedding. ASR is faster-whisper 1.2.1 (MIT), model `Systran/faster-whisper-base` pinned to revision `ebe41f70…`, run on CPU int8. Audio is decoded by ffmpeg, which avoids PyAV. Segments with no-speech probability ≥ 0.6 or no voice activity are dropped. The base model is multilingual and modest: it misheard "forklift" as "four-clift". Larger models (small.en, medium.en) are a profile change.
- D67 — OCR is RapidOCR 1.4.4 (Apache-2.0, bundled ONNX models), rendered at 200 dpi, lines with confidence ≥ 0.6 in reading order. It applies to scanned PDF pages only, because photos and renders rarely carry text, and keeping image preparation unchanged preserves cross-profile reuse.
- D68 — Video detail is set by `max_soft_tokens` per frame (passed to the processor as `processing_kwargs`). 280 tokens × 20 frames (20 s at 1 fps) plus overhead stays under 8,192. Query-time media uses the same settings as the index.

## Blockers / external
- E01 — git has no author identity configured, so no commits are made. Work stays uncommitted in the working tree.
