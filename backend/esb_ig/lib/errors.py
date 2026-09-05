"""Broker failure modes.

One leaf per failure a caller can act on differently: a missing driver or an
unreachable broker is an operations problem, while a channel used wrongly is a
programming one. Both refuse the operation — no error here carries a fallback,
because a fallback on a delivery path is how an event silently disappears.
"""

from __future__ import annotations

from .base import EsbIgError

__all__ = [
    "BrokerConfigurationError",
    "BrokerError",
    "BrokerUnavailableError",
    "ChannelError",
]


class BrokerError(EsbIgError):
    """Base class for every failure raised by the message substrate."""


class BrokerConfigurationError(EsbIgError):
    """The broker's deployment configuration is absent, blank or refused.

    A **sibling** of `BrokerError` rather than a child, because it is not a failure of
    the message substrate: nothing has been attempted yet. It is raised at startup, by
    `lib/config.py`, when the broker URL is unset or carries a shipped default credential
    — so it says *this deployment is misconfigured*, which is a different thing for an
    operator to do than *the broker is down*.

    It was `backend.core.errors.ConfigurationError` until the graduation re-rooting. No
    code in this estate caught that type, which is why the change is a contract
    correction rather than a behavioural one.
    """


class BrokerUnavailableError(BrokerError):
    """The broker cannot be reached, or its driver is not installed.

    Publication is refused rather than buffered in the process: a buffer that
    outlives the request is an outbox, and the outbox lives in the producer's
    own transaction — not here.
    """


class ChannelError(BrokerError):
    """A channel was used in a way its contract does not allow.

    Raised for delivery on a channel with no consumer, and for a second
    consumer on a channel that already has one. Both fail closed: silently
    dropping a message, or serving a channel from two consumers, would each
    break a guarantee the interface makes.
    """
