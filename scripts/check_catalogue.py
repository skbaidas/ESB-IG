"""Assert that ESB/IG's adopted catalogue still encodes the two-axis rule it adopted.

ADOPTION IS A CLAIM AND THIS IS THE INSTRUMENT. `docs/adr/0001` adopts CTM's ADR-0038 —
the envelope, the ratified catalogue and the per-type axis rule. An adoption recorded only
in an ADR is a decision; the estate's rule (CTM `CLAUDE.md` §11.3) is that gates evaluate
committed machine-readable artefacts, so the adoption ships with a checker or it is a
sentence. This is that checker.

WHAT IT ASSERTS, and each detector fails on its own so the artefact says which fired:

  `axis-union`        an axis key permitting anything but EXACTLY one of {"string", "null"}.
                      This is the detector the whole rule turns on. A widened union
                      `["string", "null"]` is what makes a seeded sentinel representable
                      again — the defect nullability was accepted on condition of avoiding —
                      and a declared-type equality check would call it a match.
  `axis-mismatch`     a type whose declared axis disagrees with the mandate derived from its
                      NAME. `ctm.tenant.*` is about a client and carries no application;
                      `ctm.application.registered` is about the platform's catalogue and
                      carries no client. Deriving the mandate from the name rather than
                      trusting the declaration is CTM `check_event_catalogue.py`'s ground:
                      a misclassification in the declaration is then caught rather than
                      propagated.
  `envelope-drift`    the adopted field enumeration no longer matches the frozen contract.
  `unreadable`        the catalogue is absent or will not parse. A FINDING, never a skip —
                      an unreadable catalogue is broken rather than missing, and returning
                      an empty set would report every type conforming.

WHAT A GREEN HERE DOES NOT PROVE.

  * That any event is PRODUCED. CTM's four `ctm.tenant.*` producers are held and unbuilt.
  * That anything is TRANSPORTED. The broker plane is still CTM's seed until W2-T10.
  * That CTM's document and this catalogue AGREE. Nothing here reads CTM's tree, and that is
    deliberate: a dual record whose halves are checked against each other is one record with
    two files. The halves are meant to be independently derivable and to disagree loudly.
  * That this ran at all. This repository has no CI. NOT-RUN as a lane, which is not a pass.

NEGATIVE CONTROL RUNS ON EVERY INVOCATION (CTM F19). A detector that has never fired and one
that cannot fire are indistinguishable in an exit code.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
CATALOGUE = REPOSITORY_ROOT / "contracts" / "integration-catalogue.toml"
ARTEFACT = REPOSITORY_ROOT / "evidence" / "gate-catalogue.json"

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_CONTROL_FAILURE = 4

#: The only two values an axis key may take. A list of these is NOT a third value.
PERMITTED_AXIS_VALUES = ("string", "null")

#: The frozen envelope enumeration, adopted from CTM `contracts/envelope.json` at
#: envelope_version 1. Written here rather than read from CTM's tree, because a dual record
#: that reads its counterpart is not a dual record.
ADOPTED_ENVELOPE_FIELDS = (
    "event_id",
    "type",
    "version",
    "occurred_at",
    "correlation_id",
    "application_code",
    "tenant_alias",
    "producer",
    "priority",
    "payload",
)


class Finding(dict):
    """One defect, carrying its own detector name so a reader is sent to the right rule."""

    def __init__(self, detector: str, subject: str, detail: str) -> None:
        super().__init__(detector=detector, subject=subject, detail=detail)


def axis_mandate(type_name: str) -> dict[str, str]:
    """Derive from the TYPE NAME what each axis must be — never from the declaration.

    A client-lifecycle fact is about the client, so it names no application. An
    application-registration fact is about the platform's catalogue, so it names no client.
    Everything else is scoped on both axes.
    """
    if type_name.startswith("ctm.tenant."):
        return {"application_code": "null", "tenant_alias": "string"}
    if type_name == "ctm.application.registered":
        return {"application_code": "string", "tenant_alias": "null"}
    return {"application_code": "string", "tenant_alias": "string"}


def judge(catalogue: dict) -> list[Finding]:
    """Return every finding in the catalogue. An empty list is the only clean answer."""
    findings: list[Finding] = []

    adopted = tuple(catalogue.get("catalogue", {}).get("envelope_fields", ()))
    if adopted != ADOPTED_ENVELOPE_FIELDS:
        findings.append(
            Finding(
                "envelope-drift",
                "catalogue.envelope_fields",
                f"adopted enumeration is {list(adopted)}; the frozen contract is "
                f"{list(ADOPTED_ENVELOPE_FIELDS)}",
            )
        )

    for entry in catalogue.get("type", []):
        name = entry.get("name", "<unnamed>")
        mandate = axis_mandate(name)
        for axis, required in mandate.items():
            declared = entry.get(axis)
            if declared not in PERMITTED_AXIS_VALUES:
                findings.append(
                    Finding(
                        "axis-union",
                        f"{name}.{axis}",
                        f"declares {declared!r}; the permitted set must be exactly one of "
                        f"{list(PERMITTED_AXIS_VALUES)} and a union is a finding",
                    )
                )
                continue
            if declared != required:
                findings.append(
                    Finding(
                        "axis-mismatch",
                        f"{name}.{axis}",
                        f"declares {declared!r}; the mandate derived from the type name is "
                        f"{required!r}",
                    )
                )
    return findings


#: A catalogue that MUST produce findings, and a clean one that must produce none. Both are
#: judged on every invocation, so a detector that has stopped detecting is caught here rather
#: than by a green that meant nothing.
_CONTROL_VIOLATING = {
    "catalogue": {"envelope_fields": ["event_id"]},
    "type": [
        {"name": "ctm.tenant.closed", "application_code": ["string", "null"], "tenant_alias": "string"},
        {"name": "ctm.tenant.created", "application_code": "string", "tenant_alias": "string"},
    ],
}
_CONTROL_CLEAN = {
    "catalogue": {"envelope_fields": list(ADOPTED_ENVELOPE_FIELDS)},
    "type": [
        {"name": "ctm.tenant.closed", "application_code": "null", "tenant_alias": "string"},
        {"name": "ctm.application.registered", "application_code": "string", "tenant_alias": "null"},
        {"name": "ctm.application.entitled", "application_code": "string", "tenant_alias": "string"},
    ],
}


def negative_control() -> tuple[bool, str]:
    """Prove the judge still discriminates. Returns (passed, why)."""
    dirty = {f["detector"] for f in judge(_CONTROL_VIOLATING)}
    if not {"axis-union", "axis-mismatch", "envelope-drift"} <= dirty:
        return False, f"violating sample produced only {sorted(dirty)}"
    if judge(_CONTROL_CLEAN):
        return False, "clean sample produced findings"
    return True, "violating sample fired all three detectors; clean sample fired none"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="write the evidence artefact")
    args = parser.parse_args()

    control_passed, control_detail = negative_control()

    try:
        catalogue = tomllib.loads(CATALOGUE.read_text(encoding="utf-8"))
        findings = judge(catalogue)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        catalogue = {}
        findings = [Finding("unreadable", str(CATALOGUE), f"{type(exc).__name__}: {exc}")]

    if not control_passed:
        outcome, code = "control-failure", EXIT_CONTROL_FAILURE
    elif findings:
        outcome, code = "findings", EXIT_FINDINGS
    else:
        outcome, code = "clean", EXIT_CLEAN

    report = {
        "gate": "esb-ig-catalogue",
        "outcome": outcome,
        "adopted": catalogue.get("catalogue", {}).get("adopted", ""),
        "types_judged": len(catalogue.get("type", [])),
        "negative_control": {"passed": control_passed, "detail": control_detail},
        "findings": findings,
        "not_verified_here": [
            "NO EVENT IS PRODUCED. CTM's four ctm.tenant.* producers are held and unbuilt; "
            "adopting a name does not emit anything.",
            "NOTHING IS TRANSPORTED. The broker plane is CTM's esb_ig seed until W2-T10.",
            "CTM'S DOCUMENT IS NOT READ. The two halves of the dual record are meant to be "
            "independently derivable; checking one against the other would make them one "
            "record in two files.",
            "NO CI RUNS THIS. This repository has no workflow. NOT-RUN as a lane, which is "
            "not a pass.",
        ],
    }

    if args.json:
        ARTEFACT.parent.mkdir(parents=True, exist_ok=True)
        ARTEFACT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    for finding in findings:
        print(f"{finding['detector']}: {finding['subject']} — {finding['detail']}")
    if not control_passed:
        print(f"CONTROL FAILURE: {control_detail}")
    print(f"{outcome}: {len(findings)} finding(s) over {report['types_judged']} type(s)")
    return code


if __name__ == "__main__":
    sys.exit(main())
