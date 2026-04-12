#!/usr/bin/env bash
# =============================================================================
# run-fixture-headless.sh — v1.16.0 Phase 2 fixture runner
# -----------------------------------------------------------------------------
# Invokes Claude Code in non-interactive mode on a fixture's idea.md + a
# pre-seeded stream of clarification answers, captures the generated
# output, and validates it against the fixture's expected-snapshot.json
# via `tests/verify_snapshot.py`.
#
# This closes the loop from "manually run /kickstart and eyeball the
# output" to "one command produces ground truth AND validates it".
#
# Usage:
#   bash tests/run-fixture-headless.sh <fixture-name> [options]
#
# Example:
#   bash tests/run-fixture-headless.sh fixture-02-tg-bot
#   bash tests/run-fixture-headless.sh fixture-01-saas-clinic --model opus
#
# Options:
#   --model <name>     Override the default Sonnet model (opus / sonnet / haiku)
#   --budget <amount>  Max USD cap for this run (default: 10.00)
#   --output <dir>     Override output directory
#                      (default: <fixture-dir>/output/)
#   --keep-output      Do not delete the output dir after a passed run
#                      (default: keep on pass, rm on fail — opposite of normal)
#   --dry-run          Show the command that would run, do not execute
#
# Prerequisites:
# - `claude` CLI on PATH (Claude Code v2.1+)
# - Authenticated Claude Code session (subscription or ANTHROPIC_API_KEY)
# - The methodology's skills installed via `bash scripts/sync-to-active.sh`
#   (so ~/.claude/skills/ has the up-to-date skill set)
# - A `stream.jsonl` file inside the fixture directory with the
#   pre-seeded conversation. See tests/fixtures/fixture-02-tg-bot/
#   stream.jsonl.example for the format.
#
# Cost expectations (observed during v1.16.0 POC, Sonnet equiv pricing):
#   /blueprint-style fixture (6 docs, Lite mode): ~$1.50-$2.00
#   /kickstart-style fixture (7 docs, Full-ish): ~$3.00-$8.00 on Sonnet
#   /kickstart-style fixture on Opus: ~$8.00-$25.00
# Budget caps are enforced by --max-budget-usd and the scheduler.
# =============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURES_ROOT="$REPO_ROOT/tests/fixtures"

# Defaults
MODEL="sonnet"
BUDGET="10.00"
OUTPUT_DIR=""
KEEP_OUTPUT="0"
DRY_RUN="0"
FIXTURE_NAME=""

say()   { printf "\033[1;36m▶\033[0m %s\n" "$*"; }
ok()    { printf "\033[1;32m✓\033[0m %s\n" "$*"; }
warn()  { printf "\033[1;33m!\033[0m %s\n" "$*"; }
err()   { printf "\033[1;31m✗\033[0m %s\n" "$*" >&2; }

usage() {
  sed -n '3,45p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

# -----------------------------------------------------------------------------
# Parse arguments
# -----------------------------------------------------------------------------
if [ "$#" -lt 1 ]; then
  usage 1
fi

FIXTURE_NAME="$1"
shift

while [ "$#" -gt 0 ]; do
  case "$1" in
    --model)       MODEL="$2"; shift 2 ;;
    --budget)      BUDGET="$2"; shift 2 ;;
    --output)      OUTPUT_DIR="$2"; shift 2 ;;
    --keep-output) KEEP_OUTPUT="1"; shift ;;
    --dry-run)     DRY_RUN="1"; shift ;;
    -h|--help)     usage 0 ;;
    *) err "unknown option: $1"; usage 1 ;;
  esac
done

# -----------------------------------------------------------------------------
# Locate fixture + stream file
# -----------------------------------------------------------------------------
FIXTURE_DIR="$FIXTURES_ROOT/$FIXTURE_NAME"
if [ ! -d "$FIXTURE_DIR" ]; then
  err "fixture not found: $FIXTURE_DIR"
  err "available fixtures:"
  ls -1 "$FIXTURES_ROOT" | sed 's/^/  /'
  exit 1
fi

