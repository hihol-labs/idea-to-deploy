#!/usr/bin/env python3
"""verify_no_bare_python3.py — positional-гейт: в bash/sh-фенсах skills/**/*.md
нет голого `python3`/`python`-вызова (v1.83.0, retro 2026-07-11 P2).

Порядок: на Windows Git Bash `python`/`python3` указывают на WindowsApps-шим
(Store-заглушку) — вызов падает (exit 49) либо, под пайпом, молча отдаёт мусор
(live-инцидент 2026-07-11: Step 1 /retro печатал «Python» вместо скана).
Функциональные вызовы python-скриптов в сниппетах идут ТОЛЬКО через запускатель
`skills/_shared/itd_py.sh`; осознанно-легитимные исключения (fallback-цепочки
до `py -3`/`/tmp`, команды под окружение проекта пользователя, probes)
помечаются маркером `win-ok` на той же строке.

Скоуп: fenced-блоки ```bash / ```sh / ```shell / ``` (без языка) в skills/**/*.md.
ASCII-safe вывод, stdlib only. Exit 0 — чисто, 1 — есть голые вызовы, 2 — сбой.

Консолидация LPD003-4: сюда же перенесены проверки бывшего
verify_py_launcher_encoding (тот же предмет — запускатель
skills/_shared/itd_py.sh, v1.85.0): static-экспорт PYTHONIOENCODING/PYTHONUTF8,
default-env для дочернего python, уважение override вызывающего, smoke-печать
не-ASCII через запускатель.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"

FENCE_OPEN_RE = re.compile(r"^```([A-Za-z0-9_-]*)\s*$")
SHELL_LANGS = {"", "bash", "sh", "shell", "console"}
# голый интерпретатор: python/python3/python3.11 как команда (после начала
# строки, |, ;, &&, ||, $(, ` или пробела), не часть пути/слова. Version-pinned
# варианты включены (minor ревью #155: python3.11 обходил гейт)
BARE_RE = re.compile(r"(^|[\s;|&`(])(python[23]?(?:\.\d+)?)(\s|$)")


def scan_file(md: Path) -> list[str]:
    hits: list[str] = []
    in_fence = False
    fence_lang = ""
    try:
        lines = md.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise RuntimeError(f"cannot read {md}: {exc}")
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        if not in_fence:
            m = FENCE_OPEN_RE.match(stripped)
            if m:
                in_fence = True
                fence_lang = m.group(1).lower()
            continue
        if stripped.startswith("```"):
            in_fence = False
            fence_lang = ""
            continue
        if fence_lang not in SHELL_LANGS:
            continue
        if "win-ok" in line or "itd_py.sh" in line:
            continue
        if stripped.startswith("#"):
            continue
        # trailing-комментарий — не код (minor ревью #155: строка вида
        # `cmd  # calls python3 internally` давала бы FP)
        code_part = line.split(" #", 1)[0]
        if BARE_RE.search(code_part):
            rel = md.relative_to(ROOT).as_posix()
            hits.append(f"{rel}:{lineno}: {stripped[:110]}")
    return hits


# --- Перенесено из verify_py_launcher_encoding (LPD003-4) -------------------
# Кодировочный контракт запускателя itd_py.sh (v1.85.0). Live-провал
# 2026-07-11 (диагностическая петля, итерация 4): itd_py.sh корректно выбирал
# интерпретатор, но не форсировал UTF-8 для stdio — на Windows-консоли cp1251
# любой print символа вне cp1251 (например U+2192) ронял скрипт с
# UnicodeEncodeError. Контракт: запускатель отвечает за среду целиком.

LAUNCHER = ROOT / "skills" / "_shared" / "itd_py.sh"


def launcher_encoding_checks() -> list[str]:
    fails: list[str] = []

    def check(name, cond, detail=""):
        if not cond:
            fails.append(name)
            print(f"FAIL launcher-encoding/{name} {detail}")
        else:
            print(f"ok   launcher-encoding/{name}")

    def run(args, env_patch=None, drop=()):
        env = {k: v for k, v in os.environ.items() if k not in drop}
        if env_patch:
            env.update(env_patch)
        return subprocess.run(
            ["sh", str(LAUNCHER)] + args,
            capture_output=True, text=True, env=env, timeout=60,
        )

    # 1. static: экспорт присутствует в тексте запускателя
    src = LAUNCHER.read_text(encoding="utf-8")
    check("static-export", "export PYTHONIOENCODING PYTHONUTF8" in src)

    # 2. default: дочерний python видит utf-8/1 при неустановленных переменных
    r = run(["-c", "import os;print(os.environ.get('PYTHONIOENCODING'),os.environ.get('PYTHONUTF8'))"],
            drop=("PYTHONIOENCODING", "PYTHONUTF8"))
    check("default-env", r.returncode == 0 and r.stdout.strip() == "utf-8 1",
          f"rc={r.returncode} out={r.stdout.strip()!r} err={r.stderr[-200:]!r}")

    # 3. override: значение вызывающего уважается
    r = run(["-c", "import os;print(os.environ.get('PYTHONIOENCODING'))"],
            env_patch={"PYTHONIOENCODING": "latin-1"})
    check("caller-override", r.returncode == 0 and r.stdout.strip() == "latin-1",
          f"rc={r.returncode} out={r.stdout.strip()!r}")

    # 4. smoke: не-ASCII печать через запускатель
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tf:
        tf.write('print("\\u2192 ok")\n')
        probe = tf.name
    try:
        r = run([probe], drop=("PYTHONIOENCODING", "PYTHONUTF8"))
        check("smoke-arrow-print", r.returncode == 0 and "→" in r.stdout,
              f"rc={r.returncode} out={r.stdout!r} err={r.stderr[-200:]!r}")
    finally:
        os.unlink(probe)

    return fails


def main() -> int:
    if not SKILLS.is_dir():
        print("FAIL: skills/ not found")
        return 2
    fails: list[str] = []
    n_files = 0
    for md in sorted(SKILLS.rglob("*.md")):
        n_files += 1
        try:
            fails.extend(scan_file(md))
        except RuntimeError as exc:
            print(f"FAIL: {exc}")
            return 2
    # Обе секции исполняются ВСЕГДА (находка чекера claim1: ранний return на
    # красном скане скрывал бы донорские launcher-проверки — до консолидации
    # это были два независимых процесса, оба сигнала обязаны выживать).
    enc_fails = launcher_encoding_checks()
    if fails:
        print(f"FAIL verify_no_bare_python3: {len(fails)} bare python call(s) "
              f"in fenced shell blocks (use skills/_shared/itd_py.sh or mark win-ok):")
        for f in fails:
            print("  " + f)
    if enc_fails:
        print("FAILED launcher-encoding:", " ".join(enc_fails))
    if fails or enc_fails:
        return 1
    print(f"PASS verify_no_bare_python3: {n_files} md files scanned, 0 bare python calls; "
          f"launcher encoding contract ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
