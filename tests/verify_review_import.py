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
          and m["findings"][0]["severity"] == "unspecified"
          and "summary" in m["findings"][0], f"rec={m}")
    # PILOT-P01: провенанс и версия словаря штампуются на записи
    check("provenance-and-taxonomy-version",
          m is not None and m["source"] == "external-github-review"
          and m["taxonomy_version"] == 1 and m["lineage"].endswith("/968"),
          f"rec={m}")
    check("category-migration-numbers", m is not None
          and m["findings"][0]["category"] == "naming-collision",
          f"cat={m and m['findings'][0]['category']}")
    s = next((x for x in recs if x["pr"] == "1049"), None)
    check("category-sql-performance",
          s is not None and s["findings"][0]["category"] == "performance")

    # непонятый комментарий помечается честно, а не выдумывает класс
    unmatched = [{"id": 201, "created_at": "2026-07-04T10:00:00Z",
                  "issue_url": "https://api.github.com/repos/x/y/issues/1051",
                  "user": {"login": "partner"},
                  "body": "Спасибо, посмотрю на следующей неделе."}]
    ru = subprocess.run(
        [sys.executable, SCRIPT, "--stdin", "--project", "probe", "--dir", mem],
        input=json.dumps(unmatched), capture_output=True, text=True, timeout=30)
    recs_u = [json.loads(l) for l in open(ledger, encoding="utf-8")]
    u = next((x for x in recs_u if x["pr"] == "1051"), None)
    check("unmatched-comment-is-unclassified",
          ru.returncode == 0 and u is not None
          and u["findings"][0]["category"] == "unclassified",
          f"rec={u}")

    # Писательские значения приходят из словаря. Проверка должна РАЗЛИЧАТЬ
    # словарь и литерал, поэтому подсовывается словарь с другими значениями:
    # захардкоженный писатель выдаст свои и покраснеет.
    TAX = json.load(open(os.path.join(ROOT, "skills", "_shared",
                                      "VERDICT_TAXONOMY.json"),
                         encoding="utf-8"))
    swapped = dict(TAX)
    swapped["writerDefaults"] = dict(TAX["writerDefaults"])
    # Значения отличаются от привычных, но остаются допустимыми ДЛЯ СВОЕГО
    # источника: словарь, в котором дефолт не разрешён собственному писателю,
    # с r19 считается испорченным и не грузится вовсе.
    swapped["writerDefaults"]["external-github-review"] = {
        "source": "external-github-review", "severity": "minor",
        "category": "readability"}
    tax2 = os.path.join(mem, "swapped-taxonomy.json")
    with open(tax2, "w", encoding="utf-8") as fh:
        json.dump(swapped, fh, ensure_ascii=False)
    mem2 = tempfile.mkdtemp()
    r_sw = subprocess.run(
        [sys.executable, SCRIPT, "--stdin", "--project", "probe",
         "--dir", mem2],
        input=json.dumps(FIXTURE + unmatched), capture_output=True, text=True,
        timeout=30, env=dict(os.environ, ITD_VERDICT_TAXONOMY=tax2))
    recs_sw = [json.loads(l) for l in
               open(os.path.join(mem2, "review-findings.jsonl"),
                    encoding="utf-8")] \
        if os.path.exists(os.path.join(mem2, "review-findings.jsonl")) else []
    sw = next((x for x in recs_sw if x["pr"] == "1051"), None)
    check("writer values follow the taxonomy, not the writer's own literals",
          r_sw.returncode == 0 and sw is not None
          and sw["source"] == "external-github-review"
          and sw["findings"][0]["severity"] == "minor"
          and sw["findings"][0]["category"] == "readability",
          f"rec={sw} out={r_sw.stdout!r}")

    r2 = run_import(mem)
    recs2 = [json.loads(l) for l in open(ledger, encoding="utf-8")]
    check("dedup-rerun-zero", "imported 0" in r2.stdout and len(recs2) == 3,
          f"out={r2.stdout!r} n={len(recs2)}")

# отклонённый комментарий не помечается обработанным: после починки словаря
# повторный импорт обязан его подобрать
with tempfile.TemporaryDirectory() as mem:
    broken = os.path.join(mem, "broken.json")
    with open(broken, "w", encoding="utf-8") as fh:
        fh.write("{ not json")
    r_bad = subprocess.run(
        [sys.executable, SCRIPT, "--stdin", "--project", "probe", "--dir", mem],
        input=json.dumps(FIXTURE), capture_output=True, text=True, timeout=30,
        env=dict(os.environ, ITD_VERDICT_TAXONOMY=broken))
    r_ok = subprocess.run(
        [sys.executable, SCRIPT, "--stdin", "--project", "probe", "--dir", mem],
        input=json.dumps(FIXTURE), capture_output=True, text=True, timeout=30)
    canon = os.path.join(mem, "review-findings.jsonl")
    recs_r = [json.loads(l) for l in open(canon, encoding="utf-8")] \
        if os.path.exists(canon) else []
    check("a rejected comment is retried after the taxonomy is repaired",
          r_bad.returncode == 0 and r_ok.returncode == 0 and len(recs_r) == 2,
          f"n={len(recs_r)} bad={r_bad.stdout!r} ok={r_ok.stdout!r}")

# словарь недоступен -> импортёр ничего не теряет и ничего не подсовывает
with tempfile.TemporaryDirectory() as mem:
    env = dict(os.environ, ITD_VERDICT_TAXONOMY=os.path.join(mem, "nope.json"))
    r3 = subprocess.run(
        [sys.executable, SCRIPT, "--stdin", "--project", "probe", "--dir", mem],
        input=json.dumps(FIXTURE), capture_output=True, text=True, timeout=30,
        env=env)
    canon = os.path.join(mem, "review-findings.jsonl")
    quarantine = os.path.join(mem, "review-findings-rejected.jsonl")
    check("unavailable-taxonomy-quarantines-import",
          r3.returncode == 0 and not os.path.exists(canon)
          and os.path.exists(quarantine)
          and "taxonomy-unavailable" in open(quarantine, encoding="utf-8").read(),
          f"rc={r3.returncode} out={r3.stdout!r}")

if fails:
    print("FAILED:", " ".join(fails))
    sys.exit(1)
print("verify_review_import: all ok")
