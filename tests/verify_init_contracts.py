#!/usr/bin/env python3
"""Functional tests for the v1.67.0 init-hardening set (init-audit 2026-07-08).

Covers all five closed gaps:
  1. itd_init_validate.py — selftest (isolated-clone bootstrap+test, positive
     and negative paths exercised by a real git repo, no mocks);
  2. check_contract_drift.py — selftest (drift compare + filled_status logic);
  3. --filled functional: a scaffolded-from-templates .itd/ is reported as NOT
     filled (template prose is not a contract); a filled one passes;
  4. crash-recovery + pre-flight consumer pipe-test: a significant tool call
     leaves clean_exit=false with cwd; a DIFFERENT session's pre-flight in the
     same cwd surfaces the crash section exactly once (consumed after); a Stop
     event marks clean_exit=true and nothing is surfaced;
  5. GOAL.json built per goal.schema.json goalTemplate (the /kickstart step 7.5
     mirror shape) validates via scripts/validate_state.py.

Cross-platform by construction: sys.executable, tempfile, no shell. Run:
  python3 tests/verify_init_contracts.py
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

try:  # legacy-консоль Windows (PYTHONUTF8=0 в CI-шаге) не должна ронять сам тест
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "docs" / "templates" / "itd"
INIT_VALIDATE = TEMPLATES / "itd_init_validate.py"
DRIFT = TEMPLATES / "check_contract_drift.py"
CRASH_HOOK = ROOT / "hooks" / "crash-recovery.sh"
PREFLIGHT = ROOT / "hooks" / "pre-flight-check.sh"
VALIDATE_STATE = ROOT / "scripts" / "validate_state.py"

PY = sys.executable or "python3"
FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("  OK   " if ok else " FAIL  ") + name + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILURES.append(name)


def run(args: list[str], cwd: Path | None = None, stdin_text: str | None = None,
        env_extra: dict | None = None) -> tuple[int, str]:
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    res = subprocess.run(args, cwd=str(cwd) if cwd else None, input=stdin_text,
                         capture_output=True, text=True, encoding="utf-8",
                         errors="replace", timeout=300, env=env)
    return res.returncode, (res.stdout or "") + (res.stderr or "")


def t1_init_validate_selftest() -> None:
    rc, out = run([PY, str(INIT_VALIDATE), "--selftest"])
    check("itd_init_validate --selftest exits 0", rc == 0, out[-300:])
    check("itd_init_validate selftest ALL PASS", "SELFTEST: ALL PASS" in out)


def t2_drift_selftest() -> None:
    rc, out = run([PY, str(DRIFT), "--selftest"])
    check("check_contract_drift --selftest exits 0", rc == 0, out[-300:])
    check("check_contract_drift selftest ALL PASS", "SELFTEST: ALL PASS" in out)


def t3_filled_functional() -> None:
    with tempfile.TemporaryDirectory(prefix="itd-filled-") as td:
        proj = Path(td)
        itd = proj / ".itd"
        itd.mkdir()
        for name in ("FORBIDDEN_CHANGES.md", "SCOPE_LOCK.md", "VERIFICATION_CONTRACT.json"):
            (itd / name).write_text((TEMPLATES / name).read_text(encoding="utf-8"),
                                    encoding="utf-8")
        script = itd / "check_contract_drift.py"
        script.write_text(DRIFT.read_text(encoding="utf-8"), encoding="utf-8")

        rc, out = run([PY, str(script), "--filled", "--strict"], cwd=proj)
        check("--filled --strict red on template scaffold", rc == 1, out[-300:])
        check("--filled names the unfilled contracts", "НЕ ЗАПОЛНЕНО" in out)

        (itd / "FORBIDDEN_CHANGES.md").write_text(
            "# Forbidden Changes\n- Никогда не трогать платёжные пути.\n", encoding="utf-8")
        (itd / "SCOPE_LOCK.md").write_text(
            "## Current Task\n- Закрыть init-дыры.\n", encoding="utf-8")
        (itd / "VERIFICATION_CONTRACT.json").write_text(
            json.dumps({"version": 1, "commands": [
                {"id": "t", "command": "make test", "timeoutSeconds": 600,
                 "expectedOutput": "", "passFailParser": "exit_code_zero"}]}),
            encoding="utf-8")
        rc, out = run([PY, str(script), "--filled", "--strict"], cwd=proj)
        check("--filled --strict green on filled contracts", rc == 0, out[-300:])


def t4_crash_pipeline() -> None:
    with tempfile.TemporaryDirectory(prefix="itd-crashproj-") as td:
        proj = Path(td)
        sid = "vtest-" + uuid.uuid4().hex[:8]
        cp_file = Path(tempfile.gettempdir()) / f"claude-checkpoint-{sid}.json"
        try:
            # significant tool call -> checkpoint with cwd + clean_exit=false
            rc, out = run([PY, str(CRASH_HOOK)], cwd=proj,
                          stdin_text=json.dumps({"tool_name": "Edit",
                                                 "tool_input": {"file_path": "a.py"}}),
                          env_extra={"CLAUDE_SESSION_ID": sid})
            data = json.loads(cp_file.read_text(encoding="utf-8"))
            # resolved-сравнение: на Windows tempdir может быть 8.3-short-path
            check("checkpoint records cwd",
                  bool(data.get("cwd"))
                  and Path(data["cwd"]).resolve() == proj.resolve(),
                  str(data.get("cwd")))
            check("checkpoint clean_exit=false mid-work", data.get("clean_exit") is False)

            # a DIFFERENT session's pre-flight in the same cwd surfaces it once
            rc, out = run([PY, str(PREFLIGHT)], cwd=proj, stdin_text="{}",
                          env_extra={"CLAUDE_SESSION_ID": sid + "-next"})
            check("pre-flight surfaces crash section", "Crash recovery" in out, out[-300:])
            rc, out = run([PY, str(PREFLIGHT)], cwd=proj, stdin_text="{}",
                          env_extra={"CLAUDE_SESSION_ID": sid + "-next"})
            check("crash section consumed (not repeated)", "Crash recovery" not in out)

            # Stop marks clean_exit=true; a clean checkpoint never surfaces
            cp_file.unlink()
            run([PY, str(CRASH_HOOK)], cwd=proj,
                stdin_text=json.dumps({"tool_name": "Edit", "tool_input": {}}),
                env_extra={"CLAUDE_SESSION_ID": sid})
            run([PY, str(CRASH_HOOK)], cwd=proj,
                stdin_text=json.dumps({"hook_event_name": "Stop"}),
                env_extra={"CLAUDE_SESSION_ID": sid})
            data = json.loads(cp_file.read_text(encoding="utf-8"))
            check("Stop flips clean_exit=true", data.get("clean_exit") is True)
            rc, out = run([PY, str(PREFLIGHT)], cwd=proj, stdin_text="{}",
                          env_extra={"CLAUDE_SESSION_ID": sid + "-again"})
            check("clean exit not surfaced as crash", "Crash recovery" not in out)
        finally:
            try:
                cp_file.unlink()
            except OSError:
                pass


def t5_goal_mirror_shape() -> None:
    with tempfile.TemporaryDirectory(prefix="itd-goal-") as td:
        goal = Path(td) / "GOAL.json"
        goal.write_text(json.dumps({
            "version": 1, "goal": "Kickstarted project", "status": "active",
            "createdAt": "2026-07-08T00:00:00Z", "updatedAt": "2026-07-08T00:00:00Z",
            "currentUnitId": "U-1",
            "units": [
                {"id": "U-1", "criterion": "pytest tests/test_auth.py all passing",
                 "verificationCommand": "pytest tests/test_auth.py", "status": "pending"},
                {"id": "U-2", "criterion": "profile CRUD passing",
                 "verificationCommand": "pytest tests/test_profile.py", "status": "pending"},
            ],
        }), encoding="utf-8")
        rc, out = run([PY, str(VALIDATE_STATE), str(goal)])
        check("kickstart GOAL.json mirror validates", rc == 0, out[-300:])


def _mini_git_project(base: Path) -> Path:
    proj = base / "proj"
    proj.mkdir()
    (proj / "CLAUDE.md").write_text("# rules\n", encoding="utf-8")
    for args in (["git", "init", "-q"],
                 ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "CLAUDE.md"],
                 ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"]):
        subprocess.run(args, cwd=str(proj), capture_output=True, timeout=30)
    return proj


def t6_classifier_l2() -> None:
    """v1.68.0 C1: init-валидатор классифицируется как L2 test_run; commit — нет."""
    sys.path.insert(0, str(ROOT / "hooks"))
    import completion_lib as cl
    s = cl.classify_bash('python3 .itd/itd_init_validate.py --bootstrap "x" --test "y"',
                         {"stdout": "PASS.", "interrupted": False})
    check("classifier: validator run -> test_run/L2",
          bool(s) and s.get("kind") == "test_run" and s.get("layer") == 2, str(s))
    s2 = cl.classify_bash("git commit -m itd_init_validate", {"stdout": ""})
    check("classifier: commit mentioning validator is NOT a signal", not s2, str(s2))


def _preflight_ctx(proj: Path) -> str:
    rc, out = run([PY, str(PREFLIGHT)], cwd=proj, stdin_text="{}")
    if not out.strip():
        return ""
    try:
        return json.loads(out)["hookSpecificOutput"]["additionalContext"]
    except Exception:
        return out


def t7_preflight_contract_health() -> None:
    """v1.68.0 C2+C3: pre-flight предупреждает о контрактах-декорациях и плане без GOAL.json."""
    with tempfile.TemporaryDirectory(prefix="itd-pf-red-") as td:
        proj = _mini_git_project(Path(td))
        itd = proj / ".itd"
        itd.mkdir()
        for name in ("FORBIDDEN_CHANGES.md", "SCOPE_LOCK.md", "VERIFICATION_CONTRACT.json"):
            (itd / name).write_text((TEMPLATES / name).read_text(encoding="utf-8"),
                                    encoding="utf-8")
        (proj / "IMPLEMENTATION_PLAN.md").write_text("# plan\n", encoding="utf-8")
        ctx = _preflight_ctx(proj)
        check("pre-flight warns on template contracts", "Контракты-декорации" in ctx, ctx[-200:])
        check("pre-flight warns on plan without GOAL.json",
              "План без машинного зеркала" in ctx, ctx[-200:])

    with tempfile.TemporaryDirectory(prefix="itd-pf-green-") as td:
        proj = _mini_git_project(Path(td))
        itd = proj / ".itd"
        itd.mkdir()
        (itd / "FORBIDDEN_CHANGES.md").write_text("# FC\n- нет платежей из кода\n", encoding="utf-8")
        (itd / "SCOPE_LOCK.md").write_text("## Current Task\n- задача X\n", encoding="utf-8")
        (itd / "VERIFICATION_CONTRACT.json").write_text('{"commands": [{"id": "t"}]}',
                                                        encoding="utf-8")
        (proj / "IMPLEMENTATION_PLAN.md").write_text("# plan\n", encoding="utf-8")
        mem = proj / ".itd-memory"
        mem.mkdir()
        (mem / "GOAL.json").write_text(json.dumps({
            "version": 1, "goal": "g", "status": "active", "createdAt": "x",
            "updatedAt": "x", "currentUnitId": "U-1", "units": []}), encoding="utf-8")
        ctx = _preflight_ctx(proj)
        check("pre-flight silent on filled contracts", "Контракты-декорации" not in ctx)
        check("pre-flight silent when GOAL.json exists",
              "План без машинного зеркала" not in ctx)


def _find_bash() -> str | None:
    """POSIX bash для sync-to-active. На Windows `bash` в PATH может быть
    WSL-заглушкой System32 (UTF-16 «no installed distributions») — предпочитаем
    Git Bash (v1.68.1)."""
    if sys.platform == "win32":
        for cand in (r"C:\Program Files\Git\bin\bash.exe",
                     r"C:\Program Files\Git\usr\bin\bash.exe"):
            if Path(cand).is_file():
                return cand
        import shutil
        p = shutil.which("bash")
        if p and "system32" not in p.lower():
            return p
        return None
    return "bash"


def t8_sync_templates_step() -> None:
    """v1.68.0 C4: sync-to-active.sh зеркалит docs/templates/{itd,itd-memory} в CLAUDE_HOME."""
    bash = _find_bash()
    if not bash:
        print("  SKIP  t8: POSIX bash не найден (WSL-заглушка не подходит) — шаг пропущен")
        return
    with tempfile.TemporaryDirectory(prefix="itd-synchome-") as td:
        home = Path(td) / "claude-home"
        home.mkdir()
        rc, out = run([bash, str(ROOT / "scripts" / "sync-to-active.sh")],
                      cwd=ROOT,
                      env_extra={
                          "CLAUDE_HOME": str(home).replace("\\", "/"),
                          # windows-target: не дать sync подобрать Store-стаб
                          # python из PATH — явный интерпретатор теста
                          "ITD_WIN_PYTHON": str(PY).replace("\\", "/"),
                      })
        check("sync-to-active exits 0 on fresh CLAUDE_HOME", rc == 0, out[-300:])
        v = home / "templates" / "itd" / "itd_init_validate.py"
        d = home / "templates" / "itd" / "check_contract_drift.py"
        g = home / "templates" / "itd-memory" / "goal.schema.json"
        check("templates/itd mirrored (validator)", v.is_file())
        check("templates/itd mirrored (drift checker) bit-identical",
              d.is_file() and d.read_bytes() == DRIFT.read_bytes())
        check("templates/itd-memory mirrored (goal schema)", g.is_file())


def t9_non_ascii_repo_path() -> None:
    """v1.68.1 regression: валидатор работает в репо с не-ASCII путём.

    Живой баг с Windows (упр. 1 init-аудита): text=True без encoding
    декодировал UTF-8-путь из `git rev-parse` локальной кодировкой →
    WinError 267 на CreateProcess. Тест гоняет валидатор subprocess'ом
    (без -X utf8) в директории с кириллицей — на Windows это и есть
    падавший сценарий, на Linux — smoke той же ветки кода.
    """
    with tempfile.TemporaryDirectory(prefix="итд-тест-") as td:
        repo = Path(td) / "проект-очередь"
        repo.mkdir()
        (repo / "README.md").write_text("# т\n", encoding="utf-8")
        for args in (["git", "init", "-q"],
                     ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A"],
                     ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i"]):
            subprocess.run(args, cwd=str(repo), capture_output=True, timeout=30)
        rc, out = run([PY, str(INIT_VALIDATE),
                       "--bootstrap", f'"{PY}" -c "print(1)"',
                       "--test", f'"{PY}" -c "import sys; sys.exit(0)"'],
                      cwd=repo)
        check("validator PASS in non-ASCII repo path", rc == 0 and "PASS" in out, out[-300:])


def t10_subagent_stop_marks_clean() -> None:
    """v1.69.0 regression: SubagentStop помечает чекпоинт clean (фантомные баннеры).

    Живой FP из упражнений init-аудита (×5 за сессию): PostToolUse фаерится и в
    контексте фоновых субагентов (свой session_id), но при их завершении
    приходит SubagentStop, а не Stop — чекпоинт вечно clean_exit=false, и
    pre-flight ГЛАВНОЙ сессии всплывал его как «Crash recovery». Умерший
    мид-флайт субагент по-прежнему должен всплывать — проверяется t4.
    """
    with tempfile.TemporaryDirectory(prefix="itd-subagent-") as td:
        proj = Path(td)
        sid = "vsub-" + uuid.uuid4().hex[:8]
        cp_file = Path(tempfile.gettempdir()) / f"claude-checkpoint-{sid}.json"
        try:
            run([PY, str(CRASH_HOOK)], cwd=proj,
                stdin_text=json.dumps({"tool_name": "Edit", "tool_input": {"file_path": "a.py"}}),
                env_extra={"CLAUDE_SESSION_ID": sid})
            data = json.loads(cp_file.read_text(encoding="utf-8"))
            check("subagent checkpoint dirty mid-work", data.get("clean_exit") is False)

            run([PY, str(CRASH_HOOK)], cwd=proj,
                stdin_text=json.dumps({"hook_event_name": "SubagentStop",
                                       "stop_hook_active": False}),
                env_extra={"CLAUDE_SESSION_ID": sid})
            data = json.loads(cp_file.read_text(encoding="utf-8"))
            check("SubagentStop flips clean_exit=true", data.get("clean_exit") is True,
                  str(data.get("clean_exit")))

            rc, out = run([PY, str(PREFLIGHT)], cwd=proj, stdin_text="{}",
                          env_extra={"CLAUDE_SESSION_ID": sid + "-main"})
            check("no phantom crash banner after SubagentStop",
                  "Crash recovery" not in out)
        finally:
            try:
                cp_file.unlink()
            except OSError:
                pass

    # Настоящая дыра была в РЕГИСТРАЦИИ: SubagentStop-события вообще не
    # доходили до хука. Проверяем, что sync-to-active регистрирует
    # crash-recovery.sh в SubagentStop-блоке settings.json.
    sync_text = (ROOT / "scripts" / "sync-to-active.sh").read_text(encoding="utf-8")
    m = re.search(r'"SubagentStop":\s*\[(.*?)\n\s*\]\s*,?\n', sync_text, re.S)
    block = m.group(1) if m else ""
    check("sync registers crash-recovery on SubagentStop",
          "crash-recovery.sh" in block, block[-200:] if block else "block not found")


def main() -> int:
    for t in (t1_init_validate_selftest, t2_drift_selftest, t3_filled_functional,
              t4_crash_pipeline, t5_goal_mirror_shape,
              t6_classifier_l2, t7_preflight_contract_health, t8_sync_templates_step,
              t9_non_ascii_repo_path, t10_subagent_stop_marks_clean):
        t()
    print()
    if FAILURES:
        print(f"FAILED ({len(FAILURES)}): " + ", ".join(FAILURES))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
