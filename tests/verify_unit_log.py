#!/usr/bin/env python3
"""verify_unit_log.py — контракт harness-писателя unit-бухгалтерии /task (v1.85.0).

G-004 (retro 2026-07-11): ручная запись unit-событий моделью теряла activated
(4 юнита verified без пары → «Аномалия учёта», слепой VCR). Контракт скрипта:
  1. activate пишет STATE.currentUnit + событие activated (actor: harness);
  2. verified БЕЗ прежней активации — отказ (fail-closed), с активацией — ок;
  3. verified без --evidence — отказ;
  4. WIP=1: activate при незавершённом другом юните — отказ;
  5. backfill-activation требует --note и отказывает при существующей паре.
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "skills", "task", "scripts", "itd_unit_log.py")

fails = []


def check(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + ((" " + detail) if (detail and not cond) else ""))
    if not cond:
        fails.append(name)


def run(mem, *args):
    return subprocess.run([sys.executable, SCRIPT, *args, "--dir", mem],
                          capture_output=True, text=True, timeout=30)


with tempfile.TemporaryDirectory() as mem:
    # 2a. verified без активации — отказ
    r = run(mem, "verified", "U-1", "--evidence", "x")
    check("verified-without-activation-refused", r.returncode != 0 and "activation" in (r.stdout + r.stderr))

    # 1. activate пишет пару STATE + событие
    r = run(mem, "activate", "U-1", "--goal", "тестовый юнит")
    ok_state = False
    ok_evt = False
    if r.returncode == 0:
        st = json.load(open(os.path.join(mem, "STATE.json"), encoding="utf-8"))
        cu = st.get("currentUnit") or {}
        ok_state = cu.get("id") == "U-1" and cu.get("status") == "in_progress"
        evs = [json.loads(l) for l in open(os.path.join(mem, "events.jsonl"), encoding="utf-8")]
        ok_evt = any(e.get("name") == "U-1" and e.get("decision") == "activated" and e.get("actor") == "harness" for e in evs)
    check("activate-writes-state-and-event", r.returncode == 0 and ok_state and ok_evt,
          f"rc={r.returncode} out={r.stdout!r}")

    # 4. WIP=1
    r = run(mem, "activate", "U-2", "--goal", "второй юнит")
    check("wip1-refused", r.returncode != 0 and "WIP=1" in (r.stdout + r.stderr))

    # 3. verified без evidence — отказ
    r = run(mem, "verified", "U-1")
    check("verified-without-evidence-refused", r.returncode != 0)

    # 2b. verified с активацией и evidence — ок, статус verified
    r = run(mem, "verified", "U-1", "--evidence", "тест зелёный")
    st = json.load(open(os.path.join(mem, "STATE.json"), encoding="utf-8"))
    evs = [json.loads(l) for l in open(os.path.join(mem, "events.jsonl"), encoding="utf-8")]
    check("verified-ok", r.returncode == 0
          and st["currentUnit"]["status"] == "verified"
          and any(e.get("name") == "U-1" and e.get("decision") == "verified" for e in evs),
          f"rc={r.returncode} out={r.stdout!r}")

    # 5. backfill: без note — отказ; с note — событие reconciliation; повторный — отказ
    r = run(mem, "backfill-activation", "U-9")
    check("backfill-note-required", r.returncode != 0)
    r = run(mem, "backfill-activation", "U-9", "--note", "историческая реконсиляция")
    evs = [json.loads(l) for l in open(os.path.join(mem, "events.jsonl"), encoding="utf-8")]
    check("backfill-ok", r.returncode == 0 and any(
        e.get("name") == "U-9" and e.get("decision") == "activated" and e.get("actor") == "harness-reconciliation" for e in evs))
    r = run(mem, "backfill-activation", "U-9", "--note", "дубль")
    check("backfill-duplicate-refused", r.returncode != 0)

if fails:
    print("FAILED:", " ".join(fails))
    sys.exit(1)
print("verify_unit_log: all ok")
