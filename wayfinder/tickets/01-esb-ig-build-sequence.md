---
id: T01
title: ESB/IG build sequence from the broker seed
labels: [wayfinder:grilling]
hitl: true
status: closed
blocked-by: []
blocks: [T02, T03]
assignee: skbaidas@gmail.com
---

## Question

Given the graduated **RabbitMQ broker seed**, what is the phase order that takes ESB/IG from that
seed to the full **L4 Enterprise Service Bus / Integration Gateway** — the API Gateway plane, the
Cloud Integration Gateway, and the broker plane — without re-litigating the doc-settled baseline?

## Recommended answer

**Graduate the seed, then build outward in six phases** (mirrors the CTM/IAM keystone pattern):

- **A — Foundations (from the seed):** move + wire the RabbitMQ broker seed (priority + per-channel
  DLQ + envelope transport + idempotency + DLQ handling) into `D:\PMO\Phase 1\ESB-IG\`; stand up the
  CI gates (one-way-domain boundary, hardcoding/LOV, least-privilege, **perf p95 < 15 ms**, lint).
- **B — API Gateway plane:** the "all boundary-crossing APIs through ESB/IG" mediation mandate +
  identity enforcement (delegate to IAM) + rate-limit/validation.
- **C — Cloud Integration Gateway:** protocol handlers (REST/SOAP/EDI) + connector/mapping model +
  outbound egress & webhook security (adapt prior-art `integrations/`).
- **D — Hybrid on-prem integration:** outbound-only mTLS gRPC agent, allow-list, interlock.
- **E — Contract governance & observability:** API versioning, correlation_id/tracing, per-tenant
  integration health.
- **F — Admin UX & hardening:** connector/webhook config UI, DLQ replay ops, integration pentest, UAT.

The **baseline** (three planes, RabbitMQ, 10-field envelope, SSRF/webhook controls, hybrid-agent
constraints, 15 ms floor, edge-gateway-is-infra) is **adopted, not re-decided** — see the map's
*Settled baseline*.

## Why

- **Docs:** the SRS fixes the three planes and the mediation mandate; the seed already delivers the
  broker plane, so foundations = graduate-and-verify, and the net-new surface is the two gateway
  planes. Building the governed path (B) before the outbound connectors (C) means every connector is
  born behind the mediation point (SEC-EVT-01) rather than retrofitted.
- **Best practice / simplicity:** one keystone that sequences the effort and pins the adopted
  baseline, so downstream tickets decide *only* what is genuinely open — no re-derivation.

## Applies globally

Keystone. Fixes the phase skeleton of `plan.md`; every other ESB/IG ticket slots into a phase and
inherits the adopted baseline. Blocks T02–T06.

## Conflicts

None. It operationalizes the SRS three-plane model and the confirmed CTM seed decisions; it does not
alter any ratified decision.

## Resolution (confirmed 2026-07-24 by the driver — closed)

**Confirmed:** the six-phase sequence **A Foundations (graduate + wire the broker seed; CI gates) →
B API Gateway plane → C Cloud Integration Gateway → D Hybrid agent → E Contract governance &
observability → F Admin UX & hardening**. Building the governed path (B) before the outbound
connectors (C) means every connector is born behind SEC-EVT-01, not retrofitted. Fixes the `plan.md`
phase skeleton; unblocks T02 and T03. Detail: [developed design §11](../ESB-IG-developed-design.md).
