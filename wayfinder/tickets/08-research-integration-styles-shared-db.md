---
id: T08
title: "Research — Integration styles: when shared-database integration is legitimate vs when to mandate broker/API mediation"
labels: [wayfinder:research]
hitl: false
status: closed
blocked-by: []
blocks: []
assignee: skbaidas@gmail.com
---

## Question

Ground the driver's rule — **"other products integrate through ESB/IG only if they do NOT share a
database."** From Hohpe & Woolf (the four integration styles: File Transfer, Shared Database, Remote
Procedure Invocation, Messaging), Fowler (SharedDatabaseIntegration / IntegrationDatabase),
Richardson (Database-per-Service), and Newman: **when is shared-database integration appropriate,
when must integration instead be messaging/event/API-mediated, and what caveats apply** (bounded
context / single deployable; schema coupling; autonomy; read-vs-write)?

## Arms
T02 (the shared-DB refinement / internal-integration scope).

## Resolution (research — closed) — ⚑ this one changes the recommended answer

**Verdict: the driver's rule is *partially consistent, but emphasis-inverted*.** Best practice's
**default** is the opposite: two **independently-evolving** products/sub-systems should integrate via
messaging/API (ESB/IG) — a **shared database across them is itself the anti-pattern**, because it
exposes internal schema as the integration contract and creates both development-time coupling
(coordinated schema change) and runtime coupling (cross-service lock contention).

**Shared-DB integration is legitimate ONLY in the narrow case:** one **bounded context / single
deployable / single schema owner**, where direct access isn't "integration" in the EIP sense but
internal data access. Caveats that must ride with it:
1. Never expose internal tables as the contract (the "integration database" trap — Fowler).
2. Shared **writes** create ambiguous invariant ownership + lock coupling → route cross-product
   writes through the owning product's API/command; prefer owned schemas / read-models.
3. **Even co-located products should still emit events over ESB/IG for cross-cutting concerns**
   (lifecycle, audit, workflow triggers, cache invalidation). The DB carries *data* at commit, not
   *behavior* or *notification*. "DB **xor** gateway" is a false dichotomy.

**Applied (design §3):** distinct sub-systems (CTM/IAM/NC/Translation — separate DBs) ⇒ **always
ESB/IG**; a shared DB there would violate N3. The "shared-DB → data-plane" branch holds **only** for
products genuinely co-located on the tenant schema-per-tenant DB under one schema owner
(IRM ↔ Procurement) — **an assumption the driver must confirm** — and even then behavioral events
still ride ESB/IG.

**Sources:** enterpriseintegrationpatterns.com (Integration Styles — Shared Database & Messaging) ·
martinfowler.com/bliki/IntegrationDatabase.html · microservices.io/patterns/data/database-per-service
& /shared-database · Newman, *Building Microservices*.
