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
import time
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
                '"category": "correctness", '
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
          == "correctness"
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
    payload = make_layout("Вердикт: PASSED_WITH_WARNINGS.\n\n" + json_cat,
                          "agent-direct")
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

    # --- PILOT-P01: закрытые словари схемы вердикта (RSI v4 §5) -------------
    TAX = json.loads((ROOT / "skills" / "_shared"
                      / "VERDICT_TAXONOMY.json").read_text(encoding="utf-8"))
    CATS = TAX["category"]["values"]

    def fresh_project():
        proj = Path(tempfile.mkdtemp(prefix="vc-pilot-"))
        TMPDIRS.append(proj)
        (proj / ".itd-memory").mkdir()
        iso = Path(tempfile.mkdtemp(prefix="vc-pilot-iso-"))
        TMPDIRS.append(iso)
        return proj, iso

    def write_verdict(proj, iso, findings_json, extra_env=None):
        text = ("Вердикт: PASSED_WITH_WARNINGS.\n\n```json\n"
                '{"verdict": "PASSED_WITH_WARNINGS", "findings": '
                + findings_json + ', "unverified": []}\n```')
        payload = make_layout(text, "agent-direct")
        payload["cwd"] = str(proj)
        env = {"TMPDIR": str(iso)}
        env.update(extra_env or {})
        return run_hook(payload, extra_env=env)

    def read_counter(proj):
        return _tax_mod.rejected_summary("", directory=proj / ".itd-memory")

    def fresh_project_reuse(proj):
        iso = Path(tempfile.mkdtemp(prefix="vc-pilot-iso2-"))
        TMPDIRS.append(iso)
        return proj, iso

    def ledger_lines(proj, name):
        f = proj / ".itd-memory" / name
        return (f.read_text(encoding="utf-8").splitlines()
                if f.is_file() else [])

    sys.path.insert(0, str(ROOT / "skills" / "_shared"))
    import itd_verdict_taxonomy as _tax_mod

    VALID_F = ('[{"severity": "important", "category": "correctness", '
               '"file": "a.py", "summary": "s"}]')

    proj, iso = fresh_project()
    write_verdict(proj, iso, VALID_F)
    rec = json.loads(ledger_lines(proj, "review-findings.jsonl")[0])
    check("accepted record carries taxonomyVersion + source provenance",
          rec.get("taxonomyVersion") == TAX["taxonomyVersion"]
          and rec.get("source") == "subagent-verdict"
          and bool(str(rec.get("lineage") or "").strip()),
          json.dumps(rec, ensure_ascii=False)[:200])

    # невалидная category: канонический леджер не растёт, запись не теряется
    proj, iso = fresh_project()
    r = write_verdict(proj, iso, '[{"severity": "important", '
                      '"category": "made-up-class", "file": "a.py", '
                      '"line": 7, "confidence": "high", "summary": "s"}]')
    rejected = ledger_lines(proj, "review-findings-rejected.jsonl")
    entry = json.loads(rejected[0]) if rejected else {}
    check("invalid category is rejected on write, not admitted",
          not blocked(r) and not ledger_lines(proj, "review-findings.jsonl")
          and len(rejected) == 1,
          "canon=%d rejected=%d" % (
              len(ledger_lines(proj, "review-findings.jsonl")), len(rejected)))
    check("the quarantined record keeps the fields the reviewer submitted",
          (entry.get("record", {}).get("findings") or [{}])[0].get("line") == 7
          and (entry.get("record", {}).get("findings") or [{}])[0]
          .get("confidence") == "high",
          json.dumps(entry, ensure_ascii=False)[:220])
    check("rejected record is kept whole with a machine-readable reason",
          any(x.startswith("category[0]") for x in entry.get("reasons", []))
          and entry.get("record", {}).get("findings", [{}])[0].get("summary") == "s",
          json.dumps(entry, ensure_ascii=False)[:220])
    counter = proj / ".itd-memory" / "review-findings-rejected.count.jsonl"
    cdata = read_counter(proj)
    check("rejection counter records the total and the reason class",
          counter.is_file() and cdata.get("total") == 1
          and cdata.get("byReason", {}).get("category") == 1,
          json.dumps(cdata, ensure_ascii=False)[:200])
    # Форма счётчика без read-modify-write. Гарантия заявляет ОДНОВРЕМЕННЫХ
    # писателей, значит проверка обязана их инстанцировать: N процессов
    # стартуют по общему барьеру и пишут через тот же модуль.
    conc = Path(tempfile.mkdtemp(prefix="vc-conc-"))
    TMPDIRS.append(conc)
    (conc / ".itd-memory").mkdir()
    writers, rounds = 8, 12
    worker = (
        "import sys, time\n"
        "sys.path.insert(0, %r)\n"
        "import itd_verdict_taxonomy as t\n"
        "start = float(sys.argv[2])\n"
        "while time.time() < start:\n"
        "    pass\n"
        "for i in range(%d):\n"
        "    t.bump_rejected_counter('', ['category[0]:%%d' %% i,],\n"
        "                            directory=%r)\n"
        % (str(ROOT / "skills" / "_shared"), rounds,
           str(conc / ".itd-memory")))
    barrier = time.time() + 1.5
    procs = [subprocess.Popen([PY, "-c", worker, str(n), str(barrier)])
             for n in range(writers)]
    for pr in procs:
        pr.wait(timeout=60)
    total = read_counter(conc).get("total")
    check("concurrent writers cannot lose a rejection (real parallel writers)",
          total == writers * rounds,
          "expected %d, got %r" % (writers * rounds, total))

    # severity вне словаря
    proj, iso = fresh_project()
    write_verdict(proj, iso, '[{"severity": "blocker", "category": '
                  '"correctness", "file": "a.py", "summary": "s"}]')
    check("invalid severity is rejected on write",
          not ledger_lines(proj, "review-findings.jsonl")
          and len(ledger_lines(proj, "review-findings-rejected.jsonl")) == 1)

    # unspecified разрешена импортёру, но НЕ ревьюеру: он всегда градуирует сам
    proj, iso = fresh_project()
    write_verdict(proj, iso, '[{"severity": "unspecified", "category": '
                  '"correctness", "file": "a.py", "summary": "s"}]')
    check("severity unspecified is invalid for a subagent verdict",
          not ledger_lines(proj, "review-findings.jsonl")
          and len(ledger_lines(proj, "review-findings-rejected.jsonl")) == 1)

    # словарь недоступен -> карантин с явной причиной, а не тихий пропуск
    proj, iso = fresh_project()
    r = write_verdict(proj, iso, VALID_F,
                      {"ITD_VERDICT_TAXONOMY": str(proj / "nope.json")})
    rejected = ledger_lines(proj, "review-findings-rejected.jsonl")
    check("unavailable taxonomy quarantines the record and never blocks",
          not blocked(r) and r.returncode == 0
          and not ledger_lines(proj, "review-findings.jsonl")
          and len(rejected) == 1
          and "taxonomy-unavailable" in rejected[0])

    # модуль словарей не загрузился -> запись всё равно не теряется
    proj, iso = fresh_project()
    r = write_verdict(proj, iso, VALID_F,
                      {"ITD_VERDICT_TAXONOMY_MODULE": str(proj / "nope.py")})
    check("unloadable taxonomy module still quarantines instead of dropping",
          not blocked(r) and r.returncode == 0
          and not ledger_lines(proj, "review-findings.jsonl")
          and len(ledger_lines(proj, "review-findings-rejected.jsonl")) == 1)
    # несчитанное отклонение — тот же молчаливый дроп, только с копией
    check("the emergency quarantine path counts its rejection too",
          read_counter(proj).get("total") == 1
          and read_counter(proj).get("byReason", {}).get(
              "taxonomy-unavailable") == 1,
          json.dumps(read_counter(proj), ensure_ascii=False)[:200])

    # испорченная находка не отфильтровывается в «чистую» пустую запись
    proj, iso = fresh_project()
    r = write_verdict(proj, iso, '["bad", {"severity": "minor", '
                      '"category": "correctness", "file": "a.py", '
                      '"summary": "s"}]')
    rejected = ledger_lines(proj, "review-findings-rejected.jsonl")
    check("a non-object finding cannot be filtered into a clean record",
          not blocked(r) and not ledger_lines(proj, "review-findings.jsonl")
          and len(rejected) == 1 and "not-an-object" in rejected[0],
          (rejected[0][:160] if rejected else "no quarantine"))

    # карантин обязан хранить ровно то, что пришло, включая чужой штамп версии
    stamp_dir = Path(tempfile.mkdtemp(prefix="vc-stamp-"))
    TMPDIRS.append(stamp_dir)
    incoming = {"source": "subagent-verdict", "lineage": "L",
                "taxonomyVersion": 99,
                "findings": [{"severity": "minor", "category": "nope"}]}
    accepted, reasons = _tax_mod.admit("", incoming, directory=stamp_dir)
    kept = json.loads((stamp_dir / "review-findings-rejected.jsonl")
                      .read_text(encoding="utf-8").splitlines()[0])["record"]
    check("a rejected record keeps its own taxonomyVersion, unaltered",
          accepted is False and kept.get("taxonomyVersion") == 99
          and any(r.startswith("taxonomyVersion:") for r in reasons),
          json.dumps(kept, ensure_ascii=False)[:200])

    # словарь не может направить карантин в канонический леджер
    proj, iso = fresh_project()
    aimed = proj / "aimed-taxonomy.json"
    aimed.write_text(json.dumps({**TAX, "rejection": {
        **TAX["rejection"], "file": "review-findings.jsonl"}}),
        encoding="utf-8")
    write_verdict(proj, iso, VALID_F, {"ITD_VERDICT_TAXONOMY": str(aimed)})
    check("a taxonomy cannot aim the quarantine at the canonical ledger",
          not ledger_lines(proj, "review-findings.jsonl")
          and len(ledger_lines(proj, "review-findings-rejected.jsonl")) == 1)

    # переполнение канонического леджера РОТИРУЕТ его, а не стирает легаси
    rot = Path(tempfile.mkdtemp(prefix="vc-rot-"))
    TMPDIRS.append(rot)
    legacy_line = json.dumps({"ts": "old", "project": "p", "verdict": "BLOCKED",
                              "findings": [{"severity": "", "category": None,
                                            "file": "legacy.py",
                                            "summary": "L" * 100}]})
    (rot / "review-findings.jsonl").write_text(legacy_line + "\n",
                                               encoding="utf-8")
    big = {"source": "subagent-verdict", "lineage": "L",
           "findings": [{"severity": "minor", "category": "correctness",
                         "summary": "B" * 500}]}
    for n in range(300):
        _tax_mod.admit("", dict(big, lineage="n-%d" % n), directory=rot)
    rotated = rot / "review-findings.jsonl.1"
    generations = sorted(rot.glob("review-findings.jsonl.[0-9]*"))
    kept = "".join(g.read_text(encoding="utf-8") for g in generations) \
        + (rot / "review-findings.jsonl").read_text(encoding="utf-8")
    check("an overflowing canonical ledger rotates instead of erasing legacy",
          bool(generations) and legacy_line in kept
          and kept.count("\"lineage\": \"n-") == 300,
          "generations=%d kept=%d" % (len(generations), kept.count("n-")))

    # ротация под ОДНОВРЕМЕННЫМИ писателями не теряет принятую запись
    conc2 = Path(tempfile.mkdtemp(prefix="vc-rot-conc-"))
    TMPDIRS.append(conc2)
    rot_worker = (
        "import sys, time\n"
        "sys.path.insert(0, %r)\n"
        "import itd_verdict_taxonomy as t\n"
        "start = float(sys.argv[2])\n"
        "while time.time() < start:\n"
        "    pass\n"
        "for i in range(40):\n"
        "    t.admit('', {'source': 'subagent-verdict',\n"
        "                 'lineage': '%%s-%%d' %% (sys.argv[1], i),\n"
        "                 'findings': [{'severity': 'minor',\n"
        "                               'category': 'correctness',\n"
        "                               'summary': 'X' * 700}]},\n"
        "             directory=%r)\n"
        % (str(ROOT / "skills" / "_shared"), str(conc2)))
    barrier2 = time.time() + 1.5
    procs2 = [subprocess.Popen([PY, "-c", rot_worker, "w%d" % n, str(barrier2)])
              for n in range(6)]
    for pr in procs2:
        pr.wait(timeout=120)
    everything = "".join(
        g.read_text(encoding="utf-8")
        for g in sorted(conc2.glob("review-findings.jsonl*")))
    check("rotation under concurrent writers loses no accepted record",
          everything.count('"lineage": "w') == 6 * 40,
          "kept=%d expected=%d" % (everything.count('"lineage": "w'), 240))

    # структурно битый, но парсящийся словарь — тоже «валидировать нечем»
    proj, iso = fresh_project()
    broken = proj / "broken-taxonomy.json"
    broken.write_text(json.dumps({**TAX, "category": {
        **TAX["category"], "bySource": ["not", "a", "mapping"]}}),
        encoding="utf-8")
    r = write_verdict(proj, iso, VALID_F,
                      {"ITD_VERDICT_TAXONOMY": str(broken)})
    rejected = ledger_lines(proj, "review-findings-rejected.jsonl")
    check("structurally corrupt taxonomy quarantines instead of dropping",
          not blocked(r) and not ledger_lines(proj, "review-findings.jsonl")
          and len(rejected) == 1 and "taxonomy-unavailable" in rejected[0],
          (rejected[0][:160] if rejected else "no quarantine"))

    # словарь, расширяющий сам себя через bySource, не является валидным
    proj, iso = fresh_project()
    widened = proj / "widened-taxonomy.json"
    widened.write_text(json.dumps({**TAX, "severity": {
        **TAX["severity"], "bySource": {
            **TAX["severity"]["bySource"],
            "subagent-verdict": ["critical", "blocker"]}}}), encoding="utf-8")
    r = write_verdict(proj, iso, VALID_F,
                      {"ITD_VERDICT_TAXONOMY": str(widened)})
    rejected = ledger_lines(proj, "review-findings-rejected.jsonl")
    check("a bySource entry cannot widen the closed vocabulary",
          not ledger_lines(proj, "review-findings.jsonl")
          and len(rejected) == 1 and "taxonomy-unavailable" in rejected[0],
          (rejected[0][:160] if rejected else "no quarantine"))

    # послабление externalOnly не может протечь в словарь ревьюера
    proj, iso = fresh_project()
    leaked = proj / "leaked-taxonomy.json"
    leaked.write_text(json.dumps({**TAX, "category": {
        **TAX["category"],
        "externalOnly": TAX["category"]["externalOnly"] + ["evil"],
        "bySource": {**TAX["category"]["bySource"],
                     "subagent-verdict":
                         TAX["category"]["bySource"]["subagent-verdict"]
                         + ["evil"]}}}), encoding="utf-8")
    r = write_verdict(proj, iso, '[{"severity": "minor", "category": "evil", '
                      '"file": "a.py", "summary": "s"}]',
                      {"ITD_VERDICT_TAXONOMY": str(leaked)})
    check("externalOnly cannot widen the reviewer's own vocabulary",
          not ledger_lines(proj, "review-findings.jsonl")
          and len(ledger_lines(proj, "review-findings-rejected.jsonl")) == 1)

    # карантин — улика: он не имеет права затирать собственные старые записи
    quar_dir = Path(tempfile.mkdtemp(prefix="vc-quar-"))
    TMPDIRS.append(quar_dir)
    first = {"source": "subagent-verdict", "lineage": "first-record",
             "findings": [{"severity": "minor", "category": "made-up",
                           "summary": "F" * 400}]}
    for n in range(400):
        _tax_mod.admit("", dict(first, lineage="rec-%d" % n),
                       directory=quar_dir)
    qtext = (quar_dir / "review-findings-rejected.jsonl").read_text(
        encoding="utf-8")
    check("the quarantine never discards the evidence it exists to keep",
          "rec-0" in qtext and "rec-399" in qtext
          and len(qtext.splitlines()) == 400
          and _tax_mod.rejected_summary("", directory=quar_dir)["total"] == 400,
          "lines=%d size=%d" % (len(qtext.splitlines()), len(qtext)))

    # инвариант воронки: неожиданная ошибка внутри admit не теряет запись
    admit_dir = Path(tempfile.mkdtemp(prefix="vc-admit-"))
    TMPDIRS.append(admit_dir)
    hostile = {"source": "subagent-verdict", "lineage": "x",
               "findings": [{"severity": "minor", "category": "correctness"}]}
    accepted, reasons = _tax_mod.admit(
        "", hostile, {"taxonomyVersion": 1}, directory=admit_dir)
    quarantined = (admit_dir / "review-findings-rejected.jsonl")
    check("an unexpected error inside admit names a reason and quarantines",
          accepted is False
          and any(r.startswith("admit-error:") for r in reasons)
          and quarantined.is_file(),
          "%r / %s" % (reasons, quarantined.exists()))

    # Не-список findings не доезжает до писателя: контракт вердикта его не
    # признаёт, поэтому в канонический леджер он попасть не может ни при каком
    # состоянии словаря (писатель при этом ничего не приводит к пустому списку).
    proj, iso = fresh_project()
    text = ("Вердикт: PASSED_WITH_WARNINGS.\n\n```json\n"
            '{"verdict": "PASSED_WITH_WARNINGS", "findings": "none", '
            '"unverified": []}\n```')
    payload = make_layout(text, "agent-direct")
    payload["cwd"] = str(proj)
    r = run_hook(payload, extra_env={"TMPDIR": str(iso)})
    check("a non-list findings verdict is blocked and never reaches the ledger",
          blocked(r) and not ledger_lines(proj, "review-findings.jsonl")
          and not ledger_lines(proj, "review-findings-rejected.jsonl"),
          (r.stdout or "")[:160])

    # forward-only: легаси-строки без taxonomyVersion не переписываются
    proj, iso = fresh_project()
    legacy = ('{"ts": "2026-01-01T00:00:00+00:00", "project": "x", '
              '"verdict": "BLOCKED", "findings": [{"severity": "", '
              '"category": null, "file": "old.py", "summary": "legacy"}]}')
    canon = proj / ".itd-memory" / "review-findings.jsonl"
    canon.write_text(legacy + "\n", encoding="utf-8")
    write_verdict(proj, iso, VALID_F)
    lines = ledger_lines(proj, "review-findings.jsonl")
    check("legacy records are normalized on read, never rewritten on write",
          len(lines) == 2 and lines[0] == legacy)

    # подсказка продюсеру называет словарь — иначе category снова придёт null
    proj, iso = fresh_project()
    payload = make_layout(VERDICT_NO_JSON_RU, "agent-direct")
    payload["cwd"] = str(proj)
    br = run_hook(payload, extra_env={"TMPDIR": str(iso)})
    reason = ""
    try:
        reason = json.loads(br.stdout or "{}").get("reason", "")
    except Exception:
        pass
    check("block reason names category and the whole closed vocabulary",
          blocked(br) and '"category"' in reason
          and all(c in reason for c in CATS),
          reason[-160:])

    # Словарь живёт в одном месте. Проверка считает, сколько РАЗНЫХ значений
    # перечня встречается в файле литералами: дрейфующая копия неизбежно тянет
    # за собой несколько значений, тогда как писателю законно нужно не больше
    # одного собственного константного значения (импортёру — "unclassified").
    VOCAB = set(CATS) | {"unclassified"}
    copies = []
    for f in (ROOT / "hooks" / "verdict-contract.sh",
              ROOT / "skills" / "retro" / "scripts" / "itd_review_import.py",
              ROOT / "skills" / "retro" / "scripts" / "itd_retro_scan.py",
              ROOT / "skills" / "_shared" / "itd_verdict_taxonomy.py"):
        text = f.read_text(encoding="utf-8")
        hits = sorted(v for v in VOCAB if '"' + v + '"' in text or "'" + v + "'" in text)
        if len(hits) > 1:
            copies.append((f.name, hits))
    check("no writer/reader keeps its own copy of the vocabulary",
          not copies, "; ".join("%s: %s" % (n, h) for n, h in copies))

    # документация схемы не расходится с файлом словарей
    for doc in (ROOT / "skills" / "review" / "SKILL.md",
                ROOT / "agents" / "code-reviewer.md"):
        txt = doc.read_text(encoding="utf-8")
        check("schema doc lists the exact vocabulary: " + doc.name,
              all(c in txt for c in CATS),
              ", ".join(c for c in CATS if c not in txt))

    # --- модуль словарей: прямые юнит-проверки правил ------------------------
    itd_verdict_taxonomy = _tax_mod
    def _load_from(data):
        f = Path(tempfile.mkdtemp(prefix="vc-tax-")) / "t.json"
        TMPDIRS.append(f.parent)
        f.write_text(json.dumps(data), encoding="utf-8")
        return _tax_mod.load_taxonomy(f)

    tx = itd_verdict_taxonomy.load_taxonomy()
    check("module loads the same taxonomy the tests read",
          tx is not None and tx["taxonomyVersion"] == TAX["taxonomyVersion"])
    ok = {"source": "subagent-verdict", "lineage": "agent-transcript-42",
          "findings": [{"severity": "minor", "category": "correctness"}]}
    check("validator accepts a well-formed reviewer record",
          itd_verdict_taxonomy.validate_record(ok, tx) == [])
    bad_src = dict(ok, source="github")
    check("a source outside the vocabulary is a reason, not a pass",
          any(r.startswith("source:")
              for r in itd_verdict_taxonomy.validate_record(bad_src, tx)))
    ext_unclassified = {"source": "external-github-review",
                        "lineage": "https://api.github.com/…/968",
                        "findings": [{"severity": "unspecified",
                                      "category": "unclassified"}]}
    check("unclassified/unspecified are valid ONLY for the external importer",
          itd_verdict_taxonomy.validate_record(ext_unclassified, tx) == []
          and itd_verdict_taxonomy.validate_record(
              dict(ext_unclassified, source="subagent-verdict"), tx) != [])
    check("provenance without a lineage is rejected, not admitted",
          any(r.startswith("lineage:")
              for r in itd_verdict_taxonomy.validate_record(
                  {k: v for k, v in ok.items() if k != "lineage"}, tx)))
    check("a source whose bySource entry is missing fails closed",
          any(r.startswith("taxonomy:bySource-missing-for")
              for r in itd_verdict_taxonomy.validate_record(
                  ok, {**tx, "severity": {**tx["severity"], "bySource": {}}})))
    check("a boolean taxonomyVersion is not accepted as an integer",
          _load_from({**TAX, "taxonomyVersion": True}) is None)
    bad_counter = Path(tempfile.mkdtemp(prefix="vc-cnt-"))
    TMPDIRS.append(bad_counter)
    (bad_counter / "review-findings-rejected.count.jsonl").write_text(
        "null\n[]\n" + json.dumps({"ts": "t", "reasons": ["category[0]:x"]})
        + "\n", encoding="utf-8")
    check("a non-object counter line loses only itself, not the whole scan",
          _tax_mod.rejected_summary("", directory=bad_counter)
          == {"total": 1, "byReason": {"category": 1}},
          repr(_tax_mod.rejected_summary("", directory=bad_counter)))
    check("legacyMapping targets outside the vocabulary make it unavailable",
          _load_from({**TAX, "legacyMapping": {
              **TAX["legacyMapping"],
              "category": {**TAX["legacyMapping"]["category"],
                           "old": "not-a-value"}}}) is None
          and _load_from(TAX) is not None,
          "mapping target not validated")

    check("legacy free-form values map into the closed vocabulary on read",
          itd_verdict_taxonomy.normalize_category("sql-performance", tx) == "performance"
          and itd_verdict_taxonomy.normalize_category("assumed-producer-shape", tx) == "correctness"
          and itd_verdict_taxonomy.normalize_severity("", tx) == "unspecified"
          and itd_verdict_taxonomy.normalize_severity("high", tx) == "critical")
    check("an unknown legacy value stays unmapped instead of being invented",
          itd_verdict_taxonomy.normalize_category("никогда-не-виданный", tx) is None)

    # --- cleanup ------------------------------------------------------------
    for d in TMPDIRS:
        shutil.rmtree(d, ignore_errors=True)

    print("\n%d passed, %d failed" % (PASSED, FAILED))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
