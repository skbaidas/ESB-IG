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

| Purpose | Command | Status |
|---|---|---|
| **Boundary gate** (N3 · deep modules · no cycles) | `python scripts/check_boundary.py` | **Live — blocking.** `--json` for committed evidence |
| Tests · lint · migrations | *(unset)* | Phase A, with `pyproject.toml` |

The gate runs clean against an empty tree and starts biting on the first package. Run it from
the repo root (`D:\PMO\Phase 1\ESB-IG`). Never guess a runner command that is not listed here.

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
