---
id: T03
title: Cloud Integration Gateway — protocol handlers & connector/mapping model
labels: [wayfinder:grilling]
hitl: true
status: closed
blocked-by: [T01]
blocks: [T04, T06]
assignee: skbaidas@gmail.com
---

## Question

How does ESB/IG's **Cloud Integration Gateway** connect to external systems — what protocol handlers
does it host (REST/SOAP/EDI), and how are individual integrations (an ERP, a logistics provider, a
bank) added: as code, or as **configuration**?

## Recommended answer

**A protocol-handler set (REST/SOAP/EDI) driving a configuration-defined connector + mapping
registry — new integrations are added by configuration (an LOV/connector definition), not code.**

- **Protocol handlers** — three pluggable transports: **REST/JSON**, **SOAP/XML**, **EDI** (the
  three the SRS names). Each handler is generic; the specifics of a given endpoint live in a
  **connector definition**.
- **Connector registry (LOV / config, per the no-hardcoding rule):** each integration is a seeded,
  versioned **connector** row — endpoint URL(s), protocol, auth profile, retry policy, rate limit,
  and the **mapping flow** it uses. Adding a new ERP/logistics/bank is a **connector definition +
  mapping**, not a code change or deploy.
- **Mapping flows** — declarative field maps between the platform's canonical message and the
  external document (the SRS names **PO / Invoice / ASN** as the first document types); mapping-flow
  *content* is a later LOV catalog (fog), but the *engine* is built here.
- **Direction:** the CIG owns **outbound** initiation (platform → external) and the response leg;
  **inbound** partner API calls arrive through the API Gateway plane
  ([All APIs through ESB/IG](02-all-apis-through-esb-ig.md)) and are handed to the same mapping layer.
- Adapt the prior-art `backend/integrations/` structure (`contract.py` tables, dispatcher, delivery)
  as the outbound skeleton; docs win where they differ; no runtime import (N3).

## Why

- **Docs:** SRS §: ESB/IG = "mapping/protocol handlers (REST/SOAP/EDI); mapping flows (PO, Invoice,
  ASN)." That is exactly a handler set + a mapping/connector model.
- **No-hardcoding rule (MREQ):** an integration endpoint, its credentials profile, and its field map
  are all "values a business user could reasonably change" → they **must** be configuration/LOV, not
  literals. This is what makes "onboard a new external system without a code change" true.
- **Best practice / simplicity:** generic handlers + a connector registry is the standard ESB shape
  and avoids a bespoke module per integration; it also keeps `application_id` on every connector so
  the gateway is app-agnostic from day one.

## Applies globally

Fixes the outbound/mediation model every connector uses. Blocks
[Egress & webhook security](04-egress-webhook-security.md) (the security envelope around outbound
calls) and [Hybrid integration agent](06-hybrid-integration-agent.md) (on-prem connectors ride this
model). The mapping-flow *catalog* graduates from fog after this lands.

## Conflicts

None. Consistent with SEC-EVT-01 (all outbound via ESB/IG) and the no-hardcoding rule. External
**banking/payment** systems are legitimate connector *targets*, but ESB/IG carries messages to them
and **never processes card data** (N8) — see the map's *Out of scope*.

## Resolution (confirmed 2026-07-24 by the driver — closed)

**Confirmed:** **REST/SOAP/EDI** protocol handlers driving a **configuration-defined connector +
mapping registry (LOV)** — a new ERP/logistics/bank is a connector definition + mapping, **no code,
no deploy**. The mapping *engine* is built here; the PO/Invoice/ASN mapping *catalog* is later fog.
CIG owns **outbound** initiation + the response leg; inbound partner calls arrive via the gateway
plane into the **same** mapping layer; the hybrid agent is **one connector type**. `application_id`
on every connector. Adapts prior-art `backend/integrations/` (no runtime import — N3). Detail:
[developed design §7](../ESB-IG-developed-design.md).
