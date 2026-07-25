"""ESB/IG boundary gate — enforces platform CLAUDE.md N3 and the deep-module rules.

    python scripts/check_boundary.py            # blocking: exits 1 on any finding
    python scripts/check_boundary.py --json     # machine-readable

N3: *never import from, call into, or read the database of a consumer
application from a sub-system.* ESB/IG **carries** every other sub-system's
traffic and **imports** none of it: the envelope is a contract, not a shared
library. It is also never on the Layer-2 in-process business path (N2/D-02).

**Blocking from day one.** ESB/IG is greenfield, so ``BASELINE`` is empty and
every finding is a live breach rather than style debt.

**Two seams, eight detectors.** Detectors 1-5 police the *inter-repo* seam —
what this tree may depend on. Detectors 6-8 police the *intra-repo* seam — how
its own packages may reach each other, so that each package stays a **deep
module**: a lot of behaviour behind a small interface (its root modules).

Detectors 1-5. The first is the obvious one; the other four exist because each
is a way round it:

1. ``forbidden-import``      — ``import ctm`` / ``from irm.x import y``.
2. ``dynamic-import``        — ``importlib.import_module("ctm.registry")``. The
   obvious bypass, and invisible to an import walk that only reads
   ``ast.Import``/``ast.ImportFrom``.
3. ``escaping-relative-import`` — ``from .... import x``, which climbs out of
   ``backend/`` and can reach anything the interpreter has on its path.
4. ``sys-path-mutation``     — appending a directory to ``sys.path`` makes any
   tree importable, which is precisely how prior-art code gets "mined" into a
   runtime dependency by accident.
5. ``prior-art-reference`` / ``outside-repo-path`` — a path literal naming
   ``Phase 1 M-Development``. **This is the specific mistake the gate exists to
   catch**: that tree holds a reusable ``backend/integrations/`` module ESB/IG is
   meant to read for patterns and never depend on. A reference to it is not
   caught by any import walk, because it is a string.

Detectors 6-8 — the deep-module rules:

6. ``private-import``        — ``from backend.gateway.lib.routing import X``
   written from *outside* ``gateway``. A package's root modules are its
   interface; anything in a subfolder is implementation. Reaching past the seam
   makes the module shallow, because the caller now depends on how it works.
7. ``domain-crossing``       — an import between packages declared mutually
   independent (``INDEPENDENT_DOMAINS``). Empty here: ESB/IG's packages form one
   sub-system.
8. ``import-cycle``          — a package-level dependency cycle. Packages in a
   cycle cannot be understood, tested or moved independently.

Imports are walked with the AST, never with a regex: a regex cannot tell an
``import`` statement from the same words inside a docstring, a comment, or a
test fixture, and both false positives and false negatives are fatal to a gate
that blocks.

Exit codes: 0 = clean · 1 = findings · 2 = usage error.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Only ESB/IG's own source tree is in scope. Anything else in this repo is tooling.
SCAN_PATHS = ("backend",)

# Consumer applications and sibling sub-systems. ESB/IG carries their traffic
# and depends on none of them: the 10-field envelope is the contract, and a
# contract is not an import.
FORBIDDEN_ROOTS = frozenset(
    {
        # Consumer applications.
        "irm",
        "procurement",
        # Sibling sub-systems.
        "ctm",
        "iam",
        "nc",
        "notification_center",
        "translation",
        "wm",
    }
)

# The prior art. Mined, never imported.
PRIOR_ART_MARKERS = re.compile(r"(?i)M-Development|Phase\s+1\s+old")

# A drive-absolute or UNC path literal leaves this repository by construction.
OUTSIDE_REPO_PATH = re.compile(r"(?i)^(?:[a-z]:[\\/]|\\\\)")

SYS_PATH_MUTATORS = frozenset({"append", "insert", "extend"})

# --- Deep-module rules ------------------------------------------------------
#
# A package is a deep module — a lot of behaviour behind a small interface — and
# that interface is its ROOT modules. Anything in a subfolder is implementation,
# and implementation is nobody else's business.
#
#   from backend.broker import publish              OK  — an entry point
#   from backend.broker.envelope import Envelope    OK  — a SECOND entry point
#   from backend.broker.lib.channels import bind    NO  — reaching past the seam
#
# Entry-point status is resolved against the tree, not by counting dots: a
# dot-count reads `broker.envelope` as implementation and so forbids the several
# small entry points this layout exists to allow (see _is_entry_point).
#
# Two deliberate adaptations from the TypeScript original, both recorded so a
# future reader does not "fix" them:
#
# 1. SHARED_KERNEL. A shared kernel is imported by everything by design;
#    routing its exception types through a re-export is ceremony that buys no
#    depth. Its root modules are all entry points.
# 2. Tests may use a package's INTERNAL seams. The TS rule forbids this because
#    there `tests/` lives inside the package; here the test tree is separate and
#    Python unit-tests modules directly. A module may have internal seams used
#    by its own tests as well as the external seam at its interface.
PACKAGES_ROOT = "backend"

SHARED_KERNEL = frozenset({"core"})

TEST_DIR_NAMES = frozenset({"tests"})

# Empty: ESB/IG's packages form one sub-system. (CTM sets this to
# {"ctm", "iam", "esb_ig"} while the seeds share its repo — T12.)
INDEPENDENT_DOMAINS: tuple[frozenset[str], ...] = ()

# Pre-existing violations, enumerated and dated rather than blanket-exempted.
# Empty and expected to stay empty: ESB/IG is greenfield, so code is born clean.
BASELINE: frozenset[tuple[str, str]] = frozenset()

# Explicit and reviewable, never silent. Deliberately not spelled `noqa: ...`,
# which ruff parses and would flag as an unknown rule code.
SUPPRESS_MARKER = "boundary: allow"


@dataclass(frozen=True)
class Finding:
    """One boundary breach, at one line, in one file."""

    category: str
    path: str
    line: int
    excerpt: str
    detail: str

    def as_dict(self) -> dict[str, object]:
        return {
            "category": self.category,
            "file": self.path,
            "line": self.line,
            "excerpt": self.excerpt,
            "detail": self.detail,
        }


def iter_python_files(root: Path) -> Iterator[Path]:
    """Yield every ``.py`` file under the scanned trees.

    A missing tree is skipped, not an error: ``backend/`` is built incrementally
    and the gate must run against whatever exists — including nothing at all, on
    the first commit.
    """
    for relative in SCAN_PATHS:
        base = root / relative
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            if path.is_file():
                yield path


def _forbidden_root(module: str | None) -> str | None:
    """Return the forbidden top-level package of a dotted module name, if any."""
    if not module:
        return None
    root = module.split(".", 1)[0]
    return root if root in FORBIDDEN_ROOTS else None


def _dotted_name(node: ast.expr) -> str:
    """Render ``a.b.c`` from an attribute/name chain; '' for anything else."""
    parts: list[str] = []
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return ""
    parts.append(current.id)
    return ".".join(reversed(parts))


def _package_depth(path: Path, root: Path) -> int:
    """How many package levels a relative import may climb before leaving the tree."""
    return len(path.relative_to(root).parts) - 1


def _string_args(node: ast.Call) -> Iterator[str]:
    for argument in node.args:
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
            yield argument.value


def _scan_imports(tree: ast.Module, relative: str, depth: int) -> Iterator[Finding]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                forbidden = _forbidden_root(alias.name)
                if forbidden:
                    yield Finding(
                        "forbidden-import",
                        relative,
                        node.lineno,
                        f"import {alias.name}",
                        f"'{forbidden}' is a consumer application or sibling sub-system (N3)",
                    )
        elif isinstance(node, ast.ImportFrom):
            forbidden = _forbidden_root(node.module) if node.level == 0 else None
            if forbidden:
                yield Finding(
                    "forbidden-import",
                    relative,
                    node.lineno,
                    f"from {node.module} import ...",
                    f"'{forbidden}' is a consumer application or sibling sub-system (N3)",
                )
            elif node.level > depth:
                yield Finding(
                    "escaping-relative-import",
                    relative,
                    node.lineno,
                    f"from {'.' * node.level}{node.module or ''} import ...",
                    f"climbs {node.level} levels from a package {depth} deep — leaves backend/",
                )


def _scan_calls(tree: ast.Module, relative: str) -> Iterator[Finding]:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = _dotted_name(node.func)
        if target.startswith("sys.path.") and target.rsplit(".", 1)[-1] in SYS_PATH_MUTATORS:
            yield Finding(
                "sys-path-mutation",
                relative,
                node.lineno,
                f"{target}(...)",
                "mutating sys.path makes any tree importable, including the prior art",
            )
            continue
        if target not in {"importlib.import_module", "__import__"}:
            continue
        for value in _string_args(node):
            forbidden = _forbidden_root(value)
            if forbidden:
                yield Finding(
                    "dynamic-import",
                    relative,
                    node.lineno,
                    f"{target}({value!r})",
                    f"'{forbidden}' imported dynamically — an import walk alone misses this",
                )


def _scan_path_literals(tree: ast.Module, relative: str) -> Iterator[Finding]:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        if PRIOR_ART_MARKERS.search(node.value):
            yield Finding(
                "prior-art-reference",
                relative,
                node.lineno,
                node.value.strip()[:120],
                "references 'Phase 1 M-Development' — the prior art is mined, never imported",
            )
        elif OUTSIDE_REPO_PATH.match(node.value):
            yield Finding(
                "outside-repo-path",
                relative,
                node.lineno,
                node.value.strip()[:120],
                "absolute path literal reaches outside this repository",
            )


def _pkg_relative(relative: str) -> str:
    """Strip the packages root, so findings and BASELINE read as 'broker/publish.py'."""
    prefix = f"{PACKAGES_ROOT}/"
    return relative[len(prefix) :] if relative.startswith(prefix) else relative


def _owning_package(relative: str) -> str | None:
    """The package a file belongs to, or None for a root module like config.py."""
    parts = _pkg_relative(relative).split("/")
    return parts[0] if len(parts) > 1 else None


def _is_test(relative: str) -> bool:
    return any(part in TEST_DIR_NAMES for part in _pkg_relative(relative).split("/"))


def _resolve(node: ast.ImportFrom, relative: str) -> str | None:
    """Resolve an ImportFrom to an absolute dotted module, relative imports included.

    A relative import is the same reach as an absolute one — it just spells the
    target differently — so a gate that only reads absolute imports is trivially
    bypassed by ``from ..broker.lib.channels import bind``.
    """
    if node.level == 0:
        return node.module
    owning = [PACKAGES_ROOT, *_pkg_relative(relative).split("/")[:-1]]
    base = owning[: len(owning) - (node.level - 1)]
    if not base:
        return None
    return ".".join([*base, *(node.module.split(".") if node.module else [])])


def _imported_packages(tree: ast.Module, relative: str) -> Iterator[tuple[str, str, int]]:
    """Yield (package, full dotted module, line) for every import into this tree."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            modules = [_resolve(node, relative)]
        elif isinstance(node, ast.Import):
            # Every name: `import backend.broker.lib.a, backend.gateway.b` is two reaches.
            modules = [alias.name for alias in node.names]
        else:
            continue
        for module in modules:
            if not module:
                continue
            parts = module.split(".")
            if len(parts) < 2 or parts[0] != PACKAGES_ROOT:
                continue
            yield parts[1], module, node.lineno


