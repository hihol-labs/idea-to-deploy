#!/usr/bin/env python3
"""Blind list of hit candidates (protocol section 3, step 2).

  blind.py make    - blind-list.md (blocker text + case reference, random order, no variant/run) and the sealed key
                     blind-key.json (line id -> run); refuses to overwrite an existing list
  blind.py reveal  - joins the owner's marks (blind-marks.txt: '<id> да|нет' per line) with the key, prints per run
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import secrets
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pilot_run import CASES  # noqa: E402

REFERENCE = {
    "K1": "подтверждение не привязано к `tool_name`; подтверждение без сессии принимается",
    "K2": "запись через symlink `.itd-memory` в существующий файл не ловится: сверяются только имена",
    "K3": "измененный кандидат не проверен через `validate_verification_receipt`",
    "H": "причина отказа диспетчера не сравнивается с прямым вызовом",
}


TAG = sys.argv[2] if len(sys.argv) > 2 else ""
ONLY = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else None


def candidates():
    out = []
    for p in sorted((HERE / "runs").glob("run-*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        case = r["case"]
        if r.get("variant") == "canary" or not r.get("valid") or not CASES[case][3] or (ONLY and case not in ONLY):
            continue
        rx = re.compile(CASES[case][3], re.I | re.S)
        stem = Path(CASES[case][2]).name
        for i, b in enumerate((r.get("answer") or {}).get("blockers") or []):
            if not isinstance(b, dict):
                continue
            where = f"{b.get('file', '')} {b.get('problem', '')}"
            if stem in where and rx.search(str(b.get("problem", ""))):
                out.append({"case": case, "variant": r["variant"], "run": r["run"], "blocker": i,
                            "file": b.get("file", ""), "problem": b.get("problem", "")})
    return out


def make():
    lst, key = HERE / f"blind-list{TAG}.md", HERE / f"blind-key{TAG}.json"
    if lst.exists():
        sys.exit("blind-list.md exists; refusing to overwrite")
    cands = candidates()
    random.SystemRandom().shuffle(cands)
    lines, mapping = ["# Слепой список кандидатов в попадание (протокол, раздел 3, шаг 2)", "",
                      "Рубрика: «да» - блокер называет то же поведение кода, что эталон, и говорит, что тест его не "
                      "проверяет или что нарушение пройдет незамеченным; «нет» - все остальное.", ""], {}
    for c in cands:
        lid = secrets.token_hex(3)
        mapping[lid] = c
        lines += [f"## {lid}", f"- Эталон: {REFERENCE[c['case']]}", f"- Блокер: `{c['file']}` - {c['problem']}", ""]
    if not cands:
        lines.append("Кандидатов нет: ни один блокер засчитанных прогонов не прошел отбор шаблоном.")
    lst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    key.write_text(json.dumps(mapping, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(cands)} candidates; list sha256 {hashlib.sha256(lst.read_bytes()).hexdigest()}")


def reveal():
    key = json.loads((HERE / f"blind-key{TAG}.json").read_text(encoding="utf-8"))
    marks_path = HERE / f"blind-marks{TAG}.txt"
    marks = {}
    for line in marks_path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] in key:
            marks[parts[0]] = parts[1].lower()
    missing = sorted(set(key) - set(marks))
    if missing:
        sys.exit(f"unmarked lines: {missing}")
    hits: dict = {}
    for lid, c in key.items():
        k = (c["case"], c["variant"], c["run"])
        hits[k] = hits.get(k, False) or marks[lid] == "да"
    print("marks sha256", hashlib.sha256(marks_path.read_bytes()).hexdigest())
    print(json.dumps([{"case": k[0], "variant": k[1], "run": k[2], "hit": v} for k, v in sorted(hits.items())],
                     ensure_ascii=False))


if __name__ == "__main__":
    {"make": make, "reveal": reveal}[sys.argv[1]]()
