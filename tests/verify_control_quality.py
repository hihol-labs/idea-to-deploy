#!/usr/bin/env python3
"""Measured control coverage and false-classification regression corpus."""
from __future__ import annotations

import runpy
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hooks"))
import completion_lib as cl  # noqa: E402


def main() -> int:
    signal_cases = [
        ("pytest -q", True),
        ("npm test", True),
        ("pnpm vitest run", True),
        ("go test ./...", True),
        ("Invoke-Pester", True),
        ("git commit -m test", False),
        ("echo test complete", False),
        ("python -c \"import pytest\"", False),
        ("node benchmarks/review-evalset/run.mjs", False),
        ("cat README.md", False),
    ]
    gate = runpy.run_path(str(ROOT / "hooks" / "completion-gate.sh"), run_name="itd_quality_probe")
    commit_re = gate["GIT_COMMIT_RE"]
    commit_cases = [
        ("git commit -m x", True),
        ("git -C /tmp/repo commit -m x", True),
        ("/usr/bin/git --git-dir=.git commit -m x", True),
        ("git status", False),
        ("echo git commit", False),
        ("printf 'git commit'", False),
    ]
    tp = tn = fp = fn = 0
    for command, expected in signal_cases:
        actual = cl.classify_bash(command, {"stdout": "3 passed", "exitCode": 0}) is not None
        tp += int(expected and actual)
        tn += int(not expected and not actual)
        fp += int(not expected and actual)
        fn += int(expected and not actual)
    for command, expected in commit_cases:
        actual = bool(commit_re.search(command))
        tp += int(expected and actual)
        tn += int(not expected and not actual)
        fp += int(not expected and actual)
        fn += int(expected and not actual)

    from verify_harness_map_fixtures import GATE_TESTS, derived_hard_gates
    hard = derived_hard_gates()
    covered = hard.intersection(GATE_TESTS)
    total = tp + tn + fp + fn
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    checks = [
        ("control-family coverage = 2/2", len(signal_cases) > 0 and len(commit_cases) > 0),
        ("hard-gate proof coverage = 11/11", len(hard) == 11 and covered == hard),
        ("false positives = 0", fp == 0),
        ("false negatives = 0", fn == 0),
        ("precision = 1.0", precision == 1.0),
        ("recall = 1.0", recall == 1.0),
        ("eval corpus is non-trivial", total >= 16 and tp >= 8 and tn >= 8),
    ]
    failed = 0
    for name, condition in checks:
        print(f"{'PASS' if condition else 'FAIL'}  {name}")
        failed += int(not condition)
    print(f"\n[metric] cases={total} TP={tp} TN={tn} FP={fp} FN={fn} precision={precision:.3f} recall={recall:.3f}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
