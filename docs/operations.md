# Operations

## Components
| Process | Command | State | Scale |
|---|---|---|---|
| API + workbench (Next.js) | `npx next build && npx next start` | stateless | horizontally; `KB_DB_POOL_MAX` per instance |
| Inference (EmbeddingGemma 2) | `uv run python -m kbpy.inference` | model in memory (~2 GiB RSS fp32) | one forward pass at a time per process. Run more processes. Separate query capacity (`KB_INFERENCE_URL`, used by the API) from import capacity (`KB_INFERENCE_IMPORT_URL`, used by workers). |
| Worker (procrastinate) | `uv run python -m kbpy.worker` | stateless | more processes / `KB_WORKER_CONCURRENCY`; `KB_WORKER_QUEUES=ingest,maintenance` |
| PostgreSQL 18 + pgvector 0.8.1 | managed or `docker compose` | catalogue, vectors, queue | PITR backups |
| S3-compatible storage | SeaweedFS in dev | originals, query assets, `ledger/` | versioning/replication |
| OIDC provider | Keycloak in dev (`infra/keycloak-realm.json`, dev users only) | identities | any OIDC provider with device grant + code/PKCE |

Database roles: migrations run as the owner (`KB_MIGRATE_DATABASE_URL`). The API connects as `kb_api` and workers as `kb_worker`. Both are non-owner and `NOBYPASSRLS`, so row security applies (create them as in `infra/pg-init.sh`). Use transaction pooling only (session state is transaction-local).

## Configuration
See `.env.example`. Config is validated at first use, and the API reports all invalid variables (`/readyz` → `config`). Production values to set (no defaults are secrets):

- `KB_DATABASE_URL`, `KB_WORKER_DATABASE_URL`, `KB_MIGRATE_DATABASE_URL`
- `KB_S3_*`
- `KB_OIDC_ISSUER`, `KB_OIDC_CLI_CLIENT_ID`, `KB_OIDC_ALLOWED_CLIENTS`, `NEXT_PUBLIC_KB_OIDC_*`
- `KB_INFERENCE_URL`, `KB_INFERENCE_IMPORT_URL`, `KB_INFERENCE_TOKEN` (shared secret between API/worker and inference; inference must not be publicly reachable)
- `KB_INFERENCE_DEVICE` (`cpu` | `cuda` | `mps`), `KB_INFERENCE_DTYPE` (`float32` | `bfloat16`; must match the profile; float16 is refused)
- `KB_PUBLIC_BASE_URL`
- `KB_DEFAULT_PLAN` (single-quoted JSON)
- `KB_RETENTION_SECONDS` (default 7 days; dev 0)
- `KB_LEASE_SECONDS` (worker lease, default 30 s)
- `KB_CONNECTOR_ALLOWED_HOSTS`
- `KB_PAYMENT_PROVIDER` (unset = none)

## Security and observability
- Response headers on every route: CSP (`frame-ancestors 'none'`, no third-party origins), `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: no-referrer`, HSTS, and a Permissions-Policy.
- Rate limits: `KB_RATE_LIMIT_PER_MINUTE` (default 600 per principal and workspace). Per plan: `limits.requests_per_minute`.
- Per-workspace queue cap: `KB_MAX_QUEUED_ITEMS` (default 20,000).
- `GET /metrics` with `Authorization: Bearer $KB_METRICS_TOKEN` exposes:
  - HTTP request counters and latency histograms, labelled by route pattern;
  - queue depth by queue and status, alive workers, jobs and items by state, segments, blob bytes, stores by kind.
  - Suggested alerts: `kb_workers_alive == 0`, rising `kb_queue_tasks{status="todo"}`, 5xx rate, p95 latency.
- Logs are one JSON line per request (`request_id`, method, route pattern, status, ms). They contain no bodies or content (tested). `KB_ACCESS_LOG=0` disables them.

## Health
- `GET /healthz`: liveness.
- `GET /readyz`: config, database (migrations present), object storage bucket, inference `/readyz`. Returns 503 with the failing check.
- Inference `GET /readyz`: model, revision, dtype, device.

## Reliability behaviour (tested)
- Jobs and queue messages commit in one transaction. Closing the CLI never loses committed work.
- A worker silent for `KB_LEASE_SECONDS` loses its tasks, which are retried by any worker (`recover_stalled` runs every 10 s). Segment IDs are deterministic and usage events have unique keys, so a re-run creates no duplicates or double charges.
- Transient failures (inference down) retry with exponential backoff up to `KB_MAX_ATTEMPTS` (default 5). The item then fails as retryable, and the user runs `jobs retry`.
- GC every 5 min: expires upload sessions (aborts multipart uploads), drops expired query assets, and removes deleted sources, superseded versions (except those pinned by snapshots) and unreferenced blobs once older than retention.

