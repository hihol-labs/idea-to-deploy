# G-004 HOOKS-AUTOINSTALL-1 - /adopt and /project offer to install enforcement hooks

Unit `G-004` (medium) is `in_progress` in `.itd-memory/GOAL.json` (harness activation
2026-09-24T20:30:36Z; goal PROPORTIONALITY-DEFAULT, 3/5 verified); the criterion and the
verificationCommand live ONLY there and are not restated here. Branch
`feat/g-004-hooks-autoinstall` over main `49a149e`. Review claim ids: `G-004`,
`G-004:general-review`. Risk tier `medium`. No strict-class surface (money/prod-config/
db-schema/auth/secrets) is touched: the helper writes only a target project's
`.claude/settings.json` after explicit user confirmation and never the user-level file.

Measured before the first edit (main `49a149e`): `/adopt` Step 2 merges hooks into
`.claude/settings.json` by agent-driven Edit with no helper and no confirmation question;
`/project` has no hook step; `README.md:123` says "(not auto-installed)";
`README.ru.md:122` says the same in Russian.

## Allowed Change Areas

- `skills/_shared/itd_project_hooks.py` (new stdlib helper): plan/apply merge of
  `skills/adopt/references/project-settings-template.json` into `<root>/.claude/settings.json`.
- `skills/adopt/SKILL.md`, `skills/project/SKILL.md`: explicit final confirmation step that
  calls the helper; `/adopt` Step 2 delegates to it.
- `README.md`, `README.ru.md`: the install step instead of "not auto-installed".
- `tests/fixtures/fixture-17-adopt/notes.md`: the manual checklist follows the Step 7 offer.
- `.itd/ACCEPTANCE_CONTRACT.json`: active followup switches to G-004 with criteria `G-004-1-oracle` and `G-004-2-ledger` (as G-001..G-003).
- `tests/verify_hooks_autoinstall.py` (new oracle), `tests/run-all.sh`.
- Runtime/inventory lists that must name a new `skills/_shared` file
  (`scripts/itd_install_runtime.py`, `scripts/sync-to-active.sh`) if the oracle suites require it.
- `CHANGELOG.md` [Unreleased], `.itd/IMPACT_GRAPH.json`, `.itd/SCOPE_LOCK.md`,
  `.itd-memory/contracts/G-004.md`, and the harness-written ledger files
  (`.itd-memory/GOAL.json`, `STATE.json`, `events.jsonl`).

## Forbidden

- Any write to `~/.claude/settings.json` or other user-level files.
- Changing the hook set in the template, hook scripts, or `scripts/sync-to-active.sh` behaviour
  for the user-level install.
- Codex adapter (`AGENTS.md`, `hooks/hooks.json`) - the step is Claude Code only.
