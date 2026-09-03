"""ESB/IG — the mediation plane's entry point.

**THE SOURCE LIVES AT `backend/esb_ig/` AND IMPORTS AS `esb_ig`.** Those are two
different choices and this package is where they meet: `pyproject.toml` maps this
directory onto the top-level distributed name, and `backend/README.md` explains
why the tree keeps its layout. A consumer writes `import esb_ig`, never
`import backend.esb_ig` — that spelling asserts "this lives inside a particular
repository", which is exactly the fact that stops being true when a consumer
installs the wheel.

**NOTHING IS PUBLISHED HERE YET, and that is not the same as nothing being
expected.** The envelope, the broker protocol, the in-memory adapter and the
RabbitMQ transport are CTM's `backend/esb_ig/` until W2-T10 moves them, and that
move is a separate step. This file exists so the packaging contract is
*executable* rather than asserted: without a package to build there is nothing to
install, and CI's install-and-import proof would be NOT-RUN — which under the
platform's §11.3 catches nothing, on the one claim whose failure mode is
discovered on the day of the move.

**THE MOVE MUST BRING RELATIVE INTRA-PACKAGE IMPORTS.** CTM's copies of these
modules import each other absolutely, as `from backend.esb_ig.envelope import
Envelope`. That spelling cannot survive installation: once this directory is
`site-packages/esb_ig/`, there is no `backend` above it. `from .envelope import
Envelope` works under BOTH names, which is what makes the source layout and the
distributed name independent of each other rather than merely reconciled.
"""

# Deliberately empty rather than absent. A package's interface is a small,
# curated surface (`backend/README.md`, "No barrel files"), and declaring that it
# currently publishes nothing is a different statement from leaving a reader to
# infer it from silence.
__all__: list[str] = []
