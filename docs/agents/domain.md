# Domain Docs

How the engineering skills should consume this sub-system's domain documentation when
exploring the codebase.

## Layout — single-context

This sub-system is a single bounded context with its own root. There is deliberately no
`CONTEXT-MAP.md` anywhere in the estate: the five sub-systems (CTM · IAM · ESB/IG · NC ·
Translation) are separate one-way domains that each graduate to their own repository, so
each carries its own domain docs rather than sharing an estate-level map.

```
<sub-system>/
├── CLAUDE.md          ← standards, rules, gates
├── CONTEXT.md         ← glossary (created lazily; may not exist)
├── docs/
│   ├── agents/        ← this file, issue-tracker.md, triage-labels.md
│   └── adr/           ← decisions (created lazily; may not exist)
└── wayfinder/         ← the issue tracker
```

## Before exploring, read these

- **`CLAUDE.md`** at this sub-system's root — the standards and non-negotiable rules
  specific to this sub-system.
- **The platform-authoritative root `CLAUDE.md`** — CTM's, at `../CTM/CLAUDE.md` today;
  vendored into this repo on graduation. Its §2 NEVER/ALWAYS rules (N1–N12) still bind,
  and its **§15 glossary, §6 entities and §7 interfaces are the ubiquitous language for
  the whole estate** — lean on them, don't re-derive them.
- **`wayfinder/map.md`** — this sub-system's settled decision baseline;
  **`wayfinder/plan.md`** for the build sequence. A decision closed there is settled — do
  not re-litigate it.
- **`CONTEXT.md`** at this sub-system's root, and **`docs/adr/`** — if they exist.

If any of these don't exist, **proceed silently**. Don't flag their absence; don't
suggest creating them upfront. The `/domain-modeling` skill (reached via
`/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms
or decisions actually get resolved.

## Use the glossary's vocabulary

When your output names a domain concept (an issue title, a refactor proposal, a
hypothesis, a test name), use the term as defined in the platform root `CLAUDE.md` §15 —
`tenant`, `LOV`, `seam`, `application dimension`, `membership`, `control plane`. Don't
drift to synonyms the glossary explicitly avoids: a tenant is a **client/customer**,
never named as an owner; applications are **IRM / future application products**; external
capacity is a **"cloud provider."**

If the concept you need isn't in the glossary yet, that's a signal — either you're
inventing language the project doesn't use (reconsider) or there's a real gap (note it
for `/domain-modeling`).

## Flag conflicts

If your output contradicts an existing ADR, a closed wayfinder ticket, or a ratified
decision, surface it explicitly rather than silently overriding:

> _Contradicts a closed decision in `wayfinder/map.md` — but worth reopening because…_

Ratified decisions win (platform root `CLAUDE.md` §14, PLAN-STALE).
