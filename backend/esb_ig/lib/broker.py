"""The broker protocol and the in-memory adapter.

The protocol exists because behaviour genuinely varies across this seam: a
message broker in a deployment, an in-memory queue in a test (`design.md` §3).
It is the estate's one real seam — `lov` and `db` have a single adapter each and
therefore no protocol.

The fake is not a stub. It implements the same delivery rules as the broker
adapter — priority classes, per-channel dead-lettering, no deduplication — so
the semantics the platform depends on are provable with no infrastructure, and a
test that passes here is not passing for want of a queue.

**`InMemoryBroker` belongs here, in the package that publishes the protocol, and
not under `tests/`.** It is exported from `esb_ig` as the executable
definition of the contract, which is a thing consumers import; relocating it
into a test tree would take the definition away from them and leave each one to
interpret the protocol docstring on its own. That it is a *definition* rather
than a second implementation is asserted, not assumed:
`backend/tests/test_broker_conformance.py` runs one set of cases against both
adapters — against this one unconditionally, and against `RabbitMqBroker` when a
broker is configured.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ..envelope import Envelope, Priority
from .errors import ChannelError

__all__ = [
    "Broker",
    "Consumer",
    "DeadLetter",
    "DeliveryReport",
    "InMemoryBroker",
]

# A consumer applies an effect and returns nothing. Raising is how it says "I
# cannot process this" — the substrate reads any exception as a rejection and
# dead-letters the message.
Consumer = Callable[[Envelope], None]


@dataclass(frozen=True)
class DeliveryReport:
    """What one drain of a channel did.

    Attributes:
        delivered: Messages the consumer accepted.
        dead_lettered: Messages it rejected, all of which are now retrievable
            from the channel's dead-letter queue.
    """

    delivered: int
    dead_lettered: int


@dataclass(frozen=True)
class DeadLetter:
    """A message the consumer could not process, kept rather than dropped.

    Attributes:
        channel: The channel it was published to. Dead-letter queues are
            per-channel, so one channel's poison cannot hide in another's.
        body: The wire body, always present. This is what "does not vanish"
            means: a message survives its own rejection verbatim.
        reason: The rejection, rendered for an operator.
        envelope: The parsed envelope, or `None` when the body was not a valid
            envelope at all — which is itself a reason to dead-letter.
    """

    channel: str
    body: str
    reason: str
    envelope: Envelope | None


@runtime_checkable
class Broker(Protocol):
    """The message substrate.

    Guarantees, which are part of this interface and not documentation:

    * **At-least-once, never exactly-once.** A message may arrive more than
      once and the substrate does **not** deduplicate. A consumer that must
      apply an effect once keys on `event_id` through an idempotency store.
    * **Ordering is per-tenant, per-type only** — `Envelope.ordering_key` — and
      within a priority class, because a higher class is served first. Nothing
      here promises global order; anything that needs it is a command, not an
      event.
    * **A channel is consumed serially by one consumer**, which is what makes
      the ordering guarantee true rather than incidental.
    * **Dead-letter queue per channel.** A rejected message leaves the channel,
      stays retrievable, and does not block what is behind it.
    * **Fail closed.** Delivery on a channel with no consumer is refused, not
      silently dropped.
    """

    def publish(self, channel: str, envelope: Envelope) -> None:
        """Place an envelope on a channel."""
        ...

    def subscribe(self, channel: str, consumer: Consumer) -> None:
        """Register the channel's one consumer.

        Raises:
            ChannelError: The channel already has a consumer.
        """
        ...

    def deliver(self, channel: str, *, limit: int | None = None) -> DeliveryReport:
        """Drain up to `limit` messages (all of them when `None`).

        Raises:
            ChannelError: The channel has no consumer.
        """
        ...

    def dead_letters(self, channel: str) -> tuple[DeadLetter, ...]:
        """Inspect the channel's dead-letter queue without consuming it."""
        ...

    def close(self) -> None:
        """Release whatever the adapter holds."""
        ...


class InMemoryBroker:
    """An in-process adapter with the same delivery rules as the real broker.

    Ordering is FIFO within a priority class, exactly as a single broker queue
    with a maximum-priority argument behaves — so a guarantee proven here holds
    there. Not thread-safe, and deliberately so: a channel is consumed serially,
    and a fake that tolerates concurrent consumers would prove an ordering
    guarantee the deployment does not have.
    """

    def __init__(self) -> None:
        self._queues: dict[str, dict[int, deque[Envelope]]] = {}
        self._consumers: dict[str, Consumer] = {}
        self._dead_letters: dict[str, list[DeadLetter]] = {}

    def publish(self, channel: str, envelope: Envelope) -> None:
        """Place an envelope on a channel, whether or not anyone is consuming it."""
        buckets = self._queues.setdefault(channel, {})
        buckets.setdefault(envelope.priority.rank, deque()).append(envelope)

    def subscribe(self, channel: str, consumer: Consumer) -> None:
        """Register the channel's one consumer."""
        if channel in self._consumers:
            raise ChannelError(
                f"channel '{channel}' already has a consumer. A channel is consumed serially — "
                f"a second consumer would forfeit the per-tenant, per-type ordering guarantee"
            )
        self._consumers[channel] = consumer

    def deliver(self, channel: str, *, limit: int | None = None) -> DeliveryReport:
        """Drain the channel, dead-lettering whatever the consumer rejects."""
        consumer = self._consumers.get(channel)
        if consumer is None:
            raise ChannelError(
                f"channel '{channel}' has no consumer. Delivery is refused rather than "
                f"discarding the message (fail closed)"
            )

        delivered = 0
        dead_lettered = 0
        while limit is None or delivered + dead_lettered < limit:
            envelope = self._take(channel)
            if envelope is None:
                break
            try:
                consumer(envelope)
            except Exception as exc:
                # Every exception, deliberately: one poison message must not
                # take the channel down with it, and the substrate cannot know
                # which exception types a consumer considers fatal. Isolation is
                # the whole point of a dead-letter queue.
                self._dead_letters.setdefault(channel, []).append(
                    DeadLetter(
                        channel=channel,
                        body=envelope.to_json(),
                        reason=f"{type(exc).__name__}: {exc}",
                        envelope=envelope,
                    )
                )
                dead_lettered += 1
            else:
                delivered += 1
        return DeliveryReport(delivered=delivered, dead_lettered=dead_lettered)

    def dead_letters(self, channel: str) -> tuple[DeadLetter, ...]:
        """Inspect, never consume — reading a dead-letter queue must not empty it."""
        return tuple(self._dead_letters.get(channel, ()))

    def close(self) -> None:
        """Nothing to release. Present so a caller need not know which adapter it holds."""

    def _take(self, channel: str) -> Envelope | None:
        """Pop the next message: highest priority class first, FIFO within it."""
        buckets = self._queues.get(channel)
        if not buckets:
            return None
        for rank in sorted(buckets, reverse=True):
            queue = buckets[rank]
            if queue:
                return queue.popleft()
        return None


def max_priority_rank() -> int:
    """The highest rank a message can carry — the queue's maximum-priority argument.

    Derived from `Priority` so the declared queue and the wire contract cannot
    disagree about how many classes exist.
    """
    return max(member.rank for member in Priority)
