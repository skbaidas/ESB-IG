---
id: T02
title: "All APIs & integrations through ESB/IG" — API Gateway plane scope
labels: [wayfinder:grilling]
hitl: true
status: closed
blocked-by: [T01]
blocks: [T05]
assignee: skbaidas@gmail.com
---

## Question

Your directive: **"all APIs and integrations must go through ESB/IG,"** and ESB/IG **must have the
functionalities of an API Gateway and a Cloud Integration Gateway.** This has **two readings** — one
puts ESB/IG on *every* request path, the other only on boundary-crossing traffic. Which do you want,
and where exactly is the line drawn against the ratified in-process business path and the
infrastructure edge gateway?

**Refinement (2026-07-24, from the driver — fold into the resolution):** the internal-integration
scope is now stated precisely. Traffic that must traverse ESB/IG:
- **Other products** (e.g., IRM ↔ a future product): **only when they do NOT share a database.**
  Products co-located on a shared database integrate **through that database** (data-plane), not
  ESB/IG.
- **Sub-systems** (CTM / IAM / NC / Translation — each owns its own DB, no shared DB): **always**
  through ESB/IG (events/commands over the broker plane, or a mediated API).
- **External third-party** systems: **always** through ESB/IG, both directions.

This **sharpens Reading B** (it does not revive Reading A): the in-process business hot path and the
infra edge gateway remain carve-outs; the **shared-database case is a new, explicit carve-out** for
product↔product traffic — grounded in the integration-styles research ([T08](08-research-integration-styles-shared-db.md)).

## The two readings (this is a genuine either/or — pick one)

- **Reading A — literal "front door for everything":** *every* inbound call, including the
  browser→app **business** request, is routed and policy-enforced by ESB/IG. ESB/IG sits on the
  per-request hot path.
- **Reading B — boundary-crossing / integration only (recommended):** ESB/IG is the single governed
  mediation point for every call that **crosses a boundary** — platform↔external (both directions)
  and, where used, sub-system↔sub-system API traffic. The **in-process business request path**
  (verified token → app instance → tenant schema) stays direct and is **not** re-routed through
  ESB/IG.

## Recommended answer — Reading B

**ESB/IG is the application-tier API Gateway + Cloud Integration Gateway for all boundary-crossing
traffic; the in-process business hot path and the edge network gateway are explicitly out of it.**

Concretely, **everything below must traverse ESB/IG** (no direct path — SEC-EVT-01):
1. **Inbound external / partner API calls** *into* the platform (this is the one case where ESB/IG
   genuinely sits on a request path): after the infra edge does TLS/WAF, ESB/IG's gateway plane does
   routing, identity hand-off to IAM ([Gateway identity enforcement](05-gateway-identity-enforcement.md)),
   per-tenant/per-role rate limiting, request validation, version negotiation, HMAC verification, audit.
2. **Outbound calls** to external ERP/logistics/banking — via the Cloud Integration Gateway
   ([Cloud Integration Gateway](03-cloud-integration-gateway.md),
   [Egress & webhook security](04-egress-webhook-security.md)).
3. **Cross-sub-system async traffic** — via the broker plane (envelope + DLQ).
4. **Synchronous, off-hot-path product → sub-system calls** — Translation's translation-icon path,
   via the gateway plane. *(Added by the 2026-07-25 modification below.)*

**Explicitly NOT through ESB/IG (the two carve-outs):**
- **The in-process business request path.** Tenant resolution and the L1→L2→L5 business request are
  **in-process, off-network** by ratified design — routing them through ESB/IG would add a network
  hop (~15 ms/hop) to *every* business call and break the split latency budgets.
- **The infrastructure edge gateway** (TLS termination, WAF, DDoS, CDN routing) — that is the
  **infrastructure plane** (CDN pillar, SEC-NET-02), ratified as managed/commodity. It sits **in
  front of** ESB/IG. ESB/IG is the *application-tier* API Gateway; the edge is a separate network layer.

## Why

- **Docs:** SEC-EVT-01 mandates "one governed mediation point for all external integration — **no
  direct application-to-external paths**," and the SRS makes ESB/IG "the single mediation point for
  all integration ... and all sub-system traffic." Reading B *is* that mandate, widened (per your
  directive) to inbound partner APIs and cross-sub-system calls.
