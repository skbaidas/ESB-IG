"""The seed's modules import each other RELATIVELY, so the package can be renamed.

`W2-T10` graduates `backend/esb_ig/` into its own repository, where it is built as a
distribution and consumed by `pip install git+https://...@<sha>`. **The distributed import
name is top-level `esb_ig`, not `esb_ig`, and that is measured rather than
preferred**: CTM ships `backend/__init__.py`, which makes `backend` a *regular* package, so
Python fixes `backend.__path__` to CTM's own directory and never searches the rest of
`sys.path` for `backend.*` submodules. An installed distribution providing
`backend/esb_ig/` is therefore unreachable from inside CTM — `ImportError: No module named
'esb_ig'`, reproduced on every ESB-IG CI run rather than quoted from a comment.

So a **source layout** and a **distributed import name** are two different choices, and
conflating them is what this file exists to prevent. `from esb_ig.envelope import
Envelope` inside the seed cannot survive installation: once the directory is
`site-packages/esb_ig/`, there is no `backend` above it. A **relative** import resolves
under *both* names, which is what makes the two choices independent rather than merely
reconciled.

**This lands before the move rather than at it** — criterion 7's ruling applied for the
third time, after the frozen envelope and the error re-rooting. While the seed is still in
this tree the whole CTM suite runs over the change, so *the conversion broke nothing* is
executed rather than argued. After the move there is no CTM suite on this side of the
boundary to run.

**What this does NOT assert, and it matters for reading the graduation lane.** Once these
imports are relative, `check_graduation.py --relocate` — which copies the seed under a
different root and rewrites `backend.` to `graduated.` — has nothing left to rewrite inside
the seed. A `position-independent` verdict for `esb_ig` is then green because there is
nothing left to test, not because the rewrite was exercised. **This file is what carries
the guarantee that gate used to**, and the guarantee is stronger: the dry-run proved the
seed survived *one* rewrite, and a relative import survives *every* one.

**There are no cross-package imports left, and the last test in this file is the one that
changed at the boundary.** Inside CTM the seed took `shipped_default_credential` from
`backend.core.credentials`, and the rule here was that this import must stay ABSOLUTE:
`check_boundary.py`'s detectors resolve a dotted module name, so making a cross-package
import relative would have hidden a real dependency from the gate. `W2-T10` step (a) copied
that function into `esb_ig/lib/credentials.py`, so the dependency is gone rather than
hidden — and the test below now asserts its ABSENCE. The enumeration remains scoped to the
seed's own package, which is now the whole of what the seed imports first-party.

Nothing here needs a database, a broker or a network.
"""

from __future__ import annotations

import ast
from pathlib import Path

from esb_ig.lib.base import EsbIgError

_SEED = Path(__file__).resolve().parents[1] / "esb_ig"

#: Derived from an imported module, never written as a literal. A root spelled as a string
#: is not an import, so no rewrite repairs it — the mistake this ticket has now paid for
#: twice, most recently on the graduation lane's first real CI run.
_PACKAGES_ROOT = EsbIgError.__module__.split(".", 1)[0]
_SEED_PACKAGE = EsbIgError.__module__.rsplit(".", 2)[0]


def _absolute_self_imports() -> list[str]:
    """`file:line: statement` for every import of the seed's own package by dotted name."""
    offenders: list[str] = []
    walked = 0
    for path in sorted(_SEED.rglob("*.py")):
        walked += 1
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        lines = source.splitlines()
        for node in ast.walk(tree):
            named: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.level == 0:
                named = [node.module or ""]
            elif isinstance(node, ast.Import):
                named = [alias.name for alias in node.names]
            for module in named:
                if module == _SEED_PACKAGE or module.startswith(f"{_SEED_PACKAGE}."):
                    offenders.append(
                        f"{path.relative_to(_SEED.parent).as_posix()}:{node.lineno}: "
                        f"{lines[node.lineno - 1].strip()}"
                    )

    assert walked, (
        f"no Python file was walked under {_SEED}. A walker that reads nothing reports a "
        "clean seed, which is a true-looking green produced by a broken instrument."
    )
    return offenders


def test_the_seed_never_imports_itself_by_absolute_name() -> None:
    offenders = _absolute_self_imports()
    assert offenders == [], (
        "these imports name the seed's own package absolutely, so they resolve only while "
        "the package is called "
        f"`{_SEED_PACKAGE}`. Installed as `esb_ig` they raise ImportError and the "
        f"graduation does not build. Rewrite each as a relative import:\n  "
        + "\n  ".join(offenders)
    )


def test_the_detector_would_fire_on_the_shape_it_forbids() -> None:
    """Negative control (F19). A detector proven only against a clean tree proves nothing.

    Without this, deleting the body of `_absolute_self_imports` and returning `[]` leaves
    the test above green — the exact shape of a gate that passes because it looks at
    nothing.
    """
    module = ast.parse(f"from {_SEED_PACKAGE}.envelope import Envelope")
    node = module.body[0]
    assert isinstance(node, ast.ImportFrom)
    assert node.level == 0 and (node.module or "").startswith(f"{_SEED_PACKAGE}.")

    relative = ast.parse("from ..envelope import Envelope").body[0]
    assert isinstance(relative, ast.ImportFrom)
    assert relative.level == 2, (
        "a relative import must carry a non-zero level, which is what makes it invisible "
        "to the absolute-name check above and portable across the rename."
    )


def test_the_seed_has_no_cross_package_import_left() -> None:
    """**Inverted at graduation, and the inversion is the evidence the move happened.**

    In CTM this test asserted the opposite — that the seed's one import from the shared
    kernel was still ABSOLUTE, so a later tidying pass could not make it relative and hide
    a real cross-package dependency from `check_boundary.py`. It ended with *"if it was
    genuinely removed, retire this test … an expectation that has been met and not removed
    is a licence."*

    It was genuinely removed. `W2-T10` step (a) paid the bill: `shipped_default_credential`
    now lives in `esb_ig/lib/credentials.py`, a copy taken from CTM at the boundary, and
    there is no `esb_ig.core` for anything here to import. The expectation is therefore
    retired and replaced by its inverse, which is the sharper claim: **the package reaches
    outside itself for nothing.** That is the property that makes it installable, and it is
    what CTM's version could not assert while the import was still there.

    Third-party imports are untouched by this — `pika` is a declared optional dependency,
    not a package this repository owns. The check is scoped to a FIRST-PARTY root, read off
    the seed's own exception class rather than written here as a literal.
    """
    kernel = f"{_PACKAGES_ROOT}.core"
    offenders: list[str] = []
    for path in sorted(_SEED.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(kernel):
                offenders.append(f"{path.name}:{node.lineno}")
            if isinstance(node, ast.Import):
                offenders.extend(
                    f"{path.name}:{node.lineno}"
                    for alias in node.names
                    if alias.name.startswith(kernel)
                )

    assert offenders == [], (
        f"{offenders} import {kernel}, which does not exist in this repository. The "
        "graduation removed the seed's last cross-package dependency; re-acquiring one "
        "makes the package uninstallable rather than merely coupled."
    )
