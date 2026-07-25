# Issue tracker: Local markdown (wayfinder)

Issues and specs (you may know a spec as a PRD) for this sub-system live as markdown
files under `wayfinder/`. There is no git remote here, so there is no GitHub/GitLab
issue tracker — `wayfinder/` *is* the tracker.

## Layout

- **Tracker root**: `wayfinder/`
- **Decision baseline — closed, do not add to it**: `wayfinder/map.md`,
  `wayfinder/plan.md`, `wayfinder/tickets/`
- **A new effort** (feature, build phase, spec) gets its own directory
  `wayfinder/<effort-slug>/`:
  - Spec: `wayfinder/<effort-slug>/spec.md`
  - Implementation issues: `wayfinder/<effort-slug>/tickets/<NN>-<slug>.md`, numbered
    from `01` — never a single combined tickets file
  - Effort map (only when `/wayfinder` drives it): `wayfinder/<effort-slug>/map.md`

Never write implementation tickets into `wayfinder/tickets/` — that is the closed
decision baseline and its frontier must stay clean.

## Ticket format — YAML front-matter (authoritative)

This is the dialect the existing tickets use. Do **not** substitute the inline
`Status:` / `Blocked by:` lines some skill templates assume.

```yaml
---
id: T01
title: <one line>
labels: [needs-triage]
hitl: false
status: open          # open | closed
blocked-by: []        # ticket names
blocks: []            # ticket names
assignee: unassigned
---
```

- `resolved: <YYYY-MM-DD>` is added when the ticket closes.
- The answer appends under a `## Resolution — <YYYY-MM-DD>` heading.
- Conversation history appends at the bottom under `## Comments`.

## Rules that override the stock conventions

- **Refer to tickets by name, not number** (`map.md`). Links use the path; prose uses
  the title.
- **Frontier** = tickets with `status: open`, `blocked-by: []`, `assignee: unassigned`.
- **Claim** a ticket by setting `assignee` before any work, and save.
- **Unblocked** when every ticket in `blocked-by` has `status: closed`.
- **Resolve** — append the answer under `## Resolution — <YYYY-MM-DD>`, set
  `status: closed` and `resolved:`, then append a one-line gist + link to the effort
  map's *Decisions so far*.

## When a skill says "publish to the issue tracker"

Create a file under `wayfinder/<effort-slug>/tickets/`, creating the directory if
needed, using the front-matter above.

## When a skill says "fetch the relevant ticket"

Read the file at the referenced path. The driver normally passes the path or the
ticket name directly.
