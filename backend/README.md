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

## The three names

| | |
|---|---|
| distribution | `esb-ig` — `pyproject.toml`'s `[project] name` |
| package directory | `backend/esb_ig/` |
| dotted import path | `backend.esb_ig` |

The third is **not** a choice `pyproject.toml` makes — it is already fixed here and in
`scripts/check_boundary.py` (`PACKAGES_ROOT = "backend"`). CTM's `check_graduation.py`
rewrites `backend.` to a destination-chosen root on its relocation dry-run, so the
packages-root name is the move's **one free variable**, and this repository has already spent
it on `backend`, exactly as CTM does. Nothing here is pip-installed and there is no
`[build-system]`: `backend.*` is importable because CI puts the workspace on `PYTHONPATH`,
which is how CTM's runner does it too.

Run the gate — it is blocking, and a red gate is the only enforcement this repo has
(no branch protection, platform `CLAUDE.md` §12):

```
python scripts/check_boundary.py            # exits 1 on any finding
python scripts/check_boundary.py --json     # machine-readable, for CI evidence
```

The tree holds no package today; the gate runs clean against nothing and starts biting the
moment the first one lands. Copy the worked template at `..\..\CTM\backend\example\`.

**What lands here is `esb_ig`, and it is not written from scratch.** The seed lives at
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
