# G-003 HOOKS-TIER-EXIT-1 - advisory hooks go quiet on a low-risk unit

Unit `G-003` (medium) is `in_progress` in `.itd-memory/GOAL.json` (harness activation
2026-09-23T19:54:45Z; goal PROPORTIONALITY-DEFAULT, 2/5 verified); the criterion and the
verificationCommand live ONLY there and are not restated here. Branch
`feat/g-003-hooks-tier-exit` over main `8d192dd`. Review claim ids: `G-003`,
`G-003:general-review`. Risk tier `medium` (sealed at decomposition): targeted
fresh-session checker + adjudication. No strict-class surface (money/prod-config/
db-schema/auth/secrets) is touched.

Measured before the first edit (main `8d192dd`, WSL, 5 runs each): `check-skills` 204 ms,
`handoff-readiness` 176 ms, `stuck-detection` 113 ms, `context-aware` 111 ms,
`context-budget` 79 ms per invocation. `docs/HARNESS_TRUST_POLICY.json` `hardGates` lists
12 enforcing hooks. `scripts/sync-to-active.sh` installs `hooks/*.sh` and `hooks/*.py`
only - a `hooks/*.json` data file would not reach `~/.claude/hooks`.

Owner decision 2026-09-24: exactly four exempt hooks; `check-skills` stays out because it
writes the skill-active sentinel that the hard gate `check-tool-skill` reads (exempting it
would remove the grace window and increase friction).

## In scope

- `hooks/TIER_EXEMPT.json` (new): `exemptTier: "low"` and exactly four hooks, each with a
  reason - `context-aware.sh`, `context-budget.sh`, `stuck-detection.sh`,
  `handoff-readiness.sh` (advisory only: no deny/ask, no evidence consumed by a gate).
- `hooks/tier_exempt.py` (new stdlib helper, next to `completion_lib.py`):
  `exempt(script, payload) -> bool`. Project: the payload `cwd` ONLY (Claude Code and
  `codex-dispatch.py` send it on all four events), walked up to the nearest
  `.itd-memory/`; no fall-through to `CLAUDE_PROJECT_DIR` or the process cwd - a payload
  without `cwd` or outside any ITD project silences nothing (the repository's own suites
  drive hooks that way and must not be governed by its live STATE). Tier: explicit
  `STATE.currentUnit.riskTier` of an ACTIVE unit (status `in_progress`/`verifying`), else
  the unit of an ACTIVE goal (`GOAL.status: active`) named by `currentUnitId` - and, when
  STATE names an active unit, only that same unit; a closed unit (the harness leaves a
  verified unit in `currentUnit`) silences nothing. NO
  fallback to a policy default (the project template default is `low`; a missing tier
  must not silence anything). True only when the tier is exactly `low`, the script is
  listed and the list parses; any error -> False (the hook behaves as before).
- The four hooks: after reading the payload and before any state read/write or output,
  `if exempt(<self>, payload): return 0`; the helper import is guarded so a missing
  helper leaves the hook unchanged.
- `scripts/sync-to-active.sh`: install `hooks/TIER_EXEMPT.json` alongside the hooks.
- `tests/verify_hook_tier_exit.py` (new, registered in `tests/run-all.sh`): drives each
  listed hook as a subprocess with isolated HOME/TMPDIR/CLAUDE_PROJECT_DIR and a fixture
  STATE. low -> exit 0, empty stdout, no new/changed file under the isolated TMPDIR and
  project `.itd-memory`; medium/high/no tier -> stdout and exit byte-identical to a
  golden captured from the pre-fix hook bytes (`git show 8d192dd:hooks/<h>`) on the same
  fixture. Forbidden list: every `hardGates` script plus state-guard, pii-egress-guard,
  completion-gate, check-review-before-commit, completion-signals, completion-stop,
  check-skills, wip-gate, careful, freeze, model-policy, risk-score, crash-recovery,
  execution-trace, cross-review-precommit, pre-flight-check, session-open-diagnostic -
  any of them in the list is a failure. `--mutations` >= 3 lethal.
