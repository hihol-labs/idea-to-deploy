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
import importlib.util
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


def load_unit_log():
    spec = importlib.util.spec_from_file_location("unit_log_recovery", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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

# A failed STATE replacement after a canonical terminal append must be
# recoverable only by the exact same CLI request.  The second invocation uses
# the actual argparse/main lifecycle, with save_state faulted once after the
# event append; no synthetic event is inserted by the test.
with tempfile.TemporaryDirectory() as mem:
    module = load_unit_log()
    original_argv = sys.argv[:]
    original_save_state = module.save_state

    def invoke(*args):
        sys.argv = [SCRIPT, *args, "--dir", mem]
        return module.main()

    def fail_once(*_args, **_kwargs):
        raise OSError("simulated STATE replacement failure")

    try:
        check("recovery-activate-verified",
              invoke("activate", "R-verified", "--goal", "recover verified",
                     "--risk-tier", "low") == 0)
        module.save_state = fail_once
        try:
            invoke("verified", "R-verified", "--evidence", "exact proof")
        except OSError:
            failed_verified = True
        else:
            failed_verified = False
        events = [json.loads(line) for line in open(
            os.path.join(mem, "events.jsonl"), encoding="utf-8")]
        state = json.load(open(os.path.join(mem, "STATE.json"), encoding="utf-8"))
        check("verified-failure-lands-one-event-keeps-open-state",
              failed_verified
              and sum(e.get("decision") == "verified" for e in events) == 1
              and state["currentUnit"]["status"] == "in_progress")
        module.save_state = original_save_state
        check("verified-recovery-refuses-different-evidence",
              invoke("verified", "R-verified", "--evidence", "different proof") != 0
              and json.load(open(os.path.join(mem, "STATE.json"), encoding="utf-8"))
              ["currentUnit"]["status"] == "in_progress")
        check("verified-exact-retry-recovers-state",
              invoke("verified", "R-verified", "--evidence", "exact proof") == 0
              and json.load(open(os.path.join(mem, "STATE.json"), encoding="utf-8"))
              ["currentUnit"]["status"] == "verified")
        events = [json.loads(line) for line in open(
            os.path.join(mem, "events.jsonl"), encoding="utf-8")]
        check("verified-recovery-never-duplicates-terminal-event",
              sum(e.get("decision") == "verified" for e in events) == 1)

        check("recovery-activate-close",
              invoke("activate", "R-close", "--goal", "recover close",
                     "--risk-tier", "low") == 0)
        module.save_state = fail_once
        try:
            invoke("close", "R-close", "--outcome", "blocked", "--note", "exact close")
        except OSError:
            failed_close = True
        else:
            failed_close = False
        module.save_state = original_save_state
        check("close-recovery-refuses-different-note",
              invoke("close", "R-close", "--outcome", "blocked",
                     "--note", "different close") != 0
              and json.load(open(os.path.join(mem, "STATE.json"), encoding="utf-8"))
              ["currentUnit"]["status"] == "in_progress")
        check("close-exact-retry-recovers-state",
              failed_close
              and invoke("close", "R-close", "--outcome", "blocked",
                         "--note", "exact close") == 0
              and json.load(open(os.path.join(mem, "STATE.json"), encoding="utf-8"))
              ["currentUnit"]["status"] == "blocked")
        events = [json.loads(line) for line in open(
            os.path.join(mem, "events.jsonl"), encoding="utf-8")]
        check("close-recovery-never-duplicates-terminal-event",
              sum(e.get("decision") == "blocked" for e in events) == 1)

        # A unique old terminal is not recoverable once a later activation
        # epoch has landed its own terminal.  The stale retry must not project
        # the old verified status over the newer open STATE.
        check("recovery-activate-stale-epoch",
              invoke("activate", "R-stale", "--goal", "old epoch",
                     "--risk-tier", "low") == 0)
        module.save_state = fail_once
        try:
            invoke("verified", "R-stale", "--evidence", "old proof")
        except OSError:
            stale_verified_failed = True
        else:
            stale_verified_failed = False
        module.save_state = original_save_state
        check("recovery-activate-newer-epoch",
              stale_verified_failed
              and invoke("activate", "R-stale", "--goal", "new epoch",
                         "--risk-tier", "low") == 0)
        module.save_state = fail_once
        try:
            invoke("close", "R-stale", "--outcome", "blocked", "--note", "new close")
        except OSError:
            stale_close_failed = True
        else:
            stale_close_failed = False
        module.save_state = original_save_state
        check("stale-old-terminal-retry-refused",
              stale_close_failed
              and invoke("verified", "R-stale", "--evidence", "old proof") != 0
              and json.load(open(os.path.join(mem, "STATE.json"), encoding="utf-8"))
              ["currentUnit"]["status"] == "in_progress")
        check("latest-terminal-retry-recovers-current-epoch",
              invoke("close", "R-stale", "--outcome", "blocked", "--note", "new close") == 0
              and json.load(open(os.path.join(mem, "STATE.json"), encoding="utf-8"))
              ["currentUnit"]["status"] == "blocked")

        check("partial-append-activation",
              invoke("activate", "R-partial", "--goal", "partial terminal",
                     "--risk-tier", "low") == 0)
        original_append = module.durable_append_bytes

        def partial_append(path, _content):
            with open(path, "ab") as handle:
                handle.write(b'{"type":"unit"')
                handle.flush()
            raise OSError("simulated partial event append")

        module.durable_append_bytes = partial_append
        try:
            invoke("verified", "R-partial", "--evidence", "partial proof")
        except OSError:
            partial_failed = True
        else:
            partial_failed = False
        finally:
            module.durable_append_bytes = original_append
        state = json.load(open(os.path.join(mem, "STATE.json"), encoding="utf-8"))
        events_path = os.path.join(mem, "events.jsonl")
        partial_bytes = open(events_path, "rb").read()
        try:
            invoke("verified", "R-partial", "--evidence", "partial proof")
        except RuntimeError:
            partial_retry_refused = True
        else:
            partial_retry_refused = False
        final_bytes = open(events_path, "rb").read()
        check("partial-append-retry-preserves-tail-and-open-state",
              partial_failed
              and partial_retry_refused
              and not partial_bytes.endswith(b"\n")
              and final_bytes == partial_bytes
              and state["currentUnit"]["status"] == "in_progress"
              and b'"name": "R-partial", "decision": "verified"' not in final_bytes,
              repr((partial_failed, partial_retry_refused,
                    partial_bytes.endswith(b"\n"), final_bytes == partial_bytes,
                    state["currentUnit"]["status"], final_bytes[-80:])))
    finally:
        module.save_state = original_save_state
        sys.argv = original_argv

if fails:
    print("FAILED:", " ".join(fails))
    sys.exit(1)
print("verify_unit_log: all ok")
