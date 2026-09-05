"""The frozen event envelope — the estate's wire contract, and a second entry point.

This module is an entry point on purpose: a producer or a consumer needs the
envelope's **shape** without needing a broker, and gating the shape behind the
transport would make every schema test require infrastructure.

**Ten fields, frozen** (platform CLAUDE.md §7): `event_id`, `type`, `version`,
`occurred_at`, `correlation_id`, `application_code`, `tenant_alias`, `producer`,
`priority`, `payload`. Not nine, not eleven. `from_mapping` refuses a wire
message that is missing one or carries an extra, because "the contract is
whatever the last producer sent" is how a wire contract stops being one.

**Evolution is additive within a version, and additive means the payload.** A
new envelope field is a new envelope, not an addition — so the *envelope* is
closed and the *payload* is open: an unknown payload key is carried, never
rejected, which is what lets consumers upgrade before producers. Bump `version`
only for a change that is not additive.

**Identifiers are CODES on the wire, never row ids** (`plan.md`). `tenant_alias`
and `application_code`
are integers in the control-plane database today; carrying them as text here
means a future key type is not an envelope change.

Everything invalid raises `EnvelopeError` — construction never repairs a value
and never substitutes a default (CLAUDE.md §2.2, fail closed).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, fields
from datetime import datetime
from enum import Enum
from types import MappingProxyType

from .lib.base import EsbIgError

__all__ = [
    "ENVELOPE_FIELD_NAMES",
    "Envelope",
    "EnvelopeError",
    "Priority",
]


class EnvelopeError(EsbIgError):
    """A value does not satisfy the envelope contract.

    Raised on construction and on parsing. The envelope is refused rather than
    coerced: a repaired envelope is an envelope nobody agreed to.
    """


class Priority(Enum):
    """The three delivery classes carried on the wire.

    This set is **not** an LOV. An LOV is a value a business user may change
    without a deployment (CLAUDE.md §5.2); these three are the frozen wire
    contract every sub-system compiles against, so widening the set is a
    protocol change that every consumer must agree to first.
    """

    # The class SET is a wire contract, per this class's own docstring above; the
    # mapping of event type to class is an LOV
    # (`config/lov/vocabularies/notification_category.json`). Marked one line at a
    # time rather than exempting "P0" in `allow_values`, which is global over
    # `backend` and `scripts` and would exempt any future unrelated `P0`.
    P0 = "P0"  # hardcoding: allow -- a wire contract, not a business value
    P1 = "P1"  # hardcoding: allow -- a wire contract, not a business value
    P2 = "P2"  # hardcoding: allow -- a wire contract, not a business value

    @property
    def rank(self) -> int:
        """Delivery precedence — higher is served first.

        A number rather than the member order because the transport needs one:
        it is published as a message priority and declared as the queue's
        maximum.
        """
        return _PRIORITY_RANKS[self]


# P0 is the most urgent, so it carries the highest rank. Ranks start at zero
# because that is the floor a message-priority field accepts.
_PRIORITY_RANKS: Mapping[Priority, int] = MappingProxyType(
    {
        Priority.P0: 2,
        Priority.P1: 1,
        Priority.P2: 0,
    }
)


def _require_text(name: str, value: object) -> str:
    """Return `value` as a non-blank string, or refuse it."""
    if not isinstance(value, str) or not value.strip():
        raise EnvelopeError(f"envelope field '{name}' must be a non-blank string")
    return value


def _optional_text(name: str, value: object) -> str | None:
    """A field that may be absent, but must not be present-and-blank.

    Absent is a platform-level event that concerns no tenant. Blank is a bug
    somewhere upstream, and letting it through is how a consumer acts on nothing
    while believing it acted on somebody.
    """
    if value is None:
        return None
    return _require_text(name, value)


@dataclass(frozen=True, slots=True)
class Envelope:
    """One event on the wire.

    Immutable: an envelope that can be edited after publication cannot be
    deduplicated on, because `event_id` would no longer identify one payload.

    Attributes:
        event_id: The deduplication key. Delivery is at-least-once, so a
            consumer that does not key on this **will** apply an effect twice.
        type: The event type, e.g. `ctm.tenant.created`. Which types exist is
            the producer's vocabulary, not this module's.
        version: Envelope-contract version, ≥ 1. Additive payload changes do
            not bump it; anything else does.
        occurred_at: When the fact happened — timezone-aware, ISO 8601 on the
            wire. A naive timestamp is refused, because "which midnight" is not
            answerable across a residency boundary.
        correlation_id: Ties an event to the request or command that caused it.
        application_code: The application dimension every sub-system carries,
            as a CODE. Codes travel; row ids do not (plan.md).
        tenant_alias: The owning tenant, as its company alias -- unique,
            immutable and public, so a consumer can act on it without calling
            back into CTM. Half of the ordering key. **None** for a
            platform-level event that concerns no tenant.
        producer: The sub-system that emitted this.
        priority: Delivery class. Higher classes are served first, which is
            exactly why global order is not promised.
        payload: The event body. JSON-serialisable, and read-only once
            constructed. Open to additive growth within a version.
    """

    event_id: str
    type: str
    version: int
    occurred_at: datetime
    correlation_id: str
    application_code: str | None
    tenant_alias: str | None
    producer: str
    priority: Priority
    payload: Mapping[str, object]

    def __post_init__(self) -> None:
        for name in (
            "event_id",
            "type",
            "correlation_id",
            "producer",
        ):
            _require_text(name, getattr(self, name))

        # THE TWO SCOPING FIELDS, and the rule is one rule rather than two exceptions
        # (ADR-0038). The envelope carries two scoping AXES, and each of these is null
        # precisely when the fact is not scoped on that axis -- never otherwise.
        #
        # The mirror was true all along without being stated. `tenant_alias` was optional
        # from the start, for the estate-scoped case: registering an application concerns
        # no tenant. `application_code` is the same shape seen from the other side: a
        # client is suspended for the CLIENT, not for one application, and
        # `ctm.tenant.created` precedes every entitlement that client will ever hold.
        #
        # It carried `str` until 2026-08-29 while `contracts/asyncapi.json` published
        # `must be null` on the four `ctm.tenant.*` types -- so the document mandated a
        # value this class refused, and an integrator generating a producer from the
        # published contract, which is what that document is FOR, would have had every
        # message rejected.
        #
        # Optional is NOT lax, and that distinction is the reason this is a loop rather
        # than a truthiness check: absent is a scope the fact does not have,
        # present-but-blank is a bug upstream, and letting a blank through is how a
        # consumer acts on nothing while believing it acted on somebody.
        for name in ("application_code", "tenant_alias"):
            value = getattr(self, name)
            if value is not None:
                _require_text(name, value)

        # `isinstance(True, int)` is True, so a bool would pass a bare int check
        # and travel as version 1.
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise EnvelopeError("envelope field 'version' must be an integer of at least 1")

        if not isinstance(self.occurred_at, datetime) or self.occurred_at.utcoffset() is None:
            raise EnvelopeError("envelope field 'occurred_at' must be a timezone-aware datetime")

        if not isinstance(self.priority, Priority):
            raise EnvelopeError(
                f"envelope field 'priority' must be one of "
                f"{', '.join(member.value for member in Priority)}"
            )

        if not isinstance(self.payload, Mapping):
            raise EnvelopeError("envelope field 'payload' must be a mapping")

        body = dict(self.payload)
        try:
            json.dumps(body)
        except (TypeError, ValueError) as exc:
            raise EnvelopeError(
                f"envelope field 'payload' is not JSON-serialisable: {exc}"
            ) from exc

        # Freeze the payload so the envelope's immutability is real rather than
        # declared: a caller holding a dict it published could otherwise change
        # what a later consumer sees.
        object.__setattr__(self, "payload", MappingProxyType(body))

    @property
    def ordering_key(self) -> tuple[str | None, str]:
        """The only key delivery order is guaranteed against: `(tenant_alias, type)`.

        Structural rather than documented, so the one guarantee the substrate
        makes is something code can point at.
        """
        return (self.tenant_alias, self.type)

    def as_mapping(self) -> dict[str, object]:
        """Render the wire form: ten keys, all JSON-native."""
        return {
            "event_id": self.event_id,
            "type": self.type,
            "version": self.version,
            "occurred_at": self.occurred_at.isoformat(),
            "correlation_id": self.correlation_id,
            "application_code": self.application_code,
            "tenant_alias": self.tenant_alias,
            "producer": self.producer,
            "priority": self.priority.value,
            "payload": dict(self.payload),
        }

    def to_json(self) -> str:
        """Serialise to the wire body."""
        return json.dumps(self.as_mapping(), ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> Envelope:
        """Parse a wire mapping, refusing anything that is not the ten fields.

        Args:
            data: The decoded wire message.

        Returns:
            The parsed envelope.

        Raises:
            EnvelopeError: A field is missing, unknown, or malformed. There is
                no partial parse — an envelope this process cannot fully
                understand is one it must not act on.
        """
        supplied = set(data)
        expected = set(ENVELOPE_FIELD_NAMES)
        if missing := expected - supplied:
            raise EnvelopeError(f"envelope is missing required field(s): {sorted(missing)}")
        if unknown := supplied - expected:
            raise EnvelopeError(
                f"envelope carries unknown field(s): {sorted(unknown)}. The envelope is frozen "
                f"at {len(ENVELOPE_FIELD_NAMES)} fields; additive change belongs in the payload"
            )

        occurred_at = data["occurred_at"]
        if not isinstance(occurred_at, str):
            raise EnvelopeError("envelope field 'occurred_at' must be an ISO 8601 string")
        try:
            parsed_at = datetime.fromisoformat(occurred_at)
        except ValueError as exc:
            raise EnvelopeError(f"envelope field 'occurred_at' is not ISO 8601: {exc}") from exc

        priority = data["priority"]
        try:
            parsed_priority = Priority(priority)
        except ValueError as exc:
            raise EnvelopeError(
                f"envelope field 'priority' must be one of "
                f"{', '.join(member.value for member in Priority)}"
            ) from exc

        version = data["version"]
        if isinstance(version, bool) or not isinstance(version, int):
            raise EnvelopeError("envelope field 'version' must be an integer of at least 1")

        payload = data["payload"]
        if not isinstance(payload, Mapping):
            raise EnvelopeError("envelope field 'payload' must be a mapping")

        return cls(
            event_id=_require_text("event_id", data["event_id"]),
            type=_require_text("type", data["type"]),
            version=version,
            occurred_at=parsed_at,
            correlation_id=_require_text("correlation_id", data["correlation_id"]),
            # Both scoping fields read with `data[...]` rather than `data.get(...)`:
            # PRESENCE stays required on all ten keys and the strict parse above has
            # already refused a missing one. It is the VALUE that may be null, and only on
            # these two (ADR-0038's axis rule). `_optional_text` still refuses a blank.
            application_code=_optional_text("application_code", data["application_code"]),
            tenant_alias=_optional_text("tenant_alias", data["tenant_alias"]),
            producer=_require_text("producer", data["producer"]),
            priority=parsed_priority,
            payload=payload,
        )

    @classmethod
    def from_json(cls, body: str) -> Envelope:
        """Parse a wire body.

        Raises:
            EnvelopeError: The body is not JSON, is not a JSON object, or does
                not satisfy the contract.
        """
        try:
            decoded = json.loads(body)
        except (TypeError, ValueError) as exc:
            raise EnvelopeError(f"envelope body is not valid JSON: {exc}") from exc
        if not isinstance(decoded, dict):
            raise EnvelopeError("envelope body must be a JSON object")
        return cls.from_mapping(decoded)


# Derived from the dataclass rather than written out, so the contract and the
# type cannot drift apart. A test pins this against the ten names in CLAUDE.md §7.
ENVELOPE_FIELD_NAMES: tuple[str, ...] = tuple(field.name for field in fields(Envelope))
