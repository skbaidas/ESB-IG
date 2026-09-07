---
id: EM03
title: "The RabbitMQ adapter is 'not published' by placement only, and nothing gates a consumer off it"
labels: [wayfinder:task, ready-for-agent]
hitl: false
status: closed
resolved: 2026-09-07
blocked-by: []
blocks: []
assignee: skbaidas@gmail.com
created: 2026-09-05
restates: []
---

# 03 — A third entry point nobody is stopped from importing

**Raised on 2026-09-05 while completing `W2-T10` step (a)**, from that ticket's own criterion
3 and the gap its review found rather than from anything that went wrong.

## 1. What the criterion says, and what is actually true

CTM's `W2-T10` ratifies the published surface in three lines:

> **What ESB/IG publishes is exactly three things:** the protocol (`publish` / `subscribe`),
> the **10-field envelope**, and the **conformance double** — the in-memory implementation.
>
> **The RabbitMQ adapter is NOT published.** A consumer that can import it eventually will,
> and then the contract is the transport.

The placement is correct. `esb_ig/__init__.py` exports the protocol, the double and the
error types; the envelope is a second entry point; `RabbitMqBroker` and
`broker_from_environment` live on a **third**, `esb_ig.transport`, which the package
docstring says a consumer must not take.

**Nothing enforces it.** `import esb_ig.transport` works from anywhere. The criterion was
recorded as *met by placement, unenforced* on `W2-T10`, and this ticket exists so that
qualifier does not quietly become *met* at step (c) review.

