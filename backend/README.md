# Packages — deep modules

Every immediate child of `backend/` is a **package**: a *deep module*, meaning a lot of
behaviour behind a small interface. A package's interface is its **root modules**; anything
in a subfolder is implementation and nobody else's business.

```
backend/
  __init__.py       ← makes `backend` the packages root. A docstring, nothing else.
  <name>/
    __init__.py     ← an entry point (public). Import this from outside.
    publish.py      ← another entry point. A package may expose SEVERAL.
    lib/            ← implementation: hidden from outside, free to import itself
  tests/            ← the test tree. No `__init__.py`; read its README before deleting it
  README.md         ← this file
```

## The three names — and the source layout is not the import name

| | |
|---|---|
| distribution | `esb-ig` — `pyproject.toml`'s `[project] name` |
| source directory | `backend/esb_ig/` — this tree, what the boundary gate scans |
| **distributed import** | **`esb_ig`** — top-level, what a consumer writes |

**This table read `dotted import path │ backend.esb_ig` until 2026-09-03, and that was
wrong in a way only the graduation would have found.** CTM ships `backend/__init__.py`,
which makes `backend` a **regular** package rather than a PEP 420 namespace package. Python
then fixes `backend.__path__` to CTM's own directory and never searches the rest of
`sys.path` for `backend.*` submodules — so an installed distribution providing
`backend/esb_ig/` is simply unreachable from inside CTM, and every
`from backend.esb_ig import ...` in CTM's `backend/wiring/` would fail the day CTM deletes
its seed and pins this repository. The graduation would not build. The reasoning and the
measured `ImportError` are in `pyproject.toml`, and CI **re-measures both on every run**.

**The tree keeps `backend/` and nothing in this file changes because of it.** A source
layout and a distributed import name are two different choices; the mistake was treating
them as one. `pyproject.toml` maps `backend/esb_ig/` onto top-level `esb_ig` for the build
only, so `PACKAGES_ROOT = "backend"` in `scripts/check_boundary.py` stays correct — it
describes the tree, which is what that gate reads.

**What this costs the move, and it is not nothing:** intra-package imports must be
**relative** (`from .envelope import Envelope`). A relative import resolves under *both*
names, which is what makes these two choices independent rather than merely reconciled.
CTM's copies currently import each other absolutely as `from backend.esb_ig.envelope import
...`, and that spelling cannot survive installation — once the directory is
`site-packages/esb_ig/` there is no `backend` above it. So the move **does** carry an import
rewrite, and an earlier note here claiming otherwise was the same error in another place.

Run the gate — it is blocking, and a red gate is the only enforcement this repo has
(no branch protection, platform `CLAUDE.md` §12):

```
python scripts/check_boundary.py            # exits 1 on any finding
python scripts/check_boundary.py --json     # machine-readable, for CI evidence
```

The tree holds **one** package, `esb_ig`, and it publishes nothing — an `__init__.py` with an
empty `__all__` and no imports. It exists so the packaging contract is *executable*: with no
package there is nothing to install, and CI's install-and-import proof would be NOT-RUN,
which under §11.3 catches nothing on the one claim whose failure surfaces on move day.
Copy the worked template at `..\..\CTM\backend\example\` when adding a second.

**What lands in `esb_ig` is not written from scratch.** The seed lives at
`..\..\CTM\backend\esb_ig\` — envelope, broker protocol, in-memory adapter, RabbitMQ
transport — and graduates under CTM's **W2-T10**. That move is a separate step done by
somebody else; nothing is copied ahead of it, because a stub module is dead code this gate
would then have to reason about. What is in place ahead of it is everything the move should
not have to also build: the packages root, the test tree, the toolchain configuration, and a
CI runner with a broker already on it.

## The four rules

**1. Entry-point boundary.** Code outside a package may import only that package's root
modules — `from backend.broker import publish` — never anything in a subfolder.
`from backend.broker.lib.channels import bind` fails the build. The moment a caller reaches
into `lib/`, it depends on *how* the package works rather than *what* it does.

A package's interface is **every** root module — `backend.broker` and `backend.broker.envelope`
alike — so entry-point status is resolved against the tree, not by counting dots in the import.
`broker/envelope.py` is public; `broker/lib/channels.py` is not; and a *folder* named
`broker/envelope/` is a subfolder, so it stays private however short the import reads.

**2. Intra-package freedom.** A package's own files import each other however they like.
Privacy is enforced at the package edge, not inside it.

**3. No forbidden dependency.** ESB/IG **carries** every other sub-system's traffic and
**imports** none of it — `ctm`, `iam`, `nc`, `translation`, `wm`, `irm`, `procurement` are all
barred. The 10-field envelope is the contract, and a contract is not an import. The gate also
catches the four ways round that rule: dynamic import, escaping relative import, `sys.path`
mutation, and prior-art path literals.

**4. No cycles.** No package-level dependency cycle. Packages in a cycle cannot be understood,
tested, or moved independently.

## A named gap the move must close, not inherit

**Once intra-package imports are relative — and they must be, see above — detectors 6-8 see
nothing inside a package.** They resolve an import against `PACKAGES_ROOT = "backend"`, and a
relative import carries no such prefix. Rule 2 says a package's own files may import each
other however they like, so *for intra-package imports that silence is correct*. What is not
covered is the case a second package creates: a cross-package import written the way an
installed consumer would write it (`from other_pkg.lib.x import y`) is invisible to
`private-import`, `domain-crossing` and `import-cycle` alike, because it does not begin with
`backend.`.

There is nothing to catch today — `esb_ig` is the only package and it imports nothing. It is
recorded here rather than discovered later, because a blocking gate that reaches no import in
the code that has just arrived is exactly the "green because nothing happened" shape the
platform's §11.3 is about. **Owner: the W2-T10 move**, which is when both preconditions — real
intra-package imports, and eventually a second package — first exist.

## No barrel files

An entry point is a **small, curated surface**, not a re-export of a whole subtree. Do not write
an `__init__.py` that does `from .lib.everything import *`; that keeps the letter of rule 1 while
losing all of its value. If a package needs more than one public surface, add **another root
module** — that is what "several entry points" means, and it costs no config change.

## Two deviations from the usual TypeScript form of these rules

Both are deliberate and recorded in `scripts/check_boundary.py`:

- **`core` is a shared kernel** — all of its root modules are entry points.
- **Tests may use a package's internal seams** — the test tree is separate here, and Python
  unit-tests modules directly.
