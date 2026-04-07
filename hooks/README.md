# Hooks — Skill Discovery Enforcement

These two hooks turn the methodology from "use it if you remember" into "you literally cannot forget". Without them, even Claude itself will skip the methodology under time pressure (verified the hard way during a 2026-04-07 production incident — see [the case study](#case-study) below).

## What they do

| Hook | When it fires | What it does |
|---|---|---|
| `check-skills.sh` | Every user prompt (UserPromptSubmit) | Scans the prompt for Russian/English trigger words. If matched, injects a system reminder telling Claude which skill should be invoked first. Silent if no trigger matches. |
| `check-tool-skill.sh` | Before every Bash/Edit/Write/NotebookEdit (PreToolUse) | Injects a checklist reminder asking Claude to verify a skill doesn't fit before doing raw tool calls. Never blocks — only reminds. |

Both hooks are written in Python 3 (works out of the box on macOS/Linux/WSL), depend only on the standard library, and exit silently in degenerate cases (bad JSON, empty payload, etc.) — they never break your session.

## Recommended setup

```bash
# 1. Copy hooks to your user-level Claude config
mkdir -p ~/.claude/hooks
cp hooks/check-skills.sh ~/.claude/hooks/
cp hooks/check-tool-skill.sh ~/.claude/hooks/
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
      }
    ]
  }
}
```

After saving, the hooks fire on the very next prompt — no restart needed (Claude Code's settings watcher picks them up live).

## Verifying

Pipe-test the prompt hook:

```bash
echo '{"prompt":"у меня баг в auth"}' | ~/.claude/hooks/check-skills.sh
```

You should see JSON output with `additionalContext` mentioning `/debug` and `security-guidance`. If you see nothing, the hook is silent — try a clearer trigger word.

Pipe-test the tool hook:

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"ls"}}' | ~/.claude/hooks/check-tool-skill.sh
```

You should see JSON with a SKILL CHECK reminder about Bash.

## Customizing triggers

Open `check-skills.sh` and edit the `TRIGGERS` list (line ~25). Each entry is a tuple `(regex_pattern, hint_text)`. The pattern matches against the lowercased prompt; add Russian or English phrases as needed. The script handles Unicode lowercasing correctly (uses Python's `str.lower()`, not `tr`).

Common pitfalls to avoid:
- Don't use `tr '[:upper:]' '[:lower:]'` for Russian — it doesn't lowercase Cyrillic without a UTF-8 locale.
- Don't make patterns too greedy. `*` matches everything; prefer word boundaries (`\b`).
- Avoid duplicate hint text — the dedup is by exact string match.

## Case study

In a 2026-04-07 hotfix session, Claude (Opus 4.6) spent ~2 hours doing direct SSH/sed/curl work to fix a 3-week-old production auth outage. Throughout that work, `/debug` was a perfect fit and was never invoked. The user noticed and asked: "почему ты не используешь методологию?". The honest answer: nothing was forcing it.

These hooks are the answer. After installation, the same prompt — "у меня баг в auth" — would inject a SKILL HINT about `/debug` and `security-guidance` into Claude's context **before** Claude's first response. It then becomes physically impossible to skip the methodology without acknowledging it first.

## Limitations

- The hooks are user-level (`~/.claude/`), not project-level. If you want them only for specific projects, move them to `.claude/settings.json` in the project root and gitignore them.
- The PreToolUse hook fires on every Bash/Edit/Write — that's a lot of noise on long sessions. If it bothers you, change the matcher to match only specific tools or specific commands (e.g., `Bash(git:*)`).
- Hooks slow each prompt by ~50ms (Python startup). Acceptable for interactive use; might matter for scripted/CI use.
- Only Russian + English triggers are included by default. Add your language by editing `check-skills.sh`.

## License

Same as the parent project (MIT).
