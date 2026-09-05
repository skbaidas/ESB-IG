"""The reference consumer — how a caller survives at-least-once delivery.

The substrate does not deduplicate, and cannot: exactly-once delivery is not
available over a network, and a broker that claims it has only moved the
duplicate somewhere harder to see. So the duplicate is handled where the effect
is — in the consumer, keyed on `event_id`.

This is the pattern every consumer in the estate copies, which is why it ships
next to the broker rather than being left to each caller to reinvent.
"""

from __future__ import annotations

from ..envelope import Envelope
from .broker import Consumer

__all__ = [
    "IdempotencyStore",
    "deduplicating",
]


class IdempotencyStore:
    """The `event_id`s whose effects have already been applied.

    In-process and therefore not durable: a crash between the effect and the
    record replays the effect. That is honest for a seed and wrong for
    production, where the record joins the effect's own transaction so the two
    commit together — at which point this class gains a second implementation
    and the protocol it does not yet deserve is earned (`design.md` §3).

    Not thread-safe, which costs nothing: a channel is consumed serially.
    """

    def __init__(self) -> None:
        self._applied: set[str] = set()

    def has_applied(self, event_id: str) -> bool:
        """Whether this event's effect is already recorded."""
        return event_id in self._applied

    def record_applied(self, event_id: str) -> None:
        """Record that this event's effect happened."""
        self._applied.add(event_id)

    def __len__(self) -> int:
        return len(self._applied)


def deduplicating(consumer: Consumer, store: IdempotencyStore) -> Consumer:
    """Wrap a consumer so a redelivered envelope produces one effect, not two.

    The record is written **after** the effect, never before. Recording first
    would mean a consumer that raises has already claimed the event, so the
    dead-lettered message could never be reprocessed — the substrate would have
    turned at-least-once into at-most-once, silently.

    Args:
        consumer: The effect to apply once per `event_id`.
        store: Where applied events are remembered.

    Returns:
        A consumer with the same signature, safe to hand to `Broker.subscribe`.
    """

    def apply_once(envelope: Envelope) -> None:
        if store.has_applied(envelope.event_id):
            return
        consumer(envelope)
        store.record_applied(envelope.event_id)

    return apply_once
