#!/usr/bin/env python3
"""itd_review_import.py — импорт ВНЕШНИХ ревью (GitHub PR-комментарии) в
review-findings ledger (v1.87.0).

Происхождение (retro 2026-07-11, сет-3, упр.3): леджер v1.86 питается только
собственным /review — повторяющиеся классы из ревью напарника в GitHub
(боевой пример: конфликт номеров миграций, PR #968 OneOfS) для retro-майнинга
невидимы. Импортёр нормализует внешние комментарии в ту же схему записей
{ts, project, verdict, findings:[{severity, category, file, summary}]}
(писатель v1.86 — hooks/verdict-contract.sh), verdict = EXTERNAL_REVIEW.

Режимы:
  --repo owner/name [--pages N] [--exclude-author login]   # тянет gh api сам
  --stdin --project name                                    # JSON-массив комментариев с stdin (тесты/офлайн)
  --dir PATH                                                # .itd-memory (default ./.itd-memory)

Дедуп: id комментария → .itd-memory/review-import.state.json; повторный
прогон даёт «imported 0». Категория — эвристика по ключевым словам (грубая,
уточняется руками/майнингом); мимо словаря → null.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

FINDINGS_FILE = "review-findings.jsonl"
STATE_FILE = "review-import.state.json"

CATEGORY_RULES = [
    ("migration-numbers", re.compile(r"миграци\w*.{0,80}(номер|заня|переимен)|номер\w*.{0,40}миграци", re.I | re.S)),
    ("sql-performance", re.compile(r"statement_timeout|seq.?scan|индекс\w*|CONCURRENTLY|медленн", re.I)),
    ("fragile-predicate", re.compile(r"ILIKE|предикат|по имени|хрупк", re.I)),
    ("serialization", re.compile(r"BigInt|serialize|сериализ", re.I)),
]


def clip(s, n: int = 200) -> str:
    s = str(s or "")
    return s if len(s) <= n else s[: n - 1] + "…"


def classify(body: str):
    for cat, rx in CATEGORY_RULES:
        if rx.search(body or ""):
            return cat
    return None


def gh_fetch(repo: str, pages: int, exclude: str) -> list:
    out = []
    for endpoint in ("issues/comments", "pulls/comments"):
        for page in range(1, pages + 1):
            try:
                res = subprocess.run(
                    ["gh", "api",
                     f"repos/{repo}/{endpoint}?per_page=100&sort=created&direction=desc&page={page}"],
                    capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=60)
            except Exception as e:
                print(f"warning: gh fetch failed ({endpoint} p{page}): {e}")
                continue
            if res.returncode != 0:
                print(f"warning: gh api rc={res.returncode} ({endpoint} p{page}): {res.stderr.strip()[:120]}")
                continue
            try:
                batch = json.loads(res.stdout)
            except json.JSONDecodeError:
                continue
            if not batch:
                break
            for c in batch:
                if exclude and ((c.get("user") or {}).get("login") == exclude):
                    continue
                out.append(c)
    return out


def normalize(c: dict, project: str) -> dict | None:
    body = (c.get("body") or "").strip()
    if not body:
        return None
    url = c.get("issue_url") or c.get("pull_request_url") or ""
    pr = url.rstrip("/").rsplit("/", 1)[-1] if url else ""
    return {
        "ts": c.get("created_at") or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "project": project,
        "verdict": "EXTERNAL_REVIEW",
        "source": "github",
        "pr": pr,
        "author": (c.get("user") or {}).get("login") or "",
        "findings": [{
            "severity": "external",
            "category": classify(body),
            "file": clip(c.get("path") or "", 160),
            "summary": clip(body),
        }],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="")
    ap.add_argument("--pages", type=int, default=2)
    ap.add_argument("--exclude-author", default="")
    ap.add_argument("--stdin", action="store_true")
    ap.add_argument("--project", default="")
    ap.add_argument("--dir", default=".itd-memory")
    a = ap.parse_args()

    mem = Path(a.dir)
    if not mem.is_dir():
        print(f"error: {mem} не существует — импорт только в проект с .itd-memory")
        return 2

    if a.stdin:
        comments = json.load(sys.stdin)
        project = a.project or "stdin"
    elif a.repo:
        comments = gh_fetch(a.repo, a.pages, a.exclude_author)
        project = a.project or a.repo.split("/")[-1]
    else:
        print("error: нужен --repo или --stdin")
        return 2

    state_p = mem / STATE_FILE
    seen = set()
    if state_p.exists():
        try:
            seen = set(json.loads(state_p.read_text(encoding="utf-8")).get("imported", []))
        except Exception:
            seen = set()

    ledger = mem / FINDINGS_FILE
    imported = 0
    by_cat: dict = {}
    with ledger.open("a", encoding="utf-8") as fh:
        for c in comments:
            cid = str(c.get("id") or "")
            if not cid or cid in seen:
                continue
            rec = normalize(c, project)
            if rec is None:
                seen.add(cid)
                continue
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            seen.add(cid)
            imported += 1
            cat = rec["findings"][0]["category"] or "(без категории)"
            by_cat[cat] = by_cat.get(cat, 0) + 1

    tmp = state_p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"imported": sorted(seen)}, ensure_ascii=False), encoding="utf-8")
    tmp.replace(state_p)

    print(f"imported {imported} внешних ревью-записей в {ledger}")
    for cat, n in sorted(by_cat.items(), key=lambda kv: -kv[1]):
        print(f"  {cat}: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
