---
id: T05
title: Gateway identity enforcement — delegate authN to IAM (PEP model)
labels: [wayfinder:grilling]
hitl: true
status: closed
blocked-by: [T02]
blocks: []
assignee: skbaidas@gmail.com
---

## Question

When an inbound API call reaches ESB/IG's gateway plane, **how is the caller authenticated and
authorized** — does ESB/IG own identity, or does it delegate? And how are **partner/service** callers
(API keys) handled versus interactive users (tokens)?

## Recommended answer

**ESB/IG is a Policy-Enforcement Point (PEP), not an identity authority. It verifies and enforces;
IAM owns identity.**

- **Interactive/user tokens:** ESB/IG validates the IAM-issued token (signature, expiry,
  token-version) and enforces the route's capability requirement **deny-by-default**; it never mints
  or stores credentials. Authorization decisions resolve against IAM's model
  (`..\..\IAM\wayfinder\tickets\02-roles-permissions-authorization.md`).
- **Partner/service callers:** verified by **API key** (SEC-IAM-08) — hashed at rest, shown once,
  capability-scoped, revocable, audited by prefix — reusing the prior-art `apikeys/` verification.
  The key resolves to a principal + `(tenant × application)` scope; ESB/IG enforces that scope.
- **Fail closed:** unresolved identity, unknown key, missing capability, or unreachable IAM →
  **deny** (no fail-open path — a release blocker if violated).
- **No identity data in ESB/IG:** the gateway holds routing/rate-limit/connector config and a cache
  of verification material; principals, roles, memberships, MFA and keys stay owned by IAM. Contact
  with IAM is via its published contract, never a business call that couples the sub-systems (N2/N3).

## Why

- **Docs:** IAM is the L1 identity sub-system and the platform's single IdP; the boundary rule is
  that a sub-system "never depends on a consumer application" and sub-systems connect by
  events/commands/published contracts. An ESB/IG that re-implemented identity would duplicate IAM and
  reopen SoD/authz surface.
- **Best practice / simplicity:** gateway-as-PEP + central IdP is the standard zero-trust pattern —
  one place owns identity (IAM), one place enforces at the boundary (ESB/IG). API-key handling reuses
  an already-implemented, audited control (SEC-IAM-08) rather than inventing a second credential path.

## Applies globally

Fixes how the gateway plane ([All APIs through ESB/IG](02-all-apis-through-esb-ig.md)) authenticates
every inbound boundary-crossing call. Establishes the ESB/IG↔IAM contract dependency (delegation,
not coupling) that the build sequence must honor as a one-way domain.

## Conflicts

- **Touches IAM (a separate effort):** this decision commits ESB/IG to *delegating* — it does **not**
  change any IAM decision, and it is consistent with IAM's sole-ownership of identity and SEC-IAM-08.
  If the IAM effort later refines the token/API-key contract, ESB/IG adopts it additively (versioned
  contract). No contradiction with a ratified decision.

## Resolution (confirmed 2026-07-24 by the driver — closed)

**Confirmed:** the gateway plane is a **Policy-Enforcement-Point** (NIST SP 800-207), not an identity
authority. It validates IAM-issued **tokens** (signature, expiry, token-version) or partner **API
keys** (SEC-IAM-08 — hashed, shown-once, capability-scoped, revocable, audited by prefix), enforces
the route's capability **deny-by-default**, mints/stores **no credentials**, and **fails closed** on
unresolved identity / unknown key / missing capability / unreachable IAM. IAM owns identity; ESB/IG
reaches it only via its published contract (N2/N3). Grounded in
[T07](07-research-gateway-esb-cig-responsibilities.md). Detail:
[developed design §6](../ESB-IG-developed-design.md).
