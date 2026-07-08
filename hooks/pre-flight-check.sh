#!/usr/bin/env python3
"""
UserPromptSubmit hook — fires on every user prompt. Injects recent git
activity, active-session lockfiles, and memory-index state into the
model's context BEFORE it starts picking tools.

Why: Claude sessions are isolated. Two sessions working on the same
repo cannot see each other's commits, task state, or lockfiles. Without
this hook, a session often starts work that was already completed by a
parallel session (see NeuroExpert 2026-04-11 incident: same kong.yml
tech debt fixed twice in parallel).

What it does:
  1. `git log --oneline -10` + `git status --short` in $PWD (if it's a
     git repo) → so the model sees recent commits and dirty files on
     entry.
  2. Looks at the Claude project memory dir for this project
     (`~/.claude/projects/<hash>/memory/`), reads MEMORY.md index if
     present, and reads `.active-session.lock` if fresher than 10
     minutes — warns that a parallel session is (likely) active.
  3. Emits everything as `hookSpecificOutput.additionalContext`.

Does NOT block: always exits 0 with permission allow. Timeout-safe:
every external call has a 2-second deadline; the hook as a whole must
complete within the 5-second budget configured in settings.json.

Reads JSON on stdin: {"user_prompt": "..."}
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:  # legacy-консоль Windows (cp866/cp1252) не должна ронять хук (v1.68.1);
    # боевые инсталлы зовут хуки через `python -X utf8`, это — страховка.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

GIT_TIMEOUT_SEC = 2
LOCK_FRESH_SECONDS = 600  # 10 minutes
MEMORY_INDEX_MAX_LINES = 30
CWD_HISTORY_MAX = 10
CWD_SWITCH_WARN_THRESHOLD = 5  # warn about /session-save after this many switches in 30 min


def run(cmd: list[str], cwd: Path | None = None) -> str:
    """Run a command with a tight timeout. Return stdout on success, '' on failure."""
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SEC,
        )
        if result.returncode != 0:
            return ""
        return result.stdout.strip()
    except Exception:
        return ""


def git_context(cwd: Path) -> str:
    """Return a compact git status + log block, or empty string if not a repo."""
    # Cheap check first: is this a git repo?
    top = run(["git", "rev-parse", "--show-toplevel"], cwd=cwd)
    if not top:
        return ""

    branch = run(["git", "branch", "--show-current"], cwd=cwd) or "(detached)"
    log = run(["git", "log", "--oneline", "-10"], cwd=cwd)
    status = run(["git", "status", "--short"], cwd=cwd)

    lines = [f"**Git context** (branch: `{branch}`, repo: `{top}`)"]
    if log:
        lines.append("")
        lines.append("Recent commits:")
        lines.append("```")
        lines.append(log)
        lines.append("```")
    if status:
        lines.append("")
        lines.append("Uncommitted changes:")
        lines.append("```")
        lines.append(status[:800])  # cap to avoid blowing context
        lines.append("```")
    return "\n".join(lines)


def find_project_memory_dir(cwd: Path) -> Path | None:
    """Find the Claude project memory dir for the current cwd.

    Claude Code stores per-project memory at:
      ~/.claude/projects/-home-USER-path-to-project/memory/
    where the dir name is the cwd with `/` replaced by `-` and a leading `-`.
    We resolve it heuristically.
    """
    home = Path.home()
    projects_root = home / ".claude" / "projects"
    if not projects_root.is_dir():
        return None

    # Compute the expected dir name for cwd
    cwd_resolved = cwd.resolve()
    expected = "-" + str(cwd_resolved).lstrip("/").replace("/", "-")
    candidate = projects_root / expected / "memory"
    if candidate.is_dir():
        return candidate

    # Fallback: find any project dir whose name ends with the cwd suffix.
    # We cannot reverse-reconstruct the path from the dir name because `-`
    # is a lossy separator (works for `/home/user/projects/myapp` but fails
    # on `/home/user/projects/my-app` — the reverse `replace("-", "/")`
    # produces `my/app`). Instead, try every suffix of cwd.parts and check
    # if the corresponding expected-dir-name exists, with root="" handled.
    parts = cwd_resolved.parts  # ('/', 'home', 'user', 'projects', 'my-app')
    for i in range(1, len(parts)):
        suffix_parts = parts[i:]
        suffix = "-".join(suffix_parts)
        for entry in projects_root.iterdir():
            if not entry.is_dir() or not entry.name.startswith("-"):
                continue
            # Dir name ends with our suffix → plausible match
            if entry.name.endswith("-" + suffix) or entry.name == "-" + suffix:
                mem = entry / "memory"
                if mem.is_dir():
                    return mem
    return None


def memory_index_context(mem_dir: Path) -> str:
    """Read MEMORY.md index and return a condensed version."""
    index = mem_dir / "MEMORY.md"
    if not index.is_file():
        return ""
    try:
        content = index.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    lines = [l for l in content.splitlines() if l.strip()]
    if len(lines) > MEMORY_INDEX_MAX_LINES:
        lines = lines[:MEMORY_INDEX_MAX_LINES] + ["(…truncated)"]
    return "**Project memory index** (`MEMORY.md`):\n\n" + "\n".join(lines)


def session_lock_context(mem_dir: Path) -> str:
    """If .active-session.lock is fresh, emit a warning about a parallel session."""
    lock = mem_dir / ".active-session.lock"
    if not lock.is_file():
        return ""
    try:
        raw = lock.read_text(encoding="utf-8", errors="replace").strip()
        data = json.loads(raw)
    except Exception:
        return ""

    ts = data.get("timestamp", 0)
    try:
        ts = float(ts)
    except (TypeError, ValueError):
        return ""

    age = time.time() - ts
    if age > LOCK_FRESH_SECONDS:
        return ""  # stale lock, ignore

    pid = data.get("pid", "?")
    branch = data.get("branch", "?")
    note = data.get("note", "")
    minutes_ago = int(age // 60)
    return (
        "⚠️ **Parallel session warning**: another Claude session touched "
        f"this project {minutes_ago} min ago (pid {pid}, branch `{branch}`)."
        + (f" Note: {note}" if note else "")
        + "\n\nRun `git log --oneline -10` and check the latest `session_*.md` "
        "in memory BEFORE starting work — the task you're about to do may "
        "already be committed."
    )


def memory_staleness_check(cwd: Path, mem_dir: Path | None) -> str:
    """Check if memory mentions a version that doesn't match current plugin.json.

    This catches the v1.13.1→v1.18.1 drift problem from the 2026-04-15 session
    where Claude used a stale version from memory instead of the actual one.
    """
    if not mem_dir:
        return ""

    # Read current version from plugin.json
    plugin_json = cwd / ".claude-plugin" / "plugin.json"
    if not plugin_json.is_file():
        return ""

    try:
        current_version = json.loads(
            plugin_json.read_text(encoding="utf-8", errors="replace")
        ).get("version", "")
    except Exception:
        return ""

    if not current_version:
        return ""

    # Read latest session file and check for version mentions
    candidates = sorted(
        mem_dir.glob("session_*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return ""

    import re

    try:
        content = candidates[0].read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""

    # Find version mentions like "v1.13.1" or "version 1.18.0"
    version_pattern = re.compile(r"\bv?(\d+\.\d+\.\d+)\b")
    mentioned_versions = set(version_pattern.findall(content))

    if not mentioned_versions:
        return ""

    # Check if any mentioned version differs from current AND looks like
    # a project version (not a random semver like Python 3.12.0)
    stale_versions = []
    for v in mentioned_versions:
        # Skip versions that look like language/tool versions (major >= 3)
        major = int(v.split(".")[0])
        if major >= 3:
            continue
        if v != current_version:
            stale_versions.append(v)

    if not stale_versions:
        return ""

    return (
        f"⚠️ **Memory staleness**: последняя сессия (`{candidates[0].name}`) "
        f"упоминает версию {', '.join('v' + v for v in stale_versions)}, "
        f"но актуальная версия — **v{current_version}** "
        f"(из `.claude-plugin/plugin.json`). Используй актуальную."
    )


def itd_state_context(cwd: Path) -> str:
    """Surface .itd-memory/STATE.json so a fresh session knows the active unit.

    v1.41.0: the machine-readable scope surface existed (STATE.json + schema +
    validate_state.py) but no session-start hook ever read it — a new session
    learned about the active unit only via /handoff. This closes that gap:
    inject currentUnit, nextAction, blockers, and unfinished gates.

    v1.44.0 (/goal layer): also surfaces .itd-memory/GOAL.json — the persistent
    long-goal unit ledger — as "Цель: X — N/M юнитов verified, текущий G-k", so
    a fresh session RESUMES the goal from the first non-verified unit instead of
    re-deriving the plan. Works even when STATE.json is absent.
    """
    mem_dir = cwd / ".itd-memory"

    def _load(p: Path) -> dict:
        if not p.is_file():
            return {}
        try:
            data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    state = _load(mem_dir / "STATE.json")
    goal = _load(mem_dir / "GOAL.json")
    if not state and not goal:
        return ""

    sources = [n for n, d in (("STATE.json", state), ("GOAL.json", goal)) if d]
    lines: list[str] = ["**ITD state** (`.itd-memory/" + " + ".join(sources) + "`):"]

    if goal:
        units = [u for u in (goal.get("units") or []) if isinstance(u, dict)]
        total = len(units)
        verified = sum(1 for u in units if u.get("status") == "verified")
        current = goal.get("currentUnitId") or next(
            (u.get("id") for u in units
             if u.get("status") in ("in_progress", "pending")), "")
        goal_status = goal.get("status") or "active"
        blocked = sum(1 for u in units if u.get("status") == "blocked")
        goal_line = (
            f"- Цель (/goal): {goal.get('goal') or '(без формулировки)'} — "
            f"{verified}/{total} юнитов verified"
        )
        if blocked:
            goal_line += f", blocked: {blocked}"
        if goal_status != "active":
            goal_line += f" [статус цели: {goal_status}]"
        elif current:
            goal_line += f", текущий `{current}`"
        lines.append(goal_line)
        if goal_status == "active" and verified < total:
            lines.append(
                "- Resume: продолжай с первого не-verified юнита через /goal — "
                "`GOAL.json` не пересоздаётся."
            )

    unit = state.get("currentUnit") or {}
    if unit.get("id") or unit.get("goal"):
        lines.append(
            f"- Активный unit: `{unit.get('id') or '?'}` — {unit.get('goal') or '(без цели)'}"
            f" [status: {unit.get('status') or '?'}]"
        )
        lines.append(
            "- **WIP=1**: пока этот unit не verified — новый unit не открывается; "
            "сначала прогони его verificationCommand'ы."
        )

    next_action = state.get("nextAction") or ""
    if next_action:
        lines.append(f"- Next action: {next_action}")

    blockers = state.get("blockers") or []
    if blockers:
        lines.append("- Blockers: " + "; ".join(str(b) for b in blockers[:5]))

    pending = [
        k for k, v in (state.get("gateResults") or {}).items()
        if v not in ("", "n/a", "passed")
    ]
    if pending:
        lines.append("- Непройденные гейты: " + ", ".join(sorted(pending)[:10]))

    # v1.47.0 (retro 2026-07-04, finding #3): a live project had STATE.json but
    # ZERO unit events — VCR and /retro were blind. If the memory dir is in use
    # but the event log is missing/empty, say so once per session-start.
    events_file = mem_dir / "events.jsonl"
    try:
        events_empty = (not events_file.is_file()) or events_file.stat().st_size == 0
    except Exception:
        events_empty = False
    if events_empty:
        lines.append(
            "- ⚠️ Unit-телеметрия: `events.jsonl` пуст/отсутствует — пиши "
            "unit-события (activated/verified) по /task Step 3.5, иначе VCR "
            "и /retro слепы."
        )

    if len(lines) == 1:
        return ""
    return "\n".join(lines)


_DRIFT_MARKER_RE = re.compile(r"снапшот\s*@\s*([0-9a-f]{7,40})", re.I)
DRIFT_CHECK_INTERVAL_SEC = 4 * 3600  # advisory раз в 4 часа на проект, не каждый промпт

# v1.68.0 (C2): заполненность ключевых контрактов — зеркалит
# check_contract_drift.py --filled, но инлайн (данные читаем, код проекта не
# исполняем). Шаблонный плейсхолдер / пустой commands[] => контракт-декорация.
_PLACEHOLDER_RE = re.compile(r"Replace this line with", re.I)
_KEY_CONTRACTS = ("FORBIDDEN_CHANGES.md", "SCOPE_LOCK.md", "VERIFICATION_CONTRACT.json")


def _unfilled_contracts(itd_dir: Path) -> list[str]:
    gaps: list[str] = []
    for name in _KEY_CONTRACTS:
        p = itd_dir / name
        try:
            if not p.is_file():
                gaps.append(name + " (нет)")
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            if not text.strip():
                gaps.append(name + " (пуст)")
            elif name.endswith(".json"):
                try:
                    data = json.loads(text)
                except Exception:
                    gaps.append(name + " (битый JSON)")
                    continue
                if name == "VERIFICATION_CONTRACT.json" and not (
                    isinstance(data, dict) and data.get("commands")
                ):
                    gaps.append(name + " (commands[] пуст)")
            elif _PLACEHOLDER_RE.search(text):
                gaps.append(name + " (плейсхолдеры)")
        except Exception:
            continue
    return gaps


def itd_contract_drift_context(cwd: Path) -> str:
    """v1.65.0: advisory-детектор дрейфа производных .itd/*.md от CLAUDE.md.

    Логика зеркалит .itd/check_contract_drift.py, но реализована ИНЛАЙН —
    user-level хук не исполняет код из проектной директории (данные читаем,
    код не запускаем). Маркер «снапшот @ <sha>» в доке сравнивается с последним
    коммитом, тронувшим CLAUDE.md. Advisory-only, rate-limited, любая ошибка
    (нет git, не репо, таймаут) — молчаливый скип: дрейф-чек не имеет права
    шуметь или ломать pre-flight.
    """
    itd_dir = cwd / ".itd"
    if not itd_dir.is_dir() or not (cwd / "CLAUDE.md").is_file():
        return ""

    # rate-limit: одна проверка на проект в DRIFT_CHECK_INTERVAL_SEC
    stamp = Path(tempfile.gettempdir()) / (
        "claude-itd-drift-" + re.sub(r"[^A-Za-z0-9]+", "-", str(cwd))[-80:] + ".stamp"
    )
    try:
        if stamp.is_file() and (time.time() - stamp.stat().st_mtime) < DRIFT_CHECK_INTERVAL_SEC:
            return ""
    except Exception:
        pass

    # drift требует git (сравнение с последним коммитом CLAUDE.md); filled —
    # нет (чистое чтение файлов). Недоступный git скипает только drift-часть.
    current = ""
    try:
        res = subprocess.run(
            ["git", "log", "-1", "--format=%h", "--", "CLAUDE.md"],
            cwd=str(cwd), capture_output=True, text=True, timeout=4,
        )
        if res.returncode == 0:
            current = res.stdout.strip().lower()
    except Exception:
        current = ""

    drift: list[str] = []
    unmarked = 0
    if current:
        try:
            for md in sorted(itd_dir.glob("*.md")):
                try:
                    m = _DRIFT_MARKER_RE.search(md.read_text(encoding="utf-8", errors="replace"))
                except Exception:
                    continue
                if not m:
                    unmarked += 1
                    continue
                marker = m.group(1).lower()
                if not (current.startswith(marker) or marker.startswith(current)):
                    drift.append(md.name)
        except Exception:
            drift = []

    unfilled = _unfilled_contracts(itd_dir)  # v1.68.0 (C2)

    try:
        stamp.write_text(str(time.time()))
    except Exception:
        pass

    if not drift and not unfilled:
        return ""  # unmarked-доки не шумят в pre-flight — advisory только на дрейф/пустоту
    parts: list[str] = []
    if drift:
        parts.append(
            f"⚠️ **Дрейф .itd-контрактов**: {', '.join(drift[:6])} — CLAUDE.md ушёл вперёд "
            f"(@ {current}) с момента снапшота. Пересверь и обнови маркер «снапшот @ <sha>» "
            f"(детали: `python .itd/check_contract_drift.py`)."
            + (f" Без маркера: {unmarked}." if unmarked else "")
        )
    if unfilled:
        parts.append(
            f"⚠️ **Контракты-декорации**: {', '.join(unfilled[:4])} — шаблон с "
            "плейсхолдерами не является связывающим контрактом; гейты, которые его "
            "читают (/review Stage A, wip-gate), работают вслепую. Заполни при "
            "первом касании (детали: `python .itd/check_contract_drift.py --filled`)."
        )
    return "\n\n".join(parts)


PLAN_GOAL_CHECK_INTERVAL_SEC = 4 * 3600


def plan_without_goal_context(cwd: Path) -> str:
    """v1.68.0 (C3): IMPLEMENTATION_PLAN.md есть, а .itd-memory/GOAL.json — нет.

    Markdown-план читают люди; машинный resume-субстрат (WIP=1, evidence-gated
    verified, инжект цели на старте сессии) работает только от GOAL.json.
    Проект с планом без зеркала перезапускается «из прозы» — скажи об этом
    один раз в 4 часа, advisory.
    """
    plan = next(
        (p for p in (cwd / "IMPLEMENTATION_PLAN.md", cwd / "docs" / "IMPLEMENTATION_PLAN.md")
         if p.is_file()),
        None,
    )
    if plan is None or (cwd / ".itd-memory" / "GOAL.json").is_file():
        return ""

    stamp = Path(tempfile.gettempdir()) / (
        "claude-itd-plangoal-" + re.sub(r"[^A-Za-z0-9]+", "-", str(cwd))[-80:] + ".stamp"
    )
    try:
        if stamp.is_file() and (time.time() - stamp.stat().st_mtime) < PLAN_GOAL_CHECK_INTERVAL_SEC:
            return ""
        stamp.write_text(str(time.time()))
    except Exception:
        pass

    return (
        f"📋 **План без машинного зеркала**: `{plan.name}` существует, а "
        "`.itd-memory/GOAL.json` — нет. Resumability и WIP=1+evidence работают "
        "только от GOAL.json-юнитов — сгенерируй зеркало (юнит на шаг плана): "
        "/kickstart Phase 3 step 7.5 для нового проекта или /goal для существующего."
    )


_PAYLOAD_SID: str = ""  # v1.69.1: session_id из stdin-payload (main() заполняет)


def session_id() -> str:
    # v1.69.1: payload-first — env CLAUDE_SESSION_ID на Windows-хуках пуст,
    # а pid-fallback нестабилен (см. crash-recovery.sh); payload несёт
    # session_id в каждом событии, что даёт тот же ключ, каким crash-recovery
    # именует чекпоинт этой сессии (иначе own-exclusion промахивался).
    if _PAYLOAD_SID:
        return _PAYLOAD_SID
    sid = os.environ.get("CLAUDE_SESSION_ID")
    if sid:
        return sid
    try:
        return f"pid{os.getppid()}"
    except Exception:
        return "default"


CRASH_CHECKPOINT_MAX_AGE_SEC = 48 * 3600
CRASH_TOOLS_SHOWN = 5


def crash_checkpoint_context(cwd: Path) -> str:
    """v1.67.0: auto-consume crash checkpoints (init-audit gap #5).

    `crash-recovery.sh` writes claude-checkpoint-<session>.json on every
    significant tool call (clean_exit=false while work is in flight) and marks
    clean_exit=true on Stop. A checkpoint that still says clean_exit=false
    belongs to a session that died mid-work. Surface it ONCE to the next
    session in the same project (cwd match), then mark it consumed — the
    "written but not automatically consumed" gap from the crash-recovery
    docstring is closed here.
    """
    tmp = Path(tempfile.gettempdir())
    own = f"claude-checkpoint-{session_id()}.json"
    cwd_str = str(cwd.resolve())
    now = time.time()

    crashed: list[tuple[float, Path, dict]] = []
    try:
        candidates = list(tmp.glob("claude-checkpoint-*.json"))
    except Exception:
        return ""
    for f in candidates:
        if f.name == own:
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if not isinstance(data, dict) or data.get("clean_exit") or data.get("consumed_at"):
            continue
        # Old-format checkpoints carry no cwd — skip rather than warn about a
        # foreign project (fail quiet, not fail loud on ambiguity). Compare
        # RESOLVED paths: Windows 8.3-short-path (RUNNER~1) и длинное имя —
        # один каталог (v1.68.1).
        stored = data.get("cwd")
        if not stored:
            continue
        try:
            if str(Path(stored).resolve()) != cwd_str:
                continue
        except Exception:
            continue
        history = data.get("tool_history") or []
        last_ts = 0.0
        for key in ("last_checkpoint", "session_start"):
            try:
                last_ts = max(last_ts, float(data.get(key) or 0))
            except (TypeError, ValueError):
                pass
        if history:
            try:
                last_ts = max(last_ts, float(history[-1].get("time") or 0))
            except (TypeError, ValueError):
                pass
        if not last_ts or (now - last_ts) > CRASH_CHECKPOINT_MAX_AGE_SEC:
            continue
        crashed.append((last_ts, f, data))

    if not crashed:
        return ""

    # Consume ALL matched checkpoints (so they don't re-fire next prompt),
    # report the most recent one.
    for _, f, data in crashed:
        try:
            data["consumed_at"] = now
            f.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    last_ts, _, data = max(crashed, key=lambda t: t[0])
    age_min = int((now - last_ts) // 60)
    age = f"{age_min} мин" if age_min < 120 else f"{age_min // 60} ч"
    git = data.get("git") or {}
    lines = [
        "💥 **Crash recovery**: предыдущая сессия в этом проекте оборвалась "
        f"без чистого завершения ~{age} назад"
        + (f" (branch `{git.get('branch')}`" + (f", last commit `{git.get('last_commit')}`" if git.get("last_commit") else "") + ")." if git.get("branch") else "."),
        "",
        "Последние действия перед обрывом:",
    ]
    for h in (data.get("tool_history") or [])[-CRASH_TOOLS_SHOWN:]:
        lines.append(f"- {h.get('tool', '?')}: {h.get('summary', '')}")
    lines.append("")
    lines.append(
        "Проверь `git status` и незакоммиченные результаты ПЕРЕД началом новой "
        "работы — часть задачи могла быть уже сделана. Чекпоинт помечен как "
        "обработанный и повторно не всплывёт."
    )
    return "\n".join(lines)


def context_switch_detect(cwd: Path) -> str:
    """Detect cwd changes between prompts. Returns warning or empty string.

    Tracks last N cwd entries with timestamps in a state file. When a switch
    is detected, warns the user. If switches exceed threshold in 30 min,
    suggests /session-save to prevent context loss.
    """
    state_file = os.path.join(tempfile.gettempdir(), f"claude-cwd-history-{session_id()}.json")
    now = time.time()
    cwd_str = str(cwd.resolve())

    # Read existing history
    history: list[dict] = []
    try:
        with open(state_file) as f:
            history = json.loads(f.read() or "[]")
    except Exception:
        history = []

    # Get previous cwd
    prev_cwd = history[-1]["cwd"] if history else None

    # Append current
    history.append({"cwd": cwd_str, "ts": now})

    # Trim to max
    if len(history) > CWD_HISTORY_MAX:
        history = history[-CWD_HISTORY_MAX:]

    # Write back
    try:
        with open(state_file, "w") as f:
            f.write(json.dumps(history))
    except Exception:
        pass

    # No switch? Return empty
    if prev_cwd is None or prev_cwd == cwd_str:
        return ""

    # Switch detected
    prev_name = Path(prev_cwd).name
    curr_name = cwd.name

    # Count recent switches (last 30 min)
    cutoff = now - 1800
    recent_cwds = [h["cwd"] for h in history if h["ts"] >= cutoff]
    unique_recent = len(set(recent_cwds))
    switch_count = sum(
        1 for i in range(1, len(recent_cwds))
        if recent_cwds[i] != recent_cwds[i - 1]
    )

    warning = (
        f"🔄 **Context switch**: `{prev_name}` → `{curr_name}`. "
        "Сессия мульти-проектная. Задача task-level прежняя или начинаем новую?"
    )

    if switch_count >= CWD_SWITCH_WARN_THRESHOLD:
        warning += (
            f"\n\n⚠️ {switch_count} переключений за последние 30 мин "
            f"между {unique_recent} проектами. Рекомендуется `/session-save` "
            "чтобы не потерять контекст."
        )

    return warning


def main() -> int:
    global _PAYLOAD_SID
    try:
        payload = json.load(sys.stdin)
        if isinstance(payload, dict) and payload.get("session_id"):
            _PAYLOAD_SID = str(payload["session_id"])
    except Exception:
        pass  # OK if missing

    cwd = Path(os.getcwd())
    sections: list[str] = []

    # Context switch detection (Gap #5)
    ctx_switch = context_switch_detect(cwd)
    if ctx_switch:
        sections.append(ctx_switch)

    # Crash recovery consumer (v1.67.0)
    crash = crash_checkpoint_context(cwd)
    if crash:
        sections.append(crash)

    git = git_context(cwd)
    if git:
        sections.append(git)

    itd_state = itd_state_context(cwd)
    if itd_state:
        sections.append(itd_state)

    drift = itd_contract_drift_context(cwd)
    if drift:
        sections.append(drift)

    plan_gap = plan_without_goal_context(cwd)
    if plan_gap:
        sections.append(plan_gap)

    mem_dir = find_project_memory_dir(cwd)
    if mem_dir:
        lock = session_lock_context(mem_dir)
        if lock:
            sections.append(lock)
        idx = memory_index_context(mem_dir)
        if idx:
            sections.append(idx)

    # Memory staleness detection (Gap #7)
    staleness = memory_staleness_check(cwd, mem_dir)
    if staleness:
        sections.append(staleness)

    if not sections:
        return 0  # nothing to report, stay silent

    context = "[PRE-FLIGHT CHECK]\n\n" + "\n\n---\n\n".join(sections)

    out = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context,
        }
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
