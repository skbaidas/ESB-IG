---
id: EM03
title: "The RabbitMQ adapter is 'not published' by placement only, and nothing gates a consumer off it"
labels: [wayfinder:task, ready-for-agent]
hitl: false
status: open
blocked-by: []
blocks: []
assignee: ""
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

- [ ] A decision is recorded on which of the three shapes is taken, and why, before code.
- [ ] The chosen control is **blocking** in this repository's CI, with a negative control —
      it must be shown to fire on the shape it forbids, not only to stay silent on the shape
      it permits.
- [ ] `test_broker_conformance.py` still imports `esb_ig.transport` and still passes. A
      control that forces the conformance suite off the adapter would remove the thing that
      makes the double a definition rather than a second implementation.
- [ ] `W2-T10`'s criterion 3 can be ticked with the enforcement named, replacing *"met by
      placement, unenforced"*.
- [ ] The package docstring stops being the only place the rule lives, and says where the
      gate is.
