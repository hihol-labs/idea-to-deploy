#!/usr/bin/env python3
"""Summary of repeated hook-bench rounds (ITD simplification, plan session 3, ADR-016).

Reads the `hook_bench.py` outputs `bench-<phase>-<combo>-r<N>.jsonl` that `run_rounds.sh` writes and prints, per
phase, one Markdown table: per combination and tool the hook processes (Pre+Post), the median of the per-round chain
medians, the per-round chain medians and the median of the per-round Pre and Post medians. A process count that
differs between rounds is marked VARIES; nonzero hook exits and unparsable lines are listed under the table, and
then the exit status is 1: such a round is not a measurement.

Usage: python3 summarize_rounds.py <raw dir> <phase> [more phases ...]
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

COMBOS = ("wsl-itd", "wsl-buying", "win-buying", "win-itd")
TOOLS = ("Bash", "Edit", "Read")


def summary(raw: Path, phase: str) -> tuple[list[str], list[str]]:
    lines = [f"## {phase}",
             "| combo | tool | processes (pre+post) | chain median of runs, ms | per-run chain medians "
             "| pre / post median of runs |",
             "|---|---|---|---|---|---|"]
    problems: list[str] = []
    for combo in COMBOS:
        rows: dict[str, list[dict]] = {}
        for path in sorted(raw.glob(f"bench-{phase}-{combo}-r*.jsonl")):
            for text in path.read_text(encoding="utf-8").splitlines():
                try:
                    record = json.loads(text)
                except ValueError:
                    problems.append(f"{combo}: {path.name}: {text[:80]}")
                    continue
                if "tool" in record:
                    rows.setdefault(record["tool"], []).append(record)
                if record.get("nonzeroExits"):
                    problems.append(f"{combo}: {path.name}: nonzeroExits {record['nonzeroExits']}")
        for tool in TOOLS:
            runs = rows.get(tool, [])
            if not runs:
                continue
            first = runs[0]["processes"]
            totals = {run["processes"]["total"] for run in runs}
            chains = [run["chainWallMs"]["median"] for run in runs]
            pre = statistics.median(run["preWallMs"]["median"] for run in runs)
            post = statistics.median(run["postWallMs"]["median"] for run in runs)
            varies = "" if len(totals) == 1 else f" VARIES {sorted(totals)}"
            lines.append(f"| {combo} | {tool} | {first['total']} ({first['pre']}+{first['post']}){varies} "
                         f"| {statistics.median(chains):.0f} | {' / '.join(map(str, chains))} "
                         f"| {pre:.0f} / {post:.0f} |")
    return lines, problems


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: summarize_rounds.py <raw dir> <phase> [more phases ...]", file=sys.stderr)
        return 2
    failed = False
    for phase in argv[1:]:
        lines, problems = summary(Path(argv[0]), phase)
        print("\n".join(lines))
        for problem in problems:
            print(f"  ! {problem}")
        failed = failed or bool(problems)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
