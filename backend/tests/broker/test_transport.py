"""The broker transport — the half of the adapter only a live broker can prove.

**Read the skip line before reading the assertions.** These tests need a running
message broker at `ESB_IG_TEST_BROKER_URL`. With none configured they **skip**, and
platform §11.3 is explicit that a skip is *not-run, which is not a pass*.

**What counts as evidence from this file.** A result here is broker evidence only
if it came from a run where a broker was actually configured — which means one of
exactly two provenances, and no third:

1. A local run against a live broker, captured to `evidence/broker-suite.txt`.
   This is the current state: wave-2 ticket W2-T04 ran all three against RabbitMQ
   4.3.4 in a container and committed the named passes.
2. The did-not-skip guard in `.github/workflows/ci.yml`, once ticket 07 attaches
   a runner. That guard has **never executed**, so it backs nothing today.

Do not read a green tick anywhere else as covering these. The distinction matters
because provenance (1) proves the *semantics* on one machine and says nothing
about whether the *lane* runs; W2-T04 closed the first and left the second open.

**Why they exist at all (ticket 21, item 3).** `backend/tests/test_broker.py`
asserts the adapter's *declared topology* against a recording channel double —
`x-max-priority`, `x-dead-letter-exchange`, the dead-letter binding, and the
per-message properties. That is real evidence about what the adapter **declares**
and no evidence whatever about what a broker **does** with those declarations,
and the difference was being carried by prose.

Three semantics, chosen because a server performs each one and this process
performs none of them — so the in-memory adapter cannot stand in for any:

1. **Redelivery after an unacknowledged consumer crash.** At-least-once is a
   promise about what happens when a consumer dies mid-message. The in-memory
   adapter has no acknowledgement and no connection to lose, so it can only
   demonstrate that a duplicate *publish* arrives twice.
2. **Dead-letter routing performed by the broker.** The in-memory adapter puts a
   rejected message on its own list. Here nothing in this process routes it: the
   queue's `x-dead-letter-exchange` argument does, which is the only version of
   the claim that survives this process exiting.
3. **Priority ordering under concurrent consumers.** `x-max-priority` is an
   argument the broker either honours or ignores; a fake that sorts its own
   buckets proves the sort, not the argument.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from esb_ig.envelope import Envelope, Priority
from esb_ig.lib.rabbitmq import declare, publish_properties

pytestmark = pytest.mark.needs_broker

URGENT_EVENT_ID = "01J0-URGENT"

# How long to wait for the server to finish something it does asynchronously —
# routing a rejection to a dead-letter exchange, or pushing to a consumer. This
# bounds a network round trip inside one test process; it is not a value any
# business user configures, so §5.2 does not reach it. Generous on purpose: the
# cost of being wrong here is a flaky release gate, which is worse than a slow
# one.
_SERVER_ROUND_TRIP_SECONDS = 5.0
_POLL_INTERVAL_SECONDS = 0.05


def get_within_round_trip(connection: Any, channel: Any, queue: str) -> tuple[Any, bytes] | None:
    """Poll `queue` until a message appears, or return `None` at the bound.

    A single `basic_get` immediately after a rejection is a race: dead-lettering
    is the server's work, not the caller's, so asserting on it without waiting
    produces a test that passes on a fast broker and fails on a slow one.
    """
    remaining = _SERVER_ROUND_TRIP_SECONDS
    while remaining > 0:
        method, _properties, body = channel.basic_get(queue=queue, auto_ack=False)
        if method is not None:
            return method, bytes(body)
        connection.sleep(_POLL_INTERVAL_SECONDS)
        remaining -= _POLL_INTERVAL_SECONDS
    return None


def pump_until(connection: Any, ready: Callable[[], bool]) -> bool:
    """Drive the connection's I/O until `ready()` holds, or the bound elapses.

    Returns whether it became true, so the caller asserts on the outcome — a
    timeout that returned nothing would read as success at the call site.
    """
    remaining = _SERVER_ROUND_TRIP_SECONDS
    while remaining > 0:
        if ready():
            return True
        connection.process_data_events(time_limit=_POLL_INTERVAL_SECONDS)
        remaining -= _POLL_INTERVAL_SECONDS
    return ready()


def envelope(*, event_id: str, priority: Priority = Priority.P1) -> Envelope:
    """A valid envelope, varying only what a test is about."""
    return Envelope(
        event_id=event_id,
        type="ctm.tenant.created",
        version=1,
        occurred_at=datetime(2026, 7, 25, 9, 30, tzinfo=UTC),
        correlation_id="01J0-CORRELATION",
        application_code="1",
        tenant_alias="1",
        producer="ctm",
        priority=priority,
        payload={"alias": "acme"},
    )


def publish(channel: Any, queue: str, message: Envelope) -> None:
    """Publish through the adapter's own property mapping.

    Deliberately not a hand-rolled `BasicProperties`: the point of these tests is
    that what `RabbitMqBroker` sends is what the broker acts on, so a test that
    built its own properties would be asserting the broker against itself.
    """
    import pika

    channel.basic_publish(
        exchange="",
        routing_key=queue,
        body=message.to_json().encode("utf-8"),
        properties=pika.BasicProperties(**publish_properties(message)),
    )


def test_an_unacknowledged_message_is_redelivered_after_the_consumer_crashes(
    amqp: Any, broker_url: str, transport_channel: str
) -> None:
    """At-least-once, in the only situation that tests it.

    A consumer that takes a message and dies before acknowledging is the case the
    guarantee exists for. Closing the connection is the crash: no acknowledgement
    is sent, no rejection is sent, and the broker has to decide on its own that
    the message is still owed to someone.
    """
    import pika

    channel = amqp.channel()
    topology = declare(channel, transport_channel)
    publish(channel, topology.queue, envelope(event_id="01J0-UNACKED"))

    crashing = pika.BlockingConnection(pika.URLParameters(broker_url))
    taken = get_within_round_trip(crashing, crashing.channel(), topology.queue)
    assert taken is not None, "the published message never arrived"
    method, body = taken
    assert method.redelivered is False, "this is the first delivery, not a redelivery"
    crashing.close()  # the crash — un-acked, and now un-ackable

    returned = get_within_round_trip(amqp, channel, topology.queue)
    assert returned is not None, "the broker dropped an unacknowledged message"
    redelivered_method, redelivered_body = returned
    assert redelivered_method.redelivered is True
    assert redelivered_body == body, "a redelivery must be the same message, verbatim"
    channel.basic_ack(delivery_tag=redelivered_method.delivery_tag)


def test_the_broker_itself_routes_a_rejected_message_to_the_dead_letter_queue(
    amqp: Any, transport_channel: str
) -> None:
    """The DLQ claim, with nothing in this process doing the routing.

    `RabbitMqBroker.deliver` nacks with `requeue=False`; what happens next is the
    queue's `x-dead-letter-exchange` argument being honoured, entirely inside the
    server. That is the version of the guarantee that still holds when this
    process is gone — which is the only version an operator can rely on.
    """
    channel = amqp.channel()
    topology = declare(channel, transport_channel)
    poison = envelope(event_id="01J0-POISON")
    publish(channel, topology.queue, poison)

    taken = get_within_round_trip(amqp, channel, topology.queue)
    assert taken is not None, "the published message never arrived"
    method, body = taken
    channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    dead = get_within_round_trip(amqp, channel, topology.dead_letter_queue)
    assert dead is not None, "a rejected message vanished instead of being dead-lettered"
    dead_method, dead_body = dead
    assert dead_body == body, "a dead letter must survive its own rejection verbatim"
    assert Envelope.from_json(dead_body.decode("utf-8")) == poison
    channel.basic_ack(delivery_tag=dead_method.delivery_tag)

    assert get_within_round_trip(amqp, channel, topology.queue) is None, (
        "the rejected message was requeued as well as dead-lettered"
    )


def test_the_broker_serves_the_higher_priority_class_first_across_two_consumers(
    amqp: Any, transport_channel: str
) -> None:
    """`x-max-priority` honoured by the server, not sorted by this process.

    Two consumers at `prefetch_count=1` means exactly two messages can be
    outstanding, so the broker must choose which two to hand out first. The
    urgent message is published **last** and behind four others, so it can only
    be in that first pair if the priority argument is being honoured.

    Asserted by SET MEMBERSHIP over the first pair, not by arrival order: which
    of the two consumers is served first is a genuine race, and pinning it would
    make this flaky for a reason unrelated to the guarantee.
    """
    channel = amqp.channel()
    topology = declare(channel, transport_channel)
    for index in range(4):
        publish(
            channel, topology.queue, envelope(event_id=f"routine-{index}", priority=Priority.P2)
        )
    publish(channel, topology.queue, envelope(event_id=URGENT_EVENT_ID, priority=Priority.P0))

    delivered: list[str] = []

    def record(_channel: Any, _method: Any, properties: Any, _body: bytes) -> None:
        delivered.append(properties.message_id)

    for _ in range(2):
        consumer_channel = amqp.channel()
        consumer_channel.basic_qos(prefetch_count=1)
        consumer_channel.basic_consume(
            queue=topology.queue, on_message_callback=record, auto_ack=False
        )

    assert pump_until(amqp, lambda: len(delivered) >= 2), (
        f"two consumers at prefetch 1 should hold two messages; saw {delivered}"
    )
    assert URGENT_EVENT_ID in delivered[:2], (
        f"the P0 message was published last and was not served first: {delivered[:2]}"
    )
