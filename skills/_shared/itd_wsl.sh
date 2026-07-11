#!/bin/sh
# itd_wsl.sh — надёжный мост Windows Git Bash -> WSL (v1.84.0, retro 2026-07-11 W1).
#
# Проблема (грабли, воспроизведены x3 за 2026-07-11): inline-команды через
# `wsl -d <distro> -- sh -c '...'` из Git Bash мнутся по дороге — MSYS
# конвертирует ведущие /пути в C:/Program Files/Git/..., подстановки $(...) и
# wildcard'ы дают ложные нули/ошибки. Рабочая практика была «только
# скрипт-файлом» (RELEASE_RUNBOOK) — этот хелпер её механизирует: команда
# уезжает в WSL как base64-строка (MSYS её не трогает) и декодируется уже там.
#
# Использование (с Windows Git Bash; на Linux/WSL-хосте честно откажет):
#   sh "$SHD/itd_wsl.sh" 'cd ~/projects/x && ls skills | wc -l'
#   sh "$SHD/itd_wsl.sh" -d Ubuntu-24.04 'git -C ~/projects/x status'
#   sh "$SHD/itd_wsl.sh" -f local-script.sh     # содержимое файла -> WSL sh
# Exit-код — код команды в WSL.
set -u
DISTRO="${ITD_WSL_DISTRO:-Ubuntu-24.04}"
if [ "${1:-}" = "-d" ]; then
  DISTRO="$2"
  shift 2
fi
if ! command -v wsl.exe >/dev/null 2>&1; then
  echo "itd_wsl.sh: wsl.exe недоступен — хелпер только для Windows-хоста" >&2
  exit 2
fi
if [ "${1:-}" = "-f" ]; then
  [ -f "${2:-}" ] || { echo "itd_wsl.sh: файл не найден: ${2:-}" >&2; exit 2; }
  CMDS=$(cat "$2")
else
  CMDS="${1:-}"
fi
if [ -z "$CMDS" ]; then
  echo "usage: sh itd_wsl.sh [-d distro] 'commands…' | [-d distro] -f script.sh" >&2
  exit 2
fi
ENC=$(printf '%s' "$CMDS" | base64 | tr -d '\r\n')
exec wsl.exe -d "$DISTRO" -- sh -c "printf '%s' '$ENC' | base64 -d | sh"
