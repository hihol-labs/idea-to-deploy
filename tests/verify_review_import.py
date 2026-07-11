#!/usr/bin/env python3
"""verify_review_import.py — контракт импортёра внешних ревью (v1.87.0).

  1. stdin-режим кладёт нормализованные записи в review-findings.jsonl
     (схема v1.86: ts/project/verdict/findings[{severity,category,file,summary}]);
  2. классификатор: текст в стиле PR #968 (номера миграций заняты) →
     category migration-numbers;
  3. дедуп: повторный прогон того же входа → imported 0;
  4. пустые тела пропускаются, id всё равно помечается обработанным.
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "skills", "retro", "scripts", "itd_review_import.py")

fails = []


def check(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + ((" " + detail) if (detail and not cond) else ""))
    if not cond:
        fails.append(name)


FIXTURE = [
    {"id": 101, "created_at": "2026-07-01T10:00:00Z",
     "issue_url": "https://api.github.com/repos/x/y/issues/968",
     "user": {"login": "partner"},
     "body": "Миграции переименованы 416/417 → 422/423 — номера уже заняты на main."},
    {"id": 102, "created_at": "2026-07-02T10:00:00Z",
     "issue_url": "https://api.github.com/repos/x/y/issues/1049",
     "user": {"login": "partner"},
     "body": "Отчёт не укладывался в statement_timeout, один месяц 37,5 с — добавил индекс."},
    {"id": 103, "created_at": "2026-07-03T10:00:00Z",
     "issue_url": "https://api.github.com/repos/x/y/issues/1050",
     "user": {"login": "partner"}, "body": ""},
]


def run_import(mem):
    return subprocess.run(
        [sys.executable, SCRIPT, "--stdin", "--project", "probe", "--dir", mem],
        input=json.dumps(FIXTURE), capture_output=True, text=True, timeout=30)


with tempfile.TemporaryDirectory() as mem:
    r = run_import(mem)
    ledger = os.path.join(mem, "review-findings.jsonl")
    recs = [json.loads(l) for l in open(ledger, encoding="utf-8")] if os.path.exists(ledger) else []
    check("imported-two", r.returncode == 0 and len(recs) == 2,
          f"rc={r.returncode} n={len(recs)} out={r.stdout!r}")
    m = next((x for x in recs if x["pr"] == "968"), None)
    check("schema-fields", m is not None and m["verdict"] == "EXTERNAL_REVIEW"
          and m["findings"][0]["severity"] == "external" and "summary" in m["findings"][0],
          f"rec={m}")
    check("category-migration-numbers", m is not None and m["findings"][0]["category"] == "migration-numbers",
          f"cat={m and m['findings'][0]['category']}")
    s = next((x for x in recs if x["pr"] == "1049"), None)
    check("category-sql-performance", s is not None and s["findings"][0]["category"] == "sql-performance")

    r2 = run_import(mem)
    recs2 = [json.loads(l) for l in open(ledger, encoding="utf-8")]
    check("dedup-rerun-zero", "imported 0" in r2.stdout and len(recs2) == 2,
          f"out={r2.stdout!r} n={len(recs2)}")

if fails:
    print("FAILED:", " ".join(fails))
    sys.exit(1)
print("verify_review_import: all ok")