> ⚠️ **THE SENTENCE IN BOLD ABOVE IS FALSE AND IS SUPERSEDED BY [§6.1](#61-the-correction-first-because-it-changes-what-this-ticket-is-for).**
> CTM's `check_graduation.py` already reported `stranded-transport-import` when this was
> written — the ticket was drafted without following a pointer `transport.py` had been
> carrying the whole time. It is left standing rather than edited away because the
> correction is worth more than the tidy version: **this is `EGRESS-PROSE`'s defect in the
> direction CTM §14 warns about**, a record asserting an exposure the tree does not have.
> The rest of this section, and §2's reasoning, survive unchanged — what is enforced is the
> *consumer's import*, in the *pre-move* spelling, by a gate that lapses at step (c).

## 2. Why placement is not publication control

The criterion's own reasoning is that **a consumer that CAN import it eventually will**, and
that on the day one does, *the contract is the transport rather than the protocol*. That is a
statement about what people do under pressure, not about what they intend — which is exactly
the class of rule this estate gates rather than documents.

Two facts make it live rather than theoretical:

- `esb_ig.transport` is the only way to reach a real broker, so a consumer with a deployment
  problem has a strong, immediate reason to import it.
- The prohibition currently lives in a **docstring**. CTM's §11.3 and N11 say prose is not
  evidence, and the same reasoning applies to a control: a rule nothing evaluates is a rule
  that holds until the first person in a hurry.

**The seed's own suite is the legitimate exception and must stay one.**
`test_broker_conformance.py` imports `esb_ig.transport` deliberately — it is what makes the
double the executable definition of the protocol rather than a second implementation — and it
travels with the package. Whatever is built here must permit that and refuse a consumer.

## 3. What this ticket is NOT

- **Not a defect in the graduation.** The move placed everything where `W2-T10` ruled it
  should go. This is a missing gate, not a misplaced module.
- **Not urgent while there are no consumers.** `W2-T10` step (c) has not happened: CTM still
  carries its own copy and imports `backend.esb_ig`. There is currently no consumer to
  constrain. **The right time to build this is BEFORE the first one**, which is step (c).
- **Not answerable by CTM's boundary gate.** That gate reads CTM's tree. The rule here is
  about what an *installed* package exposes, which is this repository's question.

## 4. Sketch, not a ruling

The shape is not settled and should be before it is built. Three candidates, cheapest first:

1. **A consumer-side AST walk, run in CTM at step (c)** — refuse `from esb_ig.transport
   import ...` outside the composition root. Cheap, and it is where the rule actually bites,
   but it constrains one consumer rather than the package, and every future consumer needs
   its own copy.
2. **`__getattr__` deprecation or a marked-private module** (`esb_ig._transport`). Honest
   about intent and readable at the import site, but a rename is a breaking change to a
   surface CTM's `wiring` is about to compile against, so it belongs in the same change as
   step (c) if at all.
3. **A gate in THIS repository over the installed wheel** — the import-name lane already
   builds one in a clean virtualenv, so asserting what a fresh `import esb_ig` does and does
   not expose is a small addition to a step that exists. This is the one that constrains the
   *package* rather than a consumer, and it scales to the second consumer for free.

(3) reads best, and the reason to prefer it is the same reason `W2-T10` moved the unit of
review to the published image in a different context: **constrain the thing that is
published, not each of the places it is read.**

## 5. Acceptance criteria

- [x] A decision is recorded on which of the three shapes is taken, and why, before code.
      — **§6, and it changed the ticket's own premise before it changed any code.**
- [x] The chosen control is **blocking** in this repository's CI, with a negative control —
      it must be shown to fire on the shape it forbids, not only to stay silent on the shape
      it permits.
- [x] `test_broker_conformance.py` still imports `esb_ig.transport` and still passes. A
      control that forces the conformance suite off the adapter would remove the thing that
      makes the double a definition rather than a second implementation.
- [x] `W2-T10`'s criterion 3 can be ticked with the enforcement named, replacing *"met by
      placement, unenforced"* — **with the step (c) bill in §6.4, which is worth more than
      the gate.**
- [x] The package docstring stops being the only place the rule lives, and says where the
      gate is.

---

## 6. Ruling — 2026-09-07: option 3, and §1 was wrong

### 6.1 The correction, first, because it changes what this ticket is for

**§1 says "Nothing enforces it." That is false, and it was false when written.**

CTM's `scripts/check_graduation.py` has carried
[`stranded-transport-import`](../../../CTM/scripts/check_graduation.py) since before this
ticket was raised. It reports any CTM file that **stays behind** and imports the seed's
transport, keyed on:

```python
NON_CONSUMER_ENTRY_POINTS: Mapping[str, frozenset[str]] = {
    "esb_ig": frozenset({f"{PACKAGES_ROOT}.esb_ig.transport"}),
}
```

Its own docstring even names the reasoning this ticket restates — *"a consumer that can
import a transport eventually will, and then the contract is the transport"*. `transport.py`
pointed at it the whole time; the ticket was written without following the pointer.

**This is `EGRESS-PROSE`'s defect in the direction CTM §14 explicitly warns about** — a
record asserting an exposure the tree does not have. Recorded here rather than quietly
edited, because the ticket's §1 heading is *"What the criterion says, and what is actually
true"*, and it was the half that was not true.

### 6.2 What the gap actually is, and it is sharper than the one filed

Two facts, both verified rather than reasoned about:

1. `NON_CONSUMER_ENTRY_POINTS` names **`backend.esb_ig.transport`** — the **pre-move**
   dotted spelling.
2. After `W2-T10` step (c), CTM deletes its seed and imports the installed package, so a
   violating import would read **`esb_ig.transport`** — which is not in that set. The
   graduation gate also iterates `GRADUATING_SEEDS` over a tree that will no longer exist.

**So the existing control expires at exactly the moment it starts mattering**: the first
real installed package, the first real consumer. That is a better finding than "nothing
enforces it", and it is the one this ticket now carries.

### 6.3 The decision

**Option 3 — a gate in this repository, over what the package publishes.** Built as
`scripts/check_published_surface.py`, blocking, with `--json` evidence.

Why not the other two:

- **Option 1** (a consumer-side AST walk in CTM) is **already built**, per §6.1. Rebuilding
  it would have been the duplication this ticket exists to avoid, and it would still have
  constrained one consumer rather than the package.
- **Option 2** (rename to `esb_ig._transport`) is a breaking change to a surface CTM's
  `wiring` is about to compile against, for a rule Python cannot enforce anyway. It buys
  a naming convention at the cost of the one moment the contract must be stable.

Option 3 constrains **the thing that is published** rather than each place it is read, which
is what scales to the second consumer. And it is the only half that survives step (c).

**A script and not workflow glue**, deliberately: `EM03` criterion 2 requires a negative
control, and a control cannot be exercised from a YAML heredoc. The estate's own note is
that *glue written into `ci.yml` is the one thing it cannot verify locally.*

### 6.4 What it does NOT do, and the bill that outlives it

**Python has no private modules.** `import esb_ig.transport` works from anywhere and this
gate does not pretend otherwise. Its `not_verified_here` says so in the artefact, in the
first entry, so a green cannot be read as "a consumer is prevented".

> **STEP (c) BILL — `NON_CONSUMER_ENTRY_POINTS` must gain the post-move spelling
> `esb_ig.transport` in the same change that switches `wiring`'s import**, or CTM's half of
> this control lapses silently. Recorded on `W2-T10` as well as here, because a bill written
> in only one of two repositories is a bill one reader will not see.

> **PAID EARLY, 2026-09-07 — and the bill above would not have paid it.** Discharged in CTM
> ahead of step (c) rather than during it, because a control that has to be remembered at the
> exact moment somebody is solving a deployment problem is the one this ticket exists about.
>
> **The correction is the part worth carrying**: adding the string alone is a **no-op**.
> CTM's import graph comes from `check_boundary.walk_imports`, which yields imports of
> `backend.*` packages only — an installed `esb_ig.transport` produces no edge, so the ban is
> never consulted no matter what is in the set. The bill named a necessary step and called it
> sufficient, which is §6.1's defect one level down: a record naming a remedy it had not
> followed through. CTM now enumerates **both** spellings and walks the post-move one
> separately, keyed on the ban rather than on its `GRADUATING_SEEDS` tuple — the seed leaves
> that tuple the day step (c) completes, so a detector driven by it would have expired a
> second time at the same moment, with a passing test.
>
> Nothing in **this** repository changed: `check_published_surface.py` reads the package's own
> surface and never depended on the spelling a consumer uses. See `W2-T10`, *"Step (c)'s bill,
> item 2 — DISCHARGED"*.

### 6.5 What was built

`scripts/check_published_surface.py` — three static rules read by AST, one asserted at
runtime, a negative control on every invocation, and a `--json` artefact.

| rule | catches |
|---|---|
| `adapter-reached-by-the-published-surface` | the package root importing the adapter **by any spelling** — relative or absolute, via `lib.rabbitmq` or via the `transport` entry point, aliased or not. Matched on the **module**, never the name, because `as` is the obvious way past a name-matching rule |
| `published-surface-changed` | `__all__` differing from the ratified set, in **either** direction — a removal is a breaking change for a consumer already compiled against it |
| `published-surface-undeclared` | no `__all__` at all, which is distinct from an empty one and would satisfy rule 1 trivially |
| *(runtime)* | a fresh `import esb_ig` leaving the adapter in `sys.modules` — the reach an AST walk of one file cannot see, such as `lib/__init__.py` importing it |

**Proven against the real tree, not only synthetic samples.** Two mutations of the committed
package, each reverted:

- re-exporting `RabbitMqBroker` on `__init__.py` → **3 findings, exit 1** (static reach,
  widened surface, and the runtime probe);
- reaching the adapter from `lib/__init__.py` only → **1 finding, exit 1**, and the message
  correctly says the reach is *not* in the package root's source and points one level down.

21 tests, RED before GREEN. The suite is 94 passed / 13 skipped locally.

**One test expectation was corrected at the RED stage rather than the code contorted to fit
it**: the direct-re-export case was written expecting one finding and reports **two** — the
reach and the widened surface are two facts, and either can exist without the other, so
collapsing them would make the survivor silent.

**Closed.**