def _is_entry_point(module: str, root: Path) -> bool:
    """True when a dotted module names one of a package's own root modules.

    A package's interface is *every* root module — ``backend.broker`` and
    ``backend.broker.envelope`` alike. Counting dots cannot tell a second entry
    point from implementation, so resolve against the tree instead:
    ``broker/envelope.py`` is an entry point, ``broker/lib/channels.py`` is not,
    and a subpackage directory ``broker/envelope/`` is a subfolder and therefore
    private.

    A name that resolves to nothing is treated as private: the gate does not
    grant entry-point status to something it cannot see.
    """
    parts = module.split(".")
    if len(parts) == 2:
        return True  # backend.<pkg> — the package's own __init__
    if len(parts) > 3:
        return False  # backend.<pkg>.<sub>.<mod> — always past the seam
    return (root / parts[0] / parts[1] / f"{parts[2]}.py").is_file()


def _scan_module_privacy(tree: ast.Module, relative: str, root: Path) -> Iterator[Finding]:
    """Entry-point boundary + independent-domain rules.

    A package's root modules are its interface. Reaching into a subfolder from
    outside is importing implementation, which is what makes a module shallow:
    the caller now depends on how it works, not on what it does.
    """
    owner = _owning_package(relative)
    testing = _is_test(relative)
    pkg_path = _pkg_relative(relative)

    for target, module, line in _imported_packages(tree, relative):
        if target == owner:
            continue  # intra-package freedom — rule 2
        if (pkg_path, module) in BASELINE:
            continue  # enumerated pre-existing debt; anything NEW still fails

        for group in INDEPENDENT_DOMAINS:
            if owner in group and target in group:
                yield Finding(
                    "domain-crossing",
                    relative,
                    line,
                    f"from {module} import ...",
                    f"'{owner}' and '{target}' are one-way domains — they cross by "
                    f"contract (event/command) only, never by import",
                )
                break
        else:
            if _is_entry_point(module, root) or target in SHARED_KERNEL or testing:
                continue
            yield Finding(
                "private-import",
                relative,
                line,
                f"from {module} import ...",
                f"'{module.split('.', 2)[2]}' is implementation inside '{target}' — "
                f"import '{PACKAGES_ROOT}.{target}' (its entry point) instead",
            )


