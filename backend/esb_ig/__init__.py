"""ESB/IG **seed** — the minimal broker slice CTM needs to develop and test.

Not the ESB/IG sub-system. A real, boundary-clean, relocatable slice that the
ESB/IG effort adopts later by **move-and-wire, with zero rework**.

Interface (this module): publish and subscribe. `esb_ig.envelope` is a **second
entry point** carrying the frozen envelope, because producers and
consumers need the envelope's *shape* without needing a broker.
`esb_ig.transport` is a **third**, and it is the one a consumer must not take —
see below.

**This is the estate's one real seam.** Two adapters exist — a message broker and
an in-memory fake — so the protocol earns its keep, and the fake is what makes
event semantics (dedupe on `event_id`, per-channel DLQ, per-tenant ordering)
testable with no infrastructure. Contrast `lov` and `db`, which have one adapter
each and therefore no protocol. See `design.md` §3.

Semantics that are part of this interface: **at-least-once, never
exactly-once**; ordering is per-tenant and per-type only; anything needing
global order is a command, not an event.

What that means for a caller, concretely:

* `Broker` is the protocol. `InMemoryBroker` needs nothing. **The deployment
  adapter is not on this surface**: `RabbitMqBroker` and the factory that
  builds one from configuration live on `esb_ig.transport`, because W2-T10
  ratifies that ESB/IG publishes exactly three things to a consumer — the
  protocol, the envelope and the double — and *"the RabbitMQ adapter is NOT
  published"*. It sat here until W2-T20, which meant every consumer **could**
  import it, and a consumer that can eventually will; at that point the
  contract is the transport rather than the protocol. Importing either module
  works with no driver installed; the refusal arrives at connect time, typed,
  as `BrokerUnavailableError`, and there is no code-side default connection
  URL (ADR-0005).
* **`InMemoryBroker` is part of this published interface, not a test fixture.**
  It is the **executable definition** of the semantics below — redelivery,
  per-channel dead-lettering, priority ordering — so every consumer shares one
  definition instead of reading the prose here and interpreting it
  independently. Import it, run your consumer against it, and what you observe
  is the contract. **Moving it under `tests/` would remove it from the
  contract**, which is a design decision and not a tidy-up. What makes it a
  definition rather than a second implementation is that both implementations
  answer one set of cases: `backend/tests/test_broker_conformance.py`, run
  against this adapter unconditionally and against the deployment adapter
  wherever a broker is configured — and *skipping the real half, which is not a
  pass* (§11.3) wherever one is not. That suite is the seed's own and relocates
  with it, which is why it may take `esb_ig.transport` where a consumer may
  not.
* **The substrate does not deduplicate.** Wrap a consumer in `deduplicating`
  with an `IdempotencyStore` and a redelivered envelope produces one effect,
  not two. A consumer that skips this will apply an effect twice, and that is
  the contract working as specified rather than a defect.
* **Ordering** holds per `Envelope.ordering_key` — `(tenant_alias, type)` — within
  a priority class, because a higher class is served first and a channel is
  consumed serially. A stream that needs strict order stays in one class;
  anything needing order *across* streams is a command, not an event.
* **A rejected message is dead-lettered per channel**, stays retrievable
  through `dead_letters`, and does not block what is behind it. Reading a
  dead-letter queue never empties it.
* **Fail closed:** delivering on a channel with no consumer, or subscribing
  twice, is refused rather than absorbed.

Who calls `publish` is not this package's business. `ctm`, `iam` and `esb_ig`
are one-way domains that never import each other (T12); the composition root
does the wiring (`design.md` §2), which is what lets this seed graduate by
moving a folder.

Built by ticket 14.
"""

from .lib.base import EsbIgError
from .lib.broker import (
    Broker,
    Consumer,
    DeadLetter,
    DeliveryReport,
    InMemoryBroker,
)
from .lib.consumer import IdempotencyStore, deduplicating
from .lib.errors import BrokerError, BrokerUnavailableError, ChannelError

__all__ = [
    "Broker",
    "BrokerError",
    "BrokerUnavailableError",
    "ChannelError",
    "Consumer",
    "DeadLetter",
    "DeliveryReport",
    "EsbIgError",
    "IdempotencyStore",
    "InMemoryBroker",
    "deduplicating",
]
