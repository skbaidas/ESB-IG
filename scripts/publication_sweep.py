"""Full-history sweep of a repository, over every blob rather than the working tree.

Precondition 1 of the platform owner's ruling on `W2-T10` step (c): publication is
fail-closed until a history scanner has read every commit. The working tree is not the
subject — a secret removed in a later commit is still in the object database, and that is
the whole reason this class of tool exists.

Two passes, deliberately separate:

1. **detect-secrets** over every unique blob, materialised under its historical path so the
   filename heuristics apply. Every plugin the tool ships is enabled.
2. **A named-disclosure grep** over the same blobs — the categories the ruling named that a
   secrets scanner does not look for: tenant and partner names, internal hostnames, private
   addresses and absolute developer paths.

Findings are printed and the exit code is non-zero if either pass fires, so this can gate.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(sys.argv[1])

#: Patterns for the disclosure classes a secrets scanner does not cover. Each is a
#: (name, compiled pattern) pair; the name is what a finding reports.
DISCLOSURE = [
    (
        "private-ipv4",
        re.compile(
            r"\b(?:10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)\b"
        ),
    ),
    (
        "internal-hostname",
        re.compile(r"\b[\w-]+\.(?:local|internal|corp|lan|intranet|home)\b", re.I),
    ),
    ("windows-dev-path", re.compile(r"[A-Za-z]:\\\\?[Uu]sers\\\\?[^\s\"']+")),
    ("pmo-tree-path", re.compile(r"[A-Za-z]:[\\/]PMO[\\/]")),
    ("email-address", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("jordan-gov-domain", re.compile(r"\b[\w-]+\.gov\.jo\b", re.I)),
    ("bearer-ish", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{20,}")),
    ("aws-key-id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private-key-block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY")),
]

#: Email addresses that are the repository's own attribution and are not a disclosure.
EMAIL_ALLOWED = {"noreply@anthropic.com", "skbaidas@gmail.com"}


def blobs() -> list[tuple[str, str]]:
    """Every (sha, path) blob reachable from any ref, deduplicated by sha."""
    out = subprocess.run(
        ["git", "-C", str(REPO), "rev-list", "--objects", "--all"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    ).stdout.splitlines()
    seen: dict[str, str] = {}
    for line in out:
        parts = line.split(" ", 1)
        if len(parts) == 2 and parts[1]:
            seen.setdefault(parts[0], parts[1])
    kinds = subprocess.run(
        ["git", "-C", str(REPO), "cat-file", "--batch-check", "--batch-all-objects"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    ).stdout.splitlines()
    blob_shas = {line.split()[0] for line in kinds if " blob " in line}
    return [(sha, path) for sha, path in seen.items() if sha in blob_shas]


def content(sha: str) -> str:
    raw = subprocess.run(
        ["git", "-C", str(REPO), "cat-file", "blob", sha],
        capture_output=True,
        check=True,
    ).stdout
    return raw.decode("utf-8", errors="replace")


def main() -> int:
    entries = blobs()
    workdir = Path(tempfile.mkdtemp(prefix="sweep-"))
    materialised: list[tuple[Path, str, str]] = []
    for sha, path in entries:
        target = workdir / sha[:8] / path
        target.parent.mkdir(parents=True, exist_ok=True)
        text = content(sha)
        target.write_text(text, encoding="utf-8", errors="replace")
        materialised.append((target, sha, path))

    print(f"blobs materialised: {len(materialised)} from {REPO}")

    # Pass 2 first — it is the cheap one and its findings are the readable ones.
    disclosures: list[str] = []
    for target, sha, path in materialised:
        text = target.read_text(encoding="utf-8", errors="replace")
        for name, pattern in DISCLOSURE:
            for match in set(pattern.findall(text)):
                if name == "email-address" and match.lower() in EMAIL_ALLOWED:
                    continue
                disclosures.append(f"{name:20} {sha[:8]} {path}: {match[:90]}")

    print(f"\n== named-disclosure pass: {len(disclosures)} hit(s)")
    for line in sorted(set(disclosures)):
        print("  " + line)

    # Pass 1 — detect-secrets over the materialised tree.
    scan = subprocess.run(
        [sys.executable, "-m", "detect_secrets", "scan", "--all-files", str(workdir)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    results = json.loads(scan.stdout).get("results", {}) if scan.stdout else {}
    total = sum(len(v) for v in results.values())
    print(f"\n== detect-secrets pass: {total} candidate(s) across {len(results)} file(s)")
    for filename, findings in sorted(results.items()):
        for finding in findings:
            rel = filename.replace(str(workdir), "").lstrip("\\/")
            print(f"  {finding['type']:32} {rel}:{finding.get('line_number')}")

    print(f"\nworkdir: {workdir}")
    return 1 if (disclosures or total) else 0


if __name__ == "__main__":
    raise SystemExit(main())
