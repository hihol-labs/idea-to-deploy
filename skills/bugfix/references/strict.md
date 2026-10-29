# Bugfix - strict route

Read this file when Step 0 of `SKILL.md` chose the strict route: the project declares `itd-route: strict` or
`itd-domain: data-sensitive`, the arguments contain `--strict`, or the task falls in a strict class of the global
rules. These steps run together with Steps 1-5 of `SKILL.md`; on the minimal path none of them runs.

## S1. Scope freeze (before Step 1)

After identifying the target file/directory from the arguments or the error context, activate the scope freeze:

```bash
# Write freeze state — limits edits to the bug's directory (dual-write: /tmp + platform temp)
tmpd="$(python3 -c 'import tempfile;print(tempfile.gettempdir())' 2>/dev/null || python -c 'import tempfile;print(tempfile.gettempdir())' 2>/dev/null || echo /tmp)"  # win-ok: цепочка падает в /tmp (шим exit!=0)
mkdir -p /tmp 2>/dev/null || true
echo "/path/to/bug/directory" | tee "/tmp/claude-freeze-${CLAUDE_SESSION_ID:-default}.state" > "$tmpd/claude-freeze-${CLAUDE_SESSION_ID:-default}.state" 2>/dev/null || echo "/path/to/bug/directory" > "$tmpd/claude-freeze-${CLAUDE_SESSION_ID:-default}.state"
```

This prevents accidental edits outside the bug's scope during debugging: `hooks/freeze.sh` warns on every edit
outside the frozen directory. If the fix legitimately requires changes outside the frozen scope (e.g., a shared
utility), the freeze hook will warn and ask for confirmation — which is correct behavior.

## S2. ROOT_CAUSE.md (Step 3)

**Root-cause gate:** before writing the fix, record the root cause as an artifact. For non-trivial bugs, create
`ROOT_CAUSE.md` (from `docs/templates/ROOT_CAUSE.md` of the methodology when it is at hand) with these sections:

- **Summary** - the root cause in one sentence.
- **Reproduction** - steps that reliably trigger the bug (or why a reliable repro is not possible).
- **Evidence** - logs, stack traces, failing test output, git bisect result.
- **Fix Hypothesis** - what the fix changes and why that removes the cause.
- **Regression Test** - the test that fails on the old code and passes on the fix.
- **Constraints** - fix the root cause, not the symptom; change one variable at a time; add the regression test
  before the implementation when feasible; after three failed fix attempts stop and question the architecture.

The gate is **fail-closed** — if you cannot state the root cause in one sentence with evidence, it is not found yet;
keep analysing (Step 2), do not jump to a fix. This prevents symptom-patching and repeat bugs. For a one-line
trivial fix (typo, off-by-one with obvious cause) the root-cause sentence of Step 3 is sufficient — no separate file.

## S3. Remove the freeze (after Step 5)

`hooks/freeze.sh` never clears the state by itself. When the fix is verified, remove both copies, so a later task in
the same session is not frozen to this directory:

```bash
tmpd="$(python3 -c 'import tempfile;print(tempfile.gettempdir())' 2>/dev/null || python -c 'import tempfile;print(tempfile.gettempdir())' 2>/dev/null || echo /tmp)"  # win-ok: цепочка падает в /tmp (шим exit!=0)
rm -f "/tmp/claude-freeze-${CLAUDE_SESSION_ID:-default}.state" "$tmpd/claude-freeze-${CLAUDE_SESSION_ID:-default}.state"
```