- **The constraint against Reading A is the ratified request-path model, not N2.** The SRS request
  path is edge → load balancer → app instance → tenant schema, with ESB/IG on the *integration* leg
  only (SRS request-path view). The Infrastructure doc sets **split latency budgets**: tenant
  resolution **p95 < 2 ms in-process** vs **integration-added p95 < 15 ms** through ESB/IG. Reading A
  would put a 15 ms mediation hop on the 2 ms in-process budget for every business call — a
  self-inflicted latency regression the perf build-gate would fail. (N2 is a *different* rule — "no
  network call into CTM"; it is not the reason here.)
- **Best practice / simplicity:** the API-Gateway pattern belongs at boundaries. Making the internal
  business hot path go through the gateway is the classic anti-pattern (gateway on the critical path).
  Reading B gives you one governed door for everything that crosses a trust or system boundary, and
  keeps the hot path fast — the simplest correct decomposition.

## Applies globally

Fixes what "all APIs through ESB/IG" means for **every** sub-system: no component may open a direct
socket to an external system or (where the async broker isn't used) to another sub-system's API —
ESB/IG mediates it. The in-process business path is the sole carve-out. Sets the gateway-plane scope
that [Gateway identity enforcement](05-gateway-identity-enforcement.md) and the Cloud Integration
Gateway build on.

## Conflicts

- **vs the ratified request-path model + latency budgets:** only **Reading A** conflicts (it adds a
  hop to the in-process path). **Reading B is conflict-free** — it leaves the hot path untouched.
- **vs the infrastructure edge gateway (SEC-NET-02, CTM infra posture):** no conflict under Reading B
  — the edge network gateway (TLS/WAF/DDoS) stays infra-plane and in front; ESB/IG is the app-tier
  gateway. Choosing Reading A would *also* raise the question of whether ESB/IG absorbs WAF/DDoS,
  which it should not (a sub-system cannot terminate its own DDoS protection).

## Resolution (confirmed 2026-07-24 by the driver — closed)

**Confirmed: Reading B**, sharpened by counterparty type (see the developed design's routing table).
External third-party ⇒ **always** ESB/IG (gateway in / CIG out); sub-system↔sub-system (each owns a
separate DB) ⇒ **always** ESB/IG; product↔product ⇒ **ESB/IG by default**.

The **shared-DB data-plane branch applies only** to products co-located on the shared tenant
schema-per-tenant DB under one schema owner — **the driver confirmed IRM ↔ Procurement do share that
DB** — and even they publish **behavioral/cross-cutting events via ESB/IG** (data via the DB, events
via the bus). This adopts the best-practice *ESB/IG-by-default* posture ([T08](08-research-integration-styles-shared-db.md))
over the literal "shared-DB ⇒ data-plane" framing. The in-process business hot path and the infra
edge gateway remain carve-outs. Detail + full in/out inventory + diagram:
[developed design §3–§5](../ESB-IG-developed-design.md).

## Modification — 2026-07-25 (`/grill-with-docs`, confirmed by the driver)

**The counterparty table gains a `product ↔ sub-system` row it did not have.** The ratified table
covered *external*, *sub-system ↔ sub-system*, *product ↔ product* (×2) and the *in-process business
request* — but not how a product reaches CTM, IAM, NC or Translation. That omission left this ticket
and [Translation T01](../../../Translation/wayfinder/tickets/01-translation-build-sequence.md) in
direct contradiction. Resolved by routing on **latency class**:

| Product → | Channel |
|---|---|
| CTM (tenant resolution), IAM (identity verify) | In-process cached SDK, **no network** — N2, p95 < 2 ms |
| NC (notifications) | **Broker plane** |
| Translation (icon — synchronous, off hot path) | **Gateway plane** (mediated internal API) |

The same reasoning this ticket already used decides it: Reading A was rejected because a 15 ms
mediation hop cannot sit on a 2 ms in-process budget — that argument protects CTM and IAM, and
**Translation is explicitly off the hot path**, so it does not extend there.

**Chart row 11 is superseded** for the product-invoked case: it read *"broker plane **or** mediated
gateway API"*; for a product calling Translation it is the gateway plane. Nothing else changes — the
shared-DB inversion, the IRM↔Procurement fact and both carve-outs stand. Full rationale:
[ADR-0001](../../../CTM/docs/adr/0001-product-to-subsystem-invocation.md).
