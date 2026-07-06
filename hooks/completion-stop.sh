#!/usr/bin/env python3
"""
Stop hook — напоминание «завершение не подтверждено» (v1.51.0, пункт 1, мягкий слой).

Второй эшелон экстернализации суждения. Коммит-гейт (completion-gate) ловит
преждевременную сдачу на границе коммита; этот хук ловит её на границе ХОДА:
если в конце хода дерево грязное по ИСХОДНОМУ коду, а трёхслойный вердикт из
леджера runtime-сигналов не зелёный, хук мягко напоминает, что «сделано» ещё не
доказано — тем же способом, что handoff-readiness напоминает про чекпоинт.

Почему soft, а не deny: «пользователь закончил ход» — семантика, а не факт
(порт рассуждения handoff-readiness §8.3). Жёсткое вето живёт на коммите
(обратимая граница), здесь — только systemMessage.

Шумоподавление: (1) только при грязном дереве с исходным кодом; (2) только когда
вердикт blocked или degraded (зелёный -> молчит); (3) rate-limit — не чаще
ITD_COMPLETION_STOP_RATE_MIN (30) минут на сессию; (4) отключение
ITD_COMPLETION_STOP=0; (5) fail-safe exit 0. Никогда не блокирует.

Читает JSON на stdin: {"session_id","cwd","stop_hook_active"}
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RATE_MIN_DEFAULT = 30
SOURCE_EXT_RE = re.compile(
    r"\.(py|js|jsx|ts|tsx|go|rb|java|rs|php|c|cc|cpp|cs|kt|kts|swift|scala|ex|exs|"
    r"vue|svelte|sql)$",
    re.I,
)


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except Exception:
        return default


def silent() -> int:
    sys.stdout.write(json.dumps({"hookSpecificOutput": {"hookEventName": "Stop"}}, ensure_ascii=False))
    return 0


def session_id(payload: dict) -> str:
    sid = payload.get("session_id") or os.environ.get("CLAUDE_SESSION_ID")
    if sid:
        return str(sid)
    try:
        return "pid%s" % os.getppid()
    except Exception:
        return "default"


def sentinel_path(sid: str, cwd: Path) -> Path:
    tag = hashlib.md5(str(cwd).encode("utf-8", "replace")).hexdigest()[:8]
    return Path(tempfile.gettempdir()) / ("claude-completion-stop-%s-%s" % (sid, tag))


def rate_limited(sid: str, cwd: Path, rate_min: int) -> bool:
    p = sentinel_path(sid, cwd)
    try:
        return (time.time() - float(p.read_text().strip())) < rate_min * 60
    except Exception:
        return False


def mark(sid: str, cwd: Path) -> None:
    try:
        sentinel_path(sid, cwd).write_text(str(time.time()))
    except Exception:
        pass


def dirty_source(cwd: Path) -> bool:
    try:
        out = subprocess.run(["git", "status", "--porcelain"], cwd=str(cwd),
                             capture_output=True, text=True, timeout=4)
        if out.returncode != 0:
            return False
        for ln in out.stdout.splitlines():
            path = ln[3:].strip() if len(ln) > 3 else ""
            # переименования "old -> new"
            if " -> " in path:
                path = path.split(" -> ")[-1]
            if path and SOURCE_EXT_RE.search(path):
                return True
    except Exception:
        return False
    return False


def main() -> int:
    if os.environ.get("ITD_COMPLETION_STOP", "1") == "0":
        return silent()
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return silent()
    if payload.get("stop_hook_active"):
        return silent()

    sid = session_id(payload)
    cwd = Path(payload.get("cwd") or os.getcwd())
    rate_min = env_int("ITD_COMPLETION_STOP_RATE_MIN", RATE_MIN_DEFAULT)
    if rate_limited(sid, cwd, rate_min):
        return silent()
    if not dirty_source(cwd):
        return silent()

    try:
        import completion_lib as cl
    except Exception:
        return silent()

    try:
        signals = cl.read_signals(cwd, sid)
        verdict = cl.compute_verdict(cwd, signals)
    except Exception:
        return silent()

    if not (verdict.get("blocked") or verdict.get("degraded")):
        return silent()  # зелёный — молчим

    mark(sid, cwd)
    if verdict.get("blocked"):
        head = "завершение НЕ доказано: " + verdict.get("reason", "")
    else:
        head = ("завершение не подтверждено — за сессию нет runtime-сигналов "
                "(сборка/тесты/smoke)")
    msg = (
        "[COMPLETION-STOP] Есть несохранённые изменения в коде, но " + head + ". "
        "«Код написан» ≠ «работает»: прогони слои L1→L2→L3 (статика→тесты→e2e) "
        "прежде чем считать задачу сделанной. Коммит-гейт всё равно потребует "
        "зелёных сигналов. (soft, раз в %d мин; отключить: ITD_COMPLETION_STOP=0)"
        % rate_min
    )
    out = {"hookSpecificOutput": {"hookEventName": "Stop"}, "systemMessage": msg}
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
