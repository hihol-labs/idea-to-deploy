#!/usr/bin/env bash
# =============================================================================
# Idea-to-Deploy — Sync methodology repo → active install (~/.claude/)
# -----------------------------------------------------------------------------
# Copies skills, hooks, and settings from this repo into the user's active
# Claude Code install so that every update to the methodology propagates
# without manual copy-paste. Idempotent: safe to run repeatedly.
#
# Usage (from the repo root):
#   bash scripts/sync-to-active.sh           # sync all
#   bash scripts/sync-to-active.sh --check   # dry-run, report drift only
#
# What it syncs:
#   1. skills/*              → ~/.claude/skills/
#   2. hooks/*.sh            → ~/.claude/hooks/
#   3. settings.json hooks   → registers all 4 hooks with correct matchers
#
# What it does NOT touch:
#   - ~/.claude/settings.json keys other than "hooks" (env, permissions, etc.)
#   - ~/.claude/projects/* (per-project memory)
#   - ~/.claude/CLAUDE.md
#
# Safety:
#   - Always backs up settings.json to settings.json.bak-<timestamp> before edit
#   - --check mode makes zero changes and reports what would be different
# =============================================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACTIVE="${CLAUDE_HOME:-$HOME/.claude}"
DRY_RUN=0

if [ "${1:-}" = "--check" ]; then
  DRY_RUN=1
fi

say()   { printf "\033[1;36m▶\033[0m %s\n" "$*"; }
ok()    { printf "\033[1;32m✓\033[0m %s\n" "$*"; }
warn()  { printf "\033[1;33m!\033[0m %s\n" "$*"; }
err()   { printf "\033[1;31m✗\033[0m %s\n" "$*" >&2; }

# Sanity check: we must be inside the methodology repo
if [ ! -f "$REPO_ROOT/.claude-plugin/plugin.json" ]; then
  err "Not inside an Idea-to-Deploy repo (missing .claude-plugin/plugin.json)"
  err "Expected repo root: $REPO_ROOT"
  exit 1
fi

if [ ! -d "$ACTIVE" ]; then
  err "Active install not found: $ACTIVE"
  err "Create it first or set CLAUDE_HOME."
  exit 1
fi

if [ "$DRY_RUN" = "1" ]; then
  warn "DRY RUN — no changes will be made"
fi

# -----------------------------------------------------------------------------
# Step 1/4: Sync skills
# -----------------------------------------------------------------------------
say "Step 1/4: skills/"
mkdir -p "$ACTIVE/skills"

added=0
updated=0
unchanged=0

