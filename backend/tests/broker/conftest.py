"""Fixtures for the live-broker transport suite.

**Why this is not in `backend/tests/conftest.py`.** The `needs_db` plumbing it
mirrors lives in the root conftest, so that is where a reviewer will look first
— the deviation is deliberate and has two reasons. The fixtures below serve
exactly one directory and no other test can use them without a broker. And the
did-not-skip guard has to run this suite *by path*: `pytest -m needs_broker`
prints `N deselected`, which the guard's grep reads as a skip, so the suite must
be addressable as a directory regardless of where its fixtures live.

Everything else mirrors `needs_db` exactly: the variable is captured at import
before the per-test purge can remove it, an unset variable **skips** with the
result named as *not-run, not a pass*, and CI asserts these tests did not skip.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from esb_ig.lib.rabbitmq import topology_for

# Captured before any test can purge it. The root conftest deletes every `CTM_`
# variable per test so a stray developer environment cannot turn a fail-closed
# test green; reading this at call time instead would make a `needs_broker` test
# skip because of that purge rather than because no broker was configured.
TEST_BROKER_URL: str | None = os.getenv("ESB_IG_TEST_BROKER_URL")


@pytest.fixture
def broker_url() -> str:
    """URL for tests marked `needs_broker`; skips when no broker is configured.

    A skip here is **not-run**, which platform §11.3 says is not a pass. CI
    asserts these tests did not skip.
    """
    if not TEST_BROKER_URL:
        pytest.skip("ESB_IG_TEST_BROKER_URL is unset — result is not-run, not a pass")
    return TEST_BROKER_URL


@pytest.fixture
def amqp(broker_url: str) -> Iterator[Any]:
    """An open connection to the configured broker.

    The driver is imported here rather than at module scope, and deliberately
    **not** through `pytest.importorskip`: a deployment that configured a broker
    and installed no driver is a red result, not a skipped one. The skip belongs
    to `broker_url` and to nothing else, so there is exactly one reason these
    tests can decline to run.
    """
    import pika

    connection = pika.BlockingConnection(pika.URLParameters(broker_url))
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture
def transport_channel(amqp: Any) -> Iterator[str]:
    """A channel name unique to this test, with its topology removed afterwards.

    Unique because these tests assert on queue *contents*: a name shared with a
    previous run would let a leftover message read as a redelivery, which is
    precisely the fact one of them is trying to establish.
    """
    name = f"ctm.transport.{uuid4().hex}"
    yield name
    topology = topology_for(name)
    channel = amqp.channel()
    for queue in (topology.queue, topology.dead_letter_queue):
        channel.queue_delete(queue=queue)
    channel.exchange_delete(exchange=topology.dead_letter_exchange)
