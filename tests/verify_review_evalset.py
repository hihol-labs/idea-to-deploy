#!/usr/bin/env python3
"""Eval-set рубрики /review (v1.88.0, GP-004, «пункт 3: рубрика оценщика»).

Посеянные дефекты (benchmarks/review-evalset/cases/) прогоняются через
машинные правила рубрики — по правилам СВОЕЙ категории (recall), чистые
фикстуры — через ВСЕ правила (false positives). Метрики печатаются и
пишутся в benchmarks/review-evalset/RESULTS.json (его читает retro-скан).

Порог: detection rate >= 80% И 0 false positives — иначе exit 1 (регрессия
рубрики). Это регрессионный корпус машинной части рубрики: меняешь правила /
категории — корпус скажет, что перестало ловиться.

Self-contained, stdlib only. Run: python3 tests/verify_review_evalset.py
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BASE = REPO / "benchmarks" / "review-evalset"

# --- машинные правила рубрики: category -> [(present_re, absent_re|None)] ---
RULES = {
    "sql-performance": [
        (re.compile(r"(?i)where[^\n]*\b(lower|upper|substr|regexp_replace|date)\s*\("), None),
        (re.compile(r"(?s)for\s*\(.*?\bawait\s+\w+\.\w+\.(findUnique|findFirst|findMany)\s*\("), None),
        (re.compile(r"(?i)\bREFERENCES\s+\w+"), re.compile(r"(?i)\bCREATE\s+INDEX\b")),
    ],
    "serialization": [
        (re.compile(r"NextResponse\.json\s*\("), None),
    ],
    "migration-numbers": [
        ("dup-migration-prefix", None),  # спец-правило: дубль номера миграции
    ],
    "security-secrets": [
        (re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*=\s*[\"'][A-Za-z0-9+/_\-]{16,}[\"']"), None),
    ],
    "security-injection": [
        (re.compile(r"(?s)\$queryRawUnsafe\s*\([^)]*\$\{"), None),
    ],
    "async-correctness": [
        (re.compile(r"(?m)^\s*(?!.*\bawait\b)(?!.*=)\s*\w+\.(create|insert|write)\w*\([^)]*\)\s*;\s*$"), None),
    ],
    "tz-date-conversion": [
        (re.compile(r"toLocaleDateString\s*\("), None),
    ],
    "error-handling": [
        (re.compile(r"catch\s*\([^)]*\)\s*\{\s*\}"), None),
    ],
}


def rule_hits(rule, text):
    present, absent = rule
    if present == "dup-migration-prefix":
        nums = re.findall(r"migrations/(\d+)_", text)
        return len(nums) != len(set(nums))
    if not present.search(text):
        return False
    if absent is not None and absent.search(text):
        return False
    return True


def main():
    manifest = json.loads((BASE / "cases.json").read_text(encoding="utf-8"))
    cases = manifest["cases"]
    seeded = [c for c in cases if c["seeded"]]
    clean = [c for c in cases if not c["seeded"]]

    detected = 0
    for case in seeded:
        text = (BASE / case["file"]).read_text(encoding="utf-8")
        rules = RULES.get(case["category"], [])
        hit = any(rule_hits(r, text) for r in rules)
        detected += hit
        print(("PASS  " if hit else "MISS  ") + case["id"] + f" [{case['category']}]")

    fps = []
    all_rules = [r for rs in RULES.values() for r in rs]
    for case in clean:
        text = (BASE / case["file"]).read_text(encoding="utf-8")
        for r in all_rules:
            if rule_hits(r, text):
                fps.append(case["id"])
                break
    for cid in fps:
        print(f"FP    {cid} — правило сработало на чистой фикстуре")

    rate = detected / len(seeded) if seeded else 0.0
    results = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seeded": len(seeded),
        "detected": detected,
        "detectionRate": round(rate, 3),
        "falsePositives": len(fps),
        "threshold": 0.8,
    }
    (BASE / "RESULTS.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\ndetection rate: {detected}/{len(seeded)} ({rate:.0%}), "
          f"false positives: {len(fps)}  -> RESULTS.json")
    ok = rate >= 0.8 and not fps
    print("OK" if ok else "BELOW THRESHOLD")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