for src_skill in "$REPO_ROOT"/skills/*/; do
  name="$(basename "$src_skill")"
  dst="$ACTIVE/skills/$name"

  if [ ! -d "$dst" ]; then
    if [ "$DRY_RUN" = "1" ]; then
      printf "  + would add  /%s\n" "$name"
    else
      cp -r "$src_skill" "$dst"
      printf "  + added      /%s\n" "$name"
    fi
    added=$((added + 1))
    continue
  fi

  # Content-based compare — ignores mtime/inode metadata that would
  # make tar+md5 report false drift on every run. `diff -rq` returns
  # non-zero if any file differs, silent if identical.
  if diff -rq "$src_skill" "$dst" >/dev/null 2>&1; then
    unchanged=$((unchanged + 1))
    continue
  fi

  if [ "$DRY_RUN" = "1" ]; then
    printf "  ~ would sync /%s (drift detected)\n" "$name"
  else
    rm -rf "$dst"
    cp -r "$src_skill" "$dst"
    printf "  ~ updated    /%s\n" "$name"
  fi
  updated=$((updated + 1))
done

ok "skills: +$added added, ~$updated updated, =$unchanged unchanged"

# -----------------------------------------------------------------------------
# Step 2/4: Sync hooks
# -----------------------------------------------------------------------------
say "Step 2/4: hooks/"
mkdir -p "$ACTIVE/hooks"

h_added=0
h_updated=0
h_unchanged=0

for src_hook in "$REPO_ROOT"/hooks/*.sh; do
  [ -e "$src_hook" ] || continue
  name="$(basename "$src_hook")"
  dst="$ACTIVE/hooks/$name"

  if [ ! -f "$dst" ]; then
    if [ "$DRY_RUN" = "1" ]; then
      printf "  + would add   %s\n" "$name"
    else
      cp "$src_hook" "$dst"
      chmod +x "$dst"
      printf "  + added       %s\n" "$name"
    fi
    h_added=$((h_added + 1))
    continue
  fi

  if cmp -s "$src_hook" "$dst"; then
    h_unchanged=$((h_unchanged + 1))
    continue
  fi

  if [ "$DRY_RUN" = "1" ]; then
    printf "  ~ would sync  %s (content drift)\n" "$name"
  else
    cp "$src_hook" "$dst"
    chmod +x "$dst"
    printf "  ~ updated     %s\n" "$name"
  fi
  h_updated=$((h_updated + 1))
done

ok "hooks: +$h_added added, ~$h_updated updated, =$h_unchanged unchanged"

# -----------------------------------------------------------------------------
# Step 3/4: Sync agents/*.md (subagents)
# -----------------------------------------------------------------------------
# Gap #9 (v1.13.1): sync-to-active.sh originally copied skills/ and hooks/
# but NOT agents/, so updates to subagent instructions (e.g. the v1.13.0
# methodology-mode Step 0 in agents/code-reviewer.md) never propagated to
# ~/.claude/agents/. That made the v1.13.0 /review fix effectively inactive
# until a manual copy. This step fixes it symmetrically with Step 2/4.
#
# Numbering note (v1.13.2): originally this was "Step 2.5/3" because agents/
# was added after the 3-step layout was fixed. v1.13.2 renumbered to the
# honest 1/4..4/4 scheme so that `--check` dry-run output matches reality.
say "Step 3/4: agents/"
mkdir -p "$ACTIVE/agents"

a_added=0
a_updated=0
a_unchanged=0

if [ -d "$REPO_ROOT/agents" ]; then
  for src_agent in "$REPO_ROOT"/agents/*.md; do
    [ -e "$src_agent" ] || continue
    name="$(basename "$src_agent")"
    dst="$ACTIVE/agents/$name"

    if [ ! -f "$dst" ]; then
      if [ "$DRY_RUN" = "1" ]; then
        printf "  + would add   %s\n" "$name"
      else
        cp "$src_agent" "$dst"
        printf "  + added       %s\n" "$name"
      fi
      a_added=$((a_added + 1))
      continue
    fi

    if cmp -s "$src_agent" "$dst"; then
      a_unchanged=$((a_unchanged + 1))
      continue
    fi

    if [ "$DRY_RUN" = "1" ]; then
      printf "  ~ would sync  %s (content drift)\n" "$name"
    else
      cp "$src_agent" "$dst"
      printf "  ~ updated     %s\n" "$name"
    fi
    a_updated=$((a_updated + 1))
  done
fi

ok "agents: +$a_added added, ~$a_updated updated, =$a_unchanged unchanged"

# -----------------------------------------------------------------------------
# Step 4/4: Patch settings.json "hooks" section
# -----------------------------------------------------------------------------
say "Step 4/4: settings.json hooks registration"

SETTINGS="$ACTIVE/settings.json"

if [ ! -f "$SETTINGS" ]; then
  warn "settings.json not found — creating from scratch"
  if [ "$DRY_RUN" = "0" ]; then
    printf '{\n  "hooks": {}\n}\n' > "$SETTINGS"
  fi
fi

# Build the desired hooks block as a JSON string
# Matchers:
#   UserPromptSubmit → pre-flight-check.sh, check-skills.sh  (order matters:
#     pre-flight first so skill-check sees its output)
#   PreToolUse matcher=Bash|Edit|Write|NotebookEdit → check-tool-skill.sh
#   PreToolUse matcher=Bash → check-commit-completeness.sh  (no-op outside
#     methodology repo, cheap)
#   PreToolUse matcher=Write|Edit|MultiEdit → check-skill-completeness.sh
#     (no-op outside methodology repo, cheap)

DESIRED_HOOKS=$(cat <<'JSON'
{
  "UserPromptSubmit": [
    {
      "hooks": [
        { "type": "command", "command": "~/.claude/hooks/pre-flight-check.sh", "timeout": 5 },
        { "type": "command", "command": "~/.claude/hooks/check-skills.sh",     "timeout": 5 }
      ]
    }
  ],
  "PreToolUse": [
    {
      "matcher": "Bash|Edit|Write|NotebookEdit",
      "hooks": [
        { "type": "command", "command": "~/.claude/hooks/check-tool-skill.sh", "timeout": 5 }
      ]
    },
    {
      "matcher": "Bash",
      "hooks": [
        { "type": "command", "command": "~/.claude/hooks/check-commit-completeness.sh", "timeout": 5 }
      ]
    },
    {
      "matcher": "Write|Edit|MultiEdit",
      "hooks": [
        { "type": "command", "command": "~/.claude/hooks/check-skill-completeness.sh", "timeout": 5 }
      ]
    }
  ]
}
JSON
)

# Check if current settings.json hooks already matches desired
current_hooks=$(python3 -c "
import json, sys
try:
    with open('$SETTINGS') as f:
        data = json.load(f)
    print(json.dumps(data.get('hooks', {}), sort_keys=True))
except Exception as e:
    print('ERROR:' + str(e))
    sys.exit(0)
" 2>/dev/null || echo "ERROR")

desired_normalized=$(echo "$DESIRED_HOOKS" | python3 -c "
import json, sys
print(json.dumps(json.load(sys.stdin), sort_keys=True))
")

if [ "$current_hooks" = "$desired_normalized" ]; then
  ok "settings.json hooks already up-to-date"
else
  if [ "$DRY_RUN" = "1" ]; then
    warn "settings.json hooks would be updated (drift detected)"
    printf "  current:  %s\n" "$(echo "$current_hooks" | head -c 120)..."
    printf "  desired:  %s\n" "$(echo "$desired_normalized" | head -c 120)..."
  else
    ts=$(date +%Y%m%d-%H%M%S)
    bak="$SETTINGS.bak-$ts"
    cp "$SETTINGS" "$bak"
    python3 - "$SETTINGS" <<PYEOF
import json, sys
path = sys.argv[1]
with open(path) as f:
    data = json.load(f)
data['hooks'] = $DESIRED_HOOKS
with open(path, 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')
PYEOF
    ok "settings.json hooks updated (backup: $(basename "$bak"))"
  fi
fi

echo ""
if [ "$DRY_RUN" = "1" ]; then
  say "DRY RUN complete — re-run without --check to apply"
else
  say "Sync complete — restart \`claude\` to pick up new skills"
fi
