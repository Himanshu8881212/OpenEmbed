# Multimodal Knowledge Store

Upload company material (text, Word, PDF, images, audio, video), name a store, and connect applications through generated code. The service hosts **Google EmbeddingGemma 2** (`google/embeddinggemma-2@914f7f8`), so customer machines need no model weights or GPU.

Built from `Multimodal_Knowledge_Store_ISO26514_User_Guide.docx` (extracted to `docs/source/iso-guide.md`). Status and evidence: `docs/requirements.md`, `docs/progress.md`.

```
CLI (kb) ─┐                       ┌─ PostgreSQL + pgvector (catalogue, RLS, queue, vectors)
Web UI  ──┼─▶ Next.js /v1 API ────┼─ S3-compatible storage (originals, query assets)
Apps    ──┘   (one business API)  ├─ Python worker (procrastinate: verify → prepare → embed → publish)
                                  └─ Python inference (EmbeddingGemma 2, OpenAI-compatible text + multimodal extension)
```

## Quick start (local development)

Prerequisites: Docker (compose v2), Node ≥ 23.6, [uv](https://docs.astral.sh/uv/), ffmpeg. About 8 GB RAM. CPU is enough.

```bash
scripts/bootstrap.sh                     # infra, lockfile installs, migrations, bucket, pinned model weights
# three processes (separate terminals):
(cd py && uv run --env-file ../.env python -m kbpy.inference)   # :8100, loads the model
(cd py && uv run --env-file ../.env python -m kbpy.worker)
npm run dev                              # API + workbench on http://localhost:3000
curl localhost:3000/readyz               # {"ok":true,...}
```

First import and search with the CLI (T02):

```bash
node cli/kb.ts config set base-url http://localhost:3000
node cli/kb.ts auth login                # device flow; dev users alice@example.com (also bob/carol/dave), password dev-<name>-password; or "Create account" (verification mail in Mailpit at http://localhost:8026)
node cli/kb.ts workspaces create acme
node cli/kb.ts stores create manuals
node cli/kb.ts ingest manuals ./company-material --wait
node cli/kb.ts search manuals "Replace the pressure sensor" --limit 5
node cli/kb.ts keys create --store manuals --scope search
node cli/kb.ts connect manuals --language python > app.py
KNOWLEDGE_API_KEY=kb_… python app.py
```

Or open http://localhost:3000 and use the workbench (same API). Dev accounts: `alice@example.com` / `dev-alice-password` (also bob, carol, dave), or **Register** (verification mail in Mailpit at http://localhost:8026).

Observability (dev): Grafana http://localhost:3001, Prometheus http://localhost:9090, Alertmanager http://localhost:9093.

## Documentation

| Document | Content |
|---|---|
| `docs/user-guide.md` | Tasks T01–T20 with the released command and endpoint syntax |
| `docs/api.md` | API conventions, errors, limits, OpenAI-compatibility subset, multimodal extension. Machine-readable: `GET /v1/openapi.json` |
| `docs/cli.md` | CLI reference (`kb help`, `kb help <command>`) |
| `docs/operations.md` | Configuration, deployment, scaling, backup/restore, recovery, measured resource use |
| `docs/release-gates.md` | Publication gates and external prerequisites (not completed by code) |
| `docs/requirements.md`, `docs/decisions.md`, `docs/plan.md`, `docs/progress.md`, `docs/review-findings.md` | Engineering state |

## Checks

```bash
scripts/ci.sh            # clean machine: bootstrap + production build + all suites (what CI runs)
npx tsc --noEmit
(cd py && uv run python -m unittest discover -s tests)
npm test                 # integration suites: real Postgres/pgvector, S3, Keycloak, EmbeddingGemma 2, Chromium
```
