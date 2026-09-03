---
id: EM02
title: "Adopt ADR-0038 — the envelope, the ratified catalogue, and the per-type axis rule; and carry the renamed terminal lifecycle type"
labels: ["wayfinder:decision", "ready-for-human"]
hitl: true
status: open
blocked-by: []
blocks: []
assignee: skbaidas@gmail.com
created: 2026-09-02
raised-by: "CTM — DT22, ADR-0037, ADR-0038"
---

# 02 — CTM asks ESB/IG to adopt the contract it has already published

**Raised by CTM, to be answered by ESB/IG.** Same shape as `EM01`: CTM puts the question, ESB/IG
rules it, and the answer is recorded here rather than in CTM's tree.

**This ticket IS the ask.** Until now the ask existed only as a sentence in CTM's `CLAUDE.md` §7
(*"ESB/IG is **asked** to carry the renamed terminal type, not told"*) and in ADR-0038's *Owed work*
item 4. A notice recorded in one repository as owed is not a notice that was given — which is the
`DEF-5` defect in the other direction, and CTM's own cross-effort register exists because of it.

> **Written 2026-09-02. Committed 2026-09-03, and the dates are left to differ.** The ticket sat in
> this repository's working tree, untracked, for a day. CTM's `DT22` had already recorded that the
> ask was *"PUT on 2026-09-02"* and its register moved eight rows to `asked` on the strength of it —
> so for that day the notice was a file on one disk and a claim in another repository, which is
> **`DEF-5`'s own shape a third time**: a record asserting an act that the tree could not evidence.
> Found 2026-09-03 by `git status`, which is the whole instrument. Backdating the commit would have
> made the record read correctly and be false; the two dates stay apart instead.

---

## What CTM has published, and where to read it

CTM's control plane publishes a **twelve-member** event allow-list. **Eight of the twelve are
ratified by ADR-0038; four are pending.** The enumeration — never the count — is the contract, and
it is machine-readable:

| What | Where, in CTM's tree |
|---|---|
| The published contract, as AsyncAPI 3 | `contracts/asyncapi.json` — **generated** from the code, never hand-edited |
| The envelope's enumerated field set | `backend/esb_ig/envelope.py` → `ENVELOPE_FIELD_NAMES` |
| The allow-list | `backend/ctm/lib/outbox.py` → `EVENT_TYPES` |
| The decision record | `docs/adr/0038-…` (envelope + catalogue), `docs/adr/0037-…` (the rename) |
| The gate that keeps document and code in agreement | `scripts/check_asyncapi.py` (blocking) |
| The gate that enforces the axis rule per type | `scripts/check_event_catalogue.py` (blocking) |

**Read `contracts/asyncapi.json` rather than this ticket** for anything you will build against. This
ticket is the ask; that document is the contract.

## The three things being asked

### 1. Adopt the renamed terminal lifecycle type

CTM's terminal tenant-lifecycle type was renamed by ADR-0037 on 2026-08-25. The **new** name is
`ctm.tenant.closed`. The **superseded** name — the one ESB/IG's catalogue carries today under
`INT-CTM-01` — is the one built on the verb meaning *destroyed*, and CTM's argument for dropping it
is that the platform structurally cannot do what it promised: the runtime role holds no `DELETE` on
any invoice table, an approved invoice is frozen against every role including its owner, and a
four-year statutory retention duty runs over exactly those records.

**ESB/IG's catalogue name changes by ESB/IG's decision, not by CTM's.** That is why this is an ask.

### 2. Dual-record ADR-0038

Three parts, and the third is the one ESB/IG made a condition:

- **The envelope** — ten presence-required keys, refused if one is missing *and* refused if an
  unknown key appears.
- **The ratified catalogue** — eight types. The four billing types in CTM's allow-list are
  **pending** and enter by the extension path (tracker decision plus schema version), not by
  widening a lint. ESB/IG carries none of them today and admits no channel for them.
- **The per-type axis rule** — two of the ten envelope keys are *value*-nullable, and each is null
  **precisely when the fact is not scoped on that axis**. The permitted set for a given type must be
  *exactly* `{null}` or *exactly* `{string}` — a widened union is a finding, because a union is what
  makes a placeholder value representable again. This was ESB/IG's stated condition of accepting the
  nullability at all, and CTM has encoded it per type in the published document and enforced it in
  two blocking gates.

### 3. Say whether the payloads meet ESB/IG's needs

Not a formality. If a payload is short of something ESB/IG's mediation flows need, CTM would rather
learn it now than after a producer ships.

## What CTM has NOT done, and will not do until this is answered

**The four tenant-lifecycle producers are held, and the hold is executable rather than remembered.**
`backend/tests/test_lifecycle_producers.py` carries a HELD table asserting that those four verbs emit
**nothing**; the day one starts emitting, that test goes red. It is designed to fail when this
ticket is answered — its own docstring says the failure *"is the signal that the held half is ready
rather than that something broke."*

The three application-entitlement producers **are** released and emit in the state change's own
transaction.

**So there is no schedule pressure being applied here.** CTM is not waiting to ship something it has
already built; it has deliberately not built it, so that the producer does not go first a second
time.

## What an answer looks like

Any of these is a real answer, and a refusal is as useful as an adoption:

- **Adopted** — the catalogue carries the new terminal name, ADR-0038 is recorded on ESB/IG's side
  with the axis rule, and the date is written down.
- **Adopted with conditions** — name them.
- **Refused** — then CTM's `ctm.tenant.closed` is wrong and ADR-0037 is reopened, which is a smaller
  cost today than after four producers exist.

## Criteria

- [ ] The catalogue's terminal lifecycle name is ruled — adopted, conditioned or refused — with a date
- [ ] ADR-0038 is recorded on ESB/IG's side: envelope, ratified catalogue, and the per-type axis rule
- [ ] ESB/IG says whether the payloads meet its needs, or names what is missing
- [ ] The answer is written back to CTM's `DT22`, which stays open until it is
