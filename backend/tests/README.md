# The test tree

**This directory is empty of tests on purpose, and its emptiness is reported rather than
hidden.** `pyproject.toml` points `testpaths` here; pytest exits **5 — no tests collected**
against an empty directory and **4 — usage error** against a missing one, and CI reads the
first as **NOT-RUN** and the second as a broken configuration. Deleting this README deletes
the directory, which turns a lane that honestly says *there is no suite* into a lane that
fails for a reason nobody intended.

The lane is **self-retiring**: it is pytest's own exit code that decides, not a second
reading of the tree, so the moment the first `test_*.py` lands here the lane starts blocking
with nothing for anyone to remember to switch on.

## What lands here

The suite that moves with the `esb_ig` seed when it graduates out of CTM (**W2-T10**) —
today it lives at `..\..\CTM\backend\tests\`, and moving it is a separate step done by
somebody else. It is not copied here in advance: a stub test proves nothing and a stub
module is dead code the boundary gate would then have to reason about.

- the envelope contract and its frozen field enumeration
- the broker protocol, its in-memory adapter, and the conformance suite that makes that
  adapter the executable definition of the protocol rather than a second implementation
- the transport adapter's semantics against a **real** broker — redelivery after an
  unacknowledged consumer crash, server-side dead-letter routing, priority ordering across
  two concurrent consumers. Those three are what a server performs and a fake cannot fake,
  which is why `.github/workflows/ci.yml` already runs a RabbitMQ service container: the
  broker is provisioned **before** the suite arrives, so the day it lands there is nothing
  left to stand up.

No `__init__.py` — the test tree is not a package here, matching CTM's `backend/tests/`.
