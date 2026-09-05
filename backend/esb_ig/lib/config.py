"""Broker connection parameters — deployment configuration, never code.

ADR-0005 settles this for the database; the same reasoning governs the broker,
and for the same reason. A code-side default means a deployment that configured
nothing still comes up — pointed at a host nobody chose, or authenticated with a
credential everybody knows. So there is **no default of any kind** here: an
unset connection URL refuses to build a broker.

The variable is read from the process environment only, exactly as
`backend.core.config` reads the DSN, and for the same reason: a file present on
one machine and absent on another is how "works here, fails there" starts.
"""

from __future__ import annotations

import os

from .credentials import shipped_default_credential
from .errors import BrokerConfigurationError

__all__ = [
    "BROKER_URL_VARIABLE",
    "broker_url_from_environment",
]

# One constant, so graduation to the ESB/IG repository is a one-line change
# rather than a search. The prefix is the deployment's namespace, not the
# package's: today the seed runs inside CTM.
BROKER_URL_VARIABLE = "CTM_BROKER_URL"

# Credential pairs a scanner tries first, `guest:guest` being the shipped
# default of the broker this adapter targets. This lives in code rather than in
# an LOV for the same reason the database list does: it is a security invariant,
# not a business choice an operator should be able to widen.
_WELL_KNOWN_CREDENTIALS: frozenset[tuple[str, str]] = frozenset(
    {
        ("guest", "guest"),
        ("guest", "password"),
        ("admin", "admin"),
        ("admin", "password"),
        ("rabbit", "rabbit"),
        ("rabbitmq", "rabbitmq"),
    }
)


def broker_url_from_environment() -> str:
    """Read the broker connection URL, or refuse.

    Returns:
        The configured URL, exactly as the deployment set it. Host, port, user,
        password and virtual host all come from here, so the cloud admin chooses
        every one of them.

    Raises:
        BrokerConfigurationError: The variable is unset or blank, carries no password,
            or uses a well-known default credential pair. The sub-system does
            not connect.
    """
    raw = os.environ.get(BROKER_URL_VARIABLE, "")
    if not raw.strip():
        raise BrokerConfigurationError(
            f"CTM refuses to connect to the broker: {BROKER_URL_VARIABLE} is unset or blank. "
            f"There is no default — the deployment supplies host, port, credentials and "
            f"virtual host (ADR-0005)."
        )
    _refuse_a_shipped_default_credential(raw)
    return raw


def _refuse_a_shipped_default_credential(url: str) -> None:
    """Reject a blank password or a well-known user/password pair.

    The detection is `.credentials`, which is a COPY of CTM's `core.credentials`
    taken on graduation — see that module's docstring. Inside CTM the two shared
    one implementation so they could not drift about what they refuse; across two
    repositories they can, and that is the price of the package being installable.

    Nothing here is echoed back: a configuration error is read in logs, and must
    not put the credential there.
    """
    reason = shipped_default_credential(url, _WELL_KNOWN_CREDENTIALS)
    if reason is not None:
        raise BrokerConfigurationError(
            f"CTM refuses to connect to the broker: {BROKER_URL_VARIABLE} {reason}"
        )
