#!/bin/sh
# itd_project_checks.sh — first-class слот project-level проверок (v1.87.0).
#
# Происхождение (retro 2026-07-11, сет-3, упр.2): архитектурные правила проекта
# (BigInt-сериализация, номера миграций, …) конвертируются в исполняемые
# проверки с agent-oriented сообщениями, но у методологии не было штатного
# места для них — интеграцию изобретали ad-hoc. Контракт:
#
#   Проверки живут в <root>/.itd/checks/* и диспатчатся по расширению:
#     *.sh → sh, *.mjs|*.js → node, *.py → itd_py.sh (обход WindowsApps-шима).
#   Изменённые файлы передаются через env ITD_CHANGED_FILES (разделитель \n);
#   проверка сама решает, учитывать ли скоуп (opt-in, whole-repo — валидно).
#   Провал ЛЮБОЙ проверки → exit 1 с её выводом (сообщения проверок обязаны
#   быть agent-oriented: WHY + FIX + file:line — см. docs/project-checks.md).
#
# Использование:
#   sh itd_project_checks.sh [--root DIR] [--list] [--files f1 f2 ...]
# Нет .itd/checks/ или пусто → exit 0 (no-op: слот opt-in).
set -u

ROOT="."
LIST=0
FILES=""
while [ $# -gt 0 ]; do
  case "$1" in
    --root) ROOT="$2"; shift 2 ;;
    --list) LIST=1; shift ;;
    --files) shift; while [ $# -gt 0 ]; do FILES="$FILES$1
"; shift; done ;;
    *) echo "itd_project_checks: unknown arg $1" >&2; exit 2 ;;
  esac
done

DIR="$ROOT/.itd/checks"
[ -d "$DIR" ] || { [ "$LIST" = "1" ] && exit 0; echo "itd_project_checks: no $DIR — no-op"; exit 0; }

SHD_SELF="$(dirname "$0")"
ITD_CHANGED_FILES="$FILES"
export ITD_CHANGED_FILES

fails=""
found=0
for c in "$DIR"/*; do
  [ -f "$c" ] || continue
  base=$(basename "$c")
  case "$base" in
    *.sh) runner="sh" ;;
    *.mjs|*.js) runner="node" ;;
    *.py) runner="itd_py" ;;
    *) continue ;;
  esac
  found=$((found + 1))
  if [ "$LIST" = "1" ]; then
    echo "$base"
    continue
  fi
  echo "── project check: $base"
  case "$runner" in
    sh)  out=$(sh "$c" 2>&1); rc=$? ;;
    node)
      if command -v node >/dev/null 2>&1; then
        out=$(node "$c" --root "$ROOT" 2>&1); rc=$?
      else
        out="node не найден — проверка $base НЕ ПРОВЕРЕНА"; rc=0
        echo "$out"
      fi ;;
    itd_py) out=$(sh "$SHD_SELF/itd_py.sh" "$c" 2>&1); rc=$? ;;
  esac
  if [ "$rc" -ne 0 ]; then
    printf '%s\n' "$out"
    fails="$fails $base"
  else
    printf '%s\n' "$out" | tail -1
  fi
done

[ "$LIST" = "1" ] && exit 0
if [ "$found" = "0" ]; then
  echo "itd_project_checks: $DIR пуст — no-op"
  exit 0
fi
if [ -n "$fails" ]; then
  echo ""
  echo "itd_project_checks: FAIL —$fails (сообщения выше: WHY + FIX per находка)"
  exit 1
fi
echo "itd_project_checks: OK ($found проверок)"
exit 0
