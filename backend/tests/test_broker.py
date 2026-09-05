"""The event substrate — envelope contract, delivery semantics, and both adapters.

What these assert is the ticket's promise, in the ticket's order: the envelope
is exactly ten fields; delivery is **at-least-once and never exactly-once**, so
a duplicate is the consumer's problem and the reference consumer solves it;
ordering is per-tenant, per-type and nothing wider; and a poison message lands
in a **per-channel** dead-letter queue where it isolates rather than blocking or
vanishing.

Deny paths come before happy paths (CLAUDE.md §11.1). A substrate that accepts
everything also delivers every happy-path test.

**Two adapters, unequal coverage — stated rather than implied (§11.3).** The
in-memory adapter carries the semantics, because it implements the same delivery
rules and needs no infrastructure. The broker adapter's *transport* is not
exercised here: nothing in this repository runs a broker, and a test that
silently skips is not-run, which is not a pass. What is exercised is everything
about that adapter which is decidable without one — the declared topology, the
per-message properties, and the refusal when no driver is installed.

**The guarded import is exercised, not inferred.** This module used to rest that
claim on its own collection succeeding, which is only evidence on a machine
where no AMQP driver happens to be installed — and W2-T20 moved the adapter off
`esb_ig` entirely, so importing the package stopped reaching the driver
at all. It is asserted against `esb_ig.transport` with `pika` masked instead,
which holds either way.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import esb_ig
import pytest
from esb_ig import (
    Broker,
    BrokerUnavailableError,
    ChannelError,
    IdempotencyStore,
    InMemoryBroker,
    deduplicating,
)
from esb_ig.envelope import (
    ENVELOPE_FIELD_NAMES,
    Envelope,
    EnvelopeError,
    Priority,
)
from esb_ig.lib.config import BROKER_URL_VARIABLE, broker_url_from_environment
from esb_ig.lib.errors import BrokerConfigurationError
from esb_ig.lib.rabbitmq import (
    declare,
    publish_properties,
    queue_arguments,
    topology_for,
)
from esb_ig.transport import RabbitMqBroker, broker_from_environment

# The ten fields, written out rather than derived — a test that computes the
# contract from the code under test cannot detect the code changing it.
CONTRACT_FIELDS = (
    "event_id",
    "type",
    "version",
    "occurred_at",
    "correlation_id",
    "application_code",
    "tenant_alias",
    "producer",
    "priority",
    "payload",
)

CHANNEL = "ctm.tenant"
OTHER_CHANNEL = "ctm.application"

# A deployment-shaped URL that reaches nothing: a documentation host, a
# non-default port, and a credential that is deliberately not a well-known pair
# (the substrate refuses those, so a test using `guest:guest` would pass for the
# wrong reason).
TEST_BROKER_URL = "amqp://ctm_broker_user:test-only-not-a-real-password@broker.internal:5673/ctm"  # hardcoding: allow -- unreachable documentation host; the adapter must accept a well-formed URL to be testable


def envelope(
    *,
    event_id: str = "01J0-EVENT",
    type_: str = "ctm.tenant.created",
    version: int = 1,
    tenant_alias: str | None = "acmecorp",
    priority: Priority = Priority.P1,
    payload: Mapping[str, object] | None = None,
) -> Envelope:
    """Build a valid envelope, varying only what a test is about."""
    return Envelope(
        event_id=event_id,
        type=type_,
        version=version,
        occurred_at=datetime(2026, 7, 25, 9, 30, tzinfo=UTC),
        correlation_id="01J0-CORRELATION",
        application_code="1",
        tenant_alias=tenant_alias,
        producer="ctm",
        priority=priority,
        payload=dict(payload or {"alias": "acme"}),
    )


class Recorder:
    """A consumer that remembers what it was handed, and how often."""

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


# --- The envelope contract --------------------------------------------------


def test_the_envelope_is_exactly_the_ten_contract_fields() -> None:
    """Not nine, not eleven. An eleventh field is a new envelope, not an addition."""
    assert ENVELOPE_FIELD_NAMES == CONTRACT_FIELDS
    assert len(ENVELOPE_FIELD_NAMES) == 10


def test_a_wire_message_missing_a_field_is_refused() -> None:
    """A partial parse would let a consumer act on an envelope it half understands."""
    wire = envelope().as_mapping()
    del wire["correlation_id"]
    with pytest.raises(EnvelopeError, match="missing"):
        Envelope.from_mapping(wire)


def test_a_wire_message_with_an_extra_field_is_refused() -> None:
    """The envelope is closed; additive change belongs in the payload."""
    wire = envelope().as_mapping()
    wire["signature"] = "extra"
    with pytest.raises(EnvelopeError, match="unknown"):
        Envelope.from_mapping(wire)


@pytest.mark.parametrize(
    "field",
    ["event_id", "type", "correlation_id", "application_code", "tenant_id", "producer"],
)
def test_a_blank_identifier_is_refused(field: str) -> None:
    """A blank `event_id` would deduplicate every event against every other."""
    wire = envelope().as_mapping()
    wire[field] = "   "
    with pytest.raises(EnvelopeError, match=field):
        Envelope.from_mapping(wire)


def test_a_naive_timestamp_is_refused() -> None:
    """'Which midnight' is not answerable across a residency boundary."""
    with pytest.raises(EnvelopeError, match="occurred_at"):
        Envelope(
            event_id="e",
            type="ctm.tenant.created",
            version=1,
            occurred_at=datetime(2026, 7, 25, 9, 30),  # deliberately naive
            correlation_id="c",
            application_code="1",
            tenant_alias="1",
            producer="ctm",
            priority=Priority.P1,
            payload={},
        )


def test_an_unknown_priority_class_is_refused() -> None:
    """P0/P1/P2 is the frozen set; a fourth class is a protocol change."""
    wire = envelope().as_mapping()
    wire["priority"] = "P3"
    with pytest.raises(EnvelopeError, match="priority"):
        Envelope.from_mapping(wire)


@pytest.mark.parametrize("version", [0, -1, True, "1"])
def test_a_malformed_version_is_refused(version: object) -> None:
    """`True` is an `int` in Python, so a bare int check would ship it as version 1."""
    wire = envelope().as_mapping()
    wire["version"] = version
    with pytest.raises(EnvelopeError, match="version"):
        Envelope.from_mapping(wire)


def test_a_payload_that_cannot_reach_the_wire_is_refused() -> None:
    """An envelope that cannot be serialised is not an envelope."""
    with pytest.raises(EnvelopeError, match="JSON"):
        envelope(payload={"when": datetime(2026, 7, 25, tzinfo=UTC)})


def test_a_round_trip_through_the_wire_preserves_theenvelope() -> None:
    """Publish and consume must agree on every field, including the timestamp."""
    original = envelope(payload={"alias": "acme", "seats": 12})
    assert Envelope.from_json(original.to_json()) == original


def test_the_payload_cannot_be_mutated_after_construction() -> None:
    """`event_id` identifies one payload; an editable payload makes dedupe a lie."""
    source: dict[str, object] = {"alias": "acme"}
    built = envelope(payload=source)
    source["alias"] = "changed"
    assert built.payload["alias"] == "acme"
    with pytest.raises(TypeError):
        built.payload["alias"] = "changed"  # type: ignore[index]


def test_payload_growth_within_a_version_does_not_break_an_older_consumer() -> None:
    """Additive evolution, and why consumers upgrade before producers.

    A producer adds a payload key without bumping `version`. A consumer written
    against the older payload still parses the envelope and still reads what it
    knows — so the estate can deploy the consumer first and the producer after.
    """
    grown = envelope(payload={"alias": "acme", "residency_region": "JO"}).to_json()
    parsed = Envelope.from_json(grown)
    assert parsed.payload["alias"] == "acme"
    assert parsed.version == 1


def test_the_ordering_key_is_tenant_and_type() -> None:
    """The only key ordering is guaranteed against, made structural."""
    assert envelope(tenant_alias="7", type_="ctm.tenant.suspended").ordering_key == (
        "7",
        "ctm.tenant.suspended",
    )


# --- Fail-closed channel use ------------------------------------------------


def test_delivering_on_a_channel_with_no_consumer_is_refused() -> None:
    """Fail closed: a message with nobody to take it waits, it is not discarded."""
    broker = InMemoryBroker()
    broker.publish(CHANNEL, envelope())
    with pytest.raises(ChannelError, match="no consumer"):
        broker.deliver(CHANNEL)

    recorder = Recorder()
    broker.subscribe(CHANNEL, recorder)
    assert broker.deliver(CHANNEL).delivered == 1


def test_a_second_consumer_on_a_channel_is_refused() -> None:
    """A channel is consumed serially — that is what makes the ordering guarantee true."""
    broker = InMemoryBroker()
    broker.subscribe(CHANNEL, Recorder())
    with pytest.raises(ChannelError, match="already has a consumer"):
        broker.subscribe(CHANNEL, Recorder())


# --- At-least-once, never exactly-once --------------------------------------


def test_the_substrate_does_not_deduplicate() -> None:
    """The negative half of the contract, asserted rather than assumed.

    At-least-once means a redelivery reaches the consumer. If this ever passes
    with one effect, the substrate has started promising exactly-once — which
    over a network it cannot keep, and which would leave every consumer trusting
    a guarantee that silently fails.
    """
    broker = InMemoryBroker()
    recorder = Recorder()
    broker.subscribe(CHANNEL, recorder)

    redelivered = envelope(event_id="01J0-DUPLICATE")
    broker.publish(CHANNEL, redelivered)
    broker.publish(CHANNEL, redelivered)
    broker.deliver(CHANNEL)

    assert recorder.event_ids == ["01J0-DUPLICATE", "01J0-DUPLICATE"]


def test_a_redelivered_envelope_produces_one_effect_not_two() -> None:
    """The reference consumer: dedupe on `event_id` through an idempotency store.

    A redelivery is indistinguishable from a duplicate publish at the consumer,
    which is precisely why the consumer — not the substrate — carries the key.
    """
    broker = InMemoryBroker()
    effects = Recorder()
    store = IdempotencyStore()
    broker.subscribe(CHANNEL, deduplicating(effects, store))

    redelivered = envelope(event_id="01J0-DUPLICATE")
    broker.publish(CHANNEL, redelivered)
    broker.publish(CHANNEL, redelivered)
    report = broker.deliver(CHANNEL)

    assert effects.event_ids == ["01J0-DUPLICATE"]
    assert report.delivered == 2, "both copies were delivered; only the effect was deduplicated"
    assert len(store) == 1


def test_distinct_events_are_not_confused_for_duplicates() -> None:
    """Dedupe keys on `event_id`, not on the payload or the type."""
    broker = InMemoryBroker()
    effects = Recorder()
    broker.subscribe(CHANNEL, deduplicating(effects, IdempotencyStore()))

    broker.publish(CHANNEL, envelope(event_id="a"))
    broker.publish(CHANNEL, envelope(event_id="b"))
    broker.deliver(CHANNEL)

    assert effects.event_ids == ["a", "b"]


def test_a_rejected_event_is_not_recorded_as_applied() -> None:
    """Recording before the effect would turn at-least-once into at-most-once.

    The dead-lettered message must remain reprocessable, so the store learns
    about an event only after its effect actually happened.
    """
    store = IdempotencyStore()
    with pytest.raises(ValueError, match="cannot process"):
        deduplicating(poison_consumer, store)(envelope(event_id="poison"))
    assert not store.has_applied("poison")


# --- Dead-letter queue, per channel -----------------------------------------


def test_a_poison_message_lands_in_the_dead_letter_queue_and_stays_retrievable() -> None:
    """It must not vanish — and inspecting the queue must not empty it either."""
    broker = InMemoryBroker()
    broker.subscribe(CHANNEL, poison_consumer)
    poison = envelope(event_id="01J0-POISON")
    broker.publish(CHANNEL, poison)

    report = broker.deliver(CHANNEL)
    assert report == esb_ig.DeliveryReport(delivered=0, dead_lettered=1)

    dead = broker.dead_letters(CHANNEL)
    assert [item.envelope for item in dead] == [poison]
    assert Envelope.from_json(dead[0].body) == poison
    assert "cannot process" in dead[0].reason
    assert broker.dead_letters(CHANNEL) == dead, "reading a DLQ must not consume it"


def test_a_poison_message_isolates_rather_than_blocking_the_channel() -> None:
    """The message behind the poison is delivered in the same drain."""
    broker = InMemoryBroker()
    recorder = Recorder()

    def reject_only_the_poison(delivered: Envelope) -> None:
        if delivered.event_id == "poison":
            raise RuntimeError("unprocessable")
        recorder(delivered)

    broker.subscribe(CHANNEL, reject_only_the_poison)
    for event_id in ("first", "poison", "second"):
        broker.publish(CHANNEL, envelope(event_id=event_id))

    report = broker.deliver(CHANNEL)

    assert recorder.event_ids == ["first", "second"]
    assert report == esb_ig.DeliveryReport(delivered=2, dead_lettered=1)
    assert len(broker.dead_letters(CHANNEL)) == 1


def test_the_dead_letter_queue_is_per_channel() -> None:
    """One channel's poison is invisible to another's — and cannot block it."""
    broker = InMemoryBroker()
    broker.subscribe(CHANNEL, poison_consumer)
    healthy = Recorder()
    broker.subscribe(OTHER_CHANNEL, healthy)

    broker.publish(CHANNEL, envelope(event_id="poison"))
    broker.publish(OTHER_CHANNEL, envelope(event_id="healthy"))
    broker.deliver(CHANNEL)
    broker.deliver(OTHER_CHANNEL)

    assert [item.envelope.event_id for item in broker.dead_letters(CHANNEL) if item.envelope] == [
        "poison"
    ]
    assert broker.dead_letters(OTHER_CHANNEL) == ()
    assert healthy.event_ids == ["healthy"]


# --- Ordering: per-tenant, per-type, and nothing wider ----------------------


def test_order_is_preserved_per_tenant_and_per_type() -> None:
    """The guarantee. Three interleaved streams, each delivered in publish order."""
    broker = InMemoryBroker()
    recorder = Recorder()
    broker.subscribe(CHANNEL, recorder)

    streams = {
        ("1", "ctm.tenant.created"): ["t1-created-1", "t1-created-2", "t1-created-3"],
        ("2", "ctm.tenant.created"): ["t2-created-1", "t2-created-2", "t2-created-3"],
        ("1", "ctm.tenant.suspended"): ["t1-suspended-1", "t1-suspended-2"],
    }
    interleaved = [
        ("1", "ctm.tenant.created", "t1-created-1"),
        ("2", "ctm.tenant.created", "t2-created-1"),
        ("1", "ctm.tenant.suspended", "t1-suspended-1"),
        ("1", "ctm.tenant.created", "t1-created-2"),
        ("2", "ctm.tenant.created", "t2-created-2"),
        ("1", "ctm.tenant.created", "t1-created-3"),
        ("1", "ctm.tenant.suspended", "t1-suspended-2"),
        ("2", "ctm.tenant.created", "t2-created-3"),
    ]
    for tenant_id, event_type, event_id in interleaved:
        broker.publish(
            CHANNEL, envelope(event_id=event_id, type_=event_type, tenant_alias=tenant_id)
        )

    broker.deliver(CHANNEL)

    for key, expected in streams.items():
        delivered = [item.event_id for item in recorder.received if item.ordering_key == key]
        assert delivered == expected, f"stream {key} was reordered"


def test_global_order_is_not_promised() -> None:
    """The limit. A higher priority class overtakes, across streams.

    This is why anything needing global order is a **command**, not an event:
    the substrate reorders across streams by design, and a consumer that infers
    a total order from two events it happened to see in sequence is wrong.
    """
    broker = InMemoryBroker()
    recorder = Recorder()
    broker.subscribe(CHANNEL, recorder)

    broker.publish(CHANNEL, envelope(event_id="earlier-p2", tenant_alias="1", priority=Priority.P2))
    broker.publish(
        CHANNEL,
        envelope(
            event_id="later-p0",
            tenant_alias="2",
            type_="ctm.tenant.suspended",
            priority=Priority.P0,
        ),
    )
    broker.deliver(CHANNEL)

    assert recorder.event_ids == ["later-p0", "earlier-p2"]


def test_a_drain_can_be_bounded() -> None:
    """`limit` lets a caller take a batch without draining the channel."""
    broker = InMemoryBroker()
    recorder = Recorder()
    broker.subscribe(CHANNEL, recorder)
    for index in range(3):
        broker.publish(CHANNEL, envelope(event_id=f"e{index}"))

    assert broker.deliver(CHANNEL, limit=2).delivered == 2
    assert broker.deliver(CHANNEL).delivered == 1


# --- Both adapters ----------------------------------------------------------


def test_both_adapters_satisfy_the_broker_protocol() -> None:
    """A seam with one conforming adapter is a hypothetical seam (design.md §3)."""
    assert isinstance(InMemoryBroker(), Broker)
    assert isinstance(RabbitMqBroker(TEST_BROKER_URL), Broker)


def test_the_deployment_adapter_is_not_on_the_consumer_surface() -> None:
    """W2-T10's ratified rule, pinned where it can regrow (W2-T20).

    `esb_ig` publishes the protocol, the errors, the reference consumer
    and the double; the adapter and its factory are `esb_ig.transport`'s. The
    graduation gate refuses an *import* of that module from anything staying
    behind in CTM — but nothing there would notice the name being re-exported
    here, and the surface would be back with the gate still green until the
    first consumer took it up. So the surface is asserted too, not only the
    imports.
    """
    assert "RabbitMqBroker" not in esb_ig.__all__
    assert "broker_from_environment" not in esb_ig.__all__
    assert not hasattr(esb_ig, "RabbitMqBroker")
    assert esb_ig.InMemoryBroker is InMemoryBroker


def test_the_transport_entry_point_imports_with_no_amqp_driver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The guarded import, re-asserted where it can still fail (W2-T20).

    Asserting this against `esb_ig` became trivially true once the
    adapter left that surface — the package no longer reaches `lib/rabbitmq` at
    all — so the claim moves to the module that does. It is exercised rather
    than inferred from collection: whether a driver happens to be installed in
    the environment is not something a test's strength may depend on, so `pika`
    is masked and the entry point is imported from source under the mask.
    `monkeypatch` restores every entry it displaced, so the modules the rest of
    the suite holds are the ones it started with.

    The package is named through `esb_ig.__name__` rather than by the literal
    `esb_ig`, because this module relocates with the seed and a
    hard-coded root is a self-reference the graduation dry-run's import rewrite
    cannot repair.

    **Why the cache is purged rather than the module loaded in isolation.**
    Loading `transport` alone from its file would resolve `lib.rabbitmq` out of
    the cache, where it is already imported and the mask cannot reach it — the
    guard would go unexercised and the test would pass for the wrong reason.
    The cost of purging is that, for the duration of this one test, the package
    in `sys.modules` is a second set of class objects: anything that resolved
    `Envelope` *during* it would compare unequal to one held from before.
    Nothing here does, and this repository pins no random-ordering plugin, so
    the window is this function body. It is written down rather than assumed.
    """
    monkeypatch.setitem(sys.modules, "pika", None)
    for name in [name for name in sys.modules if name.startswith(esb_ig.__name__)]:
        monkeypatch.delitem(sys.modules, name)

    reloaded = importlib.import_module(f"{esb_ig.__name__}.transport")

    assert reloaded.RabbitMqBroker.__name__ == RabbitMqBroker.__name__
    assert reloaded.RabbitMqBroker is not RabbitMqBroker, (
        "the module was served from cache, so the guard was never exercised"
    )


