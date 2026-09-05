"""The message-broker adapter — the other half of the estate's one real seam.

**The driver import is guarded and lazy.** `import esb_ig` must succeed
on a machine with no AMQP client installed, because the envelope contract, the
in-memory adapter and every semantic test depend on this package and none of
them depends on a broker. A missing driver therefore surfaces where it is
actionable — at connect time, as `BrokerUnavailableError` — instead of as an
`ImportError` that takes the whole package down at import.

**Topology is derived, not configured.** A channel `ctm.tenant` gets the queue
`ctm.tenant`, the dead-letter exchange `ctm.tenant.dlx` and the dead-letter
queue `ctm.tenant.dlq`. That is a naming convention in a wire contract, not a
business value, so it belongs in code; the connection parameters, which *are*
deployment choices, are in `config.py` with no default at all.

**Draining with `basic_get`, not a consumer loop.** A pull-based drain makes
`deliver()` mean the same thing in both adapters — take what is queued, then
return — so a test written against the fake describes this adapter too. A
push-based loop would need an inactivity timeout, which is a threshold, which is
a configurable value this module would then be inventing.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import ModuleType
from typing import Any

from ..envelope import Envelope, EnvelopeError
from .broker import Consumer, DeadLetter, DeliveryReport, max_priority_rank
from .config import broker_url_from_environment
from .errors import BrokerUnavailableError, ChannelError

__all__ = [
    "RabbitMqBroker",
    "Topology",
    "broker_from_environment",
    "declare",
    "publish_properties",
    "queue_arguments",
    "topology_for",
]

# AMQP's persistent delivery mode. A message that does not survive a broker
# restart would make at-least-once delivery a claim rather than a guarantee.
_PERSISTENT_DELIVERY_MODE = 2

_WIRE_CONTENT_TYPE = "application/json"


@dataclass(frozen=True)
class Topology:
    """The three names one channel occupies on the broker.

    Attributes:
        queue: Where published messages land.
        dead_letter_exchange: Where the broker routes a rejected message.
        dead_letter_queue: Bound to that exchange — the per-channel DLQ. Per
            channel is the point: one channel's poison must not be visible to,
            or block, another's.
    """

    queue: str
    dead_letter_exchange: str
    dead_letter_queue: str


def topology_for(channel: str) -> Topology:
    """Derive a channel's queue names."""
    if not channel.strip():
        raise ChannelError("channel name must be non-blank")
    return Topology(
        queue=channel,
        dead_letter_exchange=f"{channel}.dlx",
        dead_letter_queue=f"{channel}.dlq",
    )


def queue_arguments(topology: Topology) -> dict[str, object]:
    """The arguments a channel's main queue is declared with.

    `x-max-priority` comes from `Priority`, so the queue cannot be declared with
    fewer classes than the wire contract carries.
    """
    return {
        "x-dead-letter-exchange": topology.dead_letter_exchange,
        "x-max-priority": max_priority_rank(),
    }


def publish_properties(envelope: Envelope) -> dict[str, object]:
    """The per-message properties, as keyword arguments for the driver.

    Kept separate from the driver call so the mapping from envelope to wire
    metadata — priority class, deduplication key, correlation — is assertable
    without a broker or a driver.
    """
    return {
        "delivery_mode": _PERSISTENT_DELIVERY_MODE,
        "priority": envelope.priority.rank,
        "message_id": envelope.event_id,
        "correlation_id": envelope.correlation_id,
        "type": envelope.type,
        "content_type": _WIRE_CONTENT_TYPE,
    }


def declare(amqp_channel: Any, channel: str) -> Topology:
    """Declare one channel's queue, dead-letter exchange and dead-letter queue.

    Idempotent, and re-run before every operation: a queue that vanished with
    its broker is re-created rather than publishing into nothing.

    Args:
        amqp_channel: An open AMQP channel.
        channel: The logical channel name.

    Returns:
        The declared topology.
    """
    topology = topology_for(channel)
    amqp_channel.exchange_declare(
        exchange=topology.dead_letter_exchange, exchange_type="fanout", durable=True
    )
    amqp_channel.queue_declare(queue=topology.dead_letter_queue, durable=True)
    amqp_channel.queue_bind(
        queue=topology.dead_letter_queue, exchange=topology.dead_letter_exchange
    )
    amqp_channel.queue_declare(
        queue=topology.queue, durable=True, arguments=queue_arguments(topology)
    )
    return topology


def _load_driver() -> ModuleType:
    """Import the AMQP driver, or refuse the operation.

    `ImportError` rather than `ModuleNotFoundError`: both a package that is not
    installed and one that is present but unimportable are the same fact to a
    caller — this process cannot reach the broker.
    """
    try:
        import pika
    except ImportError as exc:
        raise BrokerUnavailableError(
            "no AMQP driver is installed, so CTM cannot reach the broker. The in-memory "
            "adapter serves tests; a deployment installs the driver."
        ) from exc
    return pika


