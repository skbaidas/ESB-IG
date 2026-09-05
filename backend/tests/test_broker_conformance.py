"""The shared-case suite — one set of cases, both implementations of the protocol.

**Why this file exists (IC10).** `InMemoryBroker` is published from
`esb_ig` as the executable definition of the broker contract. Until this
suite, that standing rested on an export list and a docstring: nothing asserted
the two implementations actually **agree**, and a double nobody compares to the
real thing is a second implementation, not a definition.

Every case below is written against the `Broker` protocol and nothing else, and
each one runs twice:

* against **`InMemoryBroker`, unconditionally** — it needs no infrastructure, so
  there is no configuration under which the definition goes unchecked; and
* against **`RabbitMqBroker` when `ESB_IG_TEST_BROKER_URL` names a broker**. With
  none configured that half **skips**, and platform §11.3 is explicit that a
  skip is *not-run, which is not a pass*. A green run on a broker-less machine
  says the definition is self-consistent; it does **not** say the deployment
  adapter matches it.

**What this file is not.** It is not the live transport suite. `backend/tests/
broker/` proves the three semantics a *server* performs and this process cannot
fake — redelivery after an unacknowledged crash, dead-letter routing by the
broker itself, priority under concurrent consumers — and it stays broker-only so
that `evidence/broker-suite.txt` keeps meaning exactly that. The cases here are
the *protocol's* promises, which both adapters owe.

**What the cases deliberately do not assert.** `DeadLetter.reason` is documented
as "the rejection, rendered for an operator", and the two adapters render it
differently: the in-memory one carries the consumer's exception, the broker one
cannot see it and says so generically. That divergence is legal — asserting on
the text here would freeze an operator-facing string into the wire contract. The
fields the protocol does name are asserted: the channel, the body verbatim, and
the envelope by value.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import esb_ig
import pytest
from esb_ig import (
    Broker,
    ChannelError,
    IdempotencyStore,
    InMemoryBroker,
    deduplicating,
)
from esb_ig.envelope import Envelope, Priority
from esb_ig.lib.rabbitmq import topology_for
from esb_ig.transport import RabbitMqBroker

IN_MEMORY = "in-memory"
RABBITMQ = "rabbitmq"

# Captured at import, before the root conftest's per-test `CTM_` purge can remove
# it — the same reason `backend/tests/broker/conftest.py` captures it there.
# Reading it at call time would make the real-broker half skip because of the
# purge rather than because no broker was configured.
TEST_BROKER_URL: str | None = os.getenv("ESB_IG_TEST_BROKER_URL")

# How long to let the server finish something it does asynchronously — routing a
# rejection to a dead-letter exchange. This bounds a network round trip inside
# one test process and is not a value any business user configures, so §5.2 does
# not reach it; the constant and its justification are `backend/tests/broker/
# test_transport.py`'s, repeated rather than shared because these two suites must
# stay separately runnable. Generous on purpose: a flaky release gate is worse
# than a slow one. The in-memory adapter satisfies every wait on the first check,
# so nothing sleeps on that half.
_SERVER_ROUND_TRIP_SECONDS = 5.0
_POLL_INTERVAL_SECONDS = 0.05

URGENT_EVENT_ID = "01J0-URGENT"


@dataclass(frozen=True)
class Substrate:
    """One implementation of the protocol, with channel names reserved for it.

    Attributes:
        broker: The implementation under test, held as the protocol type so a
            case cannot reach for anything the contract does not publish.
        channel: A channel name unique to this test.
        other_channel: A second one, for the cases about per-channel isolation.
    """

    broker: Broker
    channel: str
    other_channel: str


def _remove_topology(url: str, channels: tuple[str, ...]) -> None:
    """Delete what the real broker declared for these channels.

    Unique names plus teardown, because these cases assert on queue *contents*: a
    name shared with a previous run lets a leftover message read as a redelivery,
    which is one of the facts under test.
    """
    import pika

    connection = pika.BlockingConnection(pika.URLParameters(url))
    try:
        amqp = connection.channel()
        for name in channels:
            topology = topology_for(name)
            amqp.queue_delete(queue=topology.queue)
            amqp.queue_delete(queue=topology.dead_letter_queue)
            amqp.exchange_delete(exchange=topology.dead_letter_exchange)
    finally:
        connection.close()


@pytest.fixture(
    params=[
        IN_MEMORY,
        pytest.param(RABBITMQ, marks=pytest.mark.needs_broker),
    ]
)
def substrate(request: pytest.FixtureRequest) -> Iterator[Substrate]:
    """Each case, once per implementation of the published protocol.

    The real-broker parameter **skips and says so** when no broker is configured.
    That is not-run, not a pass (§11.3): on such a machine this suite proves the
    double is self-consistent and proves nothing about the deployment adapter.
    """
    unique = uuid4().hex
    channels = (f"ctm.conformance.{unique}", f"ctm.conformance.other.{unique}")
    url: str | None = None
    if request.param == IN_MEMORY:
        broker: Broker = InMemoryBroker()
    else:
        url = TEST_BROKER_URL
        if not url:
            pytest.skip(
                "ESB_IG_TEST_BROKER_URL is unset — the real-broker half of the shared-case "
                "suite is NOT-RUN, which is not a pass (§11.3). The conformance double "
                "was checked against itself and against nothing else."
            )
        broker = RabbitMqBroker(url)
    try:
        yield Substrate(broker=broker, channel=channels[0], other_channel=channels[1])
    finally:
        broker.close()
        if url is not None:
            _remove_topology(url, channels)


def eventually(ready: Callable[[], bool]) -> bool:
    """Whether `ready()` holds within the round-trip bound.

    Returns the outcome rather than raising, so the caller asserts on it: a
    helper that returned nothing on timeout would read as success at the call
    site, which is how an asynchronous guarantee comes to be reported as met.
    """
    deadline = time.monotonic() + _SERVER_ROUND_TRIP_SECONDS
    while True:
        if ready():
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(_POLL_INTERVAL_SECONDS)


def envelope(
    *,
    event_id: str = "01J0-EVENT",
    type_: str = "ctm.tenant.created",
    tenant_alias: str | None = "acmecorp",
    priority: Priority = Priority.P1,
    payload: Mapping[str, object] | None = None,
) -> Envelope:
    """Build a valid envelope, varying only what a case is about.

    Local rather than imported from another test module, on
    `backend/tests/broker/test_transport.py`'s precedent: each suite's helper is
    shaped to what that suite varies, and a shared one would couple three files
    that must stay separately runnable.
    """
    return Envelope(
        event_id=event_id,
        type=type_,
        version=1,
        occurred_at=datetime(2026, 8, 5, 9, 30, tzinfo=UTC),
        correlation_id="01J0-CORRELATION",
        application_code="1",
        tenant_alias=tenant_alias,
        producer="ctm",
        priority=priority,
        payload=dict(payload or {"alias": "acme"}),
    )


class Recorder:
    """A consumer that remembers what it was handed, and in what order."""

    def __init__(self) -> None:
        self.received: list[Envelope] = []

    def __call__(self, delivered: Envelope) -> None:
        self.received.append(delivered)

    @property
    def event_ids(self) -> list[str]:
        return [item.event_id for item in self.received]


def poison_consumer(delivered: Envelope) -> None:
    """A consumer that rejects everything, the way a real one rejects poison."""
    raise ValueError(f"cannot process {delivered.event_id}")


# --- The double's standing ---------------------------------------------------


def test_the_conformance_double_ships_with_the_published_protocol() -> None:
    """`InMemoryBroker` is interface, not fixture — and this is where a move shows.

    Moving it under `tests/` would remove it from the contract: consumers would
    lose the executable definition of redelivery, dead-lettering and priority
    ordering, and every one of them would interpret the prose independently. That
    relocation is a design decision, so it fails here rather than passing quietly.

    **The converse is asserted beside it (W2-T20).** The double is on the
    consumer surface *and the deployment adapter is not*: W2-T10 ratifies that
    ESB/IG publishes exactly three things — the protocol, the envelope and the
    double — so re-exporting `RabbitMqBroker` here would put a transport back
    within reach of every consumer of this contract.
    """
    assert "InMemoryBroker" in esb_ig.__all__
    # `esb_ig.__name__`, never the literal `esb_ig`: this suite relocates
    # with the seed, and a hard-coded root is a self-reference no import rewrite
    # can repair — which is the defect the graduation dry-run exists to find, and
    # did find here (W2-T20).
    assert InMemoryBroker.__module__.startswith(f"{esb_ig.__name__}."), (
        "the conformance double left the package that publishes the protocol"
    )
    assert isinstance(InMemoryBroker(), Broker)
    assert "RabbitMqBroker" not in esb_ig.__all__, (
        "the deployment adapter is back on the consumer surface — a consumer that "
        "can import a transport eventually will, and the contract becomes the transport"
    )


# --- Fail closed -------------------------------------------------------------


def test_delivering_on_a_channel_with_no_consumer_is_refused(substrate: Substrate) -> None:
    """A message with nobody to take it waits; it is not discarded."""
    substrate.broker.publish(substrate.channel, envelope())
    with pytest.raises(ChannelError, match="no consumer"):
        substrate.broker.deliver(substrate.channel)

    recorder = Recorder()
    substrate.broker.subscribe(substrate.channel, recorder)
    assert substrate.broker.deliver(substrate.channel).delivered == 1


def test_a_second_consumer_on_a_channel_is_refused(substrate: Substrate) -> None:
    """A channel is consumed serially — that is what makes ordering true, not likely."""
    substrate.broker.subscribe(substrate.channel, Recorder())
    with pytest.raises(ChannelError, match="already has a consumer"):
        substrate.broker.subscribe(substrate.channel, Recorder())


# --- At-least-once, and the substrate does not deduplicate -------------------


def test_the_substrate_does_not_deduplicate(substrate: Substrate) -> None:
    """The negative half of the contract, owed by both implementations.

    If either ever satisfies this with one delivery it has started promising
    exactly-once, which over a network it cannot keep.
    """
    recorder = Recorder()
    substrate.broker.subscribe(substrate.channel, recorder)
    redelivered = envelope(event_id="01J0-DUPLICATE")
    substrate.broker.publish(substrate.channel, redelivered)
    substrate.broker.publish(substrate.channel, redelivered)

    report = substrate.broker.deliver(substrate.channel)

    assert recorder.event_ids == ["01J0-DUPLICATE", "01J0-DUPLICATE"]
    assert report.delivered == 2


def test_dedupe_is_the_consumers_job_and_it_works_on_both(substrate: Substrate) -> None:
    """`deduplicating` + `IdempotencyStore` is the reference consumer, not a helper.

    Both copies are still *delivered*; only the effect is deduplicated. A
    substrate that suppressed the second delivery would make the store look
    unnecessary right up until the deployment disagreed with the double.
    """
    effects = Recorder()
    store = IdempotencyStore()
    substrate.broker.subscribe(substrate.channel, deduplicating(effects, store))
    redelivered = envelope(event_id="01J0-DUPLICATE")
    substrate.broker.publish(substrate.channel, redelivered)
    substrate.broker.publish(substrate.channel, redelivered)

    report = substrate.broker.deliver(substrate.channel)

    assert effects.event_ids == ["01J0-DUPLICATE"]
    assert report.delivered == 2
    assert len(store) == 1


# --- Priority classes --------------------------------------------------------


def test_the_higher_priority_class_is_served_first(substrate: Substrate) -> None:
    """The urgent message is published LAST and behind four others.

    Positional, not membership: `URGENT in delivered` is satisfied by a queue
    that ignores priority entirely, which would leave this suite exercising each
    adapter's own behaviour rather than the contract. The drain is serial, so
    there is no consumer race to make a positional assertion flaky here.
    """
    recorder = Recorder()
    substrate.broker.subscribe(substrate.channel, recorder)
    for index in range(4):
        substrate.broker.publish(
            substrate.channel, envelope(event_id=f"routine-{index}", priority=Priority.P2)
        )
    substrate.broker.publish(
        substrate.channel, envelope(event_id=URGENT_EVENT_ID, priority=Priority.P0)
    )

    substrate.broker.deliver(substrate.channel)

    assert recorder.event_ids == [
        URGENT_EVENT_ID,
        "routine-0",
        "routine-1",
        "routine-2",
        "routine-3",
    ], "a higher priority class must overtake, and order within a class must hold"


# --- Ordering: per tenant, per type, within a priority class -----------------


def test_order_is_preserved_per_tenant_and_per_type_within_a_priority_class(
    substrate: Substrate,
) -> None:
    """The guarantee, at the only key it is made against.

    Three interleaved streams in one priority class; each is delivered in
    publish order. Nothing here asserts an order *across* streams — the
    substrate reorders across them by design, which is why anything needing
    global order is a command rather than an event.
    """
    recorder = Recorder()
    substrate.broker.subscribe(substrate.channel, recorder)
    streams = {
        ("acme", "ctm.tenant.created"): ["a-created-1", "a-created-2", "a-created-3"],
        ("beta", "ctm.tenant.created"): ["b-created-1", "b-created-2"],
        ("acme", "ctm.tenant.suspended"): ["a-suspended-1", "a-suspended-2"],
    }
    interleaved = [
        ("acme", "ctm.tenant.created", "a-created-1"),
        ("beta", "ctm.tenant.created", "b-created-1"),
        ("acme", "ctm.tenant.suspended", "a-suspended-1"),
        ("acme", "ctm.tenant.created", "a-created-2"),
        ("beta", "ctm.tenant.created", "b-created-2"),
        ("acme", "ctm.tenant.suspended", "a-suspended-2"),
        ("acme", "ctm.tenant.created", "a-created-3"),
    ]
    for alias, event_type, event_id in interleaved:
        substrate.broker.publish(
            substrate.channel,
            envelope(event_id=event_id, type_=event_type, tenant_alias=alias),
        )

    substrate.broker.deliver(substrate.channel)

    for key, expected in streams.items():
        seen = [item.event_id for item in recorder.received if item.ordering_key == key]
        assert seen == expected, f"stream {key} was reordered"


# --- Dead-lettering, per channel ---------------------------------------------


def test_a_poison_message_is_dead_lettered_and_reading_never_empties_the_queue(
    substrate: Substrate,
) -> None:
    """It must not vanish, it must survive verbatim, and inspecting must not consume.

    `reason` is not asserted: the two adapters render it for an operator and
    render it differently, and the protocol names the field rather than its text.
    """
    substrate.broker.subscribe(substrate.channel, poison_consumer)
    poison = envelope(event_id="01J0-POISON")
    substrate.broker.publish(substrate.channel, poison)

    report = substrate.broker.deliver(substrate.channel)
    assert report == esb_ig.DeliveryReport(delivered=0, dead_lettered=1)

    assert eventually(lambda: len(substrate.broker.dead_letters(substrate.channel)) == 1), (
        "a rejected message vanished instead of being dead-lettered"
    )
    dead = substrate.broker.dead_letters(substrate.channel)
    assert dead[0].channel == substrate.channel
    assert Envelope.from_json(dead[0].body) == poison
    assert dead[0].envelope == poison

    again = substrate.broker.dead_letters(substrate.channel)
    assert [item.body for item in again] == [item.body for item in dead], (
        "reading a dead-letter queue consumed it, destroying the evidence it was opened for"
    )


def test_a_poison_message_isolates_rather_than_blocking_the_channel(
    substrate: Substrate,
) -> None:
    """The message behind the poison is delivered in the same drain."""
    recorder = Recorder()

    def reject_only_the_poison(delivered: Envelope) -> None:
        if delivered.event_id == "poison":
            raise RuntimeError("unprocessable")
        recorder(delivered)

    substrate.broker.subscribe(substrate.channel, reject_only_the_poison)
    for event_id in ("first", "poison", "second"):
        substrate.broker.publish(substrate.channel, envelope(event_id=event_id))

    report = substrate.broker.deliver(substrate.channel)

    assert recorder.event_ids == ["first", "second"]
    assert report == esb_ig.DeliveryReport(delivered=2, dead_lettered=1)


def test_the_dead_letter_queue_is_per_channel(substrate: Substrate) -> None:
    """One channel's poison is invisible to another's — and cannot block it."""
    healthy = Recorder()
    substrate.broker.subscribe(substrate.channel, poison_consumer)
    substrate.broker.subscribe(substrate.other_channel, healthy)
    substrate.broker.publish(substrate.channel, envelope(event_id="poison"))
    substrate.broker.publish(substrate.other_channel, envelope(event_id="healthy"))

    substrate.broker.deliver(substrate.channel)
    substrate.broker.deliver(substrate.other_channel)

    assert eventually(lambda: len(substrate.broker.dead_letters(substrate.channel)) == 1)
    assert substrate.broker.dead_letters(substrate.other_channel) == ()
    assert healthy.event_ids == ["healthy"]


# --- Bounded drain -----------------------------------------------------------


def test_a_drain_can_be_bounded(substrate: Substrate) -> None:
    """`limit` takes a batch without draining the channel, on both implementations."""
    recorder = Recorder()
    substrate.broker.subscribe(substrate.channel, recorder)
    for index in range(3):
        substrate.broker.publish(substrate.channel, envelope(event_id=f"e{index}"))

    assert substrate.broker.deliver(substrate.channel, limit=2).delivered == 2
    assert substrate.broker.deliver(substrate.channel).delivered == 1
    assert recorder.event_ids == ["e0", "e1", "e2"]