def test_publishing_without_a_driver_fails_closed_with_a_typed_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing driver is an operations fact, not an import-time crash.

    `sys.modules[name] = None` makes `import name` raise `ImportError` rather
    than `ModuleNotFoundError`, so this also pins that the guard catches the
    wider class — a driver that is installed but unimportable is the same fact
    to a caller.
    """
    monkeypatch.setitem(sys.modules, "pika", None)
    with pytest.raises(BrokerUnavailableError, match="AMQP driver"):
        RabbitMqBroker(TEST_BROKER_URL).publish(CHANNEL, envelope())


def test_delivering_without_a_driver_fails_closed_with_a_typed_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every path to the transport refuses the same way, not just publish."""
    monkeypatch.setitem(sys.modules, "pika", None)
    broker = RabbitMqBroker(TEST_BROKER_URL)
    broker.subscribe(CHANNEL, Recorder())
    with pytest.raises(BrokerUnavailableError, match="AMQP driver"):
        broker.deliver(CHANNEL)


# --- The broker adapter's declared topology ---------------------------------


class RecordingChannel:
    """An AMQP channel that records declarations instead of making them.

    The transport cannot run here, but the *topology* is decidable without a
    broker — and it is the half that carries the ticket's promises: priority
    classes and a dead-letter queue per channel. Asserting it keeps those two
    checkboxes on evidence rather than on prose (§11.3).
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def exchange_declare(self, **kwargs: Any) -> None:
        self.calls.append(("exchange_declare", kwargs))

    def queue_declare(self, **kwargs: Any) -> None:
        self.calls.append(("queue_declare", kwargs))

    def queue_bind(self, **kwargs: Any) -> None:
        self.calls.append(("queue_bind", kwargs))

    def arguments_for(self, queue: str) -> dict[str, Any]:
        for name, kwargs in self.calls:
            if name == "queue_declare" and kwargs["queue"] == queue:
                return dict(kwargs.get("arguments") or {})
        raise AssertionError(f"queue '{queue}' was never declared")


def test_each_channel_gets_its_own_dead_letter_queue() -> None:
    """Per channel, so one channel's poison cannot appear in — or block — another's."""
    first = topology_for(CHANNEL)
    second = topology_for(OTHER_CHANNEL)

    assert first.dead_letter_queue == f"{CHANNEL}.dlq"
    assert first.dead_letter_exchange == f"{CHANNEL}.dlx"
    assert {first.queue, first.dead_letter_queue}.isdisjoint(
        {second.queue, second.dead_letter_queue}
    )


def test_a_blank_channel_name_is_refused() -> None:
    """A blank name would declare a queue nobody can address."""
    with pytest.raises(ChannelError, match="non-blank"):
        topology_for("   ")


def test_the_declared_queue_carries_the_three_priority_classes() -> None:
    """`x-max-priority` comes from `Priority`, so the queue cannot lag the contract."""
    arguments = queue_arguments(topology_for(CHANNEL))
    assert arguments["x-max-priority"] == max(member.rank for member in Priority)
    assert arguments["x-max-priority"] == len(Priority) - 1


def test_declaring_a_channel_binds_its_dead_letter_queue_to_its_own_exchange() -> None:
    """The broker routes a rejected message itself — nothing here must stay alive for it."""
    topology = topology_for(CHANNEL)
    recording = RecordingChannel()

    assert declare(recording, CHANNEL) == topology
    assert (
        "queue_bind",
        {"queue": topology.dead_letter_queue, "exchange": topology.dead_letter_exchange},
    ) in recording.calls
    assert recording.arguments_for(topology.queue) == {
        "x-dead-letter-exchange": topology.dead_letter_exchange,
        "x-max-priority": max(member.rank for member in Priority),
    }
    assert recording.arguments_for(topology.dead_letter_queue) == {}


def test_a_published_message_carries_its_priority_class_and_deduplication_key() -> None:
    """The wire metadata a consumer and an operator both depend on."""
    urgent = envelope(event_id="01J0-URGENT", priority=Priority.P0)
    properties = publish_properties(urgent)

    assert properties["priority"] == Priority.P0.rank
    assert properties["message_id"] == urgent.event_id
    assert properties["correlation_id"] == urgent.correlation_id
    assert properties["delivery_mode"] == 2, "a message lost on restart is not at-least-once"


def test_the_priority_classes_rank_p0_highest() -> None:
    """P0 is the most urgent; the ranks are what the transport actually compares."""
    assert Priority.P0.rank > Priority.P1.rank > Priority.P2.rank
    assert Priority.P2.rank == 0


# --- Broker connection is deployment configuration (ADR-0005) ---------------


def test_an_unset_broker_url_refuses_to_build_a_broker() -> None:
    """No code-side default. A deployment that configured nothing does not connect."""
    with pytest.raises(BrokerConfigurationError, match=BROKER_URL_VARIABLE):
        broker_url_from_environment()
    with pytest.raises(BrokerConfigurationError, match=BROKER_URL_VARIABLE):
        broker_from_environment()


def test_a_blank_broker_url_refuses_to_build_a_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    """An exported-but-empty variable is a missing setting wearing a valid environment."""
    monkeypatch.setenv(BROKER_URL_VARIABLE, "   ")
    with pytest.raises(BrokerConfigurationError, match="unset or blank"):
        broker_url_from_environment()


@pytest.mark.parametrize(
    "url",
    [
        "amqp://guest:guest@broker.internal:5673/ctm",  # hardcoding: allow -- the pair under refusal
        "amqp://admin:admin@broker.internal:5673/ctm",  # hardcoding: allow -- the pair under refusal
        "amqp://rabbit:rabbit@broker.internal:5673/ctm",  # hardcoding: allow -- the pair under refusal
    ],
)
def test_a_well_known_broker_credential_refuses_to_build_a_broker(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    """ADR-0005 (3) applies to the broker too — `guest:guest` is its shipped default."""
    monkeypatch.setenv(BROKER_URL_VARIABLE, url)
    with pytest.raises(BrokerConfigurationError, match="well-known"):
        broker_url_from_environment()


def test_a_broker_url_with_no_password_refuses_to_build_a_broker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unauthenticated broker is a development convenience, not a deployment posture."""
    monkeypatch.setenv(BROKER_URL_VARIABLE, "amqp://ctm_broker_user@broker.internal:5673/ctm")
    with pytest.raises(BrokerConfigurationError, match="no password"):
        broker_url_from_environment()


