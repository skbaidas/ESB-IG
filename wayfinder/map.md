---
labels: [wayfinder:map]
kind: map
tracker: local-markdown
created: 2026-07-24
driver: skbaidas@gmail.com
subsystem: ESB-IG
---

# Map — ESB/IG sub-system build-ready decision baseline (greenfield)

> Sibling effort to CTM (`..\..\CTM\wayfinder\`) and IAM (`..\..\IAM\wayfinder\`). Index, not a
> store: each decision lives in its ticket under `tickets/`; the emerging plan is `plan.md`.
> Refer to tickets by **name**.

## Destination

A **build-ready delivery plan** for the **ESB/IG sub-system** — the platform-wide **L4 Enterprise
Service Bus / Integration Gateway** — built **greenfield in `D:\PMO\Phase 1\ESB-IG\`**, starting
from the **RabbitMQ broker seed** graduated out of the CTM effort and extending it to the full
ESB/IG surface across **three planes**:
- **API Gateway plane** (inline, synchronous) — the single **governed mediation point** for
  boundary-crossing API traffic in and out of the platform;
- **Cloud Integration Gateway** — outbound protocol mediation (REST/SOAP/EDI), mapping flows,
  SSRF-guarded signed webhooks, and the outbound-only hybrid on-prem agent;
- **broker plane** (async priority queues P0/P1/P2 + per-channel DLQ) — the governed message
  transport carrying the 10-field envelope for **all sub-system traffic**.

ESB/IG is the **single mandatory mediation point**: **no direct application-to-external path and no
unmediated cross-boundary API path** (SEC-EVT-01). It serves **all** platform sub-systems
app-agnostically and connects to consumers by **events/commands, not business calls** (N2/N3). The
map is done when every dependent decision is resolved and `plan.md` has no `pending →` left.

## Notes

**Operating rules (inherited from the CTM effort — apply to every ticket):** docs-first (settle from
docs, don't ask); **recommend, don't just ask** (docs → international standards → best practice,
simplest correct option, "no complexity"); decide once globally; flag conflicts (ratified decisions
win). Full statement: `..\..\CTM\wayfinder\tickets\10-sourcing-strategy.md`.

**Greenfield + prior art (inherited):** build fresh in this folder; **mine** the M-Development prior
art at `D:\PMO\Phase 1 old\Phase 1 M-Development` — it **does** contain a reusable
`backend/integrations/` module (webhook endpoints/subscriptions, per-tenant no-cross-tenant
dispatcher, `event_id`-keyed delivery, feature + fail-closed role gating) plus `tenancy/edge/` and
`apikeys/`. Adapt (docs win); never import at runtime (N3).

**Authoritative docs (until ESB/IG gets its own set):** the platform-wide CTM reference docs
(`..\..\CTM\References\`), especially **SRS §** (ESB/IG = single mediation point; gateway + broker
planes + REST/SOAP/EDI handlers), the **Cybersecurity Framework** (SEC-EVT-01, SEC-APP-03,
SEC-NET-02/06, hybrid-agent controls), and the **Infrastructure Architecture** (ingress path,
integration-latency floor).

**Seed handoff (the starting point — do NOT rebuild):** the CTM effort built a **RabbitMQ broker
seed** in `backend/esb_ig/` — priority P0/P1/P2 + per-channel DLQ · envelope transport for the
10-field contract · reference consumer + idempotency store (dedupe on `event_id`) · DLQ poison
handling. It graduates into this repo by **move + wire** (CTM ticket 12 boundary). This map extends
the seed to the full sub-system (gateway plane + Cloud Integration Gateway + protocol handlers).

**Reconciliation — broker ownership: ✅ CLOSED 2026-07-24 by the NC effort.** Both the **NC** box
(L3 "Event Broker · pub-sub") and the **ESB/IG** box (L4 "broker plane") reference a message broker
in the docs. This was left as fog here to avoid pre-empting the then-uncharted NC map; NC resolved it
in [NC build sequence & broker baseline](../../NC/wayfinder/tickets/01-nc-build-sequence.md):
**ESB/IG owns the single RabbitMQ broker plane; NC subscribes and owns only its internal delivery
pipeline, never a second broker** (EIP "message-broker spaghetti"; microservices.io). No longer fog.

**Boundary:** ESB/IG is a **sub-system** — it **never depends on a consumer application** (N3) and
is **not on the Layer-2 in-process business request path** (D-02, N2). It is enforced as a **one-way
domain** alongside `ctm`/`iam` (R-12, [CTM seed boundary enforcement](../../CTM/wayfinder/tickets/12-seed-boundary-enforcement.md)).
Every ESB/IG table carries `application_id`.

## Settled baseline (from docs / seed — adopt, do not re-decide)

- **SEC-EVT-01** — **one governed mediation point** for all external integration (ESB/IG); **no
  direct application-to-external paths**. *(The mandate the destination restates and extends to "all
  boundary-crossing APIs.")*
- **Three planes (SRS):** **gateway plane** (inline, synchronous) + **broker plane** (async priority
  queues P0/P1/P2 + per-channel DLQ) + **mapping/protocol handlers** (REST/SOAP/EDI).
- **Broker = RabbitMQ** (priority + per-channel DLQ), self-hosted in-estate — from the seed
  ([CTM ESB/IG seed](../../CTM/wayfinder/tickets/07-event-broker-selection.md)). Redis stays
  cache/result-backend only.
- **10-field envelope** as the wire contract; **at-least-once · dedupe on `event_id` · DLQ per
  channel · per-tenant/per-type ordering · additive evolution within a version**
  ([CTM event envelope](../../CTM/wayfinder/tickets/03-event-envelope-fields.md)).
- **SEC-APP-03** — **SSRF egress guard with DNS-rebind pinning** on **all** outbound integration.
- **SEC-NET-06** — **signed webhooks**, at-least-once delivery, DLQ, rate limiting.
- **Hybrid agent** — **outbound-only gRPC**, mutual TLS + strict command allow-list + out-of-band
  safety interlock; **monitoring/orchestration only, never real-time equipment protection** (N9-adjacent).
- **Latency floor (build gate):** ESB/IG **integration added p95 < 15 ms**.
- **Edge / WAF / TLS-termination / DDoS is the *infrastructure* plane** (CDN pillar, SEC-NET-02;
  ratified managed/commodity in [CTM infra posture](../../CTM/wayfinder/tickets/08-infra-build-vs-partner.md)) —
  it sits **in front of** ESB/IG and is **not** part of this sub-system. ESB/IG is the *application-tier*
  API Gateway; the edge network gateway is a separate layer.
- **Stack:** platform stack (Python · FastAPI · Celery · RabbitMQ · Redis · PostgreSQL · Alembic);
  **PostgreSQL for SQL + NoSQL (JSONB)**; self-hosted in-estate; `application_id` on every table.

## Decisions so far

<!-- one line per CLOSED ticket -->

- [ESB/IG build sequence](tickets/01-esb-ig-build-sequence.md) — six-phase sequence **A Foundations →
  B API Gateway plane → C Cloud Integration Gateway → D Hybrid agent → E Contract governance/
  observability → F Admin UX & hardening** (governed path built before outbound connectors).
- [All APIs & integrations through ESB/IG](tickets/02-all-apis-through-esb-ig.md) — **Reading B by
  counterparty:** external & sub-system↔sub-system ⇒ **always** ESB/IG; product↔product ⇒ **ESB/IG by
  default**, with a data-plane branch **only** for products co-located on the shared tenant DB
  (IRM↔Procurement — driver-confirmed) whose behavioral events **still** ride ESB/IG; in-process hot
  path + infra edge are carve-outs.
- [Cloud Integration Gateway](tickets/03-cloud-integration-gateway.md) — REST/SOAP/EDI handlers +
  **connector/mapping registry as LOV** (new integration = configuration, not code); mapping engine
  now, PO/Invoice/ASN catalog later.
- [Egress & webhook security](tickets/04-egress-webhook-security.md) — SSRF egress guard (allow-list,
  IP-pin, DNS-rebind, blocked metadata ranges) + signed webhooks (HMAC, signed-timestamp,
  constant-time, idempotency, per-endpoint DLQ); fail-closed, no cross-tenant.
- [Gateway identity enforcement](tickets/05-gateway-identity-enforcement.md) — gateway = **PEP** (NIST
  800-207): validates IAM tokens / SEC-IAM-08 API keys, deny-by-default, mints no credentials, fails
  closed.
- [Hybrid integration agent](tickets/06-hybrid-integration-agent.md) — **Phase D**; outbound-only
  mTLS gRPC, command allow-list, out-of-band interlock, monitoring/orchestration only (N9); one
  connector type.

- [Research — gateway/ESB/CIG responsibilities](tickets/07-research-gateway-esb-cig-responsibilities.md) —
  three-plane split (API Gateway = north–south; ESB = mediation/transport; iPaaS/CIG = outbound
  connectors); gateway-on-internal-hot-path is an anti-pattern; gateway = PEP delegating authN to the
  central IdP (NIST 800-207).
- [Research — integration styles / shared-DB](tickets/08-research-integration-styles-shared-db.md) —
  shared-DB integration is legitimate **only** within one bounded context / single schema owner;
  across independently-evolving products/sub-systems a shared DB is itself the anti-pattern → **ESB/IG
  by default**; behavioral/cross-cutting events ride ESB/IG even when a DB is shared. *(Inverts the
  emphasis of the driver's literal rule — flagged for ratification in T02.)*
- [Research — egress & webhook security](tickets/09-research-egress-webhook-security.md) — adopted
  SSRF checklist (allow-list deny-by-default, parse-then-compare IP, DNS-rebind resolve-pin-connect,
  block metadata ranges, no redirects) + webhook checklist (HMAC-SHA256 raw-body, signed-timestamp
  replay bound, constant-time verify, idempotency, retry+backoff+per-endpoint DLQ, rotation).

> **Developed design & integration chart:** [`ESB-IG-developed-design.md`](ESB-IG-developed-design.md)
> holds the full three-plane design, the complete in/out integration inventory (the chart), and the
> topology diagram. **All nine tickets are now closed** — T01–T06 confirmed by the driver on
> 2026-07-24 (including ratification of the shared-DB inversion and the IRM/Procurement-share-DB
> fact); T07–T09 are research. **The whole ESB/IG decision baseline is settled**; what remains is the
> fog below (topology/routing keys, contract governance, mapping
> catalog, observability, admin UX) plus execution.

### Cross-effort decisions — 2026-07-25 (`/grill-with-docs`)

Resolved across all five efforts after the baselines closed; recorded as ADRs in
`..\..\CTM\docs\adr\` (the platform root). Pointers, not copies.

- [ADR-0001 — Product-to-sub-system invocation](../../CTM/docs/adr/0001-product-to-subsystem-invocation.md)
  — **modifies T02 and the chart.** The ratified counterparty table had **no product ↔ sub-system
  row**; it gains one, routed by latency class: hot path (CTM tenant resolution, IAM identity verify)
  = in-process cached SDK with **no** gateway hop; async (NC) = broker plane; **synchronous
  off-hot-path (Translation) = the gateway plane**. Chart **row 11 is superseded** for the
  product-invoked case — it read "broker plane *or* mediated gateway API"; for a product calling
  Translation it is the gateway plane.
- [ADR-0002 — IAM owns no mail path](../../CTM/docs/adr/0002-iam-notifications-via-nc.md) — a new
  `iam.*` transactional/P0 event family rides the broker plane to NC.
- [ADR-0003 — Reference data pack](../../CTM/docs/adr/0003-reference-data-pack.md) — ESB/IG seeds its
  own country/currency LOVs from the shared versioned pack; **mapping flows and connector definitions
  carry ISO codes, never row ids**.
- [ADR-0004 — One platform admin shell](../../CTM/docs/adr/0004-single-platform-admin-shell.md) — the
  Phase-F ESB/IG admin UX (connector/webhook/route config, **DLQ replay/poison operations**) becomes
  a lazy-loaded admin module inside the CTM-owned platform shell.
- **Program sequencing:** this effort is **wave 2** for Phases A–C, **wave 3** for D–F. Its Phase B
  (gateway) and Phase C (egress) are the events that **open wave 3 for Translation and NC**. Full
  table: [`..\..\CTM\wayfinder\plan.md`](../../CTM/wayfinder/plan.md).

## Not yet specified

<!-- in-scope fog; graduates to tickets as the frontier advances -->

- **Broker topology & routing-key design** (exchanges, per-tenant/per-type routing keys, ordering
  guarantees) — sharpens after the build sequence lands; partly fixed by the envelope contract.
- **API versioning & contract governance** (each sub-system publishes a versioned contract + client
  SDK; the gateway negotiates versions) — graduates after the gateway-plane scope is fixed.
- **Mapping-flow catalog** (PO / Invoice / ASN and future document types as LOV-configured maps) —
  graduates after the Cloud Integration Gateway model lands.
- **Rate-limit / quota LOV specifics** (per-tenant, per-role, per-connector limits) — LOV-configurable;
  graduates in the gateway-hardening phase.
- **Observability** (correlation_id propagation, distributed tracing, per-tenant integration
  health/incident monitoring) — sharpens once the planes are in place.
- **ESB/IG admin UX** (connector/webhook/route configuration screens; DLQ replay/poison operations) —
  graduates in the UX phase.

## Out of scope

<!-- ruled beyond the destination; never graduates -->

- **The other sub-systems** — CTM (control plane), IAM, NC, Translation — separate efforts. ESB/IG
  only *carries* their traffic; it does not implement their logic.
- **The infrastructure edge gateway / WAF / CDN / DDoS absorption** — infrastructure plane (CDN
  pillar), ratified commodity/managed. Sits in front of ESB/IG, not inside it.
- **Re-building the RabbitMQ broker seed** — it graduates from CTM by move + wire, not re-development.
- **PCI / card handling / payment processing** — external banking/payment systems are *connector
  targets*; ESB/IG carries messages to them but **never processes card data** (N8).
- **A tenant-facing container-orchestration product** (N9) — the hybrid agent is outbound-only,
  monitoring/orchestration-only, and is *not* such a product.