## Backup, restore and recovery (drill: `tests/zz-backup.test.mjs`)
1. Backup: `scripts/backup.sh [DIR]` runs `pg_dump -Fc` plus an export of all objects except `ledger/`, and records `TIMESTAMP`. Production: PostgreSQL PITR and bucket versioning. **Never restore the `ledger/` prefix.**
2. Restore: stop workers, then run `scripts/restore.sh DIR`. This runs `pg_restore --clean --single-transaction`, imports the objects, then `node scripts/reapply-deletions.mjs TIMESTAMP`.
3. The ledger replay re-applies every source/store deletion, key revocation and member removal recorded after the backup, so a restored service never exposes deleted material or revived credentials (the drill demonstrates that a naive restore would). Data created after the backup is lost (RPO = backup interval).
4. Start workers. Queued jobs resume, and GC removes the physically restored bytes of deleted sources.
- Backups keep deleted content until they expire. Publish that schedule (release gate X-COMM).

## Inference device and speed (2026-10-12, Apple M3, same EmbeddingGemma 2, fp32)
| | Image | 16 passages | Video 30 s | Audio 30 s |
|---|---|---|---|---|
| CPU, 4 threads | 1.44 s | 1.93 s | 21.3 s | 1.22 s |
| CPU, 8 threads | 1.57 s | 2.07 s | 22.1 s | 1.39 s |
| Apple GPU (MPS) | 0.82 s | 1.51 s | 14.3 s | 1.95 s |

- `KB_INFERENCE_DEVICE=auto` picks CUDA, then MPS, then CPU. At start-up the **equivalence gate** compares probe vectors with `py/kbpy/probe_reference.json`; if cosine < 0.9999 the service exits (see `/readyz` → `equivalence`). CPU vs MPS measured 1.000000 for every modality.
- Reindexing reuses identical media vectors across profiles. The DUNE store (378 files, 372 images) reindexed to `p3` in 24 s.
- Video dominates import time. Plan GPU capacity for video-heavy customers.

## Alerts (Prometheus → Alertmanager → email)
Run `docker compose up -d prometheus alertmanager grafana`. URLs: Prometheus http://localhost:9090, Alertmanager http://localhost:9093, Grafana http://localhost:3001 (dashboard "Knowledge Store: operations"). Dev alert mails land in Mailpit at http://localhost:8026.

| Alert | Fires when | First action |
|---|---|---|
| KBApiDown / KBInferenceDown | target unreachable 1 min | restart the process; check `/readyz` |
| KBWorkersDown | no worker heartbeat 1 min | start `kbpy.worker` |
| KBQueueStalled | tasks queued, nothing finished in 15 min | check workers / inference saturation |
| KBQueueBacklog | > 500 queued tasks for 10 min | add worker/inference capacity |
| KBInferenceSaturated | inference busy > 90% with waiting requests | more inference processes or GPU |
| KBJobItemFailures | > 10 failed items in 15 min | read item error codes, retry |
| KBHigh5xxRate | > 5% 5xx for 5 min | logs by request_id |
| KBSlowSearch | search p95 > 2 s for 10 min | inference/database load |

Rules are unit-tested with `promtool` (`infra/observability/rules.test.yml`). Production: replace `metrics-token.dev`, point Alertmanager at real SMTP, and add on-call routing.

## Measured resource use (Apple M3, 8 cores, 24 GB RAM, CPU float32, 2026-10-12; `node scripts/measure.mjs`)
| Operation | Median latency | Tokens |
|---|---|---|
| Query text (short) | 35 ms | 13 |
| Document batch 16 × 1,600 chars | 2.0 s (~2,600 tokens/s) | 5,328 |
| Image 256×256 | 1.4 s | 260 |
| Audio 30 s | 1.05 s | 754 |
| Video 30 s at 1 fps (30 frames) | 20.8 s (slower than real time) | 3,962 |
| End-to-end store search (API, dev mode, n=5) | p50 63 ms | |

- Memory: inference ~2.0 GiB RSS (all encoders, fp32), Next.js ~140 MiB. Database 16 MB for ~450 segments (3 KiB vector + text per segment).
- MPS bfloat16 works on Apple silicon (verified), but it is a different precision. Run it as a separate profile (`dtype` is part of profile identity).
- Video-heavy workloads need a GPU host. CPU throughput is the main cost driver for import capacity. A customer pilot must measure it on the target hardware (release gate X-PILOT).

## Deployment option
`deploy/` contains container images for the API, worker and inference, plus `deploy/compose.yml`, which runs the full stack from images (self-hosted or enterprise). See `deploy/README.md`. No production deployment has been made.
