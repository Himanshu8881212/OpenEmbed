# Plan

| M | Scope | Pass condition |
|---|---|---|
| M0 | Runtime spike, compose infra, migrations, config, health | Real model embeds text/image/audio/video (done in spike); `docker compose up` + `npm run migrate` clean; `/readyz` green with DB, S3, inference. |
| M1 | Identity, workspaces, members, keys, RLS, profiles, jobs | `T:api` isolation suite passes using `kb_api`/`kb_worker` roles and pooled connections; key revocation immediate. |
| M2 | Vertical slice | `kb stores create` → `kb ingest --wait` (real bytes, resumable) → worker verifies, prepares, embeds (real model), publishes → `kb search` → `kb files inspect` → `kb connect` snippet runs (python + js) — all through HTTP. |
| M3 | Formats, revisions, retry/cancel, deletion, usage, audit | Format fixtures pass; crash/lease/duplicate tests; atomic replacement test; deletion/cleanup tests; quota 429. |
| M4 | Embeddings compatibility + retrieval | `openai` SDK (py+js) works on `/v1/embeddings` float+base64; error envelopes; exact vs approximate equality under filters; labelled eval threshold met. |
| M5 | Merge, derive, media query, reindex/promote/rollback, connector | Tests per L-* requirement. |
| M6 | Web workbench | Browser journey (create, import, progress, search, connect) on shared API; keyboard + accessible names. |
| M7 | Release prep | CI config, clean bootstrap script, backup/restore drill, docs updated, resource measurements. |