def detect_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    """Every package-level dependency cycle, each reported once.

    A cycle means neither package can be understood, tested, or moved without
    the other — the opposite of a deep module with a small interface.
    """
    cycles: list[list[str]] = []
    seen: set[frozenset[str]] = set()
    state: dict[str, int] = {}

    def walk(node: str, stack: list[str]) -> None:
        state[node] = 1
        stack.append(node)
        for nxt in sorted(graph.get(node, ())):
            if state.get(nxt) == 1:
                cycle = stack[stack.index(nxt) :]
                if frozenset(cycle) not in seen:
                    seen.add(frozenset(cycle))
                    cycles.append([*cycle, nxt])
            elif state.get(nxt, 0) == 0:
                walk(nxt, stack)
        stack.pop()
        state[node] = 2

    for node in sorted(graph):
        if state.get(node, 0) == 0:
            walk(node, [])
    return cycles


def scan_file(path: Path, root: Path) -> list[Finding]:
    """Run every detector over one Python file."""
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source)
    except OSError:
        return []
    except (SyntaxError, ValueError):
        # A syntax error is the test/lint lane's finding, not this gate's.
        return []

    lines = source.splitlines()
    relative = path.relative_to(root).as_posix()
    depth = _package_depth(path, root)

    findings = [
        *_scan_imports(tree, relative, depth),
        *_scan_calls(tree, relative),
        *_scan_path_literals(tree, relative),
        *_scan_module_privacy(tree, relative, root),
    ]
    return [
        finding
        for finding in findings
        if SUPPRESS_MARKER not in (lines[finding.line - 1] if finding.line <= len(lines) else "")
    ]


