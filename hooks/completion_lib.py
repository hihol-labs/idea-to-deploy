#!/usr/bin/env python3
"""
Completion-Gate shared library (idea-to-deploy, v1.51.0).

Единое сердце подсистемы «Врата завершения» — реализует то, чего не хватало
методологии до высокого балла по 4 пунктам «как предотвратить преждевременные
сдачи»:

  Пункт 4 — сбор runtime-сигналов:   classify_bash() + append_signal()
  Пункт 2 — трёхслойная валидация:    compute_verdict() (L1→L2→L3, с блокировкой)
  Пункт 3 — «красные пометки»+FIX:    red_mark() + FIX_HINTS
  Пункт 1 — экстернализация вето:     compute_verdict() выносит суждение из
                                      ЗАПИСАННЫХ сигналов, а не из уверенности
                                      агента; хук completion-gate применяет вето.

Вендор-нейтральность (best-effort invariant): контракт — это JSON-леджер в репо
(.claude/completion/) + текст в CLAUDE.md. Хуки лишь ТРАНСПОРТИРУЮТ контракт.
Если леджера нет — verdict деградирует в «unknown», а не в ложное «all green».

Никаких сторонних зависимостей: только stdlib. Любая ошибка проглатывается
вызывающим хуком (exit 0), чтобы никогда не ронять сессию.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Пути артефактов. .claude/ гарантированно per-project и gitignored (как
# .claude/traces у execution-trace), поэтому леджер не засоряет репозиторий.
# ---------------------------------------------------------------------------

DIR_NAME = "completion"
SIGNALS_FILE = "signals.jsonl"
VERDICT_FILE = "completion.json"
SESSION_WINDOW_SEC = 6 * 3600  # если session_id недоступен — окно свежести сигналов
MAX_LEDGER_LINES = 2000          # верхняя граница строк леджера сигналов
LEDGER_SOFT_BYTES = 512 * 1024    # прунинг срабатывает только когда файл перерос этот размер
                                  # (амортизированный O(1) на append: полный rewrite раз в ~MAX строк)


ERRORS_FILE = "errors.log"
ERRORS_SOFT_BYTES = 64 * 1024     # bound the error log the same way as the ledger


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# v1.75.0 (ACID-audit fixes #1–#3) — durable-write primitives
# ---------------------------------------------------------------------------

def atomic_write_text(path: Path, text: str) -> None:
    """tmp + fsync + os.replace: a reader never sees a truncated file (fix #1).

    os.replace is atomic on POSIX and on NTFS. The tmp file lives in the SAME
    directory so the replace never crosses a filesystem boundary.
    v1.76.0: fsync before the replace — without it the rename can outlive the
    DATA on a kernel/power crash (ext4/NTFS journal metadata, not content),
    leaving an empty-but-present file. The orphan tmp is removed on ANY
    failure, including the write itself (v1.75.0 cleaned up only on a failed
    replace). Directory fsync is POSIX-only best-effort.
    """
    tmp = path.with_name(path.name + f".tmp-{os.getpid()}")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            tmp.unlink()
        except Exception:
            pass
        raise
    try:  # durable rename on POSIX: fsync the containing directory
        dfd = os.open(str(path.parent), getattr(os, "O_DIRECTORY", os.O_RDONLY))
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    except Exception:
        pass  # Windows has no dir-fsync; the file fsync above is the guarantee


def log_persist_error(cwd: Path, where: str, exc: BaseException) -> None:
    """Persistence failures must be OBSERVABLE, not swallowed (audit fix #3).

    The whole recovery strategy is human-in-loop; an invisible persist failure
    is the one class the human can never fix. Appends one line to
    .claude/completion/errors.log, bounded (keeps the tail on overflow).
    Itself best-effort: never raises.
    """
    try:
        p = completion_dir(cwd) / ERRORS_FILE
        line = f"{now_iso()} {where}: {type(exc).__name__}: {exc}\n"
        with p.open("a", encoding="utf-8") as f:
            f.write(line)
        if p.stat().st_size > ERRORS_SOFT_BYTES:
            tail = p.read_text(encoding="utf-8", errors="replace")[-ERRORS_SOFT_BYTES // 2:]
            atomic_write_text(p, tail)
    except Exception:
        pass


def _lock_file(fileobj) -> bool:
    """Advisory exclusive lock (audit fix #2). Best-effort, cross-platform:
    fcntl on POSIX, msvcrt on Windows; True if the lock was taken.

    v1.76.0: the Windows path is NON-blocking with bounded retries (~2s).
    msvcrt.locking(LK_LOCK) blocks in 1s probes for up to 10s — longer than
    the 5s hook timeout in settings.json, so under contention the harness
    would kill the hook mid-write. LK_NBLCK keeps the worst case under the
    timeout; on giving up the caller proceeds unlocked and LOGS the
    degradation (observable isolation loss, not a silent one).
    v1.80.0: the POSIX path is symmetric — LOCK_EX|LOCK_NB with the same
    bounded retries; a blocking flock had the same kill-the-hook exposure
    under extreme contention (re-audit finding, RUNBOOK candidate closed).
    """
    try:
        import fcntl
    except ImportError:
        fcntl = None
    if fcntl is not None:
        for _ in range(20):  # 20 × 0.1s = максимум ~2s под hook-timeout 5s
            try:
                fcntl.flock(fileobj.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
            except (BlockingIOError, InterruptedError):
                time.sleep(0.1)
            except Exception:
                return False
        return False
    try:
        import msvcrt
    except Exception:
        return False
    for _ in range(20):  # 20 × 0.1s = максимум ~2s под hook-timeout 5s
        try:
            fileobj.seek(0)
            msvcrt.locking(fileobj.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            time.sleep(0.1)
        except Exception:
            return False
    return False


def _unlock_file(fileobj) -> None:
    try:
        import fcntl
        fcntl.flock(fileobj.fileno(), fcntl.LOCK_UN)
        return
    except ImportError:
        pass
    except Exception:
        return
    try:
        import msvcrt
        fileobj.seek(0)
        msvcrt.locking(fileobj.fileno(), msvcrt.LK_UNLCK, 1)
    except Exception:
        pass


def completion_dir(cwd: Path) -> Path:
    d = Path(cwd) / ".claude" / DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def signals_path(cwd: Path) -> Path:
    return completion_dir(cwd) / SIGNALS_FILE


def verdict_path(cwd: Path) -> Path:
    return completion_dir(cwd) / VERDICT_FILE


# ---------------------------------------------------------------------------
# Пункт 4 — сбор runtime-сигналов
# ---------------------------------------------------------------------------

# Раннеры тестов -> layer 2 (доказательство поведения во время выполнения).
# v1.68.0: itd_init_validate — init-валидатор (bootstrap+test в изолированном
# клоне) считается L2-сигналом: его exit 0 — реальный прогон тестов в чистом
# окружении, а не self-asserted галочка (init-audit round 2, C1).
TEST_RE = re.compile(
    r"(^|\s|;|&&|\|\|)("
    r"npm\s+(run\s+)?test|npm\s+t\b|pnpm\s+(run\s+)?test|yarn\s+(run\s+)?test|"
    r"jest|vitest|mocha|ava|playwright\s+test|cypress\s+run|"
    r"pytest|py\.test|python\s+-m\s+pytest|unittest|nose2|tox|"
    r"go\s+test|cargo\s+test|mvn\s+(test|verify)|gradle\s+test|"
    r"phpunit|rspec|bundle\s+exec\s+rspec|dotnet\s+test|"
    r"ctest|bats|\S*itd_init_validate(\.py)?)\b",
    re.I,
)

# Статика/сборка/типы/линт -> layer 1 (синтаксис и статический анализ).
STATIC_RE = re.compile(
    r"(^|\s|;|&&|\|\|)("
    r"npm\s+run\s+(build|lint|typecheck|type-check|tsc)|next\s+build|"
    r"tsc\b|eslint|biome\s+(check|lint)|prettier\s+--check|"
    r"ruff\b|flake8|pylint|mypy|pyright|black\s+--check|"
    r"cargo\s+(build|check|clippy)|go\s+(build|vet)|gofmt\s+-l|"
    r"mvn\s+compile|gradle\s+(build|compileJava)|"
    r"rubocop|phpstan|psalm|dotnet\s+build)\b",
    re.I,
)

# Запуск приложения / проверка готовности / критический путь -> layer 3.
APP_RE = re.compile(
    r"(^|\s|;|&&|\|\|)("
    r"curl\b[^|]*\b(localhost|127\.0\.0\.1|/health|/healthz|/ready|/api/)|"
    r"wget\b[^|]*\b(localhost|127\.0\.0\.1)|"
    r"docker\s+compose\s+up|docker\s+run|"
    r"npm\s+run\s+(start|dev|serve|e2e)|next\s+start|"
    r"playwright\s+test|cypress\s+run|"
    r"httpie|http\s+(GET|POST)|nc\s+-z)\b",
    re.I,
)

# Побочные эффекты в durable-состоянии (записи в БД / миграции) -> layer 0 (учёт).
SIDE_EFFECT_RE = re.compile(
    r"(^|\s|;|&&|\|\|)("
    r"prisma\s+(migrate|db\s+push)|psql\b[^|]*-f|alembic\s+upgrade|"
    r"knex\s+migrate|sequelize\s+db:migrate|"
    r"rails\s+db:migrate|php\s+artisan\s+migrate|flyway\s+migrate|"
    r"mongosh|redis-cli)\b",
    re.I,
)

# VCS / сдача-репорт — НЕ доказательство. Коммит / пуш / открытие PR — это акт
# СДАЧИ, а не ПРОВЕРКИ; он никогда не должен выдаваться за прогон теста слоя 2.
# Прямое исполнение принципа «commit ≠ test»: до этого `git commit … && git log`
# ловился как test_run/L2 и «зеленил» слой поведения самим фактом коммита.
VCS_LEAD_RE = re.compile(r"^\s*(git|gh|hg|svn|jj)\s", re.I)

# Очистка временных ресурсов -> layer 0 (учёт «cleanup»).
CLEANUP_RE = re.compile(
    r"(^|\s|;|&&|\|\|)(rm\s+-rf?\s+[^|]*\b(tmp|temp|\.cache|node_modules/\.cache|dist|build|coverage)\b|"
    r"docker\s+compose\s+down|docker\s+rm|git\s+clean)\b",
    re.I,
)


def _extract_output(tool_response) -> tuple[str, int | None]:
    """Достаёт (текст, exit_code|None) из tool_response любого разумного вида."""
    if tool_response is None:
        return "", None
    if isinstance(tool_response, str):
        return tool_response, None
    if isinstance(tool_response, dict):
        parts = []
        for k in ("stdout", "stderr", "output", "content", "result"):
            v = tool_response.get(k)
            if isinstance(v, str) and v:
                parts.append(v)
        code = None
        for k in ("exitCode", "exit_code", "returncode", "code"):
            v = tool_response.get(k)
            if isinstance(v, int):
                code = v
                break
        if tool_response.get("interrupted"):
            # прерванный запуск не может служить доказательством прохождения
            code = code if code is not None else 1
        return "\n".join(parts), code
    return str(tool_response), None


# Явные признаки провала в тексте вывода (порядок важнее «passed»).
FAIL_TEXT_RE = re.compile(
    r"("
    r"\b[1-9]\d*\s+fail(ing|ed|ures?)?\b|"        # "3 failed", "1 failing"
    r"tests?:\s*.*?\b[1-9]\d*\s+failed|"          # jest "Tests: 2 failed"
    r"=+\s*[1-9]\d*\s+failed|"                    # pytest "=== 2 failed"
    r"\bFAILED\b|\bFAIL\b|"
    r"assertionerror|traceback \(most recent|"
    r"npm\s+err!|error\s+ts\d+|"
    r"\bexit\s+(code\s+)?[1-9]\b|"
    r"\bmodule_not_found|cannot find module|"
    r"econnrefused|relation\s+\S+\s+does not exist|"
    r"segmentation fault|panic:|build failed|compilation failed)",
    re.I,
)

# Явные признаки успеха. ТОЛЬКО сильные сигналы (test-summary / build-summary /
# TAP): ложный `pass` = опасная false-зелёнка (гейт зелёный на сломанном), тогда
# как ложный `unknown` безопасно деградирует в advisory. Поэтому слабые фразы
# («clean», «no errors», голое «ok») из pass-детекции УБРАНЫ — они встречаются в
# произвольном выводе (HTTP 200-логи, прогресс сборки) и давали FP на L2/L3.
# Реальный успех почти всегда несёт exit-код или эхо EXIT=0 (см. outcome_from),
# которые авторитетнее текста; сюда доходит лишь текст-only фоллбэк.
PASS_TEXT_RE = re.compile(
    r"("
    r"\ball\s+tests?\s+pass|"
    r"\b0\s+fail(ing|ed|ures?)?\b|"
    r"tests?:\s*.*?\b\d+\s+passed(?!.*\bfailed)|"
    r"=+\s*\d+\s+passed(?!.*failed)|"
    r"\b\d+\s+passing\b|"
    r"compiled successfully|build succeeded|build passed)",
    re.I,
)


# Эхнутый exit-код команды. Раннеры часто маскируют реальный $? пайпом через
# head/tail, а хостовый tool_response не всегда несёт структурный exit-код.
# Проектная конвенция — дописывать echo "EXIT: $?" / TSC_EXIT=$? / "exit: N".
# Матчит "EXIT: 0", "TSC_EXIT=0", "exit: 0" (последний в выводе — авторитетный).
_EXIT_ECHO_RE = re.compile(r"\b(?:[A-Z][A-Z0-9_]*_)?EXIT\s*[:=]\s*(\d+)\b", re.I)


def outcome_from(text: str, exit_code: int | None) -> str:
    """pass | fail | unknown — из exit-кода, эхнутого EXIT=N, затем текста."""
    if exit_code is not None:
        return "pass" if exit_code == 0 else "fail"
    if not text:
        return "unknown"
    # Эхнутый код команды (последний в выводе) авторитетнее эвристики по тексту:
    # без него «tsc … ; echo EXIT: 0» молча оставался unknown и слой L1 никогда
    # не становился pass.
    m = None
    for mm in _EXIT_ECHO_RE.finditer(text):
        m = mm
    if m is not None:
        return "pass" if m.group(1) == "0" else "fail"
    if FAIL_TEXT_RE.search(text):
        return "fail"
    if PASS_TEXT_RE.search(text):
        return "pass"
    return "unknown"


# Проектный L2-эквивалент (для проектов без юнит-тестов). Каждый проект может
# объявить свои команды-доказательства поведения в .claude/completion/config.json:
#   {"l2_evidence_patterns": ["compare-registers", "repost-runner\\.ts"]}
# Так путь для OneOfS (compare-registers / репост как слой 2) остаётся вне
# глобальной библиотеки — контракт вендор-нейтрален и настраивается per-project.
_L2_CACHE: dict = {}


def _project_l2_patterns(cwd: Path | None):
    if cwd is None:
        return []
    key = str(cwd)
    if key in _L2_CACHE:
        return _L2_CACHE[key]
    pats = []
    try:
        cfg = Path(cwd) / ".claude" / DIR_NAME / "config.json"
        if cfg.exists():
            data = json.loads(cfg.read_text(encoding="utf-8"))
            for p in data.get("l2_evidence_patterns", []) or []:
                try:
                    pats.append(re.compile(p, re.I))
                except Exception:
                    continue
    except Exception:
        pats = []
    _L2_CACHE[key] = pats
    return pats


def classify_bash(command: str, tool_response, cwd: Path | None = None) -> dict | None:
    """Одна Bash-команда -> один runtime-сигнал (или None, если не релевантно).

    cwd (опц.) включает проектные L2-паттерны из .claude/completion/config.json —
    доказательство поведения для проектов без юнит-тестов.
    """
    if not command:
        return None
    # VCS/сдача — не runtime-доказательство (см. VCS_LEAD_RE). Коммит и его
    # многострочное тело часто случайно матчат L2-паттерны; сбрасываем до
    # классификации, чтобы акт сдачи не считался проверкой.
    if VCS_LEAD_RE.search(command):
        return None
    text, code = _extract_output(tool_response)
    outcome = outcome_from(text, code)

    if TEST_RE.search(command) or any(rx.search(command) for rx in _project_l2_patterns(cwd)):
        kind, layer = "test_run", 2
    elif STATIC_RE.search(command):
        kind, layer = "static", 1
    elif APP_RE.search(command):
        kind, layer = "app_start", 3
    elif SIDE_EFFECT_RE.search(command):
        kind, layer = "side_effect", 0
    elif CLEANUP_RE.search(command):
        kind, layer = "cleanup", 0
    else:
        return None

    # короткая выжимка доказательства (последняя значимая строка)
    ev = ""
    for line in reversed(text.splitlines()):
        s = line.strip()
        if s:
            ev = s[:200]
            break

    return {
        "ts": now_iso(),
        "kind": kind,
        "layer": layer,
        "command": command[:300],
        "outcome": outcome,
        "evidence": ev,
    }


_LOCK_FAIL_LOGGED = False  # once-per-process: не спамить errors.log на каждый append


def append_signal(cwd: Path, session_id: str, sig: dict) -> None:
    sig = dict(sig)
    sig["session"] = str(session_id or "unknown")
    p = signals_path(cwd)
    # v1.75.0 (audit fix #2): append+trim are serialized through a DEDICATED
    # lock file. Locking the ledger itself would not survive the trim — the
    # atomic os.replace swaps the inode, and a concurrent writer holding the
    # old fd would append into the unlinked file (lost lines — exactly the
    # cross-session race the audit flagged). The lock file is never replaced.
    # Best-effort: if locking is unavailable, proceed unlocked as before —
    # but v1.76.0: the degradation is LOGGED (once per process), не молчит.
    global _LOCK_FAIL_LOGGED
    lock_f = None
    try:
        lock_f = (completion_dir(cwd) / (SIGNALS_FILE + ".lock")).open("a+", encoding="utf-8")
        if not _lock_file(lock_f) and not _LOCK_FAIL_LOGGED:
            _LOCK_FAIL_LOGGED = True
            log_persist_error(cwd, "append_signal.lock", RuntimeError(
                "advisory lock unavailable — append/trim proceeding unlocked"))
    except Exception:
        lock_f = None
    try:
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(sig, ensure_ascii=False) + "\n")
        # Amortized bound: keep the ledger from growing without limit. The size
        # gate keeps this O(1) per append — a full read+rewrite fires only once
        # the file crosses the soft cap (~every MAX_LEDGER_LINES appends), so
        # read_signals / the gate never parse an unbounded file. The rewrite is
        # atomic (audit fix #1): a crash mid-trim can no longer truncate the
        # ledger, and a failed trim is logged, not swallowed (audit fix #3).
        try:
            if p.stat().st_size > LEDGER_SOFT_BYTES:
                lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
                if len(lines) > MAX_LEDGER_LINES:
                    atomic_write_text(p, "\n".join(lines[-MAX_LEDGER_LINES:]) + "\n")
        except Exception as exc:
            log_persist_error(cwd, "append_signal.trim", exc)
    finally:
        if lock_f is not None:
            try:
                _unlock_file(lock_f)
                lock_f.close()
            except Exception:
                pass


def read_signals(cwd: Path, session_id: str | None) -> list:
    """Сигналы текущей сессии (или свежие в пределах SESSION_WINDOW_SEC)."""
    p = signals_path(cwd)
    if not p.exists():
        return []
    sid = str(session_id) if session_id else None
    cutoff = time.time() - SESSION_WINDOW_SEC
    out = []
    try:
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if sid is not None and rec.get("session") == sid:
                out.append(rec)
            elif sid is None:
                ts = rec.get("ts", "")
                try:
                    when = datetime.fromisoformat(ts).timestamp()
                except Exception:
                    when = 0
                if when >= cutoff:
                    out.append(rec)
    except Exception:
        return out
    return out


# ---------------------------------------------------------------------------
# Пункт 3 — «красные пометки» с инструкцией по исправлению
# ---------------------------------------------------------------------------

# (regex по тексту сбоя) -> конкретная инструкция «как чинить».
FIX_HINTS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"econnrefused|connection refused", re.I),
     "сервис/БД не подняты — запусти зависимость (docker compose up / dev-сервер) перед прогоном"),
    (re.compile(r"relation\s+\S+\s+does not exist|no such table", re.I),
     "нет таблицы — примени миграцию (prisma migrate / alembic upgrade) на тестовую БД"),
    (re.compile(r"cannot find module|module_not_found|modulenotfound", re.I),
     "не установлена зависимость — выполни npm install / pip install и повтори"),
    (re.compile(r"\berror\s+ts\d+", re.I),
     "ошибка типов TypeScript — проверь сигнатуры/импорты, затем tsc заново"),
    (re.compile(r"\b5\d\d\b|internal server error", re.I),
     "5xx от сервиса — проверь переменные окружения и конфиг сервиса (env, шаблоны, ключи)"),
    (re.compile(r"\b401\b|\b403\b|unauthorized|forbidden", re.I),
     "отказ авторизации — проверь токен/сессию/ключ доступа в конфиге теста"),
    (re.compile(r"timeout|timed out", re.I),
     "таймаут — увеличь ожидание готовности или дождись readiness-пробы перед проверкой"),
    (re.compile(r"assertionerror|expected .* (received|to be|but got)", re.I),
     "тест-ассерт не сошёлся — сверь ожидаемое/фактическое, поправь код или ожидание"),
    (re.compile(r"eaddrinuse|address already in use", re.I),
     "порт занят — освободи порт или укажи другой перед запуском приложения"),
    (re.compile(r"permission denied|eacces", re.I),
     "нет прав — проверь права на файл/каталог или запуск от нужного пользователя"),
]


def fix_for(text: str) -> str:
    for rx, hint in FIX_HINTS:
        if rx.search(text or ""):
            return hint
    return "прочитай последнюю строку вывода, определи корневую причину и устрани её, затем перезапусти проверку"


def red_mark(what: str, why: str, fix: str, path: str | None = None) -> str:
    """Формат «красной пометки учителя»: не просто крест, а как чинить."""
    tail = f" | FILE: {path}" if path else ""
    return f"FAILED: {what} | WHY: {why} | FIX: {fix}{tail}"


# ---------------------------------------------------------------------------
# Пункт 2 — трёхслойная валидация (L1 -> L2 -> L3, с блокировкой перехода)
# ---------------------------------------------------------------------------

def repo_has_tests(cwd: Path) -> bool:
    """Есть ли в репо тест-файлы (git ls-files, быстро, с таймаутом)."""
    try:
        res = subprocess.run(
            ["git", "ls-files"],
            cwd=str(cwd), capture_output=True, text=True, timeout=4,
        )
        if res.returncode != 0:
            return False
        rx = re.compile(
            r"(^|/)(tests?|spec|__tests__)/|\.(test|spec)\.[jt]sx?$|"
            r"(^|/)test_[^/]+\.py$|[^/]+_test\.(py|go)$|_spec\.rb$",
            re.I,
        )
        for line in res.stdout.splitlines():
            if rx.search(line):
                return True
    except Exception:
        return False
    return False


def _layer_status(signals: list, layer: int) -> tuple[str, str]:
    """(status, evidence) для слоя: pass | fail | unknown.

    Латест-на-команду: для каждой уникальной команды берём её ПОСЛЕДНИЙ прогон
    (сигналы дописываются по порядку). Так «фикс → повторный зелёный прогон той
    же команды» вытесняет прежний красный, но другой всё ещё падающий сьют
    сохраняет fail. Затем: любой fail среди latest -> fail; иначе pass если есть
    хоть один pass; иначе unknown.
    """
    rows = [s for s in signals if s.get("layer") == layer]
    if not rows:
        return "unknown", ""
    latest: dict = {}
    for s in rows:
        latest[s.get("command", "")] = s  # позднейший на команду перезаписывает
    vals = list(latest.values())
    fails = [s for s in vals if s.get("outcome") == "fail"]
    if fails:
        last = fails[-1]
        return "fail", f'{last.get("command","")} -> {last.get("evidence","")}'
    passes = [s for s in vals if s.get("outcome") == "pass"]
    if passes:
        return "pass", passes[-1].get("evidence", "")
    # только unknown-исходы — исполнялось, но результат неоднозначен
    return "unknown", vals[-1].get("evidence", "")


def compute_verdict(cwd: Path, signals: list) -> dict:
    """
    Трёхслойный вердикт с блокировкой перехода. Суждение выносится из
    ЗАПИСАННЫХ runtime-сигналов (экстернализация, пункт 1), а не из слов агента.

    Возвращает dict:
      {
        "ts", "layers": {"1":{status,evidence}, "2":{...}, "3":{...}},
        "has_tests": bool, "blocked": bool, "reason": str,
        "degraded": bool  # True => нет данных для суждения (best-effort деградация)
      }
    """
    # Проект, объявивший l2_evidence_patterns (compare-registers/репост в
    # config.json), ЗАЯВЛЯЕТ об отсутствии юнит-тестов — доказательство даёт
    # ручная сверка. Инцидентный матч generic-скана (случайный .spec./test-путь)
    # для него ложный, поэтому источник истины — декларация: real_tests подавляем.
    declared_l2 = bool(_project_l2_patterns(cwd))
    real_tests = False if declared_l2 else repo_has_tests(cwd)
    has_tests = real_tests or declared_l2
    l1s, l1e = _layer_status(signals, 1)
    l2s, l2e = _layer_status(signals, 2)
    l3s, l3e = _layer_status(signals, 3)

    verdict = {
        "ts": now_iso(),
        "has_tests": has_tests,
        "layers": {
            "1": {"name": "Синтаксис/статика", "status": l1s, "evidence": l1e},
            "2": {"name": "Runtime-поведение (тесты)", "status": l2s, "evidence": l2e},
            "3": {"name": "Системное подтверждение (e2e/smoke)", "status": l3s, "evidence": l3e},
        },
        "blocked": False,
        "degraded": False,
        "reason": "",
    }

    any_signal = bool(signals)

    # L1: если статика прогонялась и упала — блок (нельзя переходить к L2).
    if l1s == "fail":
        verdict["blocked"] = True
        verdict["reason"] = red_mark(
            "Слой 1 (статика) не пройден",
            l1e or "линт/сборка/типы вернули ошибку",
            fix_for(l1e),
        )
        return verdict

    # L2: тесты — основное доказательство завершения.
    if l2s == "fail":
        verdict["blocked"] = True
        verdict["reason"] = red_mark(
            "Слой 2 (тесты) не пройден",
            l2e or "прогон тестов завершился провалом",
            fix_for(l2e),
        )
        return verdict

    if has_tests and l2s == "unknown":
        if real_tests:
            # реальные юнит-тесты в репо есть, но в этой сессии не прогнаны —
            # классический признак преждевременной сдачи → жёсткий блок.
            verdict["blocked"] = True
            verdict["reason"] = red_mark(
                "Слой 2 (тесты) не подтверждён",
                "в репозитории есть тесты, но в этой сессии не зафиксирован их успешный прогон",
                "прогони тесты (npm test / pytest / go test …) — «код написан» ≠ «работает»",
            )
            return verdict
        # только объявленный L2 (compare-registers/репост) — ручная, привязанная
        # к конкретному диффу сверка. Знать, нужна ли она ИМЕННО этому диффу,
        # автоматически нельзя → advisory, а не false-блок каждого коммита
        # (в т.ч. docs/reports). Реальный провал L2 (l2s=="fail") перехвачен выше.
        verdict["degraded"] = True
        verdict["reason"] = (
            "Слой 2 для этого проекта — ручная сверка (compare-registers/"
            "репост). Если изменение затрагивает проведение документов — "
            "прогони сверку регистров с 1С; иначе обход осознанный."
        )
        return verdict

    # Нет ни одного runtime-сигнала за сессию — судить не на чем.
    # Best-effort invariant: деградируем в advisory, НЕ блокируем и НЕ зеленим.
    if not any_signal:
        verdict["degraded"] = True
        verdict["reason"] = (
            "Нет runtime-сигналов за сессию — завершение не подтверждено "
            "объективно. Прогони сборку/тесты/smoke, либо это тривиальное "
            "изменение (тогда обход осознанный)."
        )
        return verdict

    # Сигналы есть, ни один слой не в fail, L2 либо pass, либо тестов в репо нет.
    verdict["reason"] = "Слои пройдены по зафиксированным сигналам."
    # v1.66.0 (retro-2026-07-08 P2, advisory-only): зелёный L2 доказывает
    # happy-path, но не негативные ветки — A/B-эксперимент 2026-07-08 дал
    # правдивое «6/6 готово, тесты зелёные» при непроверенных error-ветках
    # (branch coverage 87% против 94% у дисциплинированного прогона).
    # Подсказка, не вето (best-effort invariant): гейт её только показывает.
    if l2s == "pass":
        verdict["advisory"] = (
            "L2 зелёный по прогнанным тестам. Advisory: у затронутых "
            "поведений есть ПРОГНАННЫЕ негативные сценарии (ошибки/битый "
            "вход)? Где есть coverage-тулинг — глянь branch coverage."
        )
    return verdict


def write_verdict(cwd: Path, verdict: dict) -> None:
    # v1.75.0 (audit fixes #1+#3): atomic replace — the gate can never read a
    # half-written verdict; a failed persist is logged, not swallowed.
    try:
        atomic_write_text(
            verdict_path(cwd), json.dumps(verdict, ensure_ascii=False, indent=2)
        )
    except Exception as exc:
        log_persist_error(cwd, "write_verdict", exc)
