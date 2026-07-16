#!/usr/bin/env python3
"""Functional tests for hooks/verdict-contract.sh (v1.51.0).

The hook is a SubagentStop validator: it must BLOCK (root {"decision":"block"})
when the subagent's final message DECLARES a review verdict in prose but carries
no valid vendor-neutral JSON verdict block, and stay SILENT in every other case.
A false block costs a whole extra subagent turn, so the negatives matter as much
as the positives. Regression pins:
  * a message with a valid ```json {verdict, findings} block is NEVER blocked;
  * an inline (un-fenced) valid verdict object also satisfies the contract;
  * a non-review final ("all 12 tests passed", bare "PASSED") is NOT a verdict
    declaration → silent (test-generator/researcher must pass through);
  * an invalid JSON block (bad verdict value / findings not a list) does NOT
    satisfy the contract → still blocks when prose verdict present;
  * stop_hook_active / kill-switch / missing transcript / garbage → silent;
  * ping cap: at most ITD_VERDICT_MAX_PINGS blocks per subagent transcript.

Both transcript layouts observed in the wild are covered (agent-direct /
main-fallback), same as verify_narration_final.py.

Self-contained, stdlib only, cross-platform. Run:
  python3 tests/verify_verdict_contract.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks" / "verdict-contract.sh"
PY = sys.executable

PASSED, FAILED = 0, 0
TMPDIRS: list[Path] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print("PASS  " + name)
    else:
        FAILED += 1
        print("FAIL  " + name + (("  — " + detail) if detail else ""))


def assistant_entry(text: str, sidechain: bool = True) -> str:
    return json.dumps({
        "type": "assistant",
        "isSidechain": sidechain,
        "message": {"role": "assistant",
                    "content": [{"type": "text", "text": text}]},
    }, ensure_ascii=False)


def tool_use_entry() -> str:
    return json.dumps({
        "type": "assistant",
        "isSidechain": False,
        "message": {"role": "assistant",
                    "content": [{"type": "tool_use", "id": "t1",
                                 "name": "Read", "input": {}}]},
    })


def make_layout(final_text: str, layout: str) -> dict:
    """Create transcript files; return the hook payload."""
    d = Path(tempfile.mkdtemp(prefix="vc51-"))
    TMPDIRS.append(d)
    sid = "s-" + uuid.uuid4().hex[:8]
    agent_dir = d / sid / "subagents"
    agent_dir.mkdir(parents=True)
    agent = agent_dir / ("agent-" + uuid.uuid4().hex[:10] + ".jsonl")
    lines = [
        json.dumps({"type": "user", "isSidechain": True,
                    "message": {"role": "user", "content": "task"}}),
        assistant_entry("Intermediate progress message.", sidechain=True),
        assistant_entry(final_text, sidechain=True),
    ]
    agent.write_text("\n".join(lines) + "\n", encoding="utf-8")
    main = d / (sid + ".jsonl")
    main.write_text("\n".join([
        json.dumps({"type": "user", "isSidechain": False,
                    "message": {"role": "user", "content": "hi"}}),
        tool_use_entry(),
    ]) + "\n", encoding="utf-8")
    tp = agent if layout == "agent-direct" else main
    return {"session_id": sid, "transcript_path": str(tp),
            "stop_hook_active": False, "hook_event_name": "SubagentStop"}


# v1.86.0: все запуски хука по умолчанию изолируются в собственный tempdir —
# иначе valid-verdict кейсы писали бы review-findings в РЕАЛЬНЫЙ системный
# /tmp (persist_findings fallback), и retro-скан на живой машине майнил бы
# фикстурные находки. Один общий каталог на прогон: ping-cap сентинелы
# должны разделяться между вызовами.
ISO_TMP = Path(tempfile.mkdtemp(prefix="vc-iso-shared-"))
TMPDIRS.append(ISO_TMP)


def run_hook(payload, extra_env: dict | None = None,
             raw_stdin: str | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONUTF8": "1", "TMPDIR": str(ISO_TMP),
           "TEMP": str(ISO_TMP), "TMP": str(ISO_TMP)}
    env.pop("ITD_VERDICT_CONTRACT", None)
    env.pop("ITD_VERDICT_MAX_PINGS", None)
    if extra_env:
        env.update(extra_env)
    data = raw_stdin if raw_stdin is not None else json.dumps(payload)
    return subprocess.run([PY, str(HOOK)], input=data, capture_output=True,
                          encoding="utf-8", errors="replace", env=env,
                          timeout=60)


def blocked(proc: subprocess.CompletedProcess) -> bool:
    if not proc.stdout.strip():
        return False
    try:
        out = json.loads(proc.stdout)
    except Exception:
        return False
    return out.get("decision") == "block" and bool(out.get("reason"))


def make_review_repo() -> Path:
    """Git fixture with the exact-context producers required by the cache."""
    repo = Path(tempfile.mkdtemp(prefix="vc-review-cache-"))
    TMPDIRS.append(repo)

    def git(*args: str) -> None:
        proc = subprocess.run(["git", *args], cwd=str(repo), capture_output=True,
                              text=True, timeout=20)
        if proc.returncode:
            raise RuntimeError(proc.stderr)

    git("init", "-q")
    git("config", "user.email", "verdict@example.test")
    git("config", "user.name", "Verdict Test")
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    git("add", "base.txt")
    git("commit", "-qm", "base")
    for index in range(3):
        (repo / f"change-{index}.txt").write_text("change\n", encoding="utf-8")
        git("add", f"change-{index}.txt")
    (repo / ".itd").mkdir()
    (repo / ".itd" / "SCOPE_LOCK.md").write_text("# scope\n", encoding="utf-8")
    (repo / ".itd" / "ACCEPTANCE_CONTRACT.json").write_text(
        "{}\n", encoding="utf-8")
    (repo / ".itd-memory").mkdir()
    (repo / ".itd-memory" / "GOAL.json").write_text(json.dumps({
        "version": 1, "goal": "fixture", "status": "active",
        "currentUnitId": "V-1", "units": [{
            "id": "V-1", "status": "in_progress", "riskTier": "medium",
            "criterion": "verdict", "verificationCommand": "true",
        }],
    }), encoding="utf-8")
    return repo


# --- fixtures ---------------------------------------------------------------
JSON_OK = ('```json\n{"verdict": "PASSED_WITH_WARNINGS", "findings": '
           '[{"severity": "important", "confidence": "high", '
           '"file": "hooks/x.sh", "line": 10, "summary": "y"}], '
           '"unverified": []}\n```')
VERDICT_NO_JSON_EN = ("## Review findings\n\n- Important: X\n\n"
                      "FINAL STATUS: PASSED_WITH_WARNINGS (1 Important).")
VERDICT_NO_JSON_RU = ("Разобрал дифф, одно замечание.\n\n"
                      "Вердикт: BLOCKED — Critical в hooks/y.sh:5.")
VERDICT_PWW_TOKEN = ("Резюме ревью ниже.\n\nPASSED_WITH_WARNINGS — "
                     "все Critical зелёные, 2 Important.")
VERDICT_WITH_JSON = ("## Review findings\n\nВердикт: PASSED_WITH_WARNINGS.\n\n"
                     + JSON_OK)
VERDICT_WITH_INLINE_JSON = ('FINAL STATUS: BLOCKED\n\nМашиночитаемо: '
                            '{"verdict": "BLOCKED", "findings": '
                            '[{"severity": "critical"}]} — конец.')
NON_REVIEW_TESTS = ("Сгенерировал 12 юнит-тестов, прогнал — all 12 tests "
                    "passed, покрытие 94%.")
NON_REVIEW_BARE = ("Задача выполнена. Итоговое состояние: PASSED. "
                   "Ничего не сломано.")
BAD_VERDICT_VALUE = ('FINAL STATUS: PASSED\n\n```json\n{"verdict": "MAYBE", '
                     '"findings": []}\n```')
BAD_FINDINGS_SHAPE = ('Вердикт: PASSED\n\n```json\n{"verdict": "PASSED", '
                      '"findings": "none"}\n```')


def main() -> int:
    # --- positives: prose verdict, no valid JSON block → block --------------
    check("EN FINAL STATUS w/o JSON blocks (agent-direct)",
          blocked(run_hook(make_layout(VERDICT_NO_JSON_EN, "agent-direct"))))
    check("RU Вердикт: w/o JSON blocks (main-fallback)",
          blocked(run_hook(make_layout(VERDICT_NO_JSON_RU, "main-fallback"))))
    check("compound token PASSED_WITH_WARNINGS w/o JSON blocks",
          blocked(run_hook(make_layout(VERDICT_PWW_TOKEN, "agent-direct"))))
    check("invalid verdict value in JSON block still blocks",
          blocked(run_hook(make_layout(BAD_VERDICT_VALUE, "agent-direct"))))
    check("findings not a list in JSON block still blocks",
          blocked(run_hook(make_layout(BAD_FINDINGS_SHAPE, "agent-direct"))))

    # --- negatives: valid contract or non-review → silent ------------------
    p = run_hook(make_layout(VERDICT_WITH_JSON, "agent-direct"))
    check("verdict + valid fenced JSON block stays silent", not blocked(p),
          p.stdout[:200])
    p = run_hook(make_layout(VERDICT_WITH_INLINE_JSON, "agent-direct"))
    check("verdict + valid inline JSON object stays silent", not blocked(p),
          p.stdout[:200])
    p = run_hook(make_layout(NON_REVIEW_TESTS, "agent-direct"))
    check("non-review 'all tests passed' stays silent", not blocked(p),
          p.stdout[:200])
    p = run_hook(make_layout(NON_REVIEW_BARE, "agent-direct"))
    check("bare 'PASSED' (no declaration form) stays silent", not blocked(p),
          p.stdout[:200])

    # --- guards -------------------------------------------------------------
    payload = make_layout(VERDICT_NO_JSON_EN, "agent-direct")
    payload["stop_hook_active"] = True
    check("stop_hook_active=true stays silent (loop guard)",
          not blocked(run_hook(payload)))
    check("kill switch ITD_VERDICT_CONTRACT=0 stays silent",
          not blocked(run_hook(make_layout(VERDICT_NO_JSON_EN, "agent-direct"),
                               extra_env={"ITD_VERDICT_CONTRACT": "0"})))
    p = run_hook({"session_id": "x", "stop_hook_active": False,
                  "transcript_path": str(Path(tempfile.gettempdir())
                                         / "vc51-no-such.jsonl")})
    check("missing transcript stays silent (fail-open)",
          not blocked(p) and p.returncode == 0, p.stdout[:200])
    p = run_hook(None, raw_stdin="not a json {")
    check("garbage stdin stays silent, exit 0 (fail-open)",
          not blocked(p) and p.returncode == 0,
          "rc=%s %s" % (p.returncode, p.stdout[:100]))

    # --- ping cap -----------------------------------------------------------
    payload = make_layout(VERDICT_NO_JSON_RU, "agent-direct")
    r1 = run_hook(payload)
    r2 = run_hook(payload)
    r3 = run_hook(payload)
    check("ping cap: 1st and 2nd blocked, 3rd passes through",
          blocked(r1) and blocked(r2) and not blocked(r3),
          "1=%s 2=%s 3=%s" % (blocked(r1), blocked(r2), blocked(r3)))
    payload = make_layout(VERDICT_NO_JSON_RU, "agent-direct")
    p1 = run_hook(payload, extra_env={"ITD_VERDICT_MAX_PINGS": "1"})
    p2 = run_hook(payload, extra_env={"ITD_VERDICT_MAX_PINGS": "1"})
    check("ITD_VERDICT_MAX_PINGS=1 honored", blocked(p1) and not blocked(p2),
          "1=%s 2=%s" % (blocked(p1), blocked(p2)))

    # --- v1.86.0: review-findings ledger (persist on valid verdict) ---------
    json_cat = ('```json\n{"verdict": "PASSED_WITH_WARNINGS", "findings": '
                '[{"severity": "important", "confidence": "high", '
                '"category": "assumed-producer-shape", '
                '"file": "hooks/x.sh", "line": 10, "summary": "y"}], '
                '"unverified": []}\n```')
    payload = make_layout("Вердикт: PASSED_WITH_WARNINGS.\n\n" + json_cat,
                          "agent-direct")
    proj = Path(tempfile.mkdtemp(prefix="vc-proj-"))
    TMPDIRS.append(proj)
    (proj / ".itd-memory").mkdir()
    iso = Path(tempfile.mkdtemp(prefix="vc-iso-"))  # TMPDIR → изоляция дедуп-
    TMPDIRS.append(iso)                             # сентинелов между кейсами
    payload["cwd"] = str(proj)
    p1 = run_hook(payload, extra_env={"TMPDIR": str(iso)})
    ledger = proj / ".itd-memory" / "review-findings.jsonl"
    check("valid verdict stays silent AND persists to project ledger",
          not blocked(p1) and ledger.is_file(),
          (p1.stdout or "") + (p1.stderr or ""))
    rec = (json.loads(ledger.read_text(encoding="utf-8").splitlines()[0])
           if ledger.is_file() else {})
    check("ledger record mirrors producer shape (verdict/category/file)",
          rec.get("verdict") == "PASSED_WITH_WARNINGS"
          and (rec.get("findings") or [{}])[0].get("category")
          == "assumed-producer-shape"
          and (rec.get("findings") or [{}])[0].get("file") == "hooks/x.sh",
          json.dumps(rec, ensure_ascii=False)[:200])
    p2 = run_hook(payload, extra_env={"TMPDIR": str(iso)})
    check("same final does not duplicate the ledger record (dedupe sentinel)",
          not blocked(p2) and ledger.is_file()
          and len(ledger.read_text(encoding="utf-8").splitlines()) == 1,
          str(ledger.read_text(encoding="utf-8").count("\n")
              if ledger.is_file() else -1))
    # fallback: cwd без .itd-memory → глобальный tmp-леджер
    payload = make_layout(VERDICT_WITH_JSON, "agent-direct")
    noitd = Path(tempfile.mkdtemp(prefix="vc-noitd-"))
    TMPDIRS.append(noitd)
    iso2 = Path(tempfile.mkdtemp(prefix="vc-iso2-"))
    TMPDIRS.append(iso2)
    payload["cwd"] = str(noitd)
    p3 = run_hook(payload, extra_env={"TMPDIR": str(iso2)})
    check("without .itd-memory findings go to the global tmp ledger",
          not blocked(p3)
          and (iso2 / "claude-review-findings.jsonl").is_file(),
          (p3.stdout or "") + (p3.stderr or ""))
    # блок-ветка (невалидный вердикт) леджер НЕ пишет
    payload = make_layout(VERDICT_NO_JSON_EN, "agent-direct")
    proj2 = Path(tempfile.mkdtemp(prefix="vc-proj2-"))
    TMPDIRS.append(proj2)
    (proj2 / ".itd-memory").mkdir()
    payload["cwd"] = str(proj2)
    run_hook(payload)
    check("blocked (no valid JSON) writes nothing to the ledger",
          not (proj2 / ".itd-memory" / "review-findings.jsonl").exists())

    # --- PE5-013: untrusted SubagentStop cannot mint exact cache evidence ---
    review_repo = make_review_repo()
    passed_text = ('FINAL STATUS: PASSED\n\n```json\n'
                   '{"verdict":"PASSED","findings":[],"unverified":[]}\n```')
    payload = make_layout(passed_text, "agent-direct")
    payload["cwd"] = str(review_repo)
    passed_proc = run_hook(payload)
    cache_path = review_repo / ".itd-memory" / "review-cache.json"
    check("valid arbitrary SubagentStop cannot mint general review cache",
          not blocked(passed_proc) and not cache_path.exists(),
          (passed_proc.stdout or "") + (passed_proc.stderr or ""))

    blocked_text = ('FINAL STATUS: BLOCKED\n\n```json\n'
                    '{"verdict":"BLOCKED","findings":[],"unverified":[]}\n```')
    payload = make_layout(blocked_text, "agent-direct")
    payload["cwd"] = str(review_repo)
    blocked_proc = run_hook(payload)
    check("review-shaped BLOCKED SubagentStop also cannot mint cache",
          not blocked(blocked_proc) and not cache_path.exists(),
          (blocked_proc.stdout or "") + (blocked_proc.stderr or ""))

    # --- cleanup ------------------------------------------------------------
    for d in TMPDIRS:
        shutil.rmtree(d, ignore_errors=True)

    print("\n%d passed, %d failed" % (PASSED, FAILED))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