- `.itd/IMPACT_GRAPH.json` entries; `CHANGELOG.md` [Unreleased]; one line in
  `docs/HARNESS_ENGINEERING_MAP.md`.

## Allowed Change Areas

- `hooks/TIER_EXEMPT.json`, `hooks/tier_exempt.py`
- `hooks/context-aware.sh`, `hooks/context-budget.sh`, `hooks/stuck-detection.sh`,
  `hooks/handoff-readiness.sh`
- `scripts/sync-to-active.sh`
- `tests/verify_hook_tier_exit.py`, `tests/fixtures/hook_tier_exit/*.prefix.txt`,
  `tests/run-all.sh`
- `.itd/IMPACT_GRAPH.json`, `CHANGELOG.md`, `docs/HARNESS_ENGINEERING_MAP.md`
- `.itd/SCOPE_LOCK.md`, `.itd-memory/contracts/G-003.md`, `.itd/DECISIONS.md`, `BACKLOG.md`
- `docs/DESIGN_SPACE.md` - only the `context-aware.sh` row of the UserPromptSubmit audit
  table (added after c3: the row described the hook as stdin-only)

## Forbidden Change Areas

- Every other hook, `hooks/hooks.json`, `docs/HARNESS_TRUST_POLICY.json`.
- `skills/**`, `.claude/settings.json`, `docs/templates/**` (G-004 owns auto-install).
- Goal ledger transitions by hand (`GOAL.json` / `STATE.json` / `events.jsonl` are written
  by `itd_goal_verify.py` only); `.itd/ACCEPTANCE_CONTRACT.json` until the publication step.
- Any change to what the four hooks print or write on medium/high/unknown tiers.

## Declared limits

- The tier is read per invocation (two small JSON reads); a hook that fires outside a
  project with `.itd-memory/` behaves exactly as before.
- The Codex transport (`hooks/codex-dispatch.py`) keeps spawning the hook; the early exit
  lives in the hook itself so both transports share it.
- Saved time is ~0.1-0.2 s per call on a low unit; the main gain is context (four
  advisory injections disappear on low).

## Out of scope

- Early exit in the dispatcher, `check-skills` / `pre-flight-check` / any gate.
- Hook auto-install (G-004), external pilot (G-005).

## Route history

- c1 (targeted, fresh opus) BLOCKED on tree `3eb383b2`: a verified low unit left in
  `STATE.currentUnit` kept the four hooks silent after the unit ended (important) +
  SCOPE_LOCK precedence wording (minor) + unpinned lifecycle/GOAL fallback (minor). Fixed:
  active-status check in `hooks/tier_exempt.py`, oracle cases `closed-unit-not-exempt` and
  `goal-fallback-silent` (RED 4 failed on the c1 helper, GREEN after), 5th mutation.
- c2 (targeted, fresh opus) BLOCKED on tree `abfa6635`: c1 findings confirmed closed; new
  (important) root resolution fell through to `CLAUDE_PROJECT_DIR`/process cwd, so
  `verify_hook_depth` / `verify_platform_tmp_and_new_hooks` went red under an ambient low
  unit of this repository (16/4, 6/1); (minor) GOAL fallback ignored a STATE/GOAL unit
  mismatch and the goal status; (minor) SCOPE_LOCK claimed the order matched
  handoff-readiness. Fixed: payload-cwd-only resolution, same-unit and active-goal guards,
  oracle variants nocwd/foreign/mismatch/abandoned/goal-none (RED 15 failed on the c2
  helper, GREEN 70/0), mutations 7/7; both suites green under an ambient low unit (20/0,
  7/0) in a scratch copy.
- c3 (targeted, fresh opus) PASSED_WITH_WARNINGS on tree `943f6fec`: F1-F4 confirmed closed
  (F1 reproduced and controlled in a scratch copy). The route accepts only PASSED, so the
  four minor findings were closed: `chmod +x` no longer applied to `TIER_EXEMPT.json`;
  `docs/DESIGN_SPACE.md` context-aware row (scope amended by one row); an active STATE unit
  without id and tier silences nothing (oracle variant `noid`, RED 4 failed on the c3
  helper); the identity check now compares exit, stdout, stderr and the set of files a
  hook touches; 8th mutation.
