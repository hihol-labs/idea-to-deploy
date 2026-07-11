#!/bin/sh
# itd_py.sh — кросс-платформенный резолвер python-интерпретатора для inline-сниппетов скиллов.
#
# Проблема (live-инцидент 2026-07-11): на Windows Git Bash `python`/`python3`
# указывают на WindowsApps-шим (Store-заглушка) — вызов «выполняется», но
# печатает мусор вместо результата. Хуки защищены захардкоженным путём
# (ITD_WIN_PYTHON в settings.json при sync-to-active), inline-сниппеты
# скиллов (`python3 script.py ...`) — нет.
#
# Печатает пригодную python-команду. Использование в сниппете:
#   PY=$(sh "$RT/itd_py.sh"); $PY "$RT/script.py" ...
# Порядок: $ITD_WIN_PYTHON -> python3/python вне WindowsApps -> py -3 -> python3 (fail loud).
set -u
if [ -n "${ITD_WIN_PYTHON:-}" ] && [ -x "$ITD_WIN_PYTHON" ]; then
  echo "$ITD_WIN_PYTHON"
  exit 0
fi
for c in python3 python; do
  p=$(command -v "$c" 2>/dev/null) || continue
  case "$p" in
    *WindowsApps*) continue ;;
  esac
  echo "$p"
  exit 0
done
if command -v py >/dev/null 2>&1; then
  echo "py -3"
  exit 0
fi
# Ничего пригодного: печатаем python3, чтобы вызов упал с внятной ошибкой,
# а не молча ушёл в шим.
echo "python3"
