#!/usr/bin/env python3
"""Init-валидатор: доказывает, что инициализация проекта воспроизводима с нуля.

Проблема (аудит инициализации 2026-07-08, эл. 1): Initialization Acceptance
Checklist в /kickstart Phase 3 был self-asserted — агент ставил галочки
«bootstrap from scratch succeeds» и «commands.test passes» по собственному
суждению, ничто не исполняло эти команды в чистом окружении. /adopt для
brownfield-проектов запускаемость не проверял вообще.

Этот скрипт закрывает дыру исполняемо: клонирует репозиторий в ИЗОЛИРОВАННУЮ
временную директорию (git clone --local => только закоммиченное состояние,
никакого мусора рабочего дерева) и прогоняет там bootstrap- и test-команды.
Зелёный выход = «фундамент залит и столб держит вес» доказаны прогоном,
а не галочкой.

Механика (вендор-нейтральная, stdlib-only):
  - `git clone --local --no-hardlinks <root> <tmp>` — изолированная копия.
  - bootstrap-команда (напр. `make setup` / `npm ci` / `pip install -e .`)
    исполняется в клоне; ненулевой выход => FAILED c пометкой WHY + FIX.
  - test-команда (напр. `make test` / `pytest` / `npm test`) исполняется
    после зелёного bootstrap; лестница L1->L2 не перепрыгивается.
  - Грязное рабочее дерево => предупреждение: незакоммиченное НЕ проверяется
    (валидатор отвечает на вопрос «поднимется ли проект с чистого клона»).

Advisory по умолчанию для людей, gate для скиллов: /kickstart Phase 3 не
переходит к Phase 4 при exit != 0; /adopt репортит результат как runnability
check. При провале временный клон СОХРАНЯЕТСЯ и его путь печатается — для
разбора. `--selftest` строит одноразовый git-репо и проверяет позитивный и
негативный сценарии самим прогоном (никаких моков).

Usage:
  python3 .itd/itd_init_validate.py --bootstrap "make setup" --test "make test"
  python3 .itd/itd_init_validate.py --selftest
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_TIMEOUT_SEC = 900  # bootstrap на холодном кэше бывает долгим
OUTPUT_TAIL_CHARS = 2000


def run(cmd: list[str] | str, cwd: Path, timeout: int, shell: bool = False) -> tuple[int, str]:
    """Исполнить команду, вернуть (returncode, объединённый вывод). Никогда не бросает."""
    try:
        res = subprocess.run(
            cmd, cwd=str(cwd), shell=shell, capture_output=True, text=True, timeout=timeout,
        )
        out = (res.stdout or "") + (res.stderr or "")
        return res.returncode, out
    except subprocess.TimeoutExpired as e:
        out = ((e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or ""))
        return 124, out + f"\n[timeout {timeout}s]"
    except Exception as e:  # git/интерпретатор отсутствует и т.п.
        return 127, f"[exec error] {e}"


def tail(text: str) -> str:
    text = text.strip()
    return text[-OUTPUT_TAIL_CHARS:] if len(text) > OUTPUT_TAIL_CHARS else text


def fail_mark(what: str, rc: int, output: str, fix: str) -> None:
    """Красная пометка учителя — контрактный формат WHY + FIX (см. completion gate)."""
    print(f"FAILED: {what} | WHY: exit {rc} | FIX: {fix}")
    t = tail(output)
    if t:
        print("--- вывод (хвост) ---")
        print(t)
        print("---------------------")


def repo_root(start: Path) -> Path | None:
    rc, out = run(["git", "rev-parse", "--show-toplevel"], cwd=start, timeout=10)
    if rc != 0 or not out.strip():
        return None
    return Path(out.strip().splitlines()[0])


def worktree_dirty(root: Path) -> bool:
    rc, out = run(["git", "status", "--porcelain"], cwd=root, timeout=10)
    return rc == 0 and bool(out.strip())


def validate(root: Path, bootstrap: str, test: str, timeout: int, keep: bool,
             workdir: Path | None = None) -> int:
    """Клонировать root в tmp, прогнать bootstrap затем test. 0 = обе зелёные.

    workdir — переопределить временную директорию (selftest передаёт свою,
    чтобы прибрать клон и после негативного сценария).
    """
    if worktree_dirty(root):
        print("⚠ Рабочее дерево грязное: валидируется ТОЛЬКО закоммиченное состояние "
              "(git clone берёт HEAD). Незакоммиченные файлы в проверку не попадают.")

    tmp = workdir or Path(tempfile.mkdtemp(prefix="itd-init-validate-"))
    tmp.mkdir(parents=True, exist_ok=True)
    # уникальная пустая директория под клон (повторные прогоны в одном workdir)
    clone = Path(tempfile.mkdtemp(prefix="clone-", dir=str(tmp)))
    rc, out = run(["git", "clone", "--local", "--no-hardlinks", str(root), str(clone)],
                  cwd=root, timeout=120)
    if rc != 0:
        fail_mark("git clone (изолированная копия)", rc, out,
                  "проверь, что репозиторий имеет хотя бы один коммит (git log)")
        if workdir is None:
            shutil.rmtree(tmp, ignore_errors=True)
        return 1

    print(f"Изолированный клон: {clone}")
    print(f"[1/2] bootstrap: {bootstrap}")
    rc, out = run(bootstrap, cwd=clone, timeout=timeout, shell=True)
    if rc != 0:
        fail_mark("bootstrap в чистом клоне", rc, out,
                  "почини команду установки/зависимости; частые причины — файл не "
                  "закоммичен (есть только в рабочем дереве), захардкоженный путь, "
                  "отсутствующий .env (нужен .env.example + генерация)")
        print(f"Клон сохранён для разбора: {clone}")
        return 1
    print("  ok — окружение поднимается с нуля")

    print(f"[2/2] test: {test}")
    rc, out = run(test, cwd=clone, timeout=timeout, shell=True)
    if rc != 0:
        fail_mark("test в чистом клоне", rc, out,
                  "прогони команду локально; если тестов ещё нет — сначала example "
                  "test (столб должен держать вес до бизнес-кода)")
        print(f"Клон сохранён для разбора: {clone}")
        return 1
    print("  ok — тестовый каркас держит вес")

    if keep:
        print(f"PASS. Клон оставлен (--keep): {clone}")
    else:
        shutil.rmtree(clone if workdir is not None else tmp, ignore_errors=True)
        print("PASS. Инициализация воспроизводима: bootstrap + test зелёные в чистом клоне.")
    return 0


def selftest() -> int:
    """Строит одноразовый git-репо и проверяет позитив + негатив реальным прогоном."""
    rc, _ = run(["git", "--version"], cwd=Path.cwd(), timeout=10)
    if rc != 0:
        print("SKIP: git недоступен — selftest не исполняется (advisory).")
        return 0

    tmp = Path(tempfile.mkdtemp(prefix="itd-init-selftest-"))
    repo = tmp / "repo"
    repo.mkdir(parents=True)
    ok = True
    try:
        for cmd in (["git", "init", "-q"],
                    ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit",
                     "--allow-empty", "-q", "-m", "init"]):
            rc, out = run(cmd, cwd=repo, timeout=30)
            if rc != 0:
                print(f"SKIP: не удалось подготовить тест-репо ({out.strip()[:120]}).")
                return 0

        py = sys.executable or "python3"
        got = validate(repo, bootstrap=f'"{py}" -c "print(1)"',
                       test=f'"{py}" -c "import sys; sys.exit(0)"',
                       timeout=60, keep=False, workdir=tmp)
        p = got == 0
        ok = ok and p
        print(("  OK  " if p else " FAIL "), f"позитив: bootstrap+test зелёные -> exit {got} (exp 0)")

        got = validate(repo, bootstrap=f'"{py}" -c "print(1)"',
                       test=f'"{py}" -c "import sys; sys.exit(3)"',
                       timeout=60, keep=False, workdir=tmp)
        p = got == 1
        ok = ok and p
        print(("  OK  " if p else " FAIL "), f"негатив: красный test -> exit {got} (exp 1)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("SELFTEST:", "ALL PASS" if ok else "FAILED")
    return 0 if ok else 1


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Исполняемая проверка инициализации: bootstrap + test в изолированном клоне.")
    ap.add_argument("--bootstrap", help='команда подъёма окружения с нуля (напр. "make setup")')
    ap.add_argument("--test", help='команда прогона тестов (напр. "make test")')
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SEC,
                    help=f"таймаут на команду, сек (default {DEFAULT_TIMEOUT_SEC})")
    ap.add_argument("--keep", action="store_true", help="не удалять клон при PASS")
    ap.add_argument("--selftest", action="store_true", help="самопроверка на одноразовом репо")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(selftest())
    if not args.bootstrap or not args.test:
        ap.error("--bootstrap и --test обязательны (или --selftest)")

    root = repo_root(Path.cwd())
    if root is None:
        print("SKIP: не git-репозиторий — валидатору нечего клонировать (advisory).")
        sys.exit(0)
    sys.exit(validate(root, args.bootstrap, args.test, args.timeout, args.keep))


if __name__ == "__main__":
    main()
