# Hooks — Skill Discovery Enforcement

These eleven hooks turn the methodology from "use it if you remember" into "you literally cannot forget". Without them, even Claude itself will skip the methodology under time pressure (verified the hard way during a 2026-04-07 production incident — see [the case study](#case-study) below).

## Defense-in-depth overview (v1.16.2)

Quality enforcement now spans **five layers**, from earliest-feedback to latest. Each layer catches something the previous ones missed:

| # | Layer | Where it runs | When | What it catches | Bypass? |
|---|---|---|---|---|---|
| 0 | `pre-flight-check.sh` *(v1.5.0)* | Local | UserPromptSubmit | Stale context, parallel session conflicts, missing memory | Soft context injection only |
| 1 | `check-skills.sh` | Local | UserPromptSubmit | Ambiguous prompts → wrong routing | Soft reminder only |
| 2 | `check-tool-skill.sh` | Local | PreToolUse on Bash/Edit/Write | Ad-hoc tool calls when a skill fits | Soft reminder only |
| 3 | `check-skill-completeness.sh` + `check-commit-completeness.sh` | Local | PreToolUse on Write/Edit/MultiEdit, PreToolUse on `git commit` | Incomplete skills (missing references/triggers/fixtures), incomplete commits | Only via `.methodology-self-extend-override` file |
| 4 | **[CI workflow](../docs/CI.md)** (new in v1.8.0) | GitHub Actions | Push to main, every PR | Everything in the meta-rubric that local hooks missed OR scenarios where local hooks were never installed | Only by admin override of branch protection (audit-logged) |

Layers 1–3 give fast local feedback. Layer 4 is the server-side last line of defense — catches contributors who never installed local hooks and future Claude sessions on unprepared machines. See [`docs/CI.md`](../docs/CI.md) for how to enable it as a required check on the main branch.

## What they do

| Hook | When it fires | What it does | Blocks? |
|---|---|---|---|
| `pre-flight-check.sh` *(v1.5.0)* | Every user prompt (UserPromptSubmit) | Loads `git log -10`, `git status`, recent commits, and the project memory index (`MEMORY.md`) into Claude's context before each turn. Detects stale parallel-session lockfiles (`.active-session.lock`) and warns if another Claude session has touched this project in the last 10 minutes. | No — soft context injection only |
| `check-skills.sh` | Every user prompt (UserPromptSubmit) | Scans the prompt for Russian/English trigger words. If matched, injects a system reminder telling Claude which skill should be invoked first. Silent if no trigger matches. | No — soft reminder only |
| `check-tool-skill.sh` | Before every Bash/Edit/Write/NotebookEdit (PreToolUse) | Injects a checklist reminder asking Claude to verify a skill doesn't fit before doing raw tool calls. Rate-limited to one reminder per 60 seconds per session. | No — soft reminder only |
| `check-skill-completeness.sh` *(v1.5.1)* | **Before** Write/Edit/MultiEdit on `skills/*/SKILL.md` (PreToolUse) | Parses the pending tool input, extracts the skill name from the file path, verifies that `references/` exists and is non-empty (if the pending content mentions it), that `hooks/check-skills.sh` has a trigger phrase for the skill, and that a matching fixture exists in `tests/fixtures/`. | **Yes — exit 2 with `hookSpecificOutput.permissionDecision: "deny"`.** The Write never runs, the file never lands on disk. |
| `check-commit-completeness.sh` *(v1.5.1)* | Before every Bash command matching `git commit` (PreToolUse) | Parses the staged diff. If any `skills/<name>/SKILL.md` is staged, the hook requires matching references/hook/fixture to also be staged (or already present on disk). Written to be the last line of defense against the v1.4.0 "Potemkin release" pattern. | **Yes — exit 2 with `hookSpecificOutput.permissionDecision: "deny"`.** The commit never runs. |

### Safety guardrails (v1.17.0, optional)

| Hook | When it fires | What it does | Blocks? |
|---|---|---|---|
| `careful.sh` | Before Bash (PreToolUse) | Detects destructive commands (rm -rf, DROP TABLE, git push --force, git reset --hard, chmod 777, pipe-to-bash) and injects a warning asking Claude to confirm with the user. Activated via `CAREFUL_MODE=1` env var or a state file. | No — soft warning only |
| `freeze.sh` | Before Edit/Write/NotebookEdit (PreToolUse) | Restricts file modifications to a specific directory scope. Any edit outside the frozen scope triggers a warning. Activated via a state file written by `/freeze <path>`. Deactivated with `/unfreeze`. | No — soft warning only |

**Activation:**
- **`careful.sh`** — **always active** inside methodology repos (auto-detected via `.claude-plugin/plugin.json`). Outside methodology repos: opt-in via `CAREFUL_MODE=1` env var or state file.
- **`freeze.sh`** — **automatic** when skills like `/bugfix`, `/refactor`, `/perf` start work (they write the scope to `/tmp/claude-freeze-{session}.state`). Can also be activated manually: `/freeze src/auth`. Deactivate with `/unfreeze` or skill completion.

All eleven hooks are written in Python 3 (works out of the box on macOS/Linux/WSL), depend only on the standard library, and exit silently in degenerate cases (bad JSON, empty payload, not in the methodology repo) — they never break your session on unrelated work.

**Enforcement hooks are scoped to methodology-repo work only.** The two v1.5.0 hooks walk up from `cwd` looking for `.claude-plugin/plugin.json`; if not found, they return 0 immediately. You can safely install them globally and still use Claude Code on ordinary projects — they fire only when you're inside a methodology (or methodology-like) repository.

## Recommended setup

```bash
# 1. Copy hooks to your user-level Claude config
mkdir -p ~/.claude/hooks
cp hooks/check-skills.sh ~/.claude/hooks/
cp hooks/check-tool-skill.sh ~/.claude/hooks/
cp hooks/check-skill-completeness.sh ~/.claude/hooks/   # v1.5.0 enforcement
cp hooks/check-commit-completeness.sh ~/.claude/hooks/  # v1.5.0 enforcement
cp hooks/careful.sh ~/.claude/hooks/                     # v1.17.0 safety guardrail
cp hooks/freeze.sh ~/.claude/hooks/                      # v1.17.0 scope guardrail
chmod +x ~/.claude/hooks/*.sh

# 2. Register them in ~/.claude/settings.json
```

Add this `hooks` block to your `~/.claude/settings.json` (merge with existing settings, do not replace):

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/check-skills.sh",
            "timeout": 5
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash|Edit|Write|NotebookEdit",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/check-tool-skill.sh",
            "timeout": 5
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/check-commit-completeness.sh",
            "timeout": 5
          }
        ]
      },
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/check-skill-completeness.sh",
            "timeout": 5
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/careful.sh",
            "timeout": 5
          }
        ]
      },
      {
        "matcher": "Edit|Write|NotebookEdit",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/freeze.sh",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

> **v1.5.1 note:** `check-skill-completeness.sh` moved from PostToolUse to PreToolUse in v1.5.1 because PostToolUse exit 2 is non-blocking per [Anthropic's hooks spec](https://code.claude.com/docs/en/hooks.md) — the tool already ran by that point, so the file would land on disk and the "block" would only be a message. PreToolUse exit 2 actually prevents the Write from executing. Both v1.5.1 hooks emit the correct `hookSpecificOutput.permissionDecision` field (v1.5.0 used a top-level `decision` field that was silently ignored by the schema validator).

**Important — enforcement vs. reminder hooks:**

- `check-skills.sh` and `check-tool-skill.sh` are **soft reminders** (no blocking). Safe to run on all projects.
- `check-skill-completeness.sh` and `check-commit-completeness.sh` are **hard blocks** (exit 2, decision: deny/block). They only fire inside methodology repos (detected via `.claude-plugin/plugin.json`). Outside the methodology repo they return 0 immediately.

If you never work on methodology repos, the two enforcement hooks (`check-skill-completeness.sh` and `check-commit-completeness.sh`) are harmless but unused — you can skip registering them. The other three (`pre-flight-check.sh`, `check-skills.sh`, `check-tool-skill.sh`) are useful on every project regardless of whether it's a methodology repo.

After saving, the hooks fire on the very next prompt — no restart needed (Claude Code's settings watcher picks them up live).

## Verifying

Pipe-test the prompt hook:

```bash
echo '{"prompt":"у меня баг в auth"}' | ~/.claude/hooks/check-skills.sh
```

You should see JSON output with `additionalContext` mentioning `/bugfix` and `security-guidance`. If you see nothing, the hook is silent — try a clearer trigger word.

Pipe-test the tool hook:

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"ls"}}' | ~/.claude/hooks/check-tool-skill.sh
```

You should see JSON with a SKILL CHECK reminder about Bash.

Pipe-test the completeness hook (v1.5.1) — must be run inside a methodology repo to see the block:

```bash
cd /path/to/idea-to-deploy
echo '{"tool_name":"Write","tool_input":{"file_path":"skills/fake-skill/SKILL.md","content":"body references/foo-checklist.md"}}' \
  | ~/.claude/hooks/check-skill-completeness.sh
```

You should see JSON with `hookSpecificOutput.permissionDecision: "deny"` and a list of missing artifacts (references, trigger, fixture). Exit code 2.

Pipe-test the commit-gate hook (v1.5.1) — must be inside a methodology repo with a staged SKILL.md:

```bash
cd /path/to/idea-to-deploy
# Stage a fake SKILL.md without its supporting files first, then:
echo '{"tool_name":"Bash","tool_input":{"command":"git commit -m test"}}' \
  | ~/.claude/hooks/check-commit-completeness.sh
```

You should see JSON with `hookSpecificOutput.permissionDecision: "deny"` explaining which skill is incomplete. Exit code 2.

## Customizing triggers

Open `check-skills.sh` and edit the `TRIGGERS` list (line ~25). Each entry is a tuple `(regex_pattern, hint_text)`. The pattern matches against the lowercased prompt; add Russian or English phrases as needed. The script handles Unicode lowercasing correctly (uses Python's `str.lower()`, not `tr`).

Common pitfalls to avoid:
- Don't use `tr '[:upper:]' '[:lower:]'` for Russian — it doesn't lowercase Cyrillic without a UTF-8 locale.
- Don't make patterns too greedy. `*` matches everything; prefer word boundaries (`\b`).
- Avoid duplicate hint text — the dedup is by exact string match.

## Case study

In a 2026-04-07 hotfix session, Claude (Opus 4.6) spent ~2 hours doing direct SSH/sed/curl work to fix a 3-week-old production auth outage. Throughout that work, `/bugfix` was a perfect fit and was never invoked. The user noticed and asked: "почему ты не используешь методологию?". The honest answer: nothing was forcing it.

These hooks are the answer. After installation, the same prompt — "у меня баг в auth" — would inject a SKILL HINT about `/bugfix` and `security-guidance` into Claude's context **before** Claude's first response. It then becomes physically impossible to skip the methodology without acknowledging it first.

## Limitations

- The hooks are user-level (`~/.claude/`), not project-level. If you want them only for specific projects, move them to `.claude/settings.json` in the project root and gitignore them.
- The PreToolUse hook fires on every Bash/Edit/Write — that's a lot of noise on long sessions. If it bothers you, change the matcher to match only specific tools or specific commands (e.g., `Bash(git:*)`).
- Hooks slow each prompt by ~50ms (Python startup). Acceptable for interactive use; might matter for scripted/CI use.
- Only Russian + English triggers are included by default. Add your language by editing `check-skills.sh`.

## License

Same as the parent project (MIT).
