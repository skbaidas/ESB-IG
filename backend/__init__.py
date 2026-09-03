"""ESB/IG packages root.

Each immediate child directory is a **package** — a deep module whose interface
is its root modules. See `README.md` beside this file before adding one.

This file makes `backend` the importable packages root, which is the name
`scripts/check_boundary.py` already scans for (`PACKAGES_ROOT = "backend"`) and
the one every example import in `README.md` is written against.
"""
