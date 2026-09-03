# ADR-0001 — CTM's ADR-0038 is adopted: the envelope, the ratified catalogue, and the two-axis rule

- **Status:** Accepted
- **Date:** 2026-09-03
- **Author:** Sbaidas, platform owner
- **Answers:** [`EM02`](../../wayfinder/esb-ig-mediation/tickets/02-adopt-adr-0038-the-envelope-the-catalogue-and-the-axis-rule.md) — CTM's ask, put 2026-09-02, committed here 2026-09-03
- **Counterpart record:** CTM `docs/adr/0038`, CTM `docs/adr/0037`, CTM `contracts/asyncapi.json`, CTM `contracts/envelope.json`
- **Closes on the CTM side:** `DT22`, which unblocks `T22` and `CB01`

---

## The sentence that has to come first, because everything else reads differently without it

**The joint sitting was held by one person holding both chairs.** I own CTM and I own ESB/IG.
There was no meeting, there were no two parties, and nobody negotiated with anybody. This ADR
is ESB/IG's adoption of a contract I published from CTM, written by me, in ESB/IG's tree,
on 2026-09-03.

It is written that way on purpose, and the alternatives were both worse.

**Not manufactured correspondence.** No message from ESB/IG appears anywhere, because none
exists. A record reading *"ESB/IG confirms"* would be a fabrication of a second voice, and it
would be indistinguishable — to every later reader, including me — from a real counterparty
having reviewed this. That is the single most expensive lie this estate could tell itself,
because every downstream artefact would inherit a review that never happened.

**Not an indefinite hold either.** CTM's `DT22` ruled on 2026-09-02 that it would stay open
until a counterparty adopted, and that ruling was right *from where it was made*: writing
ESB/IG's half inside CTM's records is manufacturing the counterparty. But the register may
only say what it rules; the tree is what says what is. Writing the adoption in **ESB/IG's own
tree, dated, attributed** is not manufacturing anything — it is the party that owns this
repository acting in it. Holding out for a second signature that structurally cannot arrive
would have kept four CTM tickets blocked to preserve a two-party fiction that never existed.

**What is therefore weaker here than in a real two-party adoption, stated rather than
implied:** there was no independent review. Nobody read CTM's contract with fresh eyes and
looked for what it got wrong. The compensating instrument is not a second signature — it is
`scripts/check_catalogue.py`, which derives the mandate from each type's *name* rather than
trusting the declaration, so a misclassification I made in CTM is caught here rather than
copied. **That is a weaker control than a reviewer and it is the one that is actually
available.** It is named so that nobody later mistakes this for peer review.

---

## Decision

ESB/IG adopts, in full and as one act:

### 1 · The envelope, at `envelope_version` 1

The ten-field enumeration CTM froze at `contracts/envelope.json` on 2026-09-02. Recorded in
[`contracts/integration-catalogue.toml`](../../contracts/integration-catalogue.toml) as
`envelope_fields`, and **written out rather than referenced**, because a dual record whose
half is a pointer to the other half is one record.

**The contract is the enumeration, never the count** (CTM ADR-0015). No total appears in the
catalogue and none may be added — CTM's own §7 carried a stale field-name list for eight days
and an external assessment ranked the resulting confusion a *blocking* integration defect.

### 2 · The ratified catalogue, including the rename

`ctm.tenant.closed` is adopted and **`INT-CTM-01`'s `ctm.tenant.deleted` is retired by it.**

CTM's ADR-0037 is the argument and I accept it here on its own merits rather than by
deference: `deleted` names an act the producer structurally cannot perform. CTM's runtime
role holds `DELETE` on no invoice table, migration `c0027` freezes an approved invoice against
every role including its owner, and ADR-0029 runs a four-year statutory retention duty over
exactly those records. **A catalogue name describing an act the producer cannot perform is a
name a consumer will build against and be wrong about** — and the consumer's failure would
arrive as a mediation error naming nothing, far from the record that caused it. `closed` is
what happens. *Reclaim* and *erase* are separate acts, with separate names, and today with no
producer at all.

The four `ctm.billing.*` types stay **`pending`**. They enter by the extension path — a
tracker decision plus a schema version — never by widening a lint. ESB/IG admits no channel
for them today, and they are listed in the catalogue so that its silence about them cannot be
read as their absence.

### 3 · The two-axis rule — and this was the condition, not a detail

Two of the ten envelope keys are **value-nullable**, and each is null precisely when the fact
is not scoped on that axis:

