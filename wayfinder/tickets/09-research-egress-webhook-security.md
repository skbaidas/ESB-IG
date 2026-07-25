---
id: T09
title: "Research — Outbound egress & webhook security best practice (SSRF, DNS-rebind pinning, HMAC signing)"
labels: [wayfinder:research]
hitl: false
status: closed
blocked-by: []
blocks: []
assignee: skbaidas@gmail.com
---

## Question

Ground the outbound security envelope (SEC-APP-03 / SEC-NET-06). Best-practice controls for **SSRF
prevention** on outbound calls (egress allow-list; DNS-rebind resolve-then-pin + re-validate on
redirect; block private / link-local / cloud-metadata `169.254.169.254` ranges; decimal/IPv6-mapped
bypasses) and **webhook security** (HMAC signing with per-endpoint secrets; signed timestamp to
bound replay; constant-time verify; retry + exponential backoff + DLQ; idempotency keys)?

## Arms
T04 (egress & webhook security envelope), T06 (hybrid-agent boundary posture).

## Resolution (research — closed)

**SSRF / egress checklist (adopted, design §8):** allow-list + **deny by default**; **parse-then-
compare the resolved IP** (defeats decimal/octal/hex/IPv6-mapped encodings); scheme = `http`/`https`
only; block loopback / RFC1918 / **link-local+metadata `169.254.169.254`** / IPv6 ULA `fd00::/8` /
multicast; **DNS-rebind defense = resolve → validate → pin the IP → connect to the pinned IP** (no
re-resolve); **disable redirects** (or cap + re-validate + re-pin per hop); network-layer egress
firewall as defence-in-depth.

**Webhook-security checklist (adopted):** **HMAC-SHA256** over the **raw body** with a **per-endpoint
secret**; **constant-time** comparison; **signed timestamp** + replay window (reject stale);
**idempotency/dedupe** on delivery id (`event_id`, at-least-once); **retry + exponential backoff +
per-endpoint DLQ**; **secret rotation** (dual-secret window). No cross-tenant delivery (prior-art
dispatcher guarantee).

**Sources:** OWASP SSRF Prevention Cheat Sheet
(cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html) ·
PortSwigger Web Security Academy (SSRF) · Stripe (docs.stripe.com/webhooks) · Svix
(docs.svix.com/receiving/verifying-payloads/how) · GitHub (validating webhook deliveries).