STREAM_FILE="$FIXTURE_DIR/stream.jsonl"
if [ ! -f "$STREAM_FILE" ]; then
  err "no stream.jsonl in $FIXTURE_DIR"
  err ""
  err "Create one with the full idea + pre-seeded clarifications. Format:"
  err '  {"type":"user","message":{"role":"user","content":"/kickstart <idea>\\n\\nPre-emptive clarifications: ..."}}'
  err ""
  err "See tests/fixtures/fixture-02-tg-bot/stream.jsonl for a working example."
  exit 1
fi

SNAPSHOT_FILE="$FIXTURE_DIR/expected-snapshot.json"
if [ ! -f "$SNAPSHOT_FILE" ]; then
  err "no expected-snapshot.json in $FIXTURE_DIR"
  err "add at least a {\"status\": \"pending\"} stub first"
  exit 1
fi

if [ -z "$OUTPUT_DIR" ]; then
  OUTPUT_DIR="$FIXTURE_DIR/output"
fi

# -----------------------------------------------------------------------------
# Safety: refuse to run in the methodology repo itself
# -----------------------------------------------------------------------------
# The /kickstart skill detects self-hosted context via .claude-plugin/
# plugin.json and enters strict mode. We avoid that by running Claude
# with --add-dir pointing at the OUTPUT dir and invoking it from OUTPUT
# dir, so cwd is not the repo root. This matches how v1.16.0 POC ran.

if [ ! -d "$OUTPUT_DIR" ]; then
  mkdir -p "$OUTPUT_DIR"
fi

# -----------------------------------------------------------------------------
# Print plan and (if not --dry-run) execute
# -----------------------------------------------------------------------------
say "fixture:   $FIXTURE_NAME"
say "stream:    $STREAM_FILE"
say "output:    $OUTPUT_DIR"
say "snapshot:  $SNAPSHOT_FILE"
say "model:     $MODEL"
say "budget:    \$$BUDGET"

CMD=(
  claude -p
  --input-format stream-json
  --output-format stream-json
  --verbose
  --no-session-persistence
  --model "$MODEL"
  --dangerously-skip-permissions
  --add-dir "$OUTPUT_DIR"
  --max-budget-usd "$BUDGET"
)

if [ "$DRY_RUN" = "1" ]; then
  warn "DRY RUN — command that would run:"
  echo "  cd $OUTPUT_DIR"
  echo "  cat $STREAM_FILE | ${CMD[*]}"
  exit 0
fi

# -----------------------------------------------------------------------------
# Execute headless run
# -----------------------------------------------------------------------------
say "Starting headless run (this may take several minutes)..."
STREAM_LOG="$OUTPUT_DIR/.run.stream.jsonl"

# shellcheck disable=SC2086
( cd "$OUTPUT_DIR" && cat "$STREAM_FILE" | "${CMD[@]}" ) > "$STREAM_LOG" 2>&1 || {
  EXIT_CODE=$?
  err "claude -p failed with exit code $EXIT_CODE"
  err "stream log: $STREAM_LOG"
  tail -20 "$STREAM_LOG" >&2
  exit $EXIT_CODE
}

# Extract total cost from the result event (last line of the stream)
COST=$(grep -o '"total_cost_usd":[0-9.]*' "$STREAM_LOG" | tail -1 | cut -d: -f2 || echo "?")
DURATION=$(grep -o '"duration_ms":[0-9]*' "$STREAM_LOG" | tail -1 | cut -d: -f2 || echo "?")
if [ -n "$DURATION" ] && [ "$DURATION" != "?" ]; then
  DURATION_S=$((DURATION / 1000))
else
  DURATION_S="?"
fi

ok "Headless run finished"
say "cost:      \$$COST (equiv pay-as-you-go)"
say "duration:  ${DURATION_S}s"

# -----------------------------------------------------------------------------
# Validate output against snapshot
# -----------------------------------------------------------------------------
say "Validating output against snapshot..."
if python3 "$REPO_ROOT/tests/verify_snapshot.py" "$FIXTURE_DIR" --output "$OUTPUT_DIR"; then
  ok "$FIXTURE_NAME: PASSED"
  if [ "$KEEP_OUTPUT" = "0" ]; then
    say "Removing output dir (use --keep-output to preserve)"
    rm -rf "$OUTPUT_DIR"
  fi
  exit 0
else
  err "$FIXTURE_NAME: FAILED validation"
  err "output preserved at: $OUTPUT_DIR"
  err "stream log:          $STREAM_LOG"
  exit 1
fi
