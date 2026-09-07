r"""Tests for the published-surface gate (`EM03`).

Run from the repo root (`D:\PMO\Phase 1\ESB-IG`):

    python -m pytest backend/tests/test_published_surface_gate.py -q

**What the gate claims, stated here because the gate must not overclaim it.**
`W2-T10` ratifies that ESB/IG publishes exactly three things — the protocol, the envelope
and the conformance double — and that *"the RabbitMQ adapter is NOT published"*. Python has
no private modules, so **nothing in this repository can stop a consumer writing
`import esb_ig.transport`**. What it can do is make the adapter unable to arrive on the
published surface **silently**, which is the failure that has actually happened: the
adapter sat on the root surface until `W2-T20`, where every consumer could reach it.

The consumer-side half is CTM's and already exists — `check_graduation.py`'s
`stranded-transport-import`, keyed on `NON_CONSUMER_ENTRY_POINTS`. Neither half is the
control on its own, and `EM03` §1 records the correction.

Every rule is asserted against **both** a violating sample and a clean one. A detector that
never fires and one that cannot fire are indistinguishable in an exit code — this file's
subject is a gate, and a gate is code that can be wrong in two directions.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import check_published_surface as gate

# A minimal package root that satisfies the gate. Written as source rather than imported so
# the negative controls below can mutate exactly one thing about it.
_CLEAN_ROOT = '''\
"""A package docstring."""

from .lib.broker import Broker, Consumer, DeadLetter, DeliveryReport, InMemoryBroker
from .lib.consumer import IdempotencyStore, deduplicating
from .lib.errors import BrokerError, BrokerUnavailableError, ChannelError

__all__ = [
    "Broker",
    "BrokerError",
    "BrokerUnavailableError",
    "ChannelError",
    "Consumer",
    "DeadLetter",
    "DeliveryReport",
    "IdempotencyStore",
    "InMemoryBroker",
    "deduplicating",
]
'''


class TestTheDeclaredSurface:
    """`__all__` read from source by AST, never by importing and reading the attribute.

    Importing to ask what a module publishes runs the module, which is the thing under
    test — and on a synthetic sample there is nothing to import at all. The AST also sees a
    surface that a runtime read cannot: a name listed in `__all__` that does not resolve is
    still a published claim, and it is the shape a half-finished re-export leaves behind.
    """

    def test_it_reads_the_names_in_order_declared(self) -> None:
        assert gate.declared_surface(_CLEAN_ROOT)[:2] == ("Broker", "BrokerError")

    def test_a_module_with_no_all_declares_nothing(self) -> None:
        """Distinct from an EMPTY `__all__`, and the gate must not collapse them.

        No `__all__` means the surface is whatever happens to be bound at module level,
        which is not a decision anyone took. It is reported rather than read as an empty
        surface, because an empty surface would satisfy every rule below trivially.
        """
        assert gate.declared_surface('"""No __all__ here."""\nx = 1\n') is None

    def test_a_dynamically_built_all_is_refused_rather_than_guessed_at(self) -> None:
        """`__all__ = [*_PUBLIC, "Extra"]` is not a list the AST can enumerate.

        A gate that silently read what it could would report a surface smaller than the
        real one, and every rule below would then pass over the names it could not see.
        """
        with pytest.raises(gate.SurfaceError, match="literal"):
            gate.declared_surface('__all__ = [*_PUBLIC, "Extra"]\n')


class TestTheAdapterMayNotReachThePublishedSurface:
    """The rule `W2-T10` ratifies, in the only form this repository can assert it."""

    def test_the_clean_sample_is_silent(self) -> None:
        assert gate.judge_source(_CLEAN_ROOT, where="sample") == []

    def test_a_direct_re_export_of_the_adapter_is_refused(self) -> None:
        """The regression that has already happened once — the adapter sat here until W2-T20.

        **Two findings, not one, and the redundancy is deliberate.** A full re-export both
        reaches the adapter and widens the published set, and they are two facts about the
        change rather than one fact reported twice: the import could be removed while the
        name stayed in `__all__` (a dangling claim), or the name dropped while the import
        stayed (an unexported reach that the next commit re-exports). Collapsing them would
        make the remaining half silent.
        """
        violating = _CLEAN_ROOT.replace(
            "from .lib.errors import",
            "from .lib.rabbitmq import RabbitMqBroker\nfrom .lib.errors import",
        ).replace('    "Broker",', '    "Broker",\n    "RabbitMqBroker",')
        findings = gate.judge_source(violating, where="sample")
        assert {one["category"] for one in findings} == {
            gate.CATEGORY_ADAPTER_REACHED,
            gate.CATEGORY_SURFACE_CHANGED,
        }
        reached = next(one for one in findings if one["category"] == gate.CATEGORY_ADAPTER_REACHED)
        assert "rabbitmq" in reached["detail"]

    def test_an_aliased_re_export_is_refused_too(self) -> None:
        """`as` is the obvious way past a rule that matched exported NAMES.

        The rule is about the module the name comes from, never about the name, so
        `from .lib.rabbitmq import RabbitMqBroker as Broker2` is the same violation.
        """
        violating = _CLEAN_ROOT.replace(
            "from .lib.errors import",
            "from .lib.rabbitmq import RabbitMqBroker as Broker2\nfrom .lib.errors import",
        )
        assert [one["category"] for one in gate.judge_source(violating, where="sample")] == [
            gate.CATEGORY_ADAPTER_REACHED
        ]

    def test_importing_the_transport_entry_point_is_refused(self) -> None:
        """The other spelling: reaching the adapter through its own entry point."""
        violating = _CLEAN_ROOT.replace(
            "from .lib.errors import",
            "from .transport import RabbitMqBroker\nfrom .lib.errors import",
        )
        assert [one["category"] for one in gate.judge_source(violating, where="sample")] == [
            gate.CATEGORY_ADAPTER_REACHED
        ]

    def test_an_absolute_spelling_is_refused(self) -> None:
        """A relative import is the house style; an absolute one is still an import."""
        violating = _CLEAN_ROOT.replace(
            "from .lib.errors import",
            "from esb_ig.lib.rabbitmq import RabbitMqBroker\nfrom .lib.errors import",
        )
        assert [one["category"] for one in gate.judge_source(violating, where="sample")] == [
            gate.CATEGORY_ADAPTER_REACHED
        ]

    def test_naming_the_adapter_in_prose_is_not_a_violation(self) -> None:
        """The detector reads code, never text.

        `transport.py`'s own docstring explains at length why the adapter is not published,
        and `__init__.py`'s says a consumer must not take it. A gate that could not tell
        prose from an import would fire on the documentation for the rule — a failure mode
        this estate has recorded more than once.
        """
        prose = _CLEAN_ROOT.replace(
            '"""A package docstring."""',
            '"""Do not import lib.rabbitmq or esb_ig.transport from here."""',
        )
        assert gate.judge_source(prose, where="sample") == []


class TestTheSurfaceIsARatifiedSET:
    """A change to what is published is a decision, so it comes back for review.

    This is the weakest of the three rules and the one most likely to be read as
    bureaucracy, so its reason is worth stating: `W2-T10` ratifies the published set, five
    sub-systems are to compile against it, and §7's *consumers upgrade before producers* is
    meaningless if the set can widen without anyone noticing. The remedy when it fires is to
    change the enumeration in the same commit, which is what makes the change visible.
    """

    def test_the_clean_sample_matches_the_ratified_set(self) -> None:
        assert set(gate.declared_surface(_CLEAN_ROOT) or ()) == set(gate.RATIFIED_SURFACE)

    def test_an_added_name_is_reported(self) -> None:
        widened = _CLEAN_ROOT.replace('    "Broker",', '    "Broker",\n    "Extra",')
        findings = gate.judge_source(widened, where="sample")
        assert [one["category"] for one in findings] == [gate.CATEGORY_SURFACE_CHANGED]
        assert "Extra" in findings[0]["detail"]

    def test_a_removed_name_is_reported_too(self) -> None:
        """Narrowing is a breaking change for a consumer and must not pass quietly."""
        narrowed = _CLEAN_ROOT.replace('    "InMemoryBroker",\n', "")
        findings = gate.judge_source(narrowed, where="sample")
        assert [one["category"] for one in findings] == [gate.CATEGORY_SURFACE_CHANGED]
        assert "InMemoryBroker" in findings[0]["detail"]

    def test_a_missing_all_is_reported(self) -> None:
        findings = gate.judge_source('"""No __all__."""\n', where="sample")
        assert [one["category"] for one in findings] == [gate.CATEGORY_SURFACE_UNDECLARED]


class TestAgainstTheRealPackage:
    """The committed tree, which is the only sample that matters on the day."""

    def test_the_committed_package_is_clean(self) -> None:
        assert gate.judge_package() == []

    def test_the_package_root_it_reads_actually_exists(self) -> None:
        """A walker that reads nothing reports a clean estate."""
        assert gate.PACKAGE_ROOT.is_file(), f"{gate.PACKAGE_ROOT} is not a file"

    def test_importing_the_package_does_not_load_the_adapter(self) -> None:
        """The strongest form of the rule, and the only one asserted at RUNTIME.

        The AST rules above read one file. This asks the interpreter, in a **fresh process**,
        whether `import esb_ig` ends with the adapter module loaded — which catches a reach
        the source of `__init__.py` does not show, such as `lib/__init__.py` importing it.

        A fresh process is load-bearing: this suite has already imported `esb_ig.transport`
        via the conformance tests, so `sys.modules` in THIS interpreter would report it
        loaded and the check would fail for a reason that has nothing to do with the
        package.
        """
        loaded = gate.adapter_modules_loaded_on_import()
        assert loaded == (), (
            f"importing `esb_ig` loaded {loaded}. The package must not reach the adapter: "
            "that is what makes the entry-point split real rather than cosmetic."
        )

    def test_the_conformance_suite_may_still_take_the_transport(self) -> None:
        """`EM03` criterion 3, asserted rather than remembered.

        `test_broker_conformance.py` imports `esb_ig.transport` deliberately — it is what
        makes the in-memory double the executable DEFINITION of the protocol rather than a
        second implementation. A gate that forced the conformance suite off the adapter
        would remove the thing the published double is for, so the gate's subject is the
        PACKAGE's own surface and it must never read the test tree.
        """
        conformance = gate.PACKAGE_ROOT.parent.parent / "tests" / "test_broker_conformance.py"
        assert "from esb_ig.transport import" in conformance.read_text(encoding="utf-8")
        assert gate.judge_package() == []


class TestTheNegativeControl:
    """Run on every invocation, on `check_catalogue.py`'s precedent.

    A gate is trusted in proportion to the evidence that it can fail. This one carries its
    own proof rather than relying on this suite, because the suite does not run in every
    context the gate does.
    """

    def test_it_passes_on_the_committed_tree(self) -> None:
        ok, detail = gate.negative_control()
        assert ok, detail

    def test_it_reports_what_it_exercised(self) -> None:
        _, detail = gate.negative_control()
        for expected in ("violating", "clean"):
            assert expected in detail


class TestTheArtefact:
    """`--json` is the committed evidence §11.3 requires."""

    def test_it_is_valid_json_carrying_the_outcome_and_the_limit(self, tmp_path: Path) -> None:
        report = json.loads(json.dumps(gate.report()))
        assert report["gate"] == "published-surface"
        assert report["outcome"] in {"clean", "findings"}
        assert report["negative_control"]
        assert report["not_verified_here"], (
            "a gate that lists no limit is claiming it has none, and this one has a large "
            "one: Python has no private modules"
        )

    def test_the_limit_names_what_the_gate_cannot_do(self) -> None:
        """The honest claim is narrow, and the artefact must not let a reader widen it."""
        limits = " ".join(gate.report()["not_verified_here"]).lower()
        assert "consumer" in limits
        assert "check_graduation" in limits or "ctm" in limits
