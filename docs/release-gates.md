# Release gates and external prerequisites

Coding cannot complete these gates. The status below is factual as of 2026-10-12.

## Publication gates (guide §18.2)
| Gate | Evidence available from this build | Status |
|---|---|---|
| G01 Technical baseline | API v1 + CLI 0.1.0 match `docs/user-guide.md`, `docs/api.md`, `docs/cli.md` (generated) and `GET /v1/openapi.json` (contract test) | engineering evidence ready; needs a released version number |
| G02 Installation | `scripts/ci.sh` passed from a fresh copy on macOS arm64 (Apple M3); CI workflow for Ubuntu 24.04 written but **not run** (no remote CI authorised) | partial |
| G03 Core tasks by representative users | automated CLI, HTTP and browser journeys only | **open: needs user sessions** |
| G04 Recovery | resume, retry, cancel, crash/lease, restore drill automated | engineering evidence ready |
| G05 Permissions | role/scope/isolation suites (24 security tests + RLS with real roles) | engineering evidence ready |
| G06 Examples | generated Python/JavaScript/cURL + OpenAI SDK snippets executed against the service in tests | engineering evidence ready (re-run on the release deployment) |
| G07 Navigation | docs cross-links only | open |
| G08 Accessibility | redesigned workbench: axe WCAG 2.1 AA (no serious/critical) on 7 views, keyboard tabs/dialogs/palette, reduced-motion path; PDF/Word outputs not assessed | partial; needs manual screen-reader review |
| G09 Ownership | — | **open: assign named owners** |
| G10 Standard assessment | no conformity claim made | open |

## External prerequisites (not configured, no placeholders used)
| Item | Needed for | Current state |
|---|---|---|
| Production OIDC provider + client registrations (`kb-cli` device grant, `kb-web` code+PKCE) | real sign-in | dev Keycloak with test users only |
| Hosting, TLS, domain (`KB_PUBLIC_BASE_URL`), region | deployment | none, not authorised |
| GPU/CPU capacity plan | import throughput, video | CPU measurements only (operations.md) |
| Managed PostgreSQL with PITR, S3 with versioning | durability | local containers |
| Payment provider (`KB_PAYMENT_PROVIDER`), prices, plan terms, excess-use policy | billing | metering + hard caps only; no prices invented, no charging |
| Retention periods, backup removal schedule, data-processing terms, legal review | §14.3–14.4 | dev retention 0 s, default 7 days, not published |
| CLI package name and release channel | §3.1 | run as `node cli/kb.ts` |
| Support channel and response terms | T18 | none |
| User interviews, first-use observation, controlled pilot with cost measurement | §16.3, §17.2 | not done |
| Additional connector types (SharePoint, Google Drive, S3 …) | §16.2 | only `http_manifest` is implemented |
