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
#   3. settings.json hooks   → one default registration for every user (plan
#      session 5, ADR-016): the core hooks (pre-flight-check, pii-egress-guard,
#      careful, check-predeploy-gate, completion-signals, completion-gate), the
#      state hooks that stay silent without .itd-memory and the commit, agent
#      and methodology gates; the optional diagnostics only when
#      itd-enabled-hooks.txt names them, never a hook itd-disabled-hooks.txt
#      names (the same decision codex-dispatch.py makes for Codex). A user's
#      own hooks in the same events are kept.
#
# What it does NOT touch:
#   - ~/.claude/settings.json keys other than "hooks" (env, permissions, etc.),
#     and hooks in it that do not run an ITD hook file from the install
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
  if diff -rq -x '__pycache__' -x '*.pyc' "$src_skill" "$dst" >/dev/null 2>&1; then
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

# --- plugin manifest (v1.96.1) ------------------------------------------------
# The repo manifest was only existence-checked at startup and never synced, so
# ~/.claude/.claude-plugin/plugin.json drifted until someone aligned it by hand.
src_manifest="$REPO_ROOT/.claude-plugin/plugin.json"
dst_manifest="$ACTIVE/.claude-plugin/plugin.json"
if [ ! -f "$dst_manifest" ]; then
  if [ "$DRY_RUN" = "1" ]; then
    printf "  + would add   %s\n" ".claude-plugin/plugin.json"
  else
    mkdir -p "$ACTIVE/.claude-plugin"
    cp "$src_manifest" "$dst_manifest"
    printf "  + added       %s\n" ".claude-plugin/plugin.json"
  fi
elif cmp -s "$src_manifest" "$dst_manifest"; then
  ok "manifest: .claude-plugin/plugin.json unchanged"
else
  if [ "$DRY_RUN" = "1" ]; then
    printf "  ~ would sync  %s (content drift)\n" ".claude-plugin/plugin.json"
  else
    cp "$src_manifest" "$dst_manifest"
    printf "  ~ updated     %s\n" ".claude-plugin/plugin.json"
  fi
fi

# --- install provenance (v1.99.0, LPD-002 R2) ---------------------------------
# The commit gate loads the review validator from the methodology checkout it is
# judging, so that a release commit is judged by its own code instead of by the
# installed copy with the previous version. That decision must not be forgeable
# from the working directory: a plugin manifest is self-declared, so any project
# could name itself and hand the gate a validator of its own. The install is the
# non-forgeable anchor -- only sync writes here, and only from a real checkout.
src_provenance="$ACTIVE/.itd-install-source.json"
new_provenance="$(printf '{\n  "checkout": "%s",\n  "plugin": "idea-to-deploy"\n}\n' "$REPO_ROOT")"
if [ "$DRY_RUN" = "1" ]; then
  if [ ! -f "$src_provenance" ] || [ "$(cat "$src_provenance")" != "$new_provenance" ]; then
    printf "  ~ would record %s (checkout %s)\n" ".itd-install-source.json" "$REPO_ROOT"
  else
    ok "provenance: .itd-install-source.json unchanged"
  fi
elif [ -f "$src_provenance" ] && [ "$(cat "$src_provenance")" = "$new_provenance" ]; then
  ok "provenance: .itd-install-source.json unchanged"
else
  printf '%s' "$new_provenance" > "$src_provenance"
  printf "  ~ recorded    %s (checkout %s)\n" ".itd-install-source.json" "$REPO_ROOT"
