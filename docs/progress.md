# Progress

**Current milestone:** V1 engineering complete and verified. External release gates are open (`docs/release-gates.md`).

## How to run (local)
```
scripts/bootstrap.sh                                   # infra (+ Keycloak, Mailpit), lockfile installs, migrations, pinned weights
(cd py && uv run --env-file ../.env python -m kbpy.inference)   # :8100, device auto (CUDA/MPS/CPU) + equivalence gate
(cd py && uv run --env-file ../.env python -m kbpy.worker)
npm run dev                                            # API + workbench :3000
docker compose up -d prometheus alertmanager grafana   # metrics, alerts (mail → Mailpit :8026), dashboards :3001
```
Dev accounts: `alice@example.com` / `dev-alice-password` (bob, carol, dave likewise).

## Evidence (latest run: see "Check commands")
- Real-model retrieval (20 labelled queries, `p3`): vector hit@5 0.950 / MRR 0.885 → hybrid **1.000 / 0.975**.
- Passage-level chunking (DUNE sheets, answer@1/@3): p1 0.2/0.9 → **p3 0.7/1.0**. Repo fixture: `tests/fixtures/structured` (answer@1 asserted p3 ≥ p1 and ≥ 0.6).
- Speed (fp32, same model): image 1.44 → 0.82 s, video 30 s 21.3 → 14.3 s on Apple GPU; DUNE 378-file reindex 24 s via vector reuse.
- Multimodal (p4 default): transcripts (audio + video soundtracks), OCR for scanned pages, sharper video. Eval 22 queries: p1 0.955/0.932 → p4 1.000/0.970 (hit@5/MRR); DUNE cross-modal top-1 16/16 (`examples/dune/eval_multimodal.py`).
- Observability: 9 alert rules unit-tested; live worker outage fires KBWorkersDown, mails ops, resolves.
- DUNE Bags (alice): 7 store shapes from one embedding pass; RAG self-test 18/18 with the real answer model.

## Check commands
```
npx tsc --noEmit
(cd py && uv run python -m unittest discover -s tests)
npm test                 # all integration suites (needs the stack above)
scripts/ci.sh            # clean machine
deploy/smoke.sh          # container deployment
python3 examples/dune/rag.py --selftest   # DUNE demo (needs ~/Downloads/DUNE Bags + Ollama)
```

## Known gaps
- Published to https://github.com/Himanshu8881212/OpenEmbed. The GitHub Actions workflow (`.github/workflows/ci.yml`) runs on push; its first remote run has not been verified yet (it needs about 8 GB RAM and downloads the pinned models).
- External gates: production IdP/SMTP/hosting/TLS, capacity (GPU) plan, security review, pilot, commercial/legal (`docs/release-gates.md`).
