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
import re
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

    # 6a. activate без --risk-tier — отказ ДО записи (LPD-002 R4c):
    # пропорциональность маршрута ревью не выводится из имени юнита, а ручная
    # дописка riskTier в STATE терялась (S10, S11, R1-R3).
    r = run(mem, "activate", "U-1", "--goal", "тестовый юнит")
    check("activate-without-risk-tier-refused",
          r.returncode != 0 and "--risk-tier" in (r.stdout + r.stderr),
          f"rc={r.returncode} out={r.stdout!r}")
    check("refused-activation-writes-nothing",
          not os.path.exists(os.path.join(mem, "STATE.json"))
          and not os.path.exists(os.path.join(mem, "events.jsonl")))

    # 6b. мусорный тир отвергается закрытым множеством
    r = run(mem, "activate", "U-1", "--goal", "x", "--risk-tier", "lowish")
    check("activate-rejects-unknown-risk-tier", r.returncode != 0 and
          "invalid choice" in (r.stdout + r.stderr))

    # 1. activate пишет пару STATE + событие
    r = run(mem, "activate", "U-1", "--goal", "тестовый юнит", "--risk-tier", "low")
    ok_state = False
    ok_evt = False
    if r.returncode == 0:
        st = json.load(open(os.path.join(mem, "STATE.json"), encoding="utf-8"))
        cu = st.get("currentUnit") or {}
        ok_state = (cu.get("id") == "U-1" and cu.get("status") == "in_progress"
                    and cu.get("riskTier") == "low")
        evs = [json.loads(l) for l in open(os.path.join(mem, "events.jsonl"), encoding="utf-8")]
        ok_evt = any(e.get("name") == "U-1" and e.get("decision") == "activated" and e.get("actor") == "harness" for e in evs)
    check("activate-writes-state-and-event", r.returncode == 0 and ok_state and ok_evt,
          f"rc={r.returncode} out={r.stdout!r}")

    # 4. WIP=1
    r = run(mem, "activate", "U-2", "--goal", "второй юнит", "--risk-tier", "low")
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

    # 6c. терминалы флага НЕ требуют (канарейка на переблокировку): выше
    # verified/close/backfill прошли без --risk-tier.
    check("terminals-do-not-require-risk-tier", "verified-ok" not in fails
          and "backfill-ok" not in fails)

with tempfile.TemporaryDirectory() as mem:
    # 6d. объявленный тир доезжает до STATE ровно тем значением
    r = run(mem, "activate", "U-7", "--goal", "medium-юнит", "--risk-tier", "medium")
    cu = {}
    if r.returncode == 0:
        cu = (json.load(open(os.path.join(mem, "STATE.json"), encoding="utf-8"))
              .get("currentUnit") or {})
    check("declared-risk-tier-reaches-state", r.returncode == 0
          and cu.get("riskTier") == "medium", f"rc={r.returncode} cu={cu}")

# 6e. закрытое множество тиров не разъезжается с маршрутами пропорциональности
policy = json.load(open(os.path.join(ROOT, "skills", "_shared",
                                     "PROPORTIONALITY_POLICY.json"), encoding="utf-8"))
src = open(SCRIPT, encoding="utf-8").read()
declared = re.search(r'RISK_TIERS = \(([^)]*)\)', src)
tiers = tuple(re.findall(r'"([a-z]+)"', declared.group(1))) if declared else ()
check("risk-tiers-match-proportionality-policy",
      set(tiers) == set(policy["riskRoutes"]) | {"unknown"},
      f"tiers={tiers} routes={sorted(policy['riskRoutes'])}")

if fails:
    print("FAILED:", " ".join(fails))
    sys.exit(1)
print("verify_unit_log: all ok")
