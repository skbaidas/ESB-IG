# The test tree

**The suite arrived on 2026-09-05, under `W2-T10` step (a).** This file used to say the
directory was empty on purpose and describe what *would* land; it now describes what did.

**Nobody switched the lane on, and that was the design.** It is pytest's own exit code that
decides — never a second reading of the tree — so the lane stopped reporting NOT-RUN and
started blocking the moment the first `test_*.py` appeared. The RabbitMQ service container
had been running against an empty suite since 2026-09-03 for the same reason: **the day the
suite landed was a move rather than a move plus an infrastructure change.** One thing that
promise did not cover is recorded below.

## What is here

- the envelope contract and its frozen field enumeration
- the broker protocol, its in-memory adapter, and the conformance suite that makes that
  adapter the executable definition of the protocol rather than a second implementation
- the transport adapter's semantics against a **real** broker — redelivery after an
  unacknowledged consumer crash, server-side dead-letter routing, priority ordering across
  two concurrent consumers. Those three are what a server performs and a fake cannot fake
- two AST walks over the seed's own tree: that every intra-package import is **relative**,
  so the package survives being installed under a different root, and that it imports
  **nothing** first-party from outside itself

## What a green here does NOT say

**86 tests, of which 13 are `needs_broker` and skip without one.** §11.3: a skip is not-run,
which is not a pass — so a local green over 73 is strictly weaker than CI's, and the SKIP
count is the number to read rather than the exit code.

**The gateway plane is not here and is not built.** Mediated egress, the SSRF guard (CTM §14
`EGRESS-PROSE`), the REST/SOAP/EDI handlers and the hybrid agent are specified and
unimplemented. This suite says the mediation **library** holds. It never says the sub-system
exists.

**The infrastructure promise had one gap, found on move day.** The broker was provisioned
ahead of the suite, but `pika` was not installed — the workflow derived its requirements
from the `dev` extra alone and `broker` was excluded on the reasoning that nothing here
imported it yet. That would have failed **silently**: the driver import is guarded and lazy,
so nothing raises at collection and all 13 `needs_broker` tests would have skipped against a
healthy broker sitting right there.


No `__init__.py` — the test tree is not a package here, matching CTM's `backend/tests/`.
