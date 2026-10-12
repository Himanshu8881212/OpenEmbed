# Workbench UI plan ("Ink & Paper")

Critique (2026-10-12 screenshots): no product shell, workspace context buried; search (core value) not the hero and results print internals; flat hierarchy; inline file inspector; no drag-and-drop import or per-file progress; job IDs as buttons; connect dialog without copy/steps; no toasts/skeletons; tabs not in URL; no command palette; tables overflow on mobile; no dark mode or motion.

Direction: archival/editorial with instrument precision. Paper canvas, ink sidebar, single vermilion accent, teal success. Fraunces (display) + Instrument Sans (UI) + JetBrains Mono (ids/code). Signature: evidence cards with citation chips and relevance meters.

| Phase | Scope | Done when |
|---|---|---|
| P1 | tokens, fonts, shell (sidebar, workspace switcher), primitives, toasts, ⌘K palette | all pages render in the shell |
| P2 | stores overview, store header + URL tabs, search hero/evidence cards, import dropzone, jobs timeline | core journey looks finished |
| P3 | file drawer, connect stepper with copy, usage dashboard, keys, members, composition | every feature restyled |
| P4 | sign-in split screen, responsive, dark mode, motion, axe + keyboard + updated Playwright tests | `tests/web.test.mjs` green, no serious/critical axe issues |

Constraints: same /v1 API, no permanent keys in the browser, keyboard + screen-reader parity, `prefers-reduced-motion` respected.
