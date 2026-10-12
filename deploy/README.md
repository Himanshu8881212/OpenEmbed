# Self-hosted deployment (containers)

This is a minimal supported option. It runs the whole stack on one Docker host from images built here. It has been verified locally (see `docs/progress.md`), not on production infrastructure.

1. Create `deploy/prod.env` with every variable referenced in `deploy/compose.yml` (strong random passwords, `KB_INFERENCE_TOKEN`, your OIDC issuer, public base URL, plan JSON). Create `deploy/s3.json` with the S3 credentials (format: `infra/s3.json`), or point `KB_S3_*` at an external S3 service and remove the `s3` service.
2. Register two OIDC clients with your provider: a public `kb-cli` client with the device grant, and a public `kb-web` client with code + PKCE and redirect `${KB_PUBLIC_BASE_URL}/callback`.
3. `docker compose --env-file deploy/prod.env -f deploy/compose.yml up -d --build`. The `migrate` service applies migrations and creates the bucket. Inference downloads the pinned weights into the `models` volume on first start, or you can build with `--build-arg BAKE_MODEL=1`.
4. Put TLS termination (a reverse proxy) in front of `api:3000`. Do not expose `inference`, `postgres` or `s3`.
5. Check `curl https://…/readyz`.

GPU: the image uses CPU-only torch wheels (see `py/pyproject.toml`). For a GPU host, remove the `pytorch-cpu` sources, re-lock against a CUDA index, rebuild and set `KB_INFERENCE_DEVICE=cuda`. If you use `bfloat16`, create a matching profile first: dtype is part of profile identity.
