---
id: T04
title: Outbound egress & webhook security posture
labels: [wayfinder:grilling]
hitl: true
status: closed
blocked-by: [T03]
blocks: []
assignee: skbaidas@gmail.com
---

## Question

What is the security envelope around **outbound** traffic from the Cloud Integration Gateway —
the SSRF egress guard, webhook signing, the egress allow-list, and the delivery/retry/DLQ policy?

## Recommended answer

**Adopt the doc-mandated controls, implemented on top of the prior-art `integrations/` dispatcher —
fail-closed by default.**

- **SSRF egress guard with DNS-rebind pinning** on **every** outbound call (SEC-APP-03): resolve
  once, pin the IP, re-validate on redirect, and **deny by default** — block private/link-local/
  metadata ranges unless a connector's egress allow-list explicitly permits a destination.
- **Signed webhooks** (SEC-NET-06): HMAC request signing with per-endpoint secrets, a signed
  timestamp to bound replay, and constant-time verification on any inbound callback.
- **Delivery semantics:** at-least-once, **per-endpoint DLQ**, exponential-backoff retry, and
  **per-tenant/per-connector rate limiting**; poison payloads isolate to the DLQ, never dropped —
  consistent with the broker-plane envelope contract (dedupe on `event_id`).
- **No cross-tenant delivery:** the dispatcher resolves subscriptions strictly within the emitting
  tenant (carry over the prior-art `WEBHOOK-08 / INTEG-06` no-cross-tenant guarantee).
- **Reuse the prior art:** `integrations/delivery.py` (`deliver_webhook`), `dispatcher.py`
  (per-tenant fan-out, `event_id` keying), `contract.py` (endpoint/subscription tables, feature +
  fail-closed manage-role gate). Adapt to the ESB/IG repo; docs win; no runtime import (N3).

## Why

- **Docs:** SEC-APP-03 (SSRF egress guard + DNS-rebind pinning on all outbound integration) and
  SEC-NET-06 (signed, SSRF-guarded webhooks with at-least-once, DLQ, rate limiting) are explicit
  control requirements; the threat model calls SSRF-via-webhooks and object-storage/egress abuse out
  by name.
- **Prior art exists** — unlike most of ESB/IG, the outbound webhook path is already implemented in
  M-Development (`backend/integrations/`), so this is adapt-and-harden, not greenfield invention.
- **Best practice / simplicity:** deny-by-default egress + signed callbacks + DLQ is the standard,
  minimal secure-webhook posture; reusing the proven dispatcher avoids re-deriving delivery mechanics.

## Applies globally

Sets the outbound security envelope for **all** connectors and webhooks built on the Cloud
Integration Gateway model ([Cloud Integration Gateway](03-cloud-integration-gateway.md)). The
hybrid agent ([Hybrid integration agent](06-hybrid-integration-agent.md)) inherits the same
deny-by-default, allow-list posture at the on-prem boundary.

## Conflicts

None. Implements SEC-APP-03 / SEC-NET-06 and fail-closed-on-security-paths; reuses prior art the
CTM sourcing strategy already sanctioned (docs win, N3 no runtime coupling).

## Resolution (confirmed 2026-07-24 by the driver — closed)

**Confirmed:** fail-closed outbound envelope. **SSRF egress guard** — allow-list deny-by-default
(LOV hosts), parse-then-compare resolved IP, `http`/`https` only, block loopback/RFC1918/link-local
+ metadata `169.254.169.254`/IPv6-ULA/multicast, **DNS-rebind resolve → pin → connect**, redirects
disabled (or re-validated + re-pinned per hop). **Signed webhooks** — HMAC-SHA256 over raw body with
per-endpoint secret, signed-timestamp replay bound, constant-time verify, idempotency/dedupe on
`event_id`, retry + exponential backoff + **per-endpoint DLQ**, dual-secret rotation. **No
cross-tenant delivery.** Grounded in [T09](09-research-egress-webhook-security.md). Detail:
[developed design §8](../ESB-IG-developed-design.md).
