#!/bin/sh
# itd_tool.sh <tool.py> [args...] - run an Idea to Deploy project tool from the INSTALLATION, never from a copy
# inside the project (INSTALL-OWNED-1): a copy that /adopt once placed in <project>/.itd/ freezes that project
# on an old version with no update channel. Lookup order: $ITD_TEMPLATES_DIR; the methodology source next to
# this helper (<root>/docs/templates/itd - the repository checkout and the Codex plugin); the Claude
# installation ($HOME/.claude/templates/itd). A legacy project copy runs only when no installation provides
# the tool, with a warning on stderr. The tools take the project from the current directory (--root .).
set -u
name="${1:-}"
case "$name" in
  itd_hygiene.py|itd_progress.py|check_contract_drift.py|itd_init_validate.py) ;;
  *) printf 'itd_tool: unknown tool "%s"\n' "$name" >&2; exit 2 ;;
esac
shift
here=$(cd "$(dirname "$0")" && pwd)
for dir in ${ITD_TEMPLATES_DIR:+"$ITD_TEMPLATES_DIR"} "$here/../../docs/templates/itd" "$HOME/.claude/templates/itd"; do
  if [ -f "$dir/$name" ]; then
    exec sh "$here/itd_py.sh" "$dir/$name" "$@"
  fi
done
if [ -f ".itd/$name" ]; then
  printf 'itd_tool: no installed %s; running the legacy project copy .itd/%s - update Idea to Deploy\n' "$name" "$name" >&2
  exec sh "$here/itd_py.sh" ".itd/$name" "$@"
fi
printf 'itd_tool: %s is not installed - install or update Idea to Deploy\n' "$name" >&2
exit 2
