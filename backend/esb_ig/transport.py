"""ESB/IG's **deployment adapter** — a third entry point, and not a consumer's.

`esb_ig` publishes the *contract*: the `Broker` protocol, the errors, the
reference consumer and the conformance double. `esb_ig.envelope`
publishes the envelope. This module publishes the thing neither of those may
carry — the concrete RabbitMQ implementation and the factory that builds one
from deployment configuration.

**Why it is a separate entry point rather than a name on the package.** W2-T10
ratifies that ESB/IG publishes exactly three things to a consumer — the
protocol, the envelope and the double — and that *"the RabbitMQ adapter is NOT
published"*. Until W2-T20 the adapter sat on the same surface as the protocol,
so **every consumer could import it**, and a consumer that can import a
transport eventually does: at that point the contract is the transport rather
than the protocol, and the seed cannot graduate without breaking somebody. The
split makes that rule *expressible* — a consumer's import either names this
module or it does not — which is what
`scripts/check_graduation.py`'s ``transport-in-a-stay-behind-consumer`` finding
reads.

**Who may import this.** The seed itself, and the seed's own tests, which
relocate with it. **Nothing that stays behind in CTM** — not `wiring`, which is
the composition root and stays. A composition root that needs a live broker
takes one built elsewhere: either a `Broker` handed in from deployment
configuration, or a factory ESB/IG publishes for the purpose. Neither route
names this module in a CTM file, which is what makes the graduation a file
operation.

**A curated re-export, deliberately not a file move.** The implementation stays
in `lib/rabbitmq.py`, where the transport's own tests reach its internals under
`backend/README.md` rule 2 — the topology, the publish properties, the queue
arguments. Moving it here would either drag those internals onto a public
surface or force the transport tests through a seam that buys nothing.

**The guarded import lives here now.** Importing this module still must not
require an AMQP driver: the refusal arrives at connect time, typed, as
`BrokerUnavailableError` (ADR-0005 — no code-side default connection URL
either). That was previously asserted against `esb_ig`, where it is now
trivially true because the package no longer reaches `lib/rabbitmq` at all; it
is asserted here instead, which is the only place it can still fail.

Split out by ticket W2-T20.
"""

from __future__ import annotations

from .lib.rabbitmq import RabbitMqBroker, broker_from_environment

__all__ = [
    "RabbitMqBroker",
    "broker_from_environment",
]
