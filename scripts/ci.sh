#!/usr/bin/env bash
# Full release gate on a clean machine: bootstrap, production build, real inference, all checks.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .ci
scripts/bootstrap.sh
npx playwright install ${PLAYWRIGHT_WITH_DEPS:+--with-deps} chromium
set -a; . ./.env; set +a
cleanup() { kill ${PIDS:-} 2>/dev/null || true; }
trap cleanup EXIT
(cd py && exec .venv/bin/python -m kbpy.inference) > .ci/inference.log 2>&1 & PIDS="$!"
npx tsc --noEmit
(cd py && uv run python -m unittest discover -s tests)
npx next build > .ci/build.log
npx next start -p 3000 > .ci/api.log 2>&1 & PIDS="$PIDS $!"
for i in $(seq 1 120); do curl -sf http://localhost:3000/readyz >/dev/null && break; sleep 2; done
curl -sf http://localhost:3000/readyz
npm test 2>&1 | tee .ci/test.log
echo "CI passed"
