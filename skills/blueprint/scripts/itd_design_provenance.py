#!/usr/bin/env python3
"""Advisory design-provenance report validator for /blueprint (GPG-004 U17).

Reads a DESIGN_PROVENANCE.md report written during the /blueprint adversarial
debate and reports, advisorily, which architectural claims lack a recorded
provenance source. It is explicitly NOT a gate:

- every advisory outcome exits 0 — findings, a clean report, an absent report
  and a malformed report all exit 0 (absence never blocks);
- the output carries no verdict field and never the acceptance token, so it
  can never be mistaken for review or acceptance evidence;
- the tool only reads; it never writes or mutates anything.

Invocation: ``itd_design_provenance.py --report DESIGN_PROVENANCE.md``.
Without arguments it is a quiet no-op (exit 0, no output), so wiring it into
an unrelated pipeline cannot produce noise or a block.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

KNOWN_SOURCES = (
    "user-requirement",
    "measured-evidence",
    "external-doc",
    "model-assumption",
)
CLAIM_RE = re.compile(r"^##\s+Claim:\s*(?P<claim>.+?)\s*$")
SOURCE_RE = re.compile(
    r"^-\s+Source:\s*(?P<source>[a-z-]+)\s*$", re.IGNORECASE
)
REFERENCE_RE = re.compile(r"^-\s+Reference:\s*(?P<reference>.+?)\s*$")


def note(path: str, line: int, why: str, fix: str) -> dict:
    return {"path": path, "line": line, "why": why, "fix": fix}


def review_report(path: Path) -> dict:
    """Parse the report and produce the advisory summary. Never raises."""
    result = {"advisory": True, "claims": 0, "unsourced": 0, "notes": []}
    try:
        raw = path.read_bytes()
    except OSError as exc:
        result["notes"].append(note(
            str(path), 0,
            f"provenance report is absent or unreadable ({exc.__class__.__name__})",
            "optional step: create DESIGN_PROVENANCE.md from the /blueprint "
            "step 2.5b template if design provenance is wanted; absence never "
            "blocks anything",
        ))
        return result
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        result["notes"].append(note(
            str(path), 0,
            "provenance report is not valid UTF-8 text",
            "re-save DESIGN_PROVENANCE.md as UTF-8 markdown; this note is "
            "advisory and blocks nothing",
        ))
        return result
    claim_line = 0
    claim_text = ""
    source = ""
    reference = ""

    def close_claim() -> None:
        nonlocal claim_line, claim_text, source, reference
        if not claim_line:
            return
        result["claims"] += 1
        normalized = source.casefold()
        if not source:
            result["unsourced"] += 1
            result["notes"].append(note(
                str(path), claim_line,
                f"claim has no recorded Source: {claim_text!r}",
                "add '- Source: <user-requirement|measured-evidence|"
                "external-doc|model-assumption>' under the claim",
            ))
        elif normalized not in KNOWN_SOURCES:
            result["unsourced"] += 1
            result["notes"].append(note(
                str(path), claim_line,
                f"claim source {source!r} is not a known provenance class",
                "use one of: " + ", ".join(KNOWN_SOURCES),
            ))
        elif normalized == "model-assumption" and not reference:
            result["notes"].append(note(
                str(path), claim_line,
                f"model-assumption claim has no Reference: {claim_text!r}",
                "state what would confirm or refute the assumption in "
                "'- Reference: ...' (advisory)",
            ))
        claim_line, claim_text, source, reference = 0, "", "", ""

    for lineno, line in enumerate(text.splitlines(), 1):
        claim = CLAIM_RE.match(line)
        if claim:
            close_claim()
            claim_line, claim_text = lineno, claim.group("claim")
            continue
        src = SOURCE_RE.match(line)
        if src and claim_line:
            source = src.group("source")
            continue
        ref = REFERENCE_RE.match(line)
        if ref and claim_line:
            reference = ref.group("reference")
    close_claim()
    if not result["claims"]:
        result["notes"].append(note(
            str(path), 0,
            "provenance report contains no '## Claim:' entries",
            "record each architectural claim as '## Claim: ...' with a "
            "Source line; this note is advisory and blocks nothing",
        ))
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    if args.report is None:
        # Quiet no-op by contract: no target means nothing to advise on.
        return 0
    print(json.dumps(review_report(args.report), ensure_ascii=False,
                     sort_keys=True))
    # Advisory by construction (GPG-004 U17 cannotWeaken): findings, clean,
    # absent and malformed reports all exit 0 - this tool never blocks.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
