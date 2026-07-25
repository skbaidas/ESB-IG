---
labels: [wayfinder:plan]
kind: plan
status: emerging
subsystem: ESB-IG
---

# ESB/IG sub-system greenfield build plan (emerging)

> Fills in as decision tickets close. `pending → <ticket>` marks a section blocked on a decision;
> `fog →` marks deliberate fog. Starts from the graduated **RabbitMQ broker seed**; grounded in the
> platform docs and the **SEC-EVT/APP/NET** control catalogue. Simplicity is a hard constraint.

> **Status (2026-07-24):** **all decision tickets T01–T06 are confirmed & closed** (research T07–T09
> closed too). The full three-plane design, the in/out integration inventory, and the topology diagram
> are developed in [`ESB-IG-developed-design.md`](ESB-IG-developed-design.md). Each `resolved →` marker
> below points to its closed ticket; the remaining `fog →` items are the live frontier.

## Starting point: the graduated seed

The ESB/IG broker seed built in the CTM effort **moves into this repo** (move + wire, not rewrite):
RabbitMQ (priority P0/P1/P2 + per-channel DLQ) · envelope transport for the 10-field contract ·
reference consumer + idempotency store (dedupe on `event_id`) · DLQ poison handling. Everything
below **extends** it. Build sequence: `resolved →`
[ESB/IG build sequence from the seed](tickets/01-esb-ig-build-sequence.md)

> **Program sequencing (2026-07-25):** this effort is **wave 2** for Phases A–C and **wave 3** for
> D–F. Its **Phase B (gateway) and Phase C (egress) are the events that open wave 3 for Translation
> and NC** — ESB/IG sits on the program critical path. Full wave table:
> [`..\..\CTM\wayfinder\plan.md`](../../CTM/wayfinder/plan.md).

## Phase A — Foundations (from the seed)

- Graduate the broker seed into `D:\PMO\Phase 1\ESB-IG\` with its tests; wire CI gates (boundary
  one-way-domain, hardcoding/LOV, least-privilege, performance p95<15ms, lint).
- Confirm the seed's envelope transport, at-least-once, dedupe-on-`event_id`, per-channel DLQ carry
  forward green against a real RabbitMQ.

## Phase B — API Gateway plane (the mediation mandate)

- **"All boundary-crossing APIs & integrations go through ESB/IG"** — scope, the in-process hot-path
  carve-out, and the edge-vs-ESB gateway split: `resolved →`
  [All APIs & integrations through ESB/IG](tickets/02-all-apis-through-esb-ig.md)
- **Gateway identity enforcement** — ESB/IG as a policy-enforcement point that delegates authN to
  IAM; partner API-key verification (SEC-IAM-08): `resolved →`
  [Gateway identity enforcement](tickets/05-gateway-identity-enforcement.md)
- **Product ↔ sub-system routing row (added 2026-07-25):** the gateway carries **synchronous,
  off-hot-path product→sub-system calls — Translation's translation-icon path**. Hot-path calls
  (CTM tenant resolution, IAM identity verify) stay an in-process cached SDK and **never** touch the
  gateway (N2, p95 < 2 ms); async goes to the broker.
  [ADR-0001](../../CTM/docs/adr/0001-product-to-subsystem-invocation.md).
  **Completing this phase unblocks Translation Phase B.**
- **Partner API-key validation completes in wave 3** — SEC-IAM-08 keys land in IAM Phase E. Token
  validation against the graduated IAM seed works from this phase.
- Rate-limit / quota LOV, request validation, HMAC verification: `fog →` (LOV specifics graduate here).

## Phase C — Cloud Integration Gateway (outbound mediation)

- **Protocol handlers (REST/SOAP/EDI) + connector/mapping model** (connector registry as LOV):
  `resolved →` [Cloud Integration Gateway](tickets/03-cloud-integration-gateway.md)
- **Outbound egress & webhook security** — SSRF guard + DNS-rebind pinning + signed webhooks +
  egress allow-list + retry/DLQ (adapt prior-art `integrations/`): `resolved →`
  [Egress & webhook security](tickets/04-egress-webhook-security.md)
- Mapping-flow catalog (PO / Invoice / ASN as LOV maps): `fog →` (graduates after the model lands).
  Maps carry **ISO codes, never row ids** — [ADR-0003](../../CTM/docs/adr/0003-reference-data-pack.md).
- **Completing this phase unblocks NC Phase C** — NC's channels ride this egress point (the ratified
  HYBRID split: NC owns the deliverability brain, ESB/IG owns the wire).

## Phase D — Hybrid on-prem integration

- **Hybrid agent** — outbound-only gRPC, mTLS, command allow-list, out-of-band interlock,
  monitoring/orchestration only; in-scope-now vs deferred: `resolved →`
  [Hybrid integration agent](tickets/06-hybrid-integration-agent.md)

## Phase E — Contract governance & observability

- API versioning + per-sub-system versioned contracts/client SDKs; correlation_id propagation,
  distributed tracing, per-tenant integration health/incident monitoring: `fog →`.

## Phase F — Admin UX & hardening

- ESB/IG admin UI (connector/webhook/route config; DLQ replay/poison operations) — built as a
  **lazy-loaded admin module inside the CTM-owned platform admin shell**, not a standalone app:
  [ADR-0004](../../CTM/docs/adr/0004-single-platform-admin-shell.md). Full integration pentest (SSRF,
  egress, hybrid-agent pivot); latency p95<15ms gate; UAT: `fog →` (graduates here).

## Prior art — reusable from M-Development
Adapt (re-housed to the ESB/IG repo; docs win; no runtime import — N3). Inventory:
- **C** ← `backend/integrations/` — `contract.py` (webhook endpoint/subscription tables,
  `FEATURE_OUTBOUND_INTEGRATIONS`, fail-closed manage-role set), `dispatcher.py` (per-tenant
  no-cross-tenant fan-out, `event_id` keying), `delivery.py` (`deliver_webhook`), `dependency.py`
  (feature + fail-closed role gates).
- **B** ← `tenancy/edge/contract.py` (edge contract), `apikeys/` (SEC-IAM-08 API-key verification,
  for partner-API auth at the gateway).
