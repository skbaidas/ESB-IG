---
id: T06
title: Hybrid on-prem integration agent — scope & posture
labels: [wayfinder:grilling]
hitl: true
status: closed
blocked-by: [T03]
blocks: []
assignee: skbaidas@gmail.com
---

## Question

The docs specify a **hybrid agent** for reaching a customer's on-premises estate. Is it in ESB/IG's
initial scope or deferred, and what is its exact security posture?

## Recommended answer

**Build it as a later ESB/IG phase (Phase D), to the doc-mandated posture — but freeze the posture
now so the connector model accommodates it.**

- **Outbound-only gRPC** from the on-prem agent to the platform — the platform never dials into the
  customer network; there is **no inbound internet path** to on-prem.
- **Mutual TLS** (agent certificate + platform), a **strict command allow-list** (only enumerated,
  named commands execute), and an **out-of-band safety interlock** independent of the software path.
- **Monitoring / orchestration only — never real-time equipment protection or grid control.** The
  agent observes and issues allow-listed orchestration commands; it is **not** a control-loop element
  and **not** a tenant-facing orchestration product (N9).
- **Compromise response is designed in:** revoke the agent certificate, sever the tunnel, verify
  allow-list integrity, confirm the interlock held.
- **Scope now:** the connector model ([Cloud Integration Gateway](03-cloud-integration-gateway.md))
  treats the hybrid agent as one connector *type* so nothing is retrofitted; the agent itself builds
  after the outbound gateway and egress security land.

## Why

- **Docs:** the interface + threat model fix this posture verbatim (outbound-only mTLS, allow-list,
  out-of-band interlock, monitoring/orchestration-only); the risk register flags "hybrid agent as an
  on-premises foothold" as Med-High with exactly these mitigations.
- **Best practice / simplicity:** on-prem reach is a distinct, higher-risk surface; sequencing it
  after the core gateway keeps early phases simple, while freezing the posture now prevents a
  connector-model redesign later. Deferring the *build* is not deferring the *design*.

## Applies globally

Adds the on-prem connector type to the Cloud Integration Gateway model and sets its non-negotiable
security posture. Confirms N9 boundary (no tenant-facing orchestration product) for this sub-system.

## Conflicts

None. Matches the interface spec and threat model exactly; reinforces N9. External real-time
equipment/grid protection is explicitly excluded (safety-critical control stays out of the platform).

## Resolution (confirmed 2026-07-24 by the driver — closed)

**Confirmed:** built in **Phase D**, posture **frozen now** so the connector model accommodates it —
**outbound-only gRPC** (no inbound internet path to on-prem), **mutual TLS**, **strict command
allow-list**, **out-of-band safety interlock**, **monitoring/orchestration only — never real-time
equipment or grid protection** (N9). Modeled as one connector *type* on the CIG so nothing is
retrofitted; compromise response designed in (revoke cert, sever tunnel, verify allow-list, confirm
interlock). Detail: [developed design §10](../ESB-IG-developed-design.md).
