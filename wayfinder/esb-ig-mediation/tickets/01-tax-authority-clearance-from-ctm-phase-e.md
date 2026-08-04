---
id: EM01
title: "Tax-authority clearance — five questions from CTM Phase E"
labels: ["wayfinder:grilling", "ready-for-human"]
hitl: true
status: open
blocked-by: []
blocks: []
assignee: skbaidas@gmail.com
created: 2026-08-04
raised-by: "CTM Phase E — PE19, PE10"
---

# 01 — Tax-authority clearance: five questions from CTM Phase E

**First ticket of the `esb-ig-mediation` effort**, which had a spec and no tickets. It sets the id
prefix **`EM`** so these never collide with the closed baseline's `T01–T09` under
`wayfinder/tickets/`.

**Raised by CTM, answered by ESB/IG.** CTM Phase E must submit each invoice to Jordan's national
e-invoicing system (**JoFotara**) and receive back a cleared document, a UUID and a QR code.
**Clearance has been legally mandatory per invoice since 1 April 2025**, so this is a live
obligation, not a roadmap item.

## What CTM is *not* asking, because your own requirements answer it

CTM's ticket `PE19` was drafted to ask *"will ESB/IG accept a synchronous request/response
interaction into its scope?"*. All seven ESB/IG v1.0 documents were read on 2026-08-04 before the
question was put, and **the answer is yes, already, by requirement**. The question is withdrawn:

| Requirement | What it settles |
|---|---|
| **CIG-01** — *"The CIG SHALL own outbound initiation **and the response leg** for every external integration"* | A synchronous response leg is in scope, and is the CIG's, not the caller's |
| Plane table (SRS & SDD) — *Cloud Integration Gateway · Outbound integration · **Synchronous call + asynchronous retry*** | The shape is named in the architecture, not an exception to it |
| Counterparty table — *External third party · Gateway plane (in) / **CIG (out)** · **Always ESB/IG, both directions*** | A tax authority is an L6 counterparty; the routing rule is unambiguous |
| **CONN-02** — a new external system *"SHALL require a connector definition and a mapping flow only — no code change and no deployment"* | A per-region clearance adapter is **configuration** |
| **NFR-01** (added latency p95 < 15 ms per mediated hop) with **NFR-18** (*"Excludes the counterparty round trip, measured separately"*) | A slow authority does not breach your budget. CTM had this down as a probable conflict; it is not one |
| **CIG-11 / CIG-12** — response-leg size, depth and parse-time bounds; external entity resolution disabled, entity expansion bounded | Load-bearing here: JoFotara returns **UBL 2.1 XML**, so the response leg is the parse surface |
| **EGR-01…10** — deny-by-default allow-list, resolve → validate → pin → connect, fail closed | Answers CTM's SSRF and pinning criteria without CTM building anything |

**So this is not a scope request.** It is five questions about how the shape ESB/IG already has
behaves against a counterparty with two unusual properties: it is a **regulator**, and a duplicate
submission may produce a **second legally-cleared invoice**.

## Question

### Q1 — `CIG-10` park-and-retry, against a counterparty that may not deduplicate

> **CIG-10** — *"Where a counterparty is unavailable, the CIG SHALL retry with exponential backoff
> and then park the message, never drop it."*

For ordinary integrations that is exactly right. For clearance it is the one behaviour that can
cause a **regulatory** defect rather than an operational one: **a submission that times out but
*succeeded* at the authority, then gets retried, may become a second cleared invoice.** How
JoFotara handles a duplicate cannot be verified — its XSD, validation rules and error codes are
published nowhere on a Jordanian government domain, and CTM has a question open with the ISTD on
exactly this.

**BRK-15** gives the *broker* plane a bounded idempotency window *"with a business-key safeguard
for non-idempotent effects"*.

**Is there a CIG-side equivalent, and who owns the business key — the caller, or the connector
definition?** If the caller, CTM will carry it and would like that written down; if the connector,
CTM needs to know which field.

### Q2 — Does the caller receive the authority's response body inline?

`CIG-01` says the CIG owns the response leg and `CIG-11` bounds it before parsing, but neither says
what reaches the **calling sub-system**.

This decides CTM's invoice state machine. Its design sequences **`drafted → cleared → approved`**,
with approval falling *after* the authority responds, because the returned **QR must ride on the
immutable record** handed to the buyer. That only works if the cleared XML, the UUID and the QR
come back to CTM on the same call.