fi

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
# TIER_EXEMPT.json is the data file tier_exempt.py reads (G-003); without it the
# advisory hooks never go quiet on a low-risk unit.
for src_hook in "$REPO_ROOT"/hooks/*.sh "$REPO_ROOT"/hooks/*.py "$REPO_ROOT"/hooks/TIER_EXEMPT.json; do
  [ -e "$src_hook" ] || continue
  name="$(basename "$src_hook")"
  dst="$ACTIVE/hooks/$name"

  if [ ! -f "$dst" ]; then
    if [ "$DRY_RUN" = "1" ]; then
      printf "  + would add   %s\n" "$name"
    else
      cp "$src_hook" "$dst"
      case "$name" in *.json) chmod 644 "$dst" ;; *) chmod +x "$dst" ;; esac
      printf "  + added       %s\n" "$name"
    fi
    h_added=$((h_added + 1))
    continue
  fi

  if cmp -s "$src_hook" "$dst"; then
    # a data file converges to non-executable even when its bytes did not change;
    # the mode drift is reported, so --check shows what a real run would do
    case "$name" in *.json)
      # any mode other than 644 is drift (find -perm is POSIX; stat flags are not)
      if [ -n "$(find "$dst" -prune ! -perm 644 2>/dev/null)" ]; then
        if [ "$DRY_RUN" = "1" ]; then
          printf "  ~ would chmod %s (mode drift -> 644)\n" "$name"
        else
          printf "  ~ chmod       %s (mode drift -> 644)\n" "$name"
        fi
      fi
      [ "$DRY_RUN" = "1" ] || chmod 644 "$dst" ;;
    esac
    h_unchanged=$((h_unchanged + 1))
    continue
  fi

  if [ "$DRY_RUN" = "1" ]; then
    printf "  ~ would sync  %s (content drift)\n" "$name"
  else
    cp "$src_hook" "$dst"
    case "$name" in *.json) chmod 644 "$dst" ;; *) chmod +x "$dst" ;; esac
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

# Build the desired hooks block as a JSON string: every hook ITD registers, the
# optional ones included (the selection below drops what the lists switch off).
# check-skills.sh, check-tool-skill.sh and check-review-before-commit.sh are not
# registered since plan session 5 (they asked for a skill-decision line the
# global instructions no longer have); their files stay in hooks/.
# Matchers:
#   UserPromptSubmit → pre-flight-check.sh
#   PreToolUse matcher=Bash → check-dod-before-commit.sh  timeout 150 s: on a
#     commit it may run the project's .itd/checks (bounded at 120 s); under 5 s
#     the host cut it on slow Windows commits and the DoD gate never decided
#     (plan session 5, BACKLOG P2 2026-10-22). Non-commit commands exit at once.
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
        { "type": "command", "command": "~/.claude/hooks/context-aware.sh",           "timeout": 5 },
        { "type": "command", "command": "~/.claude/hooks/graph-route.sh",             "timeout": 10 }
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
      "matcher": "*",
      "hooks": [
        { "type": "command", "command": "~/.claude/hooks/execution-trace.sh", "timeout": 5 }
      ]
    },
    {
      "matcher": "Bash",
      "hooks": [
        { "type": "command", "command": "~/.claude/hooks/check-commit-completeness.sh",   "timeout": 5 },
        { "type": "command", "command": "~/.claude/hooks/check-dod-before-commit.sh",     "timeout": 150 },
        { "type": "command", "command": "~/.claude/hooks/cross-review-precommit.sh",      "timeout": 5 },
        { "type": "command", "command": "~/.claude/hooks/context-budget.sh",              "timeout": 5 },
        { "type": "command", "command": "~/.claude/hooks/careful.sh",                     "timeout": 5 },
        { "type": "command", "command": "~/.claude/hooks/completion-gate.sh",              "timeout": 900 },
        { "type": "command", "command": "~/.claude/hooks/state-guard.sh",                  "timeout": 5 },
        { "type": "command", "command": "~/.claude/hooks/check-predeploy-gate.sh",         "timeout": 90 }
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

# Which registered hooks are installed (plan session 5, ADR-016). The decision is codex-dispatch.py's, loaded from it,
# so Claude Code and Codex read the same two lists in $ACTIVE: the optional hooks (diagnostics and crash-recovery) only
# when itd-enabled-hooks.txt names them, and never a hook that itd-disabled-hooks.txt names (the owner opt-out of
# ADR-012). One hook file name per line, '#' starts a comment.
_meta="$(mktemp)"
_selected="$(ITD_DESIRED="$DESIRED_HOOKS" ITD_ACTIVE="$ACTIVE" ITD_REPO="$REPO_ROOT" ITD_META="$_meta" "$PYBIN" -B - <<'PYX'
import importlib.util, json, os, re
from pathlib import Path
repo, active = Path(os.environ["ITD_REPO"]), Path(os.environ["ITD_ACTIVE"])
spec = importlib.util.spec_from_file_location("itd_codex_dispatch", repo / "hooks" / "codex-dispatch.py")
dispatch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dispatch)
lists = {kind: active / getattr(dispatch, kind.upper() + "_HOOKS_FILE") for kind in ("disabled", "enabled")}
disabled, enabled = (dispatch.read_hook_list(lists[kind]) for kind in ("disabled", "enabled"))
known = {path.name for path in (repo / "hooks").glob("*.sh")}
data = json.loads(os.environ["ITD_DESIRED"])
registered, off_disabled, off_optional, on_optional = set(), set(), set(), set()
for event, groups in data.items():
    kept = []
    for group in groups:
        hooks = []
        for hook in group.get("hooks", []):
            name = re.search(r"hooks/([^/\s\"]+)$", hook["command"]).group(1)
            registered.add(name)
            if dispatch.hook_selected(name, disabled, enabled):
                hooks.append(hook)
                if name in dispatch.OPTIONAL_HOOKS:
                    on_optional.add(name)
            else:
                (off_disabled if name in disabled else off_optional).add(name)
        if hooks:
            group["hooks"] = hooks
            kept.append(group)
    data[event] = kept
lines = []
if lists["disabled"].is_file():
    lines.append("OK hooks disabled by %s: %d" % (lists["disabled"].name, len(off_disabled)))
if lists["enabled"].is_file():
    lines.append("OK optional hooks enabled by %s: %d" % (lists["enabled"].name, len(on_optional)))
if off_optional:
    lines.append("OK optional hooks off by default: %d (name them in %s to enable)"
                 % (len(off_optional), lists["enabled"].name))
for kind, names in (("disabled", disabled), ("enabled", enabled)):
    unknown = sorted(names - known)
    if unknown:
        lines.append("WARN %s names no ITD hook: %s (check the spelling, e.g. 'careful.sh')"
                     % (lists[kind].name, " ".join(unknown)))
not_optional = sorted((enabled & known) - dispatch.OPTIONAL_HOOKS)
if not_optional:
    lines.append("WARN %s: not an optional hook: %s (the default hooks always run; check-skills, check-tool-skill and "
                 "check-review-before-commit are no longer registered)" % (lists["enabled"].name, " ".join(not_optional)))
with open(os.environ["ITD_META"], "w", encoding="utf-8") as meta:
    meta.write("".join(line + "\n" for line in lines))
print(json.dumps(data))
PYX
)" || { rm -f "$_meta"; err "hook selection (itd-disabled-hooks.txt / itd-enabled-hooks.txt) failed"; exit 1; }
DESIRED_HOOKS="$_selected"
while IFS= read -r _line; do
  case "$_line" in
    "OK "*) ok "${_line#OK }" ;;
    "WARN "*) warn "${_line#WARN }" ;;
  esac
done < "$_meta"
rm -f "$_meta"

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

# Merge into settings.json (plan session 5): in the ITD-managed event keys the ITD hooks are replaced and every other
# hook is kept - a user's own hook stays even in the same event, matcher and group. An ITD hook is a command in one of
# the two forms sync writes - the bare path or the Windows wrapper `"<python>" -X utf8 "<path>"` - whose path is a hook
# file of this repository (current or RETIRED) in the installed hooks directory (~/.claude/hooks, $ACTIVE/hooks or its
# Windows form); a command that only mentions such a path is the user's. Foreign event keys (e.g. a SessionStart hook
# of another plugin) are not touched. The file is replaced atomically (temp file + rename, mode kept); re-running
# gives the same file. v1.73.1 fail-closed guard: an existing Windows python-wrapper registration is never downgraded to bare .sh
# commands - on Windows Git-Bash would run python-bodied hooks as shell (exit 2) and the '*'-matcher PreToolUse hook
# would deny EVERY tool call (live incident 2026-07-10); a non-windows target over such a file is refused.
_mres="$(ITD_SETTINGS="$SETTINGS" ITD_HOOKS="$EFFECTIVE_HOOKS" ITD_ACTIVE="$ACTIVE" ITD_REPO="$REPO_ROOT" \
  ITD_TARGET="$ITD_TARGET_OS" ITD_DRY="$DRY_RUN" "$PYBIN" -B - <<'PYX'
import json, os, re, shutil, tempfile, time
from pathlib import Path
KEYS = ("UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop", "SubagentStop")
# Hook files ITD registered once and no longer ships: their old registrations are still ITD's own and go away. A hook
# file deleted from hooks/ moves here (tests/verify_hook_selection.py keeps the shipped inventory).
RETIRED = set()
path = os.environ["ITD_SETTINGS"]
names = {p.name for p in Path(os.environ["ITD_REPO"], "hooks").glob("*.sh")} | RETIRED
def to_win(p):
    m = re.match(r'^/mnt/([a-zA-Z])/(.*)$', p) or re.match(r'^/([a-zA-Z])/(.*)$', p)
    return '%s:/%s' % (m.group(1).upper(), m.group(2)) if m else p.replace('\\', '/')
active = os.environ["ITD_ACTIVE"].rstrip("/")
dirs = "|".join(sorted(re.escape(d.lower()) for d in {"~/.claude/hooks", active + "/hooks", to_win(active) + "/hooks"}))
owned = re.compile(r'(?:(?:%s)/([a-z0-9._-]+\.sh)|"[^"]+" -x utf8 "(?:%s)/([a-z0-9._-]+\.sh)")' % (dirs, dirs))
def itd_owned(hook):
    command = str(hook.get("command", "")).replace("\\", "/").strip().lower() if isinstance(hook, dict) else ""
    match = owned.fullmatch(command)
    return bool(match) and (match.group(1) or match.group(2)) in names
try:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
except FileNotFoundError:
    data = {}
except (OSError, ValueError) as exc:
    print("ERROR:%s is not readable JSON (%s)" % (path, exc)); raise SystemExit(0)
hooks_value = data.get("hooks", {}) if isinstance(data, dict) else None
if not isinstance(hooks_value, dict) or not all(isinstance(groups, list) for groups in hooks_value.values()):
    print("ERROR:%s must be a JSON object whose \"hooks\" is an object of event lists; fix it or move it aside" % path)
    raise SystemExit(0)
current = data.get("hooks") or {}
desired = json.loads(os.environ["ITD_HOOKS"])
merged = dict(current)
for key in KEYS:
    foreign = []
    groups = current.get(key)
    groups = [] if groups is None else groups
    if not isinstance(groups, list):
        print("ERROR:%s: hooks.%s is not a list" % (path, key)); raise SystemExit(0)
    for group in groups:
        hooks = group.get("hooks") if isinstance(group, dict) else None
        if not isinstance(hooks, list):
            foreign.append(group)
            continue
        rest = [hook for hook in hooks if not itd_owned(hook)]
        if rest:
            foreign.append(dict(group, hooks=rest))
    if desired.get(key) or foreign:
        merged[key] = (desired.get(key) or []) + foreign
    else:
        merged.pop(key, None)
if merged == current:
    print("UPTODATE"); raise SystemExit(0)
managed = json.dumps({key: current.get(key) for key in KEYS})
if os.environ["ITD_TARGET"] != "windows" and re.search(r'[A-Za-z]:/[^"\\]*python[^"\\]*\.exe', managed, re.I):
    print("REFUSE"); raise SystemExit(0)
if os.environ["ITD_DRY"] == "1":
    print("DRIFT"); raise SystemExit(0)
backup = ""
if os.path.exists(path):
    backup = path + ".bak-" + time.strftime("%Y%m%d-%H%M%S")
    shutil.copy(path, backup)
data["hooks"] = merged
mode = os.stat(path).st_mode & 0o777 if os.path.exists(path) else 0o644
fd, tmp = tempfile.mkstemp(prefix=".settings-", dir=os.path.dirname(os.path.abspath(path)))
try:
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp, mode)
    os.replace(tmp, path)
except BaseException:
    os.unlink(tmp)
    raise
print("WROTE:" + os.path.basename(backup))
PYX
)"
case "$_mres" in
  UPTODATE) ok "settings.json hooks already up-to-date" ;;
  DRIFT)    warn "settings.json hooks would be updated (drift detected)" ;;
  WROTE:*)  ok "settings.json hooks updated (backup: ${_mres#WROTE:})" ;;
  REFUSE)
    err "settings.json registers hooks via a Windows python wrapper, but target OS resolved '$ITD_TARGET_OS'."
    err "REFUSING to overwrite (would brick every tool call). Re-run with ITD_TARGET_OS=windows (+ ITD_WIN_PYTHON), or fix CLAUDE_HOME."
    exit 1 ;;
  ERROR:*)  err "settings.json: ${_mres#ERROR:}"; exit 1 ;;
  *)        err "settings.json merge: unexpected result ($_mres)"; exit 1 ;;
esac

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
