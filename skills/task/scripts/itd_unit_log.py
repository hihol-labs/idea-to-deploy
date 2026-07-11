#!/usr/bin/env python3
"""itd_unit_log.py — harness-писатель unit-бухгалтерии /task Step 3.5 (v1.85.0).

Диагноз G-004 (retro 2026-07-11): Step 3.5 велел МОДЕЛИ вручную дописывать
JSON в STATE.json/events.jsonl — модель теряла activation-события (live:
4 юнита U-2..U-5 verified без activated → «Аномалия учёта» в retro-скане,
VCR слеп). Ремонт слоя: инструкция → инструмент. Переходами unit-статусов
/task управляет этот скрипт; пары activated/verified гарантированы fail-closed
проверкой, verified без evidence не бывает.

Использование (из корня проекта; --dir переопределяет .itd-memory):
  itd_unit_log.py activate U-9 --goal "однострочная формулировка"
  itd_unit_log.py verified U-9 --evidence "вывод команды верификации"
  itd_unit_log.py backfill-activation U-2 --note "почему активация дописывается задним числом"

Семантика:
  activate  — WIP=1 (откажет, пока текущий unit in_progress/verifying),
              пишет STATE.currentUnit + событие activated (actor: harness).
  verified  — требует существующего activated-события юнита (иначе exit 1 с
              подсказкой про осознанный backfill), обновляет STATE.currentUnit,
              пишет событие verified с обязательным evidence.
  backfill-activation — корректирующее событие activated с actor
              harness-reconciliation (для исторической реконсиляции; note
              обязателен — fail-closed, как skippedReason у /goal).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

EVIDENCE_MAX = 500


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def die(msg: str, code: int = 2) -> int:
    print(f"error: {msg}")
    return code


def append_event(mem: Path, unit_id: str, decision: str, evidence: str, actor: str = "harness") -> None:
    evt = {
        "id": f"evt-unit-{int(time.time())}",
        "at": now_iso(),
        "actor": actor,
        "type": "unit",
        "name": unit_id,
        "decision": decision,
        "evidence": evidence[:EVIDENCE_MAX],
    }
    events = mem / "events.jsonl"
    with events.open("a", encoding="utf-8") as f:
        f.write(json.dumps(evt, ensure_ascii=False) + "\n")


def has_event(mem: Path, unit_id: str, decision: str) -> bool:
    events = mem / "events.jsonl"
    if not events.exists():
        return False
    for line in events.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("type") == "unit" and e.get("name") == unit_id and e.get("decision") == decision:
            return True
    return False


def load_state(mem: Path) -> dict:
    p = mem / "STATE.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def save_state(mem: Path, state: dict) -> None:
    """Атомарная запись (ACID-контракт v1.75.0: tmp + replace)."""
    p = mem / "STATE.json"
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["activate", "verified", "backfill-activation"])
    ap.add_argument("unit_id")
    ap.add_argument("--goal", default="")
    ap.add_argument("--evidence", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--dir", default=".itd-memory")
    a = ap.parse_args()

    mem = Path(a.dir)
    if not mem.is_dir():
        return die(f"{mem} не существует — /task не создаёт .itd-memory (территория /adopt)")

    if a.command == "activate":
        state = load_state(mem)
        cur = state.get("currentUnit") or {}
        if cur.get("id") and cur.get("id") != a.unit_id and cur.get("status") in ("in_progress", "verifying", "recovery_required"):
            return die(f"WIP=1: текущий unit {cur['id']} в статусе {cur['status']} — сначала доведи его", 1)
        if not a.goal:
            return die("--goal обязателен при activate (однострочная формулировка задачи)", 1)
        state["currentUnit"] = {"id": a.unit_id, "goal": a.goal, "status": "in_progress", "startedAt": now_iso()}
        save_state(mem, state)
        append_event(mem, a.unit_id, "activated", a.goal)
        print(f"activated {a.unit_id}: {a.goal}")
        return 0

    if a.command == "verified":
        if not a.evidence:
            return die("--evidence обязателен: verified без evidence не бывает", 1)
        if not has_event(mem, a.unit_id, "activated"):
            return die(
                f"нет activation-события для {a.unit_id} — verified не пишется без пары "
                f"(осознанная реконсиляция: backfill-activation {a.unit_id} --note \"...\")", 1)
        state = load_state(mem)
        cur = state.get("currentUnit") or {}
        if cur.get("id") == a.unit_id:
            cur["status"] = "verified"
            cur["completedAt"] = now_iso()
            state["currentUnit"] = cur
            save_state(mem, state)
        append_event(mem, a.unit_id, "verified", a.evidence)
        print(f"verified {a.unit_id}")
        return 0

    # backfill-activation
    if not a.note:
        return die("--note обязателен: реконсиляция без причины не бывает (fail-closed)", 1)
    if has_event(mem, a.unit_id, "activated"):
        return die(f"activation-событие для {a.unit_id} уже есть — backfill не нужен", 1)
    append_event(mem, a.unit_id, "activated", f"backfill: {a.note}", actor="harness-reconciliation")
    print(f"backfilled activation {a.unit_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
