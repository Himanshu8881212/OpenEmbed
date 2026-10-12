<!-- BEGIN:nextjs-agent-rules -->

## This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

## Project workflow (Multimodal Knowledge Store)

Source of truth: `docs/source/iso-guide.md` (extracted from the .docx, SHA-256 in `docs/decisions.md` D01).
State files, which you must reread after a restart or compaction before acting: `docs/requirements.md` (IDs, status, evidence), `docs/decisions.md`, `docs/plan.md`, `docs/progress.md`, `docs/review-findings.md`. Written status is not proof. Rerun the checks.

Layout: `app/v1/**` Next.js route handlers (the only business API), `lib/` shared server code, `lib/web` + `app/{page,stores,settings}` workbench, `cli/kb.ts` (zero-dependency CLI over HTTP), `py/kbpy` (inference service, procrastinate worker, preparation), `db/migrations` (plain SQL, applied in order by `npm run migrate`).

Rules:
- Every remote business operation gets a `/v1` route and an entry in `lib/openapi.ts`. `tests/contract.test.mjs` enforces this.
- Apps connect as `kb_api`/`kb_worker` (RLS). Always use `tx(workspaceId, …)` / `tx(ws)` so `app.workspace_id` is transaction-local.
- Embedding profiles and aliases are immutable. A model or preparation change means a new profile plus reindex/promotion.
- Never use fake inference outside explicitly labelled unit tests. Retrieval quality claims need `tests/fixtures/eval.json`.
- Workflow per slice: read requirement → implement smallest complete change → `npx tsc --noEmit`, `(cd py && uv run python -m unittest discover -s tests)`, `npm test` (needs `docker compose up -d`, inference on :8100, API on :3000) → review → update docs/ state files.
- Do not push, deploy, or buy infrastructure. Do not commit secrets (`.env` is local only).
