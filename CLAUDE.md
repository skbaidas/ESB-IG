# CLAUDE.md — ESB/IG Sub-system

> Project context for Claude Code. Auto-loaded each session.
> **Platform rules live in `..\CTM\CLAUDE.md` and still bind** (N1–N12, LOV rule, DoD,
> evidence rules). This file is a pointer stub — it adds no ESB/IG-specific rule that the
> decision baseline has not already settled.
> Decision baseline: `wayfinder\map.md` · emerging plan: `wayfinder\plan.md`.

---

## 1. What this is

**ESB/IG = the L4 Enterprise Service Bus / Integration Gateway sub-system.** It is the
**single mediation point for all external integration**: gateway + broker planes, mapping
flows, REST/SOAP/EDI handlers, the event envelope transport and the per-channel DLQ. It
carries CTM→IAM lifecycle events.

One of the five Phase-1 sub-systems (CTM · IAM · **ESB/IG** · NC · Translation). It owns
its own data and never imports from, calls into, or reads the database of a consumer
application (platform N3, one-way dependency).

---

## 2. Authoritative documents — read in this order

1. **Platform root `CLAUDE.md`** — `..\CTM\CLAUDE.md`. Estate-wide NEVER/ALWAYS rules (§2),
   architecture (§3), glossary (§15), entities (§6), interfaces (§7), standards (§9),
   build gates (§12). **Authoritative.**
2. **`wayfinder\ESB-IG-developed-design.md`** — the developed design + integration chart.
   Read before building.
3. **`wayfinder\map.md`** — the settled decision baseline (9 tickets, all closed 2026-07-24).
4. **`wayfinder\plan.md`** — the build sequence.

A decision closed in `wayfinder\` is **settled** — do not re-litigate it (platform root
`CLAUDE.md` §14, PLAN-STALE: ratified decisions win).

---

## 3. Code layout & the boundary gate

Source lives under `backend/`. Every immediate child is a **package** — a *deep module* whose
interface is its **root modules**; anything in a subfolder is implementation and may not be
imported from outside. Read [`backend/README.md`](./backend/README.md) before adding or
importing a package.

**The source layout is not the import name**, and they are stated separately because
conflating them was a real defect: distribution `esb-ig` · source directory `backend/esb_ig/`
· **distributed import `esb_ig`** (top-level). A consumer writes `import esb_ig`, never
`import backend.esb_ig` — CTM's own `backend/__init__.py` makes `backend` a *regular* package,
so its `__path__` is fixed to CTM's directory and an installed distribution providing
`backend/esb_ig/` is never searched for. `pyproject.toml` carries the measured `ImportError`;
CI **re-measures it every run** alongside a clean-venv install-and-import proof. The tree
keeps `backend/`, so `PACKAGES_ROOT = "backend"` in the boundary gate stays correct — it
describes the tree, which is what that gate reads.

**The move carries an import rewrite**: intra-package imports must be **relative**
(`from .envelope import Envelope`), because an absolute `from backend.esb_ig.x import y`
cannot resolve once the directory is `site-packages/esb_ig/`.

| Purpose | Command | Status |
|---|---|---|
| **Boundary gate** (N3 · deep modules · no cycles) | `python scripts/check_boundary.py` | **Live — blocking.** `--json` prints to **stdout**; redirect it for evidence |
| **Catalogue gate** (envelope · axis rule) | `python scripts/check_catalogue.py` | **Live — blocking.** `--json` **writes** `evidence/gate-catalogue.json`. Exit 2 is a control failure, not a finding |
| **Distributed import name** | *(CI only — see below)* | **Live — blocking.** Installs this project into a **clean virtualenv**, runs from a directory that is **not** the repo root with `PYTHONPATH` cleared, and requires `esb_ig.__file__` to resolve inside site-packages. All three conditions are load-bearing: drop any one and the source tree answers the import and the lane passes for the wrong reason. Mutation-checked in both directions. Artefact `gate-import-name.json` |
| **Lint** | `python -m ruff check backend scripts` | **Live — blocking.** Rules are CTM's, copied into `pyproject.toml` |
| **Format** | `python -m ruff format --check backend scripts` | **Live — blocking.** Drop `--check` to apply. `ruff` is pinned **exactly** in the `dev` extra: a formatter's output is its verdict |
| **Tests** | `python -m pytest -q` | **BLOCKING since `W2-T10` step (a), 2026-09-05.** The lane was self-retiring and it retired itself: the suite arrived, pytest no longer exits 5, and nobody had to switch anything on. **86 tests — 73 pass locally and 13 are `needs_broker`, which only CI can run**, so a local green is a strictly weaker claim than this lane's. **Read the SKIP count, not the exit code**: a `needs_broker` skip in CI means the broker or the `pika` driver is missing, never that the semantics hold |
| **CI** | `.github/workflows/ci.yml` | **Live — it runs.** Every branch, every path, no filter (CTM §14 `TRIGGER-FILTERED`: a filtered push leaves nothing to read, which is worse than a skip). A **RabbitMQ 4 service container pinned by digest** is provisioned ahead of the transport suite; the lane probes its **port** and speaks no AMQP |
| Migrations | *(unset)* | ESB/IG owns its own data and has no lineage yet |

The boundary gate runs clean against an empty tree and starts biting on the first package.
Run everything from the repo root (`D:\PMO\Phase 1\ESB-IG`). Never guess a runner command
that is not listed here.

**Branch protection is unavailable** on this repository as on CTM's (platform `CLAUDE.md`
§12, GOV-GATE — the API returns 403 on this plan), so nothing can technically block a merge
and **a red build is the only enforcement signal there is**.

---

## Agent skills

### Issue tracker

Local markdown under `wayfinder/` — `wayfinder/tickets/` is the closed decision baseline;
new work gets `wayfinder/<effort>/{spec.md,tickets/}`. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical labels, unchanged, appended to each ticket's front-matter `labels:`
array. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — `CONTEXT.md` and `docs/adr/` belong at this sub-system's root *when they
exist* (created lazily by `/domain-modeling`; neither exists yet). The estate-wide glossary
is the platform root `CLAUDE.md` §15/§6/§7. See `docs/agents/domain.md`.