| Key | Null when | The types |
|---|---|---|
| `application_code` | the fact is about a **client**, not one of their applications | the four `ctm.tenant.*` |
| `tenant_alias` | the fact is about the **platform's catalogue**, not any client | `ctm.application.registered` |

**The permitted set for a given type must be exactly `{null}` or exactly `{string}`.** A
widened union `["string", "null"]` is a **finding**, not a match.

This is the whole of ESB/IG's stated condition for accepting nullability at all, and the
reason is worth restating rather than citing: **a union is what makes a placeholder
representable again.** Absent nullability, a producer with no application to name must invent
a sentinel — an empty string, a `-`, a seeded `NONE` code — and a sentinel travelling in place
of an absent fact is a value every consumer must learn about out of band. Nullability removes
the need for the sentinel; a *union* puts it straight back, because a field permitting both a
string and null accepts the sentinel and the absence indistinguishably.

**Adopting the rename without the rule would have been the fragment adoption**, closing CTM's
`DT22` and immediately reopening what `DT01` settled. The two are adopted on one commit
because ADR-0038 says they are one dual-recording act.

### 4 · The payloads meet ESB/IG's needs

Nothing is missing that ESB/IG's mediation flows need. **This is the criterion where a single
owner is weakest and I am not going to dress it up**: ESB/IG's mediation flows are not built,
so "meets its needs" is a judgement about software that does not exist, made by the person who
wrote the contract. It is recorded as a judgement, not as a verification.

**The consumer that could answer for real did, and the answer was informative.** IAM is a seed
inside CTM's tree until `W2-T11`, so its confirmation is a fact rather than a claim about
another party — and it was written as 18 assertions rather than as prose. **Four were red on
the first run**, catching a defect that would have made IAM refuse every one of the four
tenant-lifecycle events on the day their producers were released: IAM's own envelope copy
still declared the application field value-*required*. That is the value of an executable
confirmation over a written one, and it is why this ADR does not treat item 3 as a formality.

**NC's leg is an expiring exception, not a silent gap** — carried in the catalogue's
`not_established_here`, owner the platform owner, expiring on the earlier of NC becoming live
or 2026-12-31. **Nothing computes that expiry**, which is the residual this exception leaves.

---

## Consequences

**Immediately true.** ESB/IG's catalogue exists, is machine-readable, and encodes the axis rule
per type. `scripts/check_catalogue.py` asserts it, with a negative control on every invocation;
two mutations were run before this ADR was written — a widened union on `ctm.tenant.closed` and
a flipped axis on `ctm.application.registered` — and each turned it red under its own detector,
with a clean restore.

**Unblocked in CTM.** `DT22` closes, and `T22` and `CB01` may build the four `ctm.tenant.*`
producers against a name that is now adopted rather than proposed. `CB05` and `CB13` follow
them.

**Not true, and stated so it is not inherited.**

- **No event is produced.** The four producers are held and unbuilt. Adoption is a name, not
  an emission.
- **Nothing is transported by this repository.** The broker plane is CTM's `esb_ig` seed until
  `W2-T10` moves it.
- **A green bounds itself to this document.** This bullet read *"No CI runs the checker. This
  repository has no workflow"* until 2026-09-03, when `.github/workflows/ci.yml` made
  `check_catalogue.py` a blocking lane on every push (first green run `33750045456`). What
  replaces it is narrower and has to be said rather than inferred: a green proves the
  catalogue still encodes the axis rule and the frozen envelope enumeration, and proves
  nothing about a producer, a transport, a gateway or a handler.
- **There is no test suite.** `backend/tests/` is empty, so CI's Tests lane reports **NOT-RUN,
  which is not a pass** (CTM `CLAUDE.md` §11.3). The RabbitMQ container the workflow
  provisions is probed for **port reachability** and never spoken to — no AMQP, no
  redelivery, no dead-letter routing, no priority ordering.
- **There was no independent review.** See the top.

## Owed

1. ~~**CI in this repository**, so the checker is a lane rather than a command someone
   remembers. Rides with CTM's `W2-T10`.~~ **CLOSED 2026-09-03** — `.github/workflows/ci.yml`,
   run `33750045456`. **It did not ride with `W2-T10`, and that is the right order rather than
   an accident**: the runner and the broker container are what the graduation should not also
   have to build, so they are standing before the code arrives. What `W2-T10` still brings is
   the suite that makes the Tests lane say something.
2. **The v1.6 document set** still reads *"INT-CTM-01 keeps `deleted` until that tracker
   decision"* and *"adoption at the joint sitting pending"*. Both are superseded by this ADR
   and are to be updated citing this commit's hash. Owed to the platform owner.
3. **NC's confirmation**, on the exception above.
