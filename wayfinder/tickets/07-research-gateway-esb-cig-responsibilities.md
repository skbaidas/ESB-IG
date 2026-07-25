---
id: T07
title: "Research — API Gateway vs ESB vs Cloud Integration Gateway: responsibilities, boundaries, on-critical-path anti-pattern"
labels: [wayfinder:research]
hitl: false
status: closed
blocked-by: []
blocks: []
assignee: skbaidas@gmail.com
---

## Question

Ground the ESB/IG plane model in best practice. (1) What responsibilities belong to an **API
Gateway** (north–south, boundary) vs an **ESB / integration layer** (mediation, transformation,
routing, connectors) vs a **Cloud Integration Gateway / iPaaS** (managed connector catalog, hybrid
connectivity agent, B2B/EDI, mapping designer)? (2) Confirm the anti-pattern of placing an API
gateway on the internal east–west service-to-service critical path (per-hop latency; gateway vs
service mesh). (3) The gateway-as-**Policy-Enforcement-Point (PEP)** delegating authN to a central
Identity Provider (zero-trust) pattern.

## Arms
T02 (plane scope), T03 (Cloud Integration Gateway model), T05 (gateway identity / PEP).

## Resolution (research — closed)

**(1) Responsibility split (adopted as the three-plane model, design §2):**
- **API Gateway = north–south / boundary:** single entry point, path/version routing, TLS
  termination, authN/authZ delegation, rate-limit/throttle, request validation, versioning, quota,
  monitoring (Azure Gateway Routing/Offloading; microservices.io; AWS API Gateway).
- **ESB / integration layer = east–west + outbound:** content-based routing, message
  transformation/translation, guaranteed delivery, connectors (EIP Content-Based Router, Message
  Translator, Guaranteed Delivery, Message Broker).
- **Cloud Integration Gateway / iPaaS = outbound integration:** managed connector catalog, B2B/EDI,
  visual mapping, orchestration, hybrid/on-prem connectivity agent, embedded API management (Gartner
  iPaaS).

**(2) Anti-pattern confirmed:** gateways belong at the **edge** (untrusted north–south); internal
service-to-service (east–west) is the service mesh's job. A centralized gateway proxy on the internal
per-call path adds a network hop — *"proxies introduce additional hops in the data path, which can
increase latency"* (Kong; CNCF). ⇒ ESB/IG must **not** sit on the in-process business hot path
(reinforces N2, the < 2 ms budget).

**(3) PEP pattern:** the gateway is a **Policy-Enforcement-Point** that *"mediates access… requests
authorization decisions from the PDP… and enforces those decisions"* and must be **non-bypassable**
(NIST SP 800-207). It issues no credentials — it **validates tokens** minted by the central IdP.
⇒ ESB/IG = PEP; IAM owns identity (design §6, §11 / T05).

**Sources:** microservices.io/patterns/apigateway.html · learn.microsoft.com Gateway Routing &
Offloading · aws.amazon.com/api-gateway · enterpriseintegrationpatterns.com (Content-Based Router,
Message Translator, Guaranteed Delivery, Message Broker) · gartner.com iPaaS glossary ·
konghq.com & cncf.io (gateway vs service mesh) · NIST SP 800-207.
