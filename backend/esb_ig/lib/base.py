"""The one exception root every ESB/IG failure descends from.

**Why this is its own module rather than a class in `errors.py`.** The root spans the
whole sub-system — the broker, the envelope and deployment configuration — while
`errors.py` is specifically *broker* failure modes. Putting the root there would make
`envelope.py` import a module named for something it is not, and reading the hierarchy
would mean knowing that "broker errors" secretly contains the base of everything.

It is not in `__init__.py` either, and that one is structural rather than aesthetic:
`__init__` imports `lib.errors`, so a root defined in `__init__` would have `lib.errors`
importing back into it. A leaf that imports nothing cannot participate in a cycle.

**Why the root is ESB/IG's and not CTM's.** Every error here used to descend from
`CtmError`, which was invisible while this package lived in CTM's tree and becomes wrong
the moment it graduates (`W2-T10`): a consumer would have to import CTM's exception
hierarchy to catch a broker failure, which is the dependency direction the graduation
exists to cut. A sub-system owns its own failures or it is not a sub-system.
"""

from __future__ import annotations

__all__ = ["EsbIgError"]


class EsbIgError(Exception):
    """Base class for every error raised by the ESB/IG mediation plane.

    One root so a caller can catch everything this package raises without a bare
    `except`, and leaves that stay **siblings** rather than nesting: a malformed envelope
    is a producer defect and an unreachable broker is an operations problem, and a caller
    that catches one must not silently acquire the other.

    Like CTM's own root, no error descending from this carries a recovery value. A
    recovery value on a delivery path is how a fail-open default gets reintroduced.
    """