**Does the caller get the parsed response inline, or an acknowledgement now and the response later
by another route?** If the latter, CTM's state machine needs a fourth state.

### Q3 — What does the caller observe when `CIG-10` parks?

CTM must distinguish three outcomes, and they carry different legal consequences:

- **cleared** — the invoice may be approved and given to the buyer;
- **rejected by the authority** — the invoice must not be approved, and the reason must be recorded;
- **not yet known** — the invoice queues, and the client is told nothing.

A parked message is a **fourth** state, and today CTM cannot tell it from the third.

**When the CIG parks, what does the caller see — a distinguishable status, a callback when the park
resolves, or nothing until it does?** CTM fails closed either way; it needs to know whether "fails
closed" means *blocks* or *returns pending*.

### Q4 — Is a tax authority an ordinary connector, or a connector class?

ESB/IG created a **payment connector class** (`CIG-07`, `PCI-01…15`) because payment carries an
assessment boundary. Clearance carries a different one: a regulator, per-region, non-interoperable
(Jordan and Saudi Arabia are both centralised clearance and **not** interoperable; the UAE goes
Peppol 5-corner in 2026).

**Ordinary connector with the REST/JSON handler, or a clearance connector class?** CTM's assumption
is **ordinary** — JoFotara is JSON-over-HTTPS with base64 UBL 2.1 inside — and would rather have
that confirmed than assumed. Noting that `CONN-02`'s "config not code" promise is recorded as
*conditional for EDI only*; REST/JSON satisfies it fully, which is the case here.

### Q5 — Phase C, and whether CTM is on ESB/IG's critical path

> **CONN-03** — *"Mapping flows SHALL be declarative field maps… The mapping engine is **built in
> Phase C**; the document catalogue (purchase order, **invoice**, advance shipping notice)
> graduates later."*

**This is the question with a date attached, and it is the one CTM did not know it had.** PE10
cannot be built before a mapping engine exists, and five further CTM tickets sit behind PE10 —
invoice lifecycle, credit notes, settlement, retention applied to invoices, and the tenant billing
portal. **Six of Phase E's eighteen tickets are downstream of ESB/IG's Phase C.**

**When is Phase C expected, and does the catalogue's "invoice" entry cover a UBL 2.1 *tax* invoice
for clearance — or is that a separate document type CTM should be specifying now?**

**Q5b.** `CONN-08` requires a connector be dry-run testable before activation, *"without dispatching
a live business message"*. CTM separately requires a **conformance double**, because no test suite
can run against a live tax authority. **Are these the same artefact, or two?** If ESB/IG's covers
it, CTM will not build one.

## What CTM commits to, so this is an exchange rather than a request

- **No direct application→external path.** Root `CLAUDE.md` §7 forbids it and CTM is not asking for
  an exception. If clearance cannot go through ESB/IG, CTM's design is wrong and will be redesigned
  rather than routed around you.
- **Credentials** (Client ID, Secret Key, Activity Number) resolve from the in-estate secrets
  manager, never a literal — matching `CIG-04`.
- **Fail closed.** An invoice that has not cleared is not approved. CTM will not issue a document
  that may not be valid in order to keep a queue moving.
- **Three-decimal JOD.** The fils is the third decimal, and the authority's own portal computes at
  nine and displays three. **If any mapping layer normalises amounts, it must not round to two** —
  that is a compliance defect, not a display one.

## What resolving this looks like

- [ ] Each of Q1–Q5b answered in ESB/IG's words, appended under `## Resolution — <date>`.
- [ ] **Q5 carries a date**, not a sequence position — six CTM tickets are scheduled off it.
- [ ] Any shape constraints ESB/IG imposes (timeout, idempotency ownership, retry ownership) are
      named, because CTM's `PE10` builds to them.
- [ ] The answer is carried back to CTM's `PE19`, which closes on it.

## Notes

**CTM's `PE19` does not list this ticket in its `blocked-by:`.** That field names tickets in the
same repository only — a cross-repo string resolves to no status and would make `PE19` permanently
unblockable, which is the exact defect `PE19` was created to fix. The pointer is prose in `PE19`'s
body instead.

**The other party CTM waits on is separate and must stay separate.** `PE10` also needs the
**ISTD** — the JoFotara XSD is published nowhere on a government domain, and eight bilingual
questions are drafted for them. That is a schema gap; this is a mediation contract. A reader who
conflates the two will discount one along with the other.

Source: `..\..\..\..\CTM\wayfinder\ctm-phase-e\questions\esb-ig-clearance-shape.md`.
