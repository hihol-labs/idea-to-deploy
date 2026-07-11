#!/bin/sh
# itd_py.sh — кросс-платформенный запуск python-скриптов из inline-сниппетов скиллов.
#
# Проблема (live-инцидент 2026-07-11): на Windows Git Bash `python`/`python3`
# указывают на WindowsApps-шим (Store-заглушка) — вызов «выполняется», но
# печатает мусор вместо результата. Хуки защищены захардкоженным путём
# (ITD_WIN_PYTHON в settings.json при sync-to-active), inline-сниппеты
# скиллов (`python3 script.py ...`) — нет.
#
# Использование (запускатель, а не принтер пути — пути с пробелами вроде
# C:/Program Files/... остаются корректно закавыченными, находка ревью #154):
#   sh "$RT/itd_py.sh" "$RT/script.py" args...
# Без аргументов — печатает выбранный интерпретатор (диагностика).
# Порядок выбора: $ITD_WIN_PYTHON -> python3/python вне WindowsApps -> py -3
# -> python3 (fail loud).
set -u

pick() {
  if [ -n "${ITD_WIN_PYTHON:-}" ] && [ -x "$ITD_WIN_PYTHON" ]; then
    printf '%s\n' "$ITD_WIN_PYTHON"
    return 0
  fi
  for c in python3 python; do
    p=$(command -v "$c" 2>/dev/null) || continue
    case "$p" in
      *WindowsApps*) continue ;;
    esac
    printf '%s\n' "$p"
    return 0
  done
  return 1
}

PYBIN=$(pick) || PYBIN=""

if [ $# -eq 0 ]; then
  # Диагностический режим: показать, что было бы выбрано.
  if [ -n "$PYBIN" ]; then
    printf '%s\n' "$PYBIN"
  elif command -v py >/dev/null 2>&1; then
    echo "py -3"
  else
    echo "python3"
  fi
  exit 0
fi

if [ -n "$PYBIN" ]; then
  exec "$PYBIN" "$@"
fi
if command -v py >/dev/null 2>&1; then
  exec py -3 "$@"
fi
# Ничего пригодного: python3, чтобы вызов упал с внятной ошибкой, а не молча
# ушёл в шим.
exec python3 "$@"
