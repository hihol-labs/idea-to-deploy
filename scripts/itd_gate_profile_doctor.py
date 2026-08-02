#!/usr/bin/env python3
"""Profile-aware ITD gate doctor; no arguments is a quiet no-op."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "skills" / "_shared"
sys.path.insert(0, str(SHARED))

import itd_gate_control as gate  # noqa: E402


MAX_INPUT_BYTES = 1024 * 1024


def load_profile_registry(path: Path) -> dict[str, Any]:
    try:
        raw = path.resolve().read_bytes()
    except OSError as exc:
        raise gate.GateError(
            "UNAVAILABLE", f"profile registry unavailable: {path}"
        ) from exc
    if not raw or len(raw) > MAX_INPUT_BYTES:
        raise gate.GateError("UNVERIFIED", "profile registry size is invalid")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise gate.GateError("UNVERIFIED", "profile registry JSON is invalid") from exc
    return gate.validate_profile_registry(value)


def inspect(
    registry: dict[str, Any],
    *,
    all_repositories: bool,
    repository: str | None,
) -> dict[str, Any]:
    selected = [
        row for row in registry["repositories"]
        if all_repositories or row["repository"] == repository
    ]
    if not selected:
        raise gate.GateError("UNVERIFIED", "no profile registry entries selected")
    rows = [gate.profile_doctor_entry(row) for row in selected]
    rows.sort(key=lambda row: row["repository"].casefold())
    counts = {
        claim: sum(row["status"] == claim for row in rows)
        for claim in gate.CLAIM_ORDER
    }
    return {
        "status": gate.aggregate_claim(rows), "total": len(rows),
        "claims": counts, "repositories": rows,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--input", type=Path)
    selection = result.add_mutually_exclusive_group()
    selection.add_argument("--all", action="store_true")
    selection.add_argument("--repository")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.input is None and not args.all and args.repository is None:
        return 0
    if args.input is None or (not args.all and args.repository is None):
        parser().error("--input and one of --all/--repository are required")
    try:
        result = inspect(
            load_profile_registry(args.input),
            all_repositories=args.all, repository=args.repository,
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result["status"] != "UNVERIFIED" else 1
    except gate.GateError as exc:
        print(
            json.dumps({"status": exc.status, "reason": exc.reason}, sort_keys=True),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
