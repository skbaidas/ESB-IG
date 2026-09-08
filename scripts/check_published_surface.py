r"""The published-surface gate — what `import esb_ig` may and may not hand a consumer.

`EM03`. Run from the repository root:

    python scripts/check_published_surface.py
    python scripts/check_published_surface.py --json > gate-published-surface.json

WHAT THIS GATE CLAIMS, AND THE CLAIM IS DELIBERATELY NARROW. `W2-T10` ratifies that ESB/IG
publishes exactly three things to a consumer — the protocol, the envelope and the
conformance double — and that *"the RabbitMQ adapter is NOT published"*.

**Python has no private modules.** Nothing in this repository can stop a consumer writing
`import esb_ig.transport`, and this gate does not pretend to. What it refuses is the
adapter arriving on the published surface **silently**, which is not hypothetical: the
adapter sat on the root surface until `W2-T20`, so every consumer could reach it, and
`W2-T10`'s own reasoning is that *a consumer that CAN import a transport eventually will —
and then the contract is the transport rather than the protocol.*

**THE CONSUMER-SIDE HALF IS CTM'S AND ALREADY EXISTS**, which `EM03` §1 originally got
wrong. `check_graduation.py` reports `stranded-transport-import` for any CTM file that
stays behind and imports the seed's transport, keyed on `NON_CONSUMER_ENTRY_POINTS`.
Neither half is the control on its own:

* CTM's gate refuses a **consumer's import** — and is spelled in the PRE-MOVE dotted name,
  so it lapses at `W2-T10` step (c) unless that constant gains the post-move spelling;
* this gate refuses the **package's own export** — and survives the move, because it reads
  this repository.

THREE RULES, and each is asserted against a violating sample as well as a clean one
(`negative_control`, run on every invocation):

1. `adapter-reached-by-the-published-surface` — the package root imports the adapter, by
   any spelling: relative or absolute, through `lib.rabbitmq` or through the `transport`
   entry point, aliased or not. **The rule is about the module a name comes from, never
   about the name**, because `as` is the obvious way past a rule that matched names.
2. `published-surface-changed` — `__all__` differs from the ratified set. The weakest rule
   here and the one most likely to read as bureaucracy, so: five sub-systems are to compile
   against this set, and §7's *consumers upgrade before producers* is meaningless if it can
   widen without anyone noticing. Narrowing is reported too — that is a breaking change.
3. `published-surface-undeclared` — no `__all__` at all. Distinct from an empty one: the
   surface is then whatever happens to be bound at module level, which is not a decision
   anybody took, and an empty surface would satisfy rule 1 trivially.

Rules 1–3 read the **syntax tree**, never the text: `transport.py`'s own docstring explains
at length why the adapter is not published, and a detector that could not tell prose from
an import would fire on the documentation for the rule.

**One rule is asserted at runtime instead**, by `adapter_modules_loaded_on_import`: a fresh
interpreter imports `esb_ig` and is asked whether the adapter is in `sys.modules`. That
catches a reach the source of one file cannot show — `lib/__init__.py` importing it, say —
and it is the property that makes the entry-point split real rather than cosmetic.

WHAT IT MUST NOT DO: read the test tree. `test_broker_conformance.py` imports
`esb_ig.transport` deliberately, and that import is what makes the in-memory double the
executable definition of the protocol rather than a second implementation. A gate that
forced the conformance suite off the adapter would remove the thing the published double is
for. Its subject is the package's own surface, and nothing else.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
SOURCE_DIR: Final[Path] = REPO_ROOT / "backend"
PACKAGE_NAME: Final[str] = "esb_ig"
PACKAGE_ROOT: Final[Path] = SOURCE_DIR / PACKAGE_NAME / "__init__.py"

#: What `W2-T10` ratifies as published, enumerated rather than counted (ADR-0015). This is
#: the source of record and it is meant to be edited by a person: a change to what five
#: sub-systems compile against is a decision, and this line is where it becomes visible.
RATIFIED_SURFACE: Final[tuple[str, ...]] = (
    "Broker",
    "BrokerError",
    "BrokerUnavailableError",
    "ChannelError",
    "Consumer",
    "DeadLetter",
    "DeliveryReport",
    "EsbIgError",
    "IdempotencyStore",
    "InMemoryBroker",
    "deduplicating",
)

#: The modules a consumer may not be handed. `transport` is the published entry point that
#: carries the adapter; `lib.rabbitmq` is where it actually lives, and reaching it directly
#: is the same violation by a shorter route.
ADAPTER_MODULES: Final[tuple[str, ...]] = (
    f"{PACKAGE_NAME}.transport",
    f"{PACKAGE_NAME}.lib.rabbitmq",
)

CATEGORY_ADAPTER_REACHED: Final[str] = "adapter-reached-by-the-published-surface"
CATEGORY_SURFACE_CHANGED: Final[str] = "published-surface-changed"
CATEGORY_SURFACE_UNDECLARED: Final[str] = "published-surface-undeclared"

EXIT_CLEAN: Final[int] = 0
EXIT_FINDINGS: Final[int] = 1
EXIT_CONTROL_FAILURE: Final[int] = 2


class SurfaceError(Exception):
    """The published surface cannot be READ, which is not the same as it being wrong.

    Raised rather than reported as a finding, and rather than being worked around: a gate
    that silently read the part of `__all__` it could enumerate would report a surface
    smaller than the real one, and every rule would then pass over the names it could not
    see. A surface nobody can read is a surface nobody has reviewed.
    """


class Finding(dict):
    """One reason the gate is not clean. A `dict` so the artefact is the object."""

    def __init__(self, category: str, subject: str, detail: str) -> None:
        super().__init__(category=category, subject=subject, detail=detail)


def declared_surface(source: str) -> tuple[str, ...] | None:
    """The names in `__all__`, in declaration order, or `None` if there is no `__all__`.

    Read by AST rather than by importing the module: importing to ask what a module
    publishes runs the module, which is the thing under test, and a synthetic sample has
    nothing to import at all. The tree also sees a surface a runtime read cannot — a name
    listed but not bound is still a published claim, and it is the shape a half-finished
    re-export leaves behind.

    Raises:
        SurfaceError: `__all__` is not a literal list or tuple of plain strings.
    """
    tree = ast.parse(source)
    for node in tree.body:
        targets = (
            node.targets
            if isinstance(node, ast.Assign)
            else [node.target]
            if isinstance(node, ast.AnnAssign)
            else []
        )
        if not any(isinstance(one, ast.Name) and one.id == "__all__" for one in targets):
            continue
        value = node.value
        if not isinstance(value, ast.List | ast.Tuple):
            raise SurfaceError(
                "__all__ is not a literal list or tuple, so the published surface cannot be "
                "enumerated from the source. Write it out: a surface nobody can read is a "
                "surface nobody has reviewed."
            )
        names: list[str] = []
        for element in value.elts:
            if not isinstance(element, ast.Constant) or not isinstance(element.value, str):
                raise SurfaceError(
                    "__all__ contains an entry that is not a string literal (found "
                    f"{ast.dump(element)[:60]}…). The gate refuses to guess at a "
                    "dynamically built surface rather than reading the part it can see."
                )
            names.append(element.value)
        return tuple(names)
    return None


def _resolved_module(node: ast.ImportFrom) -> str:
    """The absolute dotted name an `ImportFrom` in the PACKAGE ROOT refers to.

    `level == 1` in `__init__.py` is the package itself, so `from .lib.rabbitmq import X`
    resolves to `esb_ig.lib.rabbitmq`. A level above that would leave the package, which is
    a different rule's business (the boundary gate's), and is left alone here.
    """
    if node.level == 0:
        return node.module or ""
    if node.level > 1:
        return ""
    return f"{PACKAGE_NAME}.{node.module}" if node.module else PACKAGE_NAME


def _is_adapter(module: str) -> bool:
    return any(module == one or module.startswith(f"{one}.") for one in ADAPTER_MODULES)


def adapter_reaches(source: str) -> list[tuple[int, str]]:
    """`(line, module)` for every import of the adapter, by any spelling.

    Matched on the MODULE, never on the imported name: `from .lib.rabbitmq import
    RabbitMqBroker as Broker2` is the same violation, and a rule that read names would miss
    it. Both `Import` and `ImportFrom` are walked, so `import esb_ig.transport` is caught
    alongside `from esb_ig.transport import ...`.
    """
    found: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            module = _resolved_module(node)
            if _is_adapter(module):
                found.append((node.lineno, module))
        elif isinstance(node, ast.Import):
            found.extend(
                (node.lineno, alias.name) for alias in node.names if _is_adapter(alias.name)
            )
    return found


def judge_source(source: str, *, where: str) -> list[Finding]:
    """The three static rules, applied to one package root."""
    findings = [
        Finding(
            CATEGORY_ADAPTER_REACHED,
            where,
            f"line {line} imports '{module}', which '{PACKAGE_NAME}' publishes as a separate "
            "entry point and a consumer may not take. The package root must not reach the "
            "adapter: a consumer that can import a transport eventually will, and then the "
            "contract is the transport rather than the protocol (W2-T10)",
        )
        for line, module in adapter_reaches(source)
    ]

    surface = declared_surface(source)
    if surface is None:
        findings.append(
            Finding(
                CATEGORY_SURFACE_UNDECLARED,
                where,
                "the package root declares no __all__, so its published surface is whatever "
                "happens to be bound at module level. That is not a decision anybody took, "
                "and five sub-systems are to compile against it",
            )
        )
        return findings

    ratified = set(RATIFIED_SURFACE)
    declared = set(surface)
    added = sorted(declared - ratified)
    removed = sorted(ratified - declared)
    if added or removed:
        parts = []
        if added:
            parts.append(f"adds {added}")
        if removed:
            parts.append(f"removes {removed}")
        findings.append(
            Finding(
                CATEGORY_SURFACE_CHANGED,
                where,
                f"__all__ {' and '.join(parts)} against the set W2-T10 ratifies. A change to "
                "what is published is a decision: update RATIFIED_SURFACE in the same commit "
                "so it is reviewed rather than absorbed. Removing a name is a breaking change "
                "for every consumer already compiled against it",
            )
        )
    return findings


def judge_package() -> list[Finding]:
    """The static rules against the committed package root."""
    return judge_source(
        PACKAGE_ROOT.read_text(encoding="utf-8"),
        where=str(PACKAGE_ROOT.relative_to(REPO_ROOT)).replace(os.sep, "/"),
    )


def adapter_modules_loaded_on_import() -> tuple[str, ...]:
    """Which adapter modules a bare `import esb_ig` leaves in `sys.modules`.

    **A fresh interpreter, and that is load-bearing.** The suite that exercises this gate has
    already imported `esb_ig.transport` through the conformance tests, so asking `sys.modules`
    in the current process would report the adapter loaded and the check would fail for a
    reason that has nothing to do with the package.

    This is the one rule not answerable from the syntax tree of a single file: it catches a
    reach further down, such as `lib/__init__.py` importing the adapter, which `__init__.py`'s
    own source does not show.

    Returns:
        The adapter modules found loaded, empty when the package does not reach them. A
        subprocess that cannot run at all raises rather than returning empty — a probe that
        silently reports nothing is indistinguishable from a clean result.
    """
    probe = (
        "import json, sys; import esb_ig; "
        f"print(json.dumps([m for m in {list(ADAPTER_MODULES)!r} if m in sys.modules]))"
    )
    environment = dict(os.environ, PYTHONPATH=str(SOURCE_DIR))
    completed = subprocess.run(  # noqa: S603 - fixed argv, no shell, no user input
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=environment,
        check=False,
    )
    if completed.returncode != 0:
        raise SurfaceError(
            "the import probe did not run, so nothing about the package was established: "
            f"{(completed.stderr or completed.stdout).strip()[:400]}"
        )
    return tuple(json.loads(completed.stdout))


def negative_control() -> tuple[bool, str]:
    """Prove the detectors fire, on every invocation. `check_catalogue.py`'s precedent.

    A gate is trusted in proportion to the evidence that it can fail, and a detector that
    never fires is indistinguishable from one that cannot. Both directions are exercised:
    a violating sample must be caught, and a clean one must be silent.
    """
    clean = "__all__ = [\n" + "".join(f'    "{n}",\n' for n in RATIFIED_SURFACE) + "]\n"
    violating = f"from .lib.rabbitmq import RabbitMqBroker\n{clean}"

    caught = [one["category"] for one in judge_source(violating, where="control")]
    if CATEGORY_ADAPTER_REACHED not in caught:
        return False, f"the violating control sample was NOT caught (reported {caught})"

    silent = judge_source(clean, where="control")
    if silent:
        return False, f"the clean control sample was reported: {silent}"

    return True, "violating sample caught, clean sample silent"


def report() -> dict[str, object]:
    """The evidence artefact §11.3 requires, including what a green does NOT prove."""
    findings = judge_package()
    loaded = adapter_modules_loaded_on_import()
    if loaded:
        # WHERE TO LOOK depends on whether the static rule also fired, and saying the wrong
        # one sends a reader to the wrong file. If `__init__.py` already reported the
        # import, this finding is the same reach observed at runtime; if it did not, the
        # reach is further down and the package root's source will not show it.
        elsewhere = not any(one["category"] == CATEGORY_ADAPTER_REACHED for one in findings)
        findings.append(
            Finding(
                CATEGORY_ADAPTER_REACHED,
                str(PACKAGE_ROOT.relative_to(REPO_ROOT)).replace(os.sep, "/"),
                f"a fresh `import {PACKAGE_NAME}` leaves {list(loaded)} in sys.modules. "
                + (
                    "Nothing in the package root's own source imports it, so the reach is "
                    "further down — lib/__init__.py is the usual place"
                    if elsewhere
                    else "This is the import reported above, observed at runtime rather "
                    "than in the syntax tree"
                ),
            )
        )
    control_passed, control_detail = negative_control()
    return {
        "gate": "published-surface",
        "outcome": "findings" if findings else "clean",
        "package": PACKAGE_NAME,
        "ratified_surface": list(RATIFIED_SURFACE),
        "adapter_modules": list(ADAPTER_MODULES),
        "adapter_modules_loaded_on_import": list(loaded),
        "negative_control": {"passed": control_passed, "detail": control_detail},
        "findings": findings,
        "not_verified_here": [
            "A CONSUMER IS NOT PREVENTED FROM IMPORTING THE ADAPTER, and cannot be. Python "
            "has no private modules, so `import esb_ig.transport` works from anywhere. What "
            "this gate refuses is the adapter arriving on the PUBLISHED surface silently.",
            "THE CONSUMER-SIDE HALF IS CTM'S. check_graduation.py reports "
            "stranded-transport-import for a CTM file that stays behind and imports the "
            "seed's transport (NON_CONSUMER_ENTRY_POINTS). That constant is spelled in the "
            "PRE-MOVE dotted name and lapses at W2-T10 step (c) unless it gains the "
            "post-move spelling.",
            "NOTHING HERE READS THE TEST TREE, deliberately. "
            "test_broker_conformance.py imports esb_ig.transport, and that import is what "
            "makes the in-memory double the executable definition of the protocol.",
            "THE ENVELOPE ENTRY POINT IS NOT JUDGED. This gate reads the package root; "
            "esb_ig.envelope is a second published entry point whose contract is "
            "contracts/integration-catalogue.toml's and check_catalogue.py's.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check what `import esb_ig` publishes.")
    parser.add_argument("--json", action="store_true", help="print the evidence artefact")
    arguments = parser.parse_args(argv)

    try:
        artefact = report()
    except SurfaceError as error:
        print(f"CONTROL FAILURE: {error}", file=sys.stderr)
        return EXIT_CONTROL_FAILURE

    control = artefact["negative_control"]
    if not control["passed"]:  # type: ignore[index]
        print(f"CONTROL FAILURE: {control['detail']}", file=sys.stderr)  # type: ignore[index]
        return EXIT_CONTROL_FAILURE

    if arguments.json:
        print(json.dumps(artefact, indent=2))

    findings = artefact["findings"]
    if not arguments.json:
        for finding in findings:  # type: ignore[union-attr]
            print(f"  {finding['category']}  {finding['subject']}\n      {finding['detail']}")
        print(f"\n  {len(findings)}  TOTAL")  # type: ignore[arg-type]

    return EXIT_FINDINGS if findings else EXIT_CLEAN


if __name__ == "__main__":
    raise SystemExit(main())
