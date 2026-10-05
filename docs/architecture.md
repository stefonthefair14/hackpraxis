# Architecture

HackPraxis is a small FastAPI app serving a single-page GUI and a thin JSON API.
The design keeps three concerns separate: **scope** (are we allowed?),
**module** (what command expresses this technique?), and **runner** (execute it
safely). The browser never decides anything that matters — it only renders.

```
browser (static/)                 server (hackpraxis/)
  │                                  │
  │  GET /api/modules  ───────────▶  modules.catalog()        META for each technique
  │  POST /api/plan    ───────────▶  modules.<m>.build(params) → Plan (not run)
  │  POST /api/run     ───────────▶  build(params) → Plan
  │                                     └─ runner.run_steps()
  │                                          └─ for each Step:
  │                                               scope.guard(target)   ← HARD GATE
  │                                               subprocess.run(argv)
  ◀── results / command text / flag explanations ──┘
```

## The pieces

### `scope.py` — the safety core
`Scope.decision(target)` returns `(allowed, reason)` by matching the target's
**host** against in/out-of-scope lists (out always wins). `Project` wraps a
scope plus metadata and persists to `projects/<slug>.json`. This module has no
dependency on the web layer and is unit-testable on its own.

### `modules/` — one file per technique
Each module exposes:

- `META` — a dict describing the technique and the form fields/engines the UI
  should render.
- `build(params) -> Plan` — pure function that turns user input into a `Plan`
  of `Step`s. It does **not** run anything, which is what lets `/api/plan`
  preview the exact command safely.

Register a new module in `modules/__init__.py` and it appears in the sidebar.
Nothing else needs to change — the app is module-agnostic.

### `runner.py` — construction + execution
`Step` carries the `argv`, the `target` (for scope), per-token `explain`
metadata, and a `parse` hint. `run_step` enforces scope, checks the binary is on
PATH, runs with a timeout, and returns a structured result. `run_steps` fans a
large matrix of short probes across a small thread pool so a 100-request bypass
run returns in seconds.

### `app.py` — transport only
Validates input, calls `build`, serialises the `Plan`, and (for `/api/run`)
requires a project so scope is always available. It adds no logic of its own.

## Why this shape
- **Auditable safety.** There is exactly one place a request can be sent, and it
  calls `scope.guard` on the line above `subprocess.run`. A reviewer can verify
  the guarantee in one screen.
- **Teachable by construction.** Because `build` is separate from execution, the
  same `Plan` powers both the "here's the command and what it means" preview and
  the actual run.
- **Cheap to extend.** New techniques are additive — a single file — so the repo
  grows without the core changing.
