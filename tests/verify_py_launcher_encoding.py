#!/usr/bin/env python3
"""verify_py_launcher_encoding.py — кодировочный контракт запускателя itd_py.sh (v1.85.0).

Live-провал 2026-07-11 (диагностическая петля, итерация 4): itd_py.sh корректно
выбирал интерпретатор, но не форсировал UTF-8 для stdio — на Windows-консоли
cp1251 любой print символа вне cp1251 (например «→» U+2192) ронял скрипт с
UnicodeEncodeError. Контракт: запускатель отвечает за среду целиком.

Проверки:
  1. static  — itd_py.sh экспортирует PYTHONIOENCODING и PYTHONUTF8;
  2. default — при неустановленных переменных дочерний python видит
               PYTHONIOENCODING=utf-8, PYTHONUTF8=1;
  3. override— явно заданное вызывающим значение НЕ перетирается;
  4. smoke   — print("→") через запускатель завершается rc=0 и отдаёт стрелку
               (на Linux проходит и без фикса — поведенческая точка для Windows
               ловится в windows-verify; здесь гард от регресса семантики).
"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAUNCHER = os.path.join(ROOT, "skills", "_shared", "itd_py.sh")

fails = []


def check(name, cond, detail=""):
    if not cond:
        fails.append(name)
        print(f"FAIL {name} {detail}")
    else:
        print(f"ok   {name}")


def run(args, env_patch=None, drop=()):
    env = {k: v for k, v in os.environ.items() if k not in drop}
    if env_patch:
        env.update(env_patch)
    return subprocess.run(
        ["sh", LAUNCHER] + args,
        capture_output=True, text=True, env=env, timeout=60,
    )


# 1. static: экспорт присутствует в тексте запускателя
with open(LAUNCHER, encoding="utf-8") as f:
    src = f.read()
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

if fails:
    print("FAILED:", " ".join(fails))
    sys.exit(1)
print("verify_py_launcher_encoding: all ok")