def build_package_graph(root: Path) -> dict[str, set[str]]:
    """Package → packages it imports, from non-test source only.

    Tests are excluded on purpose: a test importing two packages is doing its
    job, not creating a runtime cycle.
    """
    graph: dict[str, set[str]] = {}
    for path in iter_python_files(root):
        relative = path.relative_to(root).as_posix()
        owner = _owning_package(relative)
        if owner is None or _is_test(relative):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError, ValueError):
            continue
        edges = graph.setdefault(owner, set())
        for target, _module, _line in _imported_packages(tree, relative):
            if target != owner:
                edges.add(target)
    return graph


def collect(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_python_files(root):
        findings.extend(scan_file(path, root))

    for cycle in detect_cycles(build_package_graph(root)):
        findings.append(
            Finding(
                "import-cycle",
                f"{PACKAGES_ROOT}/{cycle[0]}",
                1,
                " -> ".join(cycle),
                "packages in a cycle cannot be understood, tested or moved independently",
            )
        )

    return sorted(findings, key=lambda f: (f.path, f.line))


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(description="ESB/IG boundary gate (N3 / deep modules)")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="repository root to scan")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if not root.is_dir():
        print(f"ERROR: --root {root} is not a directory", file=sys.stderr)
        return 2

    findings = collect(root)

    if args.json:
        print(
            json.dumps(
                {
                    "gate": "boundary",
                    "root": str(root),
                    "total": len(findings),
                    "findings": [f.as_dict() for f in findings],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        for finding in findings:
            print(f"{finding.category:<26} {finding.path}:{finding.line}")
            print(f"    {finding.excerpt}")
            print(f"    -> {finding.detail}")
        print(f"\n  {len(findings):>5}  TOTAL")

    if findings:
        print(f"\nFAIL: {len(findings)} boundary violation(s) — N3", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