def test_the_refusal_never_prints_the_configured_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """A configuration error is read in logs; it must not put the credential there."""
    monkeypatch.setenv(
        BROKER_URL_VARIABLE,
        "amqp://guest:guest@secret-broker.internal:5673/ctm",  # hardcoding: allow -- the value asserted absent from the refusal message
    )
    with pytest.raises(BrokerConfigurationError) as caught:
        broker_url_from_environment()
    message = str(caught.value)
    assert "secret-broker.internal" not in message
    assert "guest" not in message
    assert BROKER_URL_VARIABLE in message


def test_a_configured_broker_url_is_accepted_and_connects_to_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The cloud admin chooses host, port, credential and virtual host — all of them.

    Building the adapter must not connect: a composition root has to be able to
    construct one before the broker is reachable.
    """
    monkeypatch.setenv(BROKER_URL_VARIABLE, TEST_BROKER_URL)
    assert broker_url_from_environment() == TEST_BROKER_URL
    assert isinstance(broker_from_environment(), RabbitMqBroker)


# ── the tenant field is optional, and optional is not lax (wave-2 ticket 01) ──


def test_a_platform_level_event_needs_no_tenant() -> None:
    """`ctm.application.registered` concerns no tenant, so it must be representable.

    Before this, a required field forced a placeholder — and a placeholder tenant
    on a real event is how a consumer eventually acts on tenant zero.
    """
    built = envelope(type_="ctm.application.registered", tenant_alias=None)
    assert built.tenant_alias is None


@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_a_present_but_blank_tenant_alias_is_refused(blank: str) -> None:
    """Absent means "no tenant". Blank means something upstream went wrong.

    Letting blank through would make the optional field lax rather than optional,
    and a consumer cannot tell the two apart after the fact.
    """
    with pytest.raises(EnvelopeError, match="tenant_alias"):
        envelope(tenant_alias=blank)


def test_a_tenantless_event_still_has_an_ordering_key() -> None:
    """Ordering is per-tenant per-type, and a tenantless event is its own stream.

    Without this the ordering key would raise on exactly the events the optional
    field was added to permit.
    """
    built = envelope(type_="ctm.application.registered", tenant_alias=None)
    assert built.ordering_key == (None, "ctm.application.registered")


def test_the_wire_mapping_round_trips_a_tenantless_event() -> None:
    """The field is optional on the wire too, not only in the dataclass."""
    built = envelope(type_="ctm.application.registered", tenant_alias=None)
    restored = Envelope.from_mapping(built.as_mapping())
    assert restored.tenant_alias is None
    assert restored.application_code == built.application_code
