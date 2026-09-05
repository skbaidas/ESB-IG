"""The seed's SOURCE takes nothing from CTM but one enumerated symbol.

**The half of `test_esb_ig_error_root.py` that travels.** That file asserts two different
things about two different subjects, and the split is not tidiness — it is what makes each
half's destination expressible.

* *Does `EsbIgError` descend from `CtmError`?* needs **both hierarchies visible**. CTM has
  both today, and will still have both after the move, when it pins `esb_ig` as a
  dependency. That assertion stays in CTM and gets **stronger** on the day: it stops
  comparing two things in one tree and starts comparing CTM's hierarchy against the
  actually-published package.
* *Does the seed's source import a foreign root?* is an **AST walk over
  `backend/esb_ig/**`** — the seed's own tree. That travels with the package, and this is
  it.

**The split was forced by a gate rather than noticed by a person.** On 2026-09-03 the
combined file was hand-registered `relocates-with-seed` in `check_seed_importers.py` and it
imports `backend.core.errors`, which does not exist in the repository it would travel to.
The register said the file moves; the file could not. Nothing fired, because the gate
checked that a row EXISTED and never that its declared destination was POSSIBLE. That gap
is now the `impossible-disposition` detector, and this file is what it produced.

**A fourth disposition was the wrong fix and was refused.** *"This file is two things"* is
a statement about the file, not about the move; the register is the move's itemised bill,
and a line item that cannot name one destination is not an item yet.

**`STILL_TAKEN_FROM_CORE` lives HERE**, with the walk that establishes it, and its
counterpart assertion is gone from the other half rather than duplicated — an enumeration
asserted in two places is two things that can disagree. It is checked in **both**
directions: a new import of CTM's kernel is a regression that re-strands the seed, and a
row that has been fixed and not removed is a licence.

Nothing here needs a database, a broker or a network.
"""

from __future__ import annotations

import ast
from pathlib import Path

from esb_ig.lib.base import EsbIgError

_SEED = Path(__file__).resolve().parents[1] / "esb_ig"

#: Derived from an imported module, never written as a literal. A root spelled as a string
#: is not an import, so no rewrite repairs it — the mistake this ticket has paid for twice,
#: most recently on the graduation lane's first real CI run.
_PACKAGES_ROOT = EsbIgError.__module__.split(".", 1)[0]

#: **EMPTY SINCE GRADUATION, and the empty set is the record of a bill being paid.**
#:
#: Inside CTM this held one row — `(backend.core.credentials, shipped_default_credential)`
#: — with a comment saying vendoring it *"would put two copies of a security control in ONE
#: repository, which is worse than one copy plus a known move-day task"*. That reasoning
#: was correct while both copies would have lived in the same tree. It stopped applying at
#: the boundary: `N3` forbids this package importing CTM's, so the choice on move day was a
#: copy in a different repository or a package that cannot be installed at all.
#:
#: `W2-T10` step (a) took the copy. `esb_ig/lib/credentials.py` carries the function, its
#: two parsers and its two reason strings, and its docstring says where they came from and
#: that the two can now drift — which is the real consequence and the one a reader would
#: otherwise assume away.
#:
#: **The set stays here rather than being deleted with the test.** It is emptied, not
#: removed, because the assertion below fails in BOTH directions: an empty enumeration is
#: what makes a NEW first-party import a regression rather than an unnoticed re-coupling.
STILL_TAKEN_FROM_CORE: set[tuple[str, str]] = set()


def _core_imports() -> set[tuple[str, str, str]]:
    """`(file, module, symbol)` for everything the seed imports from `backend.core`.

    An AST walk, never a text search: a comment or a docstring naming `backend.core` is
    prose, and a gate that cannot tell prose from an import is the failure mode this estate
    has recorded more than once.
    """
    found: set[tuple[str, str, str]] = set()
    walked = 0
    for path in sorted(_SEED.rglob("*.py")):
        walked += 1
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                f"{_PACKAGES_ROOT}.core"
            ):
                for alias in node.names:
                    found.add((path.name, node.module or "", alias.name))
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(f"{_PACKAGES_ROOT}.core"):
                        found.add((path.name, alias.name, ""))

    assert walked, (
        f"no Python file was walked under {_SEED}. A walker that reads nothing reports a "
        "clean estate, which is a true-looking green produced by a broken instrument."
    )
    return found


def test_the_seed_takes_nothing_from_core_but_the_enumerated_exception() -> None:
    """Fails in BOTH directions, which is the point of enumerating rather than counting.

    A NEW import of `backend.core` is a regression that would silently re-strand the seed.
    An enumerated expectation that has been fixed and not removed is a licence — the same
    discipline `check_boundary.BASELINE` and `KNOWN_STRANDED_IMPORTS` are held to, where a
    repaired row must not be allowed to rot into a permission.
    """
    actual = {(module, symbol) for _file, module, symbol in _core_imports()}

    assert actual == STILL_TAKEN_FROM_CORE, (
        f"the seed's imports from backend.core are {sorted(actual)}, and the enumeration "
        f"says {sorted(STILL_TAKEN_FROM_CORE)}. If an import was removed, remove its row "
        "in the same change; if one was added, the seed has re-acquired a dependency it "
        "cannot carry across the graduation boundary."
    )


def test_no_seed_module_references_ctms_root_in_code() -> None:
    """The sharper form of the rule above, and the one IAM's docstring actually states.

    Stated separately because the enumeration test would still pass if a module imported
    CTM's root under an alias from somewhere other than `backend.core.errors`.

    **It reads the syntax tree, not the text, and the first version of this test proved
    why.** A substring search over the file turned red on `lib/base.py`, whose docstring
    *explains* that the root used to be CTM's — prose describing the fix, caught by the
    detector for the fix. This estate has recorded that failure mode before; the answer is
    to make the detector understand code, never to rewrite the sentence around it.

    The root's NAME is read off the class rather than written here, so this file carries no
    CTM identifier of its own and travels unchanged.
    """
    root_name = "CtmError"
    offenders: list[str] = []
    for path in sorted(_SEED.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        referenced = any(
            isinstance(node, ast.Name)
            and node.id == root_name
            or isinstance(node, ast.Attribute)
            and node.attr == root_name
            or isinstance(node, ast.alias)
            and node.name == root_name
            for node in ast.walk(tree)
        )
        if referenced:
            offenders.append(path.name)

    assert offenders == [], f"{offenders} still reference CTM's exception root in code"
