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
# Windows target (v1.38.0) — sync a Windows ~/.claude from WSL, emitting
# python.exe hook invocations instead of bare shebang paths:
#   CLAUDE_HOME=/mnt/c/Users/<you>/.claude bash scripts/sync-to-active.sh
# (v1.73.1: the Windows target is auto-detected from the CLAUDE_HOME path —
# /mnt/<drive>/ or <drive>:/ — and from a Git-Bash/MSYS/Cygwin host; the
# interpreter is harvested from an existing wrapper registration in the target
# settings.json. ITD_TARGET_OS / ITD_WIN_PYTHON remain as explicit overrides.)
#
# What it syncs:
#   1. skills/*              → ~/.claude/skills/
#   2. hooks/*.sh            → ~/.claude/hooks/
#   3. settings.json hooks   → registers the enforcement/guardrail hooks with
#      correct matchers: UserPromptSubmit context hooks; PreToolUse (check-tool-skill,
#      commit/review/dod gates, context-budget, check-skill-completeness,
#      pii-egress-guard on all tools); PostToolUse (record-agent-skill on
#      Task|Agent, cost-tracker + risk-score on *)
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

# Python launcher: python3 on Unix/WSL, python on Git-Bash-Windows.
# Runnable python for inline snippets. On Windows Git-Bash, `python`/`python3`
# on PATH may be the Microsoft Store STUB that prints "Python" and exits
# non-zero — `command -v` alone cannot tell. Validate the candidate by actually
# executing it; honour explicit ITD_WIN_PYTHON first (v1.68.1).
PYBIN=""
for _cand in "${ITD_WIN_PYTHON:-}" python3 python py; do
  [ -n "$_cand" ] || continue
  if "$_cand" -c "print(1)" >/dev/null 2>&1; then PYBIN="$_cand"; break; fi
done
[ -n "$PYBIN" ] || PYBIN=python3