class RabbitMqBroker:
    """The deployment adapter. Same guarantees as the in-memory one, over AMQP.

    Priority classes are the queue's `x-max-priority` argument and each
    message's priority property; the dead-letter queue is the channel's
    dead-letter exchange, so a rejected message is routed by the broker itself
    rather than by anything this process must stay alive to do.

    Constructing one connects to nothing. The first operation opens the
    connection, so a composition root can build the object before the broker is
    reachable, and a missing driver is a typed refusal rather than an import
    failure.
    """

    def __init__(self, url: str) -> None:
        """Args:
        url: The connection URL, supplied by the deployment. There is no
            default; see `config.broker_url_from_environment`.
        """
        self._url = url
        self._driver: ModuleType | None = None
        self._connection: Any | None = None
        self._amqp_channel: Any | None = None
        self._consumers: dict[str, Consumer] = {}

    def publish(self, channel: str, envelope: Envelope) -> None:
        """Publish an envelope onto a channel's queue."""
        amqp_channel = self._open()
        topology = declare(amqp_channel, channel)
        properties = self._require_driver().BasicProperties(**publish_properties(envelope))
        amqp_channel.basic_publish(
            exchange="",
            routing_key=topology.queue,
            body=envelope.to_json().encode("utf-8"),
            properties=properties,
        )

    def subscribe(self, channel: str, consumer: Consumer) -> None:
        """Register the channel's one consumer."""
        if channel in self._consumers:
            raise ChannelError(
                f"channel '{channel}' already has a consumer. A channel is consumed serially — "
                f"a second consumer would forfeit the per-tenant, per-type ordering guarantee"
            )
        self._consumers[channel] = consumer

    def deliver(self, channel: str, *, limit: int | None = None) -> DeliveryReport:
        """Drain the channel, acknowledging what the consumer accepts.

        A rejected message is nacked without requeue, which is what routes it to
        the dead-letter exchange: it leaves the queue, stays retrievable, and
        does not block the messages behind it. A body that is not a valid
        envelope is rejected the same way — an unreadable message is poison too.
        """
        consumer = self._consumers.get(channel)
        if consumer is None:
            raise ChannelError(
                f"channel '{channel}' has no consumer. Delivery is refused rather than "
                f"discarding the message (fail closed)"
            )

        amqp_channel = self._open()
        topology = declare(amqp_channel, channel)
        delivered = 0
        dead_lettered = 0
        while limit is None or delivered + dead_lettered < limit:
            method, _properties, body = amqp_channel.basic_get(queue=topology.queue, auto_ack=False)
            if method is None:
                break
            try:
                envelope = Envelope.from_json(bytes(body).decode("utf-8"))
                consumer(envelope)
            except Exception:
                # Every exception, deliberately: one poison message must not
                # take the channel down with it, and the substrate cannot know
                # which exception types a consumer considers fatal.
                amqp_channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                dead_lettered += 1
            else:
                amqp_channel.basic_ack(delivery_tag=method.delivery_tag)
                delivered += 1
        return DeliveryReport(delivered=delivered, dead_lettered=dead_lettered)

    def dead_letters(self, channel: str) -> tuple[DeadLetter, ...]:
        """Inspect the channel's dead-letter queue without consuming it.

        Every message read is returned to the queue, because an inspection that
        empties a DLQ destroys the evidence it was opened to look at. Ordering
        is best-effort for the same reason.
        """
        amqp_channel = self._open()
        topology = declare(amqp_channel, channel)
        found: list[DeadLetter] = []
        tags: list[int] = []
        while True:
            method, _properties, body = amqp_channel.basic_get(
                queue=topology.dead_letter_queue, auto_ack=False
            )
            if method is None:
                break
            tags.append(method.delivery_tag)
            found.append(self._as_dead_letter(channel, bytes(body).decode("utf-8")))
        for tag in tags:
            amqp_channel.basic_nack(delivery_tag=tag, requeue=True)
        return tuple(found)

    def close(self) -> None:
        """Close the connection, if one was ever opened."""
        if self._connection is not None:
            self._connection.close()
        self._connection = None
        self._amqp_channel = None

    @staticmethod
    def _as_dead_letter(channel: str, body: str) -> DeadLetter:
        """Present a dead-lettered body, parsed when it can be."""
        try:
            envelope = Envelope.from_json(body)
        except EnvelopeError as exc:
            return DeadLetter(channel=channel, body=body, reason=str(exc), envelope=None)
        return DeadLetter(
            channel=channel, body=body, reason="rejected by the consumer", envelope=envelope
        )

    def _require_driver(self) -> ModuleType:
        """Return the driver, importing it once per broker."""
        if self._driver is None:
            self._driver = _load_driver()
        return self._driver

    def _open(self) -> Any:
        """Return the AMQP channel, opening the connection on first use."""
        if self._amqp_channel is None:
            driver = self._require_driver()
            self._connection = driver.BlockingConnection(driver.URLParameters(self._url))
            self._amqp_channel = self._connection.channel()
        return self._amqp_channel


def broker_from_environment() -> RabbitMqBroker:
    """Build the deployment adapter from configuration, or refuse to build one.

    The composition root calls this; nothing inside `esb_ig` reads the
    environment on a delivery path.

    Raises:
        ConfigurationError: The broker URL is unset, blank, or carries a
            well-known default credential.
    """
    return RabbitMqBroker(broker_url_from_environment())
