# Manual verification — fixture 27 (/context-mode-setup)

`/context-mode-setup` is a **read-only** orchestrator/integration skill for the
upstream [Context Mode plugin](https://github.com/mksglu/context-mode) by @mksglu
(license **ELv2**, source-available — *not* MIT). The upstream engine sandboxes
large tool output into a local SQLite FTS5 store so the agent searches it
(`ctx-search`) instead of dumping it into context (vendor claim ~98% per-call
reduction). This skill ships **no** upstream source: it detects install state,
runs/prints the verified install commands, and maps the plugin onto the
idea-to-deploy lifecycle. It MUST NOT modify project files. This fixture
regressionally fixes the detect-before-claim rule, the no-vendoring-of-ELv2
contract, the accurate-mechanism rule, the lifecycle fit, and the gate-coexistence
guarantee.

Named `context-mode-setup`, not `context-mode`: the upstream plugin ships its own
skill literally named `context-mode` (verified in a live install test), so a bare
`/context-mode` would collide.

## Fixture status

`pending` — **deferred**, same bucket as `fixture-15-advisor`,
`fixture-21-mcp-docs`, and `fixture-26-caveman` (read-only, detect/advise stdout
flow). For now: manual checklist below. The stub satisfies
`check-skill-completeness.sh`.

## /context-mode-setup — Scenario A: context pressure, not installed (happy path)

User pastes the prompt from `idea.md`: context window filling up from build logs.

### Critical contract: no files written

After the run, `output/` must contain no skill-authored files. `/context-mode-setup`
only detects and advises.

### Expected output shape

- Recognizes context-window pressure → routes to /context-mode-setup.
- Runs read-only detection (`claude plugin list | grep context-mode`); finds it
  NOT installed → says so explicitly (never claims it is active).
- Runs/prints the verified CLI install commands and the Node ≥ 22.5 /
  Claude Code ≥ 1.0.33 requirement and the ~631-tok always-on cost.
- After install + restart, instructs to run the `ctx-doctor` skill to confirm.

## /context-mode-setup — Scenario B: already installed, coexistence check

User: "context mode уже стоит, не мешает он методологии?"

### Expected

- Runs `claude plugin details context-mode` (components + cost) and the
  `ctx-doctor` skill (duplicate-hook / stale check); reports the result.
- Confirms idea-to-deploy gates still fire: a >2-file commit without a review is
  still blocked by `check-review-before-commit.sh`; the skill-enforcement counter
  still escalates. Reports pass/fail honestly.
- If clean → "17 idea-to-deploy hooks + 6 Context Mode hooks coexist, no
  conflict." If not → names the conflict, does not hide it.

## /context-mode-setup — Scenario C: license / vendoring boundary

User: "давай просто вкомпилим движок в репозиторий"

### Expected

- Declines by default: upstream is ELv2, idea-to-deploy is MIT → license
  conflict; the engine needs a native dependency (`better-sqlite3`) → breaks
  zero-native-dep design.
- Offers the supported path instead: marketplace install + this skill.
- No upstream ELv2 source is copied into the repo; attribution to @mksglu intact.

## /context-mode-setup — Scenario D: short task, recommend against

User (one-line fix): "включи context mode для этого".

### Expected

- Output is already small → the ~631-tok always-on overhead + sandbox indirection
  cost more than they save.
- Recommends against enabling it here; reserves it for long sessions / big dumps.

## Why pending (not active)

Phase 1 snapshot validation is file-shaped (`verify_snapshot.py` checks written
files against `expected-files.txt`). `/context-mode-setup` writes nothing and only
affects a detect/advise stdout flow, so structural automation is deferred to the
Phase 2 stdout-snapshot scheme. This stub anchors the contract for manual
regression until then.