# Target OS (v1.38.0). On a Windows target, .sh hooks cannot run via a shebang —
# Claude Code must invoke them through python.exe. Auto-detect a Git-Bash/MSYS/
# Cygwin host; ITD_TARGET_OS env still overrides everything.
ITD_TARGET_OS="${ITD_TARGET_OS:-}"
if [ -z "$ITD_TARGET_OS" ]; then
  case "$(uname -s 2>/dev/null)" in
    MINGW*|MSYS*|CYGWIN*) ITD_TARGET_OS=windows ;;
    *) ITD_TARGET_OS=unix ;;
  esac
  # v1.73.1: target OS is a property of the TARGET path, not of the host.
  # WSL→/mnt/c (or a raw C:/ path) means the deployed ~/.claude lives on
  # Windows, where .sh hooks have no shebang execution. Root cause 2026-07-10:
  # sync from WSL with CLAUDE_HOME=/mnt/c/... auto-detected 'unix' and wrote
  # bare POSIX hook commands into the Windows settings.json — Git-Bash then
  # executed python-bodied hooks as shell (syntax error → exit 2), and a
  # '*'-matcher PreToolUse hook DENIED every tool call until manual restore
  # from the .bak. Detect by path so the operator no longer has to remember
  # the env var from the header comment.
  case "${CLAUDE_HOME:-}" in
    /mnt/[a-zA-Z]/*|[A-Za-z]:*) ITD_TARGET_OS=windows ;;
  esac
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
# Step 1/6: Sync skills
# -----------------------------------------------------------------------------
say "Step 1/6: skills/"
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
# Step 2/6: Sync hooks
# -----------------------------------------------------------------------------
say "Step 2/6: hooks/"
# --- utility scripts (v1.88.0: OTel-экспортёр — транспорт, не контракт) ------
mkdir -p "$ACTIVE/scripts"
for u in itd_otel_export.py; do
  if [ -f "$REPO_ROOT/scripts/$u" ]; then
    cp "$REPO_ROOT/scripts/$u" "$ACTIVE/scripts/$u"
    echo "  script: $u"
  fi
done

mkdir -p "$ACTIVE/hooks"

h_added=0
h_updated=0
h_unchanged=0

# Sync executable hooks (*.sh) AND their Python libraries (*.py, e.g.
# completion_lib.py imported by the completion-* hooks) — a lib left unsynced
# makes its hooks silently no-op on a fresh machine (import fails, fail-safe).
for src_hook in "$REPO_ROOT"/hooks/*.sh "$REPO_ROOT"/hooks/*.py; do
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
# Step 3/6: Sync agents/*.md (subagents)
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
say "Step 3/6: agents/"
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
# Step 4/6: Sync docs/templates (itd contracts + itd-memory examples)
# -----------------------------------------------------------------------------
# v1.68.0 (init-audit round 2, C4): /adopt Step 3.5 and /kickstart Phase 3
# resolve the .itd/ scaffold templates from a plugin install or the repo
# checkout; a sync-based install on a machine WITHOUT the checkout (e.g. the
# Windows side of a WSL repo) had no template source at all — scaffolding
# degraded to "warn and skip". Mirror the templates to
# $ACTIVE/templates/{itd,itd-memory} so the scaffold works install-locally.
say "Step 4/6: docs/templates/ (itd + itd-memory)"
t_added=0
t_updated=0
t_unchanged=0
for sub in itd itd-memory; do
  src_dir="$REPO_ROOT/docs/templates/$sub"
  [ -d "$src_dir" ] || continue
  mkdir -p "$ACTIVE/templates/$sub"
  for src_t in "$src_dir"/*; do
    [ -f "$src_t" ] || continue   # dirs (__pycache__) are skipped
    name="$(basename "$src_t")"
    dst="$ACTIVE/templates/$sub/$name"
    if [ ! -f "$dst" ]; then
      if [ "$DRY_RUN" = "1" ]; then
        printf "  + would add   %s/%s\n" "$sub" "$name"
      else
        cp "$src_t" "$dst"
        printf "  + added       %s/%s\n" "$sub" "$name"
      fi
      t_added=$((t_added + 1))
      continue
    fi
    if cmp -s "$src_t" "$dst"; then
      t_unchanged=$((t_unchanged + 1))
      continue
    fi
    if [ "$DRY_RUN" = "1" ]; then
      printf "  ~ would sync  %s/%s (content drift)\n" "$sub" "$name"
    else
      cp "$src_t" "$dst"
      printf "  ~ updated     %s/%s\n" "$sub" "$name"
    fi
    t_updated=$((t_updated + 1))
  done
done
ok "templates: +$t_added added, ~$t_updated updated, =$t_unchanged unchanged"

# -----------------------------------------------------------------------------
# Step 5/6: Patch settings.json "hooks" section
# -----------------------------------------------------------------------------
say "Step 5/6: settings.json hooks registration"

SETTINGS="$ACTIVE/settings.json"

if [ ! -f "$SETTINGS" ]; then
  warn "settings.json not found — creating from scratch"
  if [ "$DRY_RUN" = "0" ]; then
    printf '{\n  "hooks": {}\n}\n' > "$SETTINGS"
  fi
fi

# Build the desired hooks block as a JSON string
# Matchers:
#   UserPromptSubmit → pre-flight-check.sh, check-skills.sh (order matters:
#     pre-flight first so skill-check sees its output)
#   PreToolUse matcher=Bash|Edit|Write|NotebookEdit|Skill → check-tool-skill.sh
#     (Skill in matcher = v1.24.0 forward-compat; harmless no-op until the
#      harness emits Skill hook events)
#   PreToolUse matcher=Bash → check-commit-completeness.sh  (no-op outside
#     methodology repo, cheap)
#   PreToolUse matcher=Write|Edit|MultiEdit → check-skill-completeness.sh
#     (no-op outside methodology repo, cheap)
#   PostToolUse matcher=Task|Agent → record-agent-skill.sh  (writes the
#     skill sentinel when review/test/security work is delegated to a
#     subagent, so the commit gates count it — bug #2 follow-up)
#   Stop → handoff-readiness.sh  (v1.40.0 — soft systemMessage when the turn
#     ends with a dirty git tree AND no fresh session_*.md; never blocks,
#     rate-limited; the "end every session handoff-ready" half of the
#     Anthropic long-running-agents port)
#   SubagentStop → narration-final.sh  (v1.49.0 — mechanical narration-final
#     detector: blocks a subagent's stop (≤2 pings) when its final message
#     ends on process narration with no verdict; retro signal ×5 — the
#     prompt-level contract alone did not fix this class)
#   SubagentStop → verdict-contract.sh  (v1.51.0 — vendor-neutral verdict
#     contract: blocks a subagent's stop (≤2 pings) when its final message
#     declares a review verdict in prose but ships no valid ```json verdict
#     block; complementary to narration-final on the same event, no loop)
#   state-guard.sh — шесть регистраций (v1.78.1: + PreToolUse/PostToolUse PowerShell —
#     тот же канал мутаций на Windows-инсталле):
#     PreToolUse  matcher=Bash → тот же single-writer гейт для Bash-канала
#       (deny, когда леджер — ЦЕЛЬ записи: редирект/tee/sed -i/mv/cp/dd of=/
#       Set-Content; target-anchored, со-вхождение не гейтится)
#     PreToolUse  matcher=Write|Edit|MultiEdit|NotebookEdit → single-writer
#       гейт леджера: deny записи .itd-memory/STATE.json|GOAL*.json при
#       свежем локе ДРУГОЙ сессии (≤2 deny/сессию, потом warn-allow)
#     PostToolUse matcher=Write|Edit|MultiEdit|NotebookEdit → (v1.75.0)
#       немедленная валидация леджера + heartbeat .active-session.lock
#     PostToolUse matcher=Bash → детект мутации леджера в обход Write/Edit
#       (редиректы/sed -i/tee/jq) → перевалидация, красная пометка

DESIRED_HOOKS=$(cat <<'JSON'
{
  "UserPromptSubmit": [
    {
      "hooks": [
        { "type": "command", "command": "~/.claude/hooks/session-open-diagnostic.sh", "timeout": 5 },
        { "type": "command", "command": "~/.claude/hooks/pre-flight-check.sh",        "timeout": 5 },
        { "type": "command", "command": "~/.claude/hooks/check-skills.sh",            "timeout": 5 },
        { "type": "command", "command": "~/.claude/hooks/context-aware.sh",           "timeout": 5 }
      ]
    }
  ],
  "PreToolUse": [
    {
      "matcher": "Bash|PowerShell|Task|Agent",
      "hooks": [
        { "type": "command", "command": "~/.claude/hooks/cost-tracker.sh", "timeout": 5 }
      ]
    },
    {
      "matcher": "Bash|Edit|Write|NotebookEdit|Skill",
      "hooks": [
        { "type": "command", "command": "~/.claude/hooks/check-tool-skill.sh", "timeout": 5 }
      ]
    },
    {
      "matcher": "*",
      "hooks": [
        { "type": "command", "command": "~/.claude/hooks/execution-trace.sh", "timeout": 5 }
      ]
    },
    {
      "matcher": "Bash",
      "hooks": [
        { "type": "command", "command": "~/.claude/hooks/check-commit-completeness.sh",   "timeout": 5 },
        { "type": "command", "command": "~/.claude/hooks/check-review-before-commit.sh",  "timeout": 5 },
        { "type": "command", "command": "~/.claude/hooks/check-dod-before-commit.sh",     "timeout": 5 },
        { "type": "command", "command": "~/.claude/hooks/cross-review-precommit.sh",      "timeout": 5 },
        { "type": "command", "command": "~/.claude/hooks/context-budget.sh",              "timeout": 5 },
        { "type": "command", "command": "~/.claude/hooks/careful.sh",                     "timeout": 5 },
        { "type": "command", "command": "~/.claude/hooks/completion-gate.sh",              "timeout": 900 },
        { "type": "command", "command": "~/.claude/hooks/state-guard.sh",                  "timeout": 5 }
      ]
    },
    {
      "matcher": "Write|Edit|MultiEdit|NotebookEdit",
      "hooks": [
        { "type": "command", "command": "~/.claude/hooks/check-skill-completeness.sh", "timeout": 5 },
        { "type": "command", "command": "~/.claude/hooks/wip-gate.sh",                 "timeout": 5 },
        { "type": "command", "command": "~/.claude/hooks/freeze.sh",                   "timeout": 5 },
        { "type": "command", "command": "~/.claude/hooks/state-guard.sh",              "timeout": 5 }
      ]
    },
    {
      "matcher": "PowerShell",
      "hooks": [
        { "type": "command", "command": "~/.claude/hooks/completion-gate.sh", "timeout": 900 },
        { "type": "command", "command": "~/.claude/hooks/state-guard.sh", "timeout": 5 }
      ]
    },
    {
      "matcher": "*",
      "hooks": [
        { "type": "command", "command": "~/.claude/hooks/pii-egress-guard.sh", "timeout": 5 }
      ]
    },
    {
      "matcher": "Task|Agent",
      "hooks": [
        { "type": "command", "command": "~/.claude/hooks/model-policy.sh", "timeout": 5 }
      ]
    }
  ],
  "PostToolUse": [
    {
      "matcher": "Task|Agent",
      "hooks": [
        { "type": "command", "command": "~/.claude/hooks/record-agent-skill.sh", "timeout": 5 }
      ]
    },
    {
      "matcher": "Write|Edit|MultiEdit|NotebookEdit",
      "hooks": [
        { "type": "command", "command": "~/.claude/hooks/state-guard.sh", "timeout": 5 }
      ]
    },
    {
      "matcher": "*",
      "hooks": [
        { "type": "command", "command": "~/.claude/hooks/execution-trace.sh",   "timeout": 5 },
        { "type": "command", "command": "~/.claude/hooks/cost-tracker.sh",      "timeout": 5 },
        { "type": "command", "command": "~/.claude/hooks/risk-score.sh",        "timeout": 5 },
        { "type": "command", "command": "~/.claude/hooks/stuck-detection.sh",   "timeout": 5 },
        { "type": "command", "command": "~/.claude/hooks/crash-recovery.sh",    "timeout": 5 }
      ]
    },
    {
      "matcher": "Bash",
      "hooks": [
        { "type": "command", "command": "~/.claude/hooks/completion-signals.sh", "timeout": 5 },
        { "type": "command", "command": "~/.claude/hooks/state-guard.sh",        "timeout": 5 }
      ]
    },
    {
      "matcher": "PowerShell",
      "hooks": [
        { "type": "command", "command": "~/.claude/hooks/completion-signals.sh", "timeout": 5 },
        { "type": "command", "command": "~/.claude/hooks/state-guard.sh",        "timeout": 5 }
      ]
    }
  ],
  "Stop": [
    {
      "hooks": [
        { "type": "command", "command": "~/.claude/hooks/handoff-readiness.sh", "timeout": 5 },
        { "type": "command", "command": "~/.claude/hooks/completion-stop.sh",   "timeout": 5 },
        { "type": "command", "command": "~/.claude/hooks/crash-recovery.sh",    "timeout": 5 }
      ]
    }
  ],
  "SubagentStop": [
    {
      "hooks": [
        { "type": "command", "command": "~/.claude/hooks/narration-final.sh",  "timeout": 10 },
        { "type": "command", "command": "~/.claude/hooks/verdict-contract.sh", "timeout": 10 },
        { "type": "command", "command": "~/.claude/hooks/crash-recovery.sh",   "timeout": 5 }
      ]
    }
  ]
}
JSON
)

# v1.38.0: platform-aware command form. On a Windows target, rewrite each
# "~/.claude/hooks/X.sh" into a python.exe invocation with an absolute Windows
# path — .sh files there have no executable shebang. Unix/WSL keeps bare paths
# (the shebang runs them). ACTIVE (/mnt/c/... or /c/... → C:/...) is normalised;
# the interpreter is ITD_WIN_PYTHON (required for the WSL→/mnt/c case) or is
# discovered on PATH (Git-Bash host).
if [ "$ITD_TARGET_OS" = "windows" ]; then
  WIN_PY="${ITD_WIN_PYTHON:-}"
  # v1.73.1: harvest the interpreter from an EXISTING wrapper registration in
  # the target settings.json before PATH discovery. On a WSL host `command -v
  # python` finds the LINUX interpreter — a wrapper built from it is broken on
  # Windows; the .exe path already recorded in settings.json is the one
  # interpreter known to work on that machine.
  if [ -z "$WIN_PY" ] && [ -f "$SETTINGS" ]; then
    # JSON escapes the wrapper's inner quotes (\"C:/...python.exe\"), so match
    # the bare path, not surrounding quotes; `|| true` — no match must not
    # trip set -e.
    WIN_PY="$(grep -o '[A-Za-z]:/[^"\\ ]*python[^"\\ ]*\.exe' "$SETTINGS" 2>/dev/null | head -1 || true)"
    [ -n "$WIN_PY" ] && warn "ITD_WIN_PYTHON unset — interpreter harvested from existing settings.json: $WIN_PY"
  fi
  if [ -z "$WIN_PY" ]; then
    _p="$(command -v python 2>/dev/null || command -v py 2>/dev/null || true)"
    [ -n "$_p" ] && WIN_PY="$(cygpath -m "$_p" 2>/dev/null || echo "$_p")"
    case "$WIN_PY" in
      /usr/*|/bin/*|/opt/*) warn "PATH python ($WIN_PY) is a Linux interpreter — useless in a Windows wrapper; set ITD_WIN_PYTHON"; WIN_PY="" ;;
    esac
  fi
  [ -z "$WIN_PY" ] && { WIN_PY="python"; warn "ITD_WIN_PYTHON unset and python not found — using bare 'python'"; }
  EFFECTIVE_HOOKS="$(ITD_DESIRED="$DESIRED_HOOKS" ITD_WIN_PY="$WIN_PY" ITD_ACTIVE="$ACTIVE" "$PYBIN" - <<'PYX'
import json, os, re
def to_win(p):
    m = re.match(r'^/mnt/([a-zA-Z])/(.*)$', p) or re.match(r'^/([a-zA-Z])/(.*)$', p)
    return '%s:/%s' % (m.group(1).upper(), m.group(2)) if m else p.replace('\\', '/')
py = os.environ['ITD_WIN_PY']
active = to_win(os.environ['ITD_ACTIVE'].rstrip('/'))
data = json.loads(os.environ['ITD_DESIRED'])
for ev in data.values():
    for grp in ev:
        for h in grp.get('hooks', []):
            m = re.match(r'^~/\.claude/hooks/(.+)$', h['command'])
            if m:
                h['command'] = '"%s" -X utf8 "%s/hooks/%s"' % (py, active, m.group(1))
print(json.dumps(data))
PYX
)"
else
  EFFECTIVE_HOOKS="$DESIRED_HOOKS"
fi

# Check if current settings.json hooks already matches desired. Compare only the
# ITD-managed event keys — foreign keys (e.g. a SessionStart hook registered by
# another plugin) are preserved by the merge below and must not read as "drift".
current_hooks=$($PYBIN -c "
import json, sys
KEYS = ('UserPromptSubmit', 'PreToolUse', 'PostToolUse', 'Stop', 'SubagentStop')
try:
    with open('$SETTINGS') as f:
        data = json.load(f)
    h = data.get('hooks', {})
    print(json.dumps({k: h.get(k) for k in KEYS}, sort_keys=True))
except Exception as e:
    print('ERROR:' + str(e))
    sys.exit(0)
" 2>/dev/null || echo "ERROR")

desired_normalized=$(echo "$EFFECTIVE_HOOKS" | $PYBIN -c "
import json, sys
print(json.dumps(json.load(sys.stdin), sort_keys=True))
")

if [ "$current_hooks" = "$desired_normalized" ]; then
  ok "settings.json hooks already up-to-date"
# v1.73.1 fail-closed guard: never downgrade an existing Windows python-wrapper
# registration to bare .sh commands. A bare-.sh registration on Windows makes
# Git-Bash execute python-bodied hooks as shell → exit 2 → the '*'-matcher
# PreToolUse hook denies EVERY tool call (live incident 2026-07-10). If the
# target settings.json shows wrapper form but the target OS resolved non-
# windows, the resolution is wrong — refuse and tell the operator, keep the
# working registration untouched.
elif [ "$ITD_TARGET_OS" != "windows" ] && printf '%s' "$current_hooks" | grep -qi '[A-Za-z]:/[^"]*python[^"]*\.exe'; then
  err "settings.json registers hooks via a Windows python wrapper, but target OS resolved '$ITD_TARGET_OS'."
  err "REFUSING to overwrite (would brick every tool call). Re-run with ITD_TARGET_OS=windows (+ ITD_WIN_PYTHON), or fix CLAUDE_HOME."
else
  if [ "$DRY_RUN" = "1" ]; then
    warn "settings.json hooks would be updated (drift detected)"
    printf "  current:  %s\n" "$(echo "$current_hooks" | head -c 120)..."
    printf "  desired:  %s\n" "$(echo "$desired_normalized" | head -c 120)..."
  else
    ts=$(date +%Y%m%d-%H%M%S)
    bak="$SETTINGS.bak-$ts"
    cp "$SETTINGS" "$bak"
    $PYBIN - "$SETTINGS" <<PYEOF
import json, sys
path = sys.argv[1]
with open(path) as f:
    data = json.load(f)
_itd = $EFFECTIVE_HOOKS
# Merge the ITD-managed event keys; preserve any foreign event keys (e.g. a
# SessionStart hook registered by another plugin such as context-mode). ITD owns
# UserPromptSubmit/PreToolUse/PostToolUse/Stop/SubagentStop in full, so replacing
# those is correct.
data.setdefault('hooks', {})
for _k, _v in _itd.items():
    data['hooks'][_k] = _v
with open(path, 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')
PYEOF
    ok "settings.json hooks updated (backup: $(basename "$bak"))"
  fi
fi

# -----------------------------------------------------------------------------
# Step 6/6: Sync the ITD methodology block into ~/.claude/CLAUDE.md (v1.39.0)
# -----------------------------------------------------------------------------
# The global CLAUDE.md carries the MANDATORY methodology instruction plus
# personal sections (e.g. token-efficiency prefs). To keep the methodology block
# in lockstep across machines WITHOUT clobbering personal content, the repo owns
# the block (docs/templates/global-claude-md.md, between ITD:BEGIN/ITD:END
# markers) and this step replaces ONLY that marked region in the active file.
say "Step 6/6: CLAUDE.md methodology block"
TPL="$REPO_ROOT/docs/templates/global-claude-md.md"
CLAUDE_MD="$ACTIVE/CLAUDE.md"
if [ ! -f "$TPL" ]; then
  warn "template not found ($TPL) — skipping CLAUDE.md sync"
else
  _cmres="$(ITD_TPL="$TPL" ITD_CLAUDE="$CLAUDE_MD" ITD_DRY="$DRY_RUN" "$PYBIN" - <<'PYX'
import os, sys, time, shutil
BEGIN = "<!-- ITD:BEGIN"; END = "<!-- ITD:END methodology -->"
tpl = open(os.environ["ITD_TPL"], encoding="utf-8").read()
b, e = tpl.find(BEGIN), tpl.find(END)
if b == -1 or e == -1:
    print("ERROR:template markers missing"); sys.exit(0)
block = tpl[b:e + len(END)]
active = os.environ["ITD_CLAUDE"]; dry = os.environ["ITD_DRY"]
if not os.path.exists(active):
    action, result = "create", block + "\n"
else:
    cur = open(active, encoding="utf-8").read()
    ab, ae = cur.find(BEGIN), cur.find(END)
    if ab != -1 and ae != -1:
        if cur[ab:ae + len(END)] == block:
            print("UPTODATE"); sys.exit(0)
        action, result = "update", cur[:ab] + block + cur[ae + len(END):]
    else:
        action, result = "prepend", block + "\n\n" + cur
if dry == "1":
    print("DRIFT:" + action); sys.exit(0)
if os.path.exists(active):
    shutil.copy(active, active + ".bak-" + time.strftime("%Y%m%d-%H%M%S"))
with open(active, "w", encoding="utf-8") as f:
    f.write(result)
print("WROTE:" + action)
PYX
)"
  case "$_cmres" in
    UPTODATE) ok "CLAUDE.md methodology block already up-to-date" ;;
    DRIFT:*)  warn "CLAUDE.md methodology block drift (${_cmres#DRIFT:}) — would sync" ;;
    WROTE:*)  ok "CLAUDE.md methodology block synced (${_cmres#WROTE:})" ;;
    ERROR:*)  err "CLAUDE.md sync: ${_cmres#ERROR:}" ;;
    *)        warn "CLAUDE.md sync: unexpected result ($_cmres)" ;;
  esac
fi

# v1.20.1 cleanup: keep the 5 most recent settings.json.bak-* files, delete
# older ones. `sync-to-active` is run routinely, so these accumulate fast.
if [ "$DRY_RUN" = "0" ]; then
  for _glob in "settings.json.bak-" "CLAUDE.md.bak-"; do
    mapfile -t _old_baks < <(ls -1t "$ACTIVE/$_glob"* 2>/dev/null | tail -n +6)
    if [ "${#_old_baks[@]}" -gt 0 ]; then
      rm -f "${_old_baks[@]}"
      ok "backup cleanup: pruned ${#_old_baks[@]} old ${_glob}* files (kept 5 most recent)"
    fi
  done
fi

echo ""
if [ "$DRY_RUN" = "1" ]; then
  say "DRY RUN complete — re-run without --check to apply"
else
  say "Sync complete — restart \`claude\` to pick up new skills"
fi
