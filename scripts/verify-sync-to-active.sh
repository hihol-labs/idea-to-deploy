#!/usr/bin/env bash
# =============================================================================
# Idea-to-Deploy — verify that every hook in hooks/ is registered in
# scripts/sync-to-active.sh (or explicitly exempted).
# -----------------------------------------------------------------------------
# Closes the gap where new hooks land in the repo but never propagate to the
# user-level install (see v1.19.1 check-review-before-commit.sh — shipped in
# PR #42 but missed by sync-to-active until v1.20.1).
#
# Exit codes:
#   0 — every hook is either registered in DESIRED_HOOKS or on the allow-list
#   1 — drift detected (a new hook was added without updating sync-to-active)
#
# Usage:
#   bash scripts/verify-sync-to-active.sh          # fail on drift
#   bash scripts/verify-sync-to-active.sh --list   # show status for every hook
#
# Wired into CI via .github/workflows/meta-review.yml.
# =============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOKS_DIR="$REPO_ROOT/hooks"
SYNC_SCRIPT="$REPO_ROOT/scripts/sync-to-active.sh"
LIST_MODE=0

if [ "${1:-}" = "--list" ]; then
  LIST_MODE=1
fi

# Hooks that are intentionally NOT registered in sync-to-active.sh.
# These are experimental / opt-in — users enable them manually if they want.
# If you add a new canonical hook, DO NOT put it here — add it to
# DESIRED_HOOKS in sync-to-active.sh instead.
EXEMPT=(
  "careful.sh"           # opt-in per-command caution messages
  "context-aware.sh"     # experimental context-rot detection
  "cost-tracker.sh"      # optional cost telemetry
  "crash-recovery.sh"    # manual inspection checkpoint, no consumer yet
  "freeze.sh"            # opt-in freeze-on-mistake
  "stuck-detection.sh"   # experimental stuck-session detection
)

is_exempt() {
  local name="$1"
  for e in "${EXEMPT[@]}"; do
    [ "$e" = "$name" ] && return 0
  done
  return 1
}

is_registered() {
  local name="$1"
  grep -q "~/\.claude/hooks/${name}" "$SYNC_SCRIPT"
}

status=0
registered=0
exempt=0
missing=0

for hook in "$HOOKS_DIR"/*.sh; do
  name="$(basename "$hook")"
  if is_registered "$name"; then
    [ "$LIST_MODE" = "1" ] && printf "  \033[1;32m✓\033[0m registered   %s\n" "$name"
    registered=$((registered + 1))
  elif is_exempt "$name"; then
    [ "$LIST_MODE" = "1" ] && printf "  \033[1;33m~\033[0m exempt       %s\n" "$name"
    exempt=$((exempt + 1))
  else
    printf "\033[1;31m✗\033[0m DRIFT        %s — not in DESIRED_HOOKS of sync-to-active.sh AND not on the EXEMPT list.\n" "$name" >&2
    printf "  Fix: either register it in scripts/sync-to-active.sh (DESIRED_HOOKS block) or add it to EXEMPT in scripts/verify-sync-to-active.sh with a justification comment.\n" >&2
    missing=$((missing + 1))
    status=1
  fi
done

if [ "$LIST_MODE" = "1" ] || [ "$status" != "0" ]; then
  echo ""
  printf "Summary: %d registered, %d exempt, %d drift.\n" "$registered" "$exempt" "$missing"
fi

if [ "$status" = "0" ] && [ "$LIST_MODE" != "1" ]; then
  printf "\033[1;32m✓\033[0m sync-to-active drift check: OK (%d registered + %d exempt).\n" "$registered" "$exempt"
fi

exit $status
