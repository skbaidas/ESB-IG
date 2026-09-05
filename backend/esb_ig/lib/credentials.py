"""DSN inspection — is this credential a shipped default?

**This is a COPY of CTM's `backend/core/credentials.py`, taken on graduation
(`W2-T10` step (a)), and the two can now drift.** That is stated first because a
reader will otherwise assume they are kept in sync, and nothing keeps them in
sync. It is not a smell: `N3` forbids a sub-system importing a consumer's
package, there is no shared-kernel distribution between the two repositories, and
a graduated package that reached back into CTM would not be graduated. Copying
the control was the alternative to leaving `esb_ig` unable to be installed at
all.

**Only what `config.py` calls travelled.** CTM's module answers two questions
about a DSN — *is this credential a shipped default?* and *which server and
database does this address?* The second, `connection_target`, is CTM's: it exists
for ADR-0006's two-database rule, which is a control-plane concern and no
business of a broker adapter. Taking it would have made this file look like a
shared kernel, which is exactly what it is not.

ADR-0005 (3) is one rule — *refuse a blank or well-known credential at startup* —
and it applies to the database, the broker, and anything else that
authenticates. It was implemented twice in CTM once already, which is how two
copies of a security control start disagreeing about what they refuse. This is a
third copy, and the honest mitigation is not pretending otherwise but stating
where it came from and what it covers.

**Both DSN spellings are inspected.** A URL-only check is a fail-open gap rather
than a partial one: a keyword-form DSN such as `host=b user=guest password=guest`
sails through a URL-only guard carrying the exact pair the guard exists to
reject. The keyword form is therefore parsed too.

What is deliberately *not* attempted: resolving a service file or environment
fallbacks. Those are the driver's business, and guessing at them would produce
refusals nobody can act on. The limit is stated here so a later reader extends it
knowingly rather than assuming it was covered.
"""

from __future__ import annotations

import shlex
from urllib.parse import unquote, urlsplit

__all__ = [
    "NO_PASSWORD",
    "WELL_KNOWN_PAIR",
    "shipped_default_credential",
]

NO_PASSWORD = (
    "carries no password. Trust authentication is a development convenience, "
    "not a deployment posture (ADR-0005)."
)
WELL_KNOWN_PAIR = (
    "uses a well-known default credential pair. This is the exposure ADR-0005 "
    "exists to close: a service reachable with a shipped default account. "
    "Create a dedicated least-privilege account."
)


def _from_url(dsn: str) -> tuple[str, str] | None:
    """Credentials from a `scheme://user:password@host` DSN, if it is one."""
    split = urlsplit(dsn)
    if not split.scheme or split.username is None:
        return None
    return unquote(split.username), unquote(split.password or "")


def _from_keywords(dsn: str) -> tuple[str, str] | None:
    """Credentials from a libpq-style `key=value key=value` DSN, if it is one.

    `shlex` handles the single-quoting such a form allows around a value
    containing spaces. A DSN that does not split cleanly is left alone: this
    guard refuses credentials, and refusing something it merely failed to parse
    would be a different behaviour.
    """
    if "=" not in dsn:
        return None
    try:
        tokens = shlex.split(dsn)
    except ValueError:
        return None

    settings = dict(
        token.split("=", 1) for token in tokens if "=" in token and not token.startswith("=")
    )
    if "user" not in settings:
        return None
    return settings["user"], settings.get("password", "")


def shipped_default_credential(dsn: str, well_known: frozenset[tuple[str, str]]) -> str | None:
    """Why `dsn` must be refused, or `None` if it carries no shipped-default credential.

    A reason is returned rather than raised so each caller can name the variable
    the operator actually has to change, without this module knowing about any of
    them.

    Args:
        dsn: The connection string, in either URL or keyword form.
        well_known: The (user, password) pairs to refuse, compared case-folded.
            Each caller supplies its own — a broker's shipped defaults are not a
            database's.

    Returns:
        `NO_PASSWORD`, `WELL_KNOWN_PAIR`, or `None`. `None` also covers a DSN
        this module cannot parse, which is left to the driver rather than guessed
        at — see the module docstring for what that excludes.
    """
    credentials = _from_url(dsn) or _from_keywords(dsn)
    if credentials is None:
        return None

    user, password = credentials
    if not password:
        return NO_PASSWORD
    if (user.casefold(), password.casefold()) in well_known:
        return WELL_KNOWN_PAIR
    return None
