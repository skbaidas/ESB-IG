---
id: SPEC-ESBIG
title: ESB/IG — the single governed mediation point for boundary-crossing traffic
labels: [ready-for-agent]
hitl: false
status: open
blocked-by: []
blocks: []
assignee: unassigned
created: 2026-07-25
---

# ESB/IG sub-system — spec

> Synthesised from the closed decision baseline (`../map.md`, 9 tickets), the developed design
> (`../ESB-IG-developed-design.md`), the build plan (`../plan.md`), the SEC-EVT/APP/NET control
> catalogue, and ADR-0001 (`../../../CTM/docs/adr/`).
> **Seams: see the shared seam model in [CTM's spec](../../../CTM/wayfinder/ctm-control-plane/spec.md#testing-decisions).**

## Problem Statement

The platform has to talk to the outside world — customer ERPs, logistics providers, banks, partner
APIs, webhook subscribers, on-premise estates — and its own sub-systems have to talk to each other.
If every component opens its own outbound connection, then the hardest security control on the
platform, **outbound request filtering**, has to be implemented correctly in a dozen places. It
will not be. A customer-supplied webhook URL is the classic server-side request forgery sink, and
one component that resolves a hostname twice — once to validate, once to connect — reopens the
whole class.

The same fragmentation hits inbound: without one door, rate limiting, request validation, version
negotiation and identity enforcement are each implemented per endpoint, and the first endpoint that
forgets one is the one that gets found.

## Solution

**One governed mediation point** for traffic that crosses a trust or system boundary, in three
planes: an **API Gateway plane** for inbound boundary-crossing calls, a **Cloud Integration
Gateway** for outbound protocol mediation and connectors, and a **broker plane** carrying the
10-field envelope for asynchronous traffic between sub-systems.

The gateway is a **policy-enforcement point**: it validates a token or API key and resolves the
verdict against IAM, but **mints and stores no credentials of its own**. Outbound calls pass a
fail-closed egress guard that resolves a hostname, validates the resulting address, **pins it, and
connects to the pinned address** — so a name that changes between validation and connection cannot
be used. Webhooks are signed and replay-bounded.

New integrations are **configuration, not code**: a connector definition plus a mapping flow, both
list-of-values, so adding an ERP or a bank needs no deployment.

Two things are deliberately **not** ESB/IG: the in-process business request path, which would gain
a mediation hop on a 2 ms budget, and the infrastructure edge (TLS termination, WAF, DDoS, CDN),
because a sub-system cannot terminate its own denial-of-service protection.

## User Stories

**Partner / external system**

1. As a partner system, I want one documented door into the platform, so that I do not integrate
   against several inconsistent endpoints.
2. As a partner system, I want my API key validated on every call, so that a revoked key stops
   working at once.
3. As a partner system, I want a clear rate limit, so that I can pace my traffic rather than
   discover a cliff.
4. As a partner system, I want my request validated against a published contract, so that a
   malformed call fails immediately and informatively.
5. As a partner system, I want a negotiated API version, so that my integration is not broken by
   someone else's release.
6. As an external system, I want my callback signature verified, so that nobody can forge a status
   update to the platform.

**Webhook subscriber**

7. As a webhook subscriber, I want deliveries signed with a shared secret over the raw body, so
   that I can verify authenticity.
8. As a webhook subscriber, I want a signed timestamp, so that a captured delivery cannot be
   replayed later.
9. As a webhook subscriber, I want a delivery identifier I can deduplicate on, so that at-least-once
   delivery does not become at-least-twice processing.
10. As a webhook subscriber, I want failed deliveries retried with backoff and then parked, so that
    a brief outage on my side does not lose events.
11. As a webhook subscriber, I want to rotate my secret without downtime, so that rotation is not
    an outage.

**Platform operator / security**

12. As a security engineer, I want **one** egress enforcement layer, so that the SSRF control is
    implemented and reviewed once.
13. As a security engineer, I want outbound destinations on a deny-by-default allow-list, so that a
    new destination is a deliberate act.
14. As a security engineer, I want the resolved address parsed and compared numerically, so that
    decimal, octal, hex and IPv6-mapped encodings cannot slip past a string check.
15. As a security engineer, I want loopback, private, link-local and cloud-metadata ranges blocked,
    so that an outbound call cannot reach the platform's own control surfaces.
16. As a security engineer, I want the validated address **pinned** and connected to directly, so
    that a name cannot change between validation and connection.
17. As a security engineer, I want redirects disabled or re-validated per hop, so that a redirect
    is not a bypass.
18. As a security engineer, I want no direct application-to-external path to exist at all, so that
    the control cannot be sidestepped.
19. As an operator, I want a dead-letter queue per channel, so that a poison message isolates
    rather than blocking or vanishing.
20. As an operator, I want to inspect and replay a dead-lettered message, so that a transient
    failure is recoverable.
21. As an operator, I want every boundary crossing audited append-only, so that an incident is
    reconstructable.
22. As an operator, I want per-tenant integration health visible, so that I can tell one client's
    outage from a platform outage.

**Consumer sub-system / product**

23. As a producing sub-system, I want to publish on the 10-field envelope without knowing who
    consumes, so that adding a consumer needs no change to me.
24. As a consuming sub-system, I want at-least-once delivery with an `event_id` to deduplicate on,
    so that I can be idempotent.
25. As a consuming sub-system, I want per-tenant, per-type ordering, so that two events for one
    tenant do not arrive reversed.
26. As a consuming sub-system, I want priority classes, so that a security event is not queued
    behind a bulk export.
27. As a product, I want to call Translation synchronously through the gateway, so that the
    translation icon returns immediately while still passing one enforcement point.
28. As a product, I want tenant resolution and identity verification to **bypass** the gateway, so
    that the request path keeps its 2 ms budget.
29. As an integration engineer, I want to add an ERP or bank as a connector definition, so that a
    new integration needs no code change and no deployment.
30. As an integration engineer, I want canonical-to-external field mapping declared rather than
    coded, so that a field change is configuration.

**On-premise estate**

31. As a customer with on-premise systems, I want the agent to connect **outbound only**, so that
    I open no inbound path through my firewall.
32. As a customer, I want mutual TLS and a strict command allow-list, so that only enumerated
    operations can run.
33. As a customer, I want an out-of-band safety interlock independent of the software path, so that
    a software compromise cannot defeat it.

## Implementation Decisions

**Starting point.** The **RabbitMQ broker seed** graduated from the CTM effort — priority P0/P1/P2,
per-channel DLQ, envelope transport, reference consumer with an idempotency store, DLQ poison
handling — **moves in by move-and-wire, not rewrite**.

**Three planes.** API Gateway (north–south, inline, synchronous) · Cloud Integration Gateway
(outbound protocol mediation, connectors, mapping, webhooks, hybrid agent) · broker plane
(east–west, asynchronous). Redis stays cache and result-backend only.

**Mediation rule, by counterparty.** External third party ⇒ always ESB/IG, both directions.
Sub-system ↔ sub-system ⇒ always ESB/IG. Product ↔ product not sharing a database ⇒ always ESB/IG.
Product ↔ product **sharing the tenant database** (IRM ↔ Procurement, driver-confirmed) ⇒ data over
the shared database, but **behavioural and cross-cutting events still ride ESB/IG**. **Product ↔
sub-system** (added by ADR-0001) ⇒ hot path (CTM tenant resolution, IAM identity verify) is an
in-process cached SDK with **no gateway hop**; asynchronous is the broker; **synchronous
off-hot-path — Translation's icon path — is the gateway plane**.

**Carve-outs.** The in-process business request path (a mediation hop cannot sit on a 2 ms budget —
the gateway-on-the-internal-hot-path anti-pattern) and the infrastructure edge (TLS/WAF/DDoS/CDN,
the CDN pillar, ratified managed/commodity, sitting **in front of** ESB/IG).

**Gateway identity.** The gateway is a **policy-enforcement point** (NIST SP 800-207): it validates
IAM tokens and API keys and resolves authorization against IAM, **mints and stores no credentials**,
denies by default per route, and binds tenant from the **verified token, never the Host** (N7).

**Egress security, fail-closed.** Allow-list deny-by-default (LOV, no hardcoded hosts) ·
parse-then-compare the resolved address · `http`/`https` only · block loopback, RFC1918,
link-local/metadata and IPv6 ULA · **resolve → validate → pin → connect to the pinned address**,
with redirects disabled or re-validated and re-pinned per hop · network-layer egress firewall as
defence in depth.

**Webhooks.** HMAC-SHA256 with a per-endpoint secret over the **raw body**, constant-time verify ·
signed timestamp bounding replay · idempotency on delivery id · retry with exponential backoff plus
**per-endpoint DLQ** · dual-secret rotation window · **no cross-tenant dispatch** — subscriptions
resolve strictly within the emitting tenant.

**Connectors and mapping.** A versioned connector registry (LOV): endpoints, protocol, auth profile,
retry policy, rate limit, egress allow-list and the mapping flow it uses. Protocol handlers are
generic REST/SOAP/EDI; specifics live in the connector. Mapping flows are declarative; the engine is
built now and the PO/Invoice/ASN catalogue graduates later. Mapping values carry **ISO codes, never
row ids** (ADR-0003).

**Hybrid agent.** Phase D, posture frozen now so the connector model accommodates it: outbound-only
gRPC, mutual TLS, strict command allow-list, out-of-band safety interlock, **monitoring and
orchestration only — never real-time equipment or grid protection** (N9). Compromise response is
designed in: revoke certificate, sever tunnel, verify allow-list, confirm interlock.

**Broker ownership.** ESB/IG owns the single RabbitMQ broker plane; **NC subscribes and builds no
broker of its own**. Closed by the NC effort on 2026-07-24; no longer fog.

**Sequencing.** **Wave 2** for Phases A–C, **wave 3** for D–F. This effort is on the **program
critical path**: Phase B (gateway) opens wave 3 for Translation, and Phase C (egress) opens it for
NC. Partner API-key validation completes only when IAM Phase E lands.

## Testing Decisions

**What makes a good test here.** For the egress guard, the test asserts the **attacker's** view: a
hostname that resolves to a blocked range is refused, an encoded address is refused, and a name that
changes between validation and connection cannot be reached — the last is only meaningful if the
test drives a resolver that answers differently on the second call, which is why pinning is tested
at the guard's seam rather than through a live socket. For webhooks, signature verification is
asserted **constant-time-safe and raw-body-based**, and a replayed delivery outside the tolerance is
rejected.

**Seams.** Use the shared model in
[CTM's spec](../../../CTM/wayfinder/ctm-control-plane/spec.md#testing-decisions). ESB/IG's centre of
gravity is **S2** (envelope semantics: at-least-once, dedupe on `event_id`, per-channel DLQ,
per-tenant/per-type ordering, additive evolution within a version, consumers upgrade before
producers) and **S4** (gateway as PEP: deny-by-default per route, token and API-key validation,
rate limit, request validation, version negotiation, HMAC verify, tenant from verified token).
**S3** covers the connector/mapping/rate-limit LOVs; **G** covers the boundary gate.

**Prior art.** `IAM/backend/tests/` is the estate's model — in particular `test_gates.py`'s
discipline of asserting **every detector against both a violating and a clean sample**, which
applies directly to each egress-guard and signature check here. The M-Development
`backend/integrations/` module is **read for patterns and never imported** (N3): its per-tenant
no-cross-tenant dispatcher and `event_id`-keyed delivery are the shape to adapt.

**Latency.** ESB/IG's added latency is a **build gate at p95 < 15 ms**. It is asserted, not
assumed, because it is the number the ADR-0001 decision was justified against.

## Out of Scope

- **Rebuilding the RabbitMQ broker seed** — it graduates from CTM by move-and-wire.
- **The infrastructure edge gateway, WAF, CDN and DDoS absorption** — infrastructure plane, ratified
  managed/commodity, in front of ESB/IG.
- **The other sub-systems' logic** — ESB/IG carries their traffic and implements none of it.
- **Card data.** External banking and payment systems are connector targets; ESB/IG carries messages
  to them and **never processes card data** (N8).
- **A tenant-facing container-orchestration product** (N9) — the hybrid agent is outbound-only and
  monitoring/orchestration-only.
- **Broker topology and routing-key design, contract-governance detail, the mapping-flow catalogue,
  rate-limit LOV specifics, observability and admin UX** — fog, graduating as the frontier advances.

## Further Notes

The build order is itself a control: **the governed path (Phase B) is built before the outbound
connectors (Phase C)**, so every connector is *born* behind the mediation point rather than
retrofitted behind it. A connector written first and mediated later is a connector that worked
unmediated once.
