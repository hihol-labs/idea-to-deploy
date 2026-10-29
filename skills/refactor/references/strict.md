# Refactor - strict route

Read this file when Step 0 of `SKILL.md` chose the strict route: the project declares `itd-route: strict` or
`itd-domain: data-sensitive`, the arguments contain `--strict`, or the task falls in a strict class of the global
rules. These steps run together with Steps 1-4 of `SKILL.md`; on the minimal path none of them runs.

## S1. Scope freeze (before Step 1)

After identifying the target file/directory from the arguments, activate the scope freeze:

```bash
# Write freeze state — limits edits to the refactoring target (dual-write: /tmp + platform temp)
tmpd="$(python3 -c 'import tempfile;print(tempfile.gettempdir())' 2>/dev/null || python -c 'import tempfile;print(tempfile.gettempdir())' 2>/dev/null || echo /tmp)"  # win-ok: цепочка падает в /tmp (шим exit!=0)
mkdir -p /tmp 2>/dev/null || true
echo "/path/to/refactor/directory" | tee "/tmp/claude-freeze-${CLAUDE_SESSION_ID:-default}.state" > "$tmpd/claude-freeze-${CLAUDE_SESSION_ID:-default}.state" 2>/dev/null || echo "/path/to/refactor/directory" > "$tmpd/claude-freeze-${CLAUDE_SESSION_ID:-default}.state"
```

This prevents accidental edits outside the refactoring scope: `hooks/freeze.sh` warns on every edit outside the
frozen directory. If the refactoring legitimately requires changes outside the frozen scope (e.g., updating callers),
the freeze hook will warn and ask for confirmation. With the worktree isolation of Step 0.5 the freeze is not needed:
the worktree already keeps the main tree untouched.

## S2. Remove the freeze (after Step 4)

`hooks/freeze.sh` never clears the state by itself. When the refactoring is verified, remove both copies, so a later
task in the same session is not frozen to this directory:

```bash
tmpd="$(python3 -c 'import tempfile;print(tempfile.gettempdir())' 2>/dev/null || python -c 'import tempfile;print(tempfile.gettempdir())' 2>/dev/null || echo /tmp)"  # win-ok: цепочка падает в /tmp (шим exit!=0)
rm -f "/tmp/claude-freeze-${CLAUDE_SESSION_ID:-default}.state" "$tmpd/claude-freeze-${CLAUDE_SESSION_ID:-default}.state"
```
