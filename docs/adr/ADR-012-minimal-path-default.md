# ADR-012: The default route for ordinary work is the minimal path; methodology development stops

- **Status:** accepted (owner decision 2026-10-06, after the ITD value measurement; amended the same day by the
  owner's variant B: narrower conclusion, module-level class check and leak journal on neuroexpert, two more hooks
  opted out, Windows in the same rollout)
- **Supersedes:** the MANDATORY routing of ordinary work in the global methodology block (skill line on every
  request, `/task` routing, mandatory `/review` before a multi-file commit, the `/test` refute pass, the Sol round
  for medium work) for this owner's installs. Does not touch ADR-011 (default risk tier `low`) or the human gates for
  irreversible actions.
- **Amended by:** [ADR-013](ADR-013-graph-lite-measured-exception.md) (owner decision 2026-10-07) - one measured,
  default-off exception to item 5: the `/graph` skill and its first template. Nothing else in this record changes.

## Context

The retro of 2026-10-04 paused new methodology goals: 60 of the last 82 verified units were repairs of the
methodology itself, and its value had never been measured. A pre-registered A/B measurement ran in
`~/projects/itd-value-exp` (goal 6/6, commits 29e4527..e37047b): 6 ABBA pairs on the frozen neuroexpert base, 16
seeded defects in a sealed manifest, fresh subagent executors, arm M on the full ITD route (Skill `/task` -> `/test`
with the refute pass -> `/review`, plus one gpt-5.6-sol round on the two medium pairs), arm B without the route. The
decision rule was fixed before the run: the route is justified for a tier only if the catch rate gain is at least
0.25 (and, for low, the median duration ratio M/B is at most 3.0).

| Tier | Seeded | Caught by M | Caught by B | Median duration M/B | Median tokens M/B |
|---|---|---|---|---|---|
| low | 11 | 6 | 6 | 3.22 | 1.53 |
| medium | 5 | 2 | 2 | 12.68 | 1.66 |

`DECISION: medium=BENEFIT_NOT_SHOWN low=BENEFIT_NOT_SHOWN`. All 16 defects had the same outcome in both arms. Arm B
also loaded the global CLAUDE.md with the methodology habits (write tests, run the suite, sometimes a mutation
check), so the cheap habits were in both arms; what arm M added was the machinery, and it added cost without a
single extra catch. The protocol's own `decision.otherwise` says what follows: work in that tier goes without the
route. Report: `reports/REPORT.md` and `reports/SUMMARY-ru.md` of the experiment.

**Scope of the conclusion** (owner, variant B, 2026-10-06): the benefit is not shown on defects that were already in
the code (pre-existing seeded defects). Not measured: defects the executor introduces itself, leaks after a commit,
and high-risk work. Both arms missed the same 8 defects, all in neighbouring functions of the module (owner and access
checks, an empty currency, a dedup window, a 24-hour boundary); a diff review does not look there by construction.

## Decision

1. **Ordinary work** (feature, bug, refactor, tests, docs in an existing project) takes the minimal path: understand,
   change, write or adjust tests, run the suite, report with numbers. The skill line, `/task` routing, mandatory
   `/review`, the refute pass, the Sol round, `/goal` ledgers and `.itd/` contracts are not required for it. Skills
   run on the owner's request or when one clearly shortens the work.
2. **Kept as mandatory**: human confirmation before irreversible or external actions (deploy, migrations and
   production data, money, push/PR/egress, deletion); secrets never leave the machine; tests for new code and a suite
   run before a commit; `/session-save` memory.
3. **Hooks**: `check-tool-skill.sh`, `check-skills.sh`, `check-review-before-commit.sh`,
   `session-open-diagnostic.sh` (a multi-kilobyte, often stale diagnostic on every prompt) and `execution-trace.sh`
   (methodology debugging telemetry that writes `.claude/traces` into product repositories) are no longer registered
   on the owner's installs, WSL and Windows. `scripts/sync-to-active.sh` now honours a user-owned
   `~/.claude/itd-disabled-hooks.txt`, so a later sync does not bring them back. `pre-flight-check.sh` (the
   parallel-session warning) and `state-guard.sh` stay. The other hooks stay registered, among them `check-predeploy-gate.sh`
   and `pii-egress-guard.sh` (with `permissions.defaultMode: bypassPermissions` they are the mechanical confirmation
   for deploy and egress), `careful.sh` (destructive commands), `completion-gate.sh` (tests actually ran green before
   a commit), `check-dod-before-commit.sh` and `cross-review-precommit.sh` (a reminder only). If
   `check-dod-before-commit.sh` blocks ordinary commits by demanding the `/test` skill rather than a test run, it is
   added to the same list; that is one line, not a methodology change.
4. **Where the rule lives**: a personal section after the `ITD:END` marker of `~/.claude/CLAUDE.md` on WSL and on
   Windows (sync preserves it; the managed block is untouched, so the template tests stay green) and
   `~/projects/.claude/CLAUDE.md`.
5. **Methodology development stops.** No new methodology goals. A change to ITD is made only when it blocks product
   work, and it is minimal. A new check becomes mandatory only after it wins a measurement of the same kind.
6. **Module-level class check for money and access on neuroexpert** (variant B): one line in the project CLAUDE.md of
   neuroexpert - when a task touches money or access, read the whole module for four classes: owner or empty id,
   currency and amount, dedup and idempotency, time boundaries. It is not a gate; whether it found something is
   written to the leak journal.
7. **Leak journal on neuroexpert for 30 days** (2026-10-07..2026-11-05), threshold fixed in advance: any leak in money
   or access, or two or more leaks of the same class, leads to one targeted check that is measured the same way before
   it becomes mandatory. The journal separates "introduced by the change" from "was there before".
8. **Rollout order**: merge only on the owner's command; the Windows opt-out and personal section are created before
   any Windows sync; then one `sync-to-active.sh` (it lifts the freeze at 86ca61f); then check that `settings.json`
   has none of the removed hooks and the personal sections are in place. No sync from `main` before this ADR is merged:
   it would bring the hooks back.

### Retro proposals closed by this decision

- `docs/retros/RETRO-2026-10-04.md`: candidates 3, 5 and 7 are replaced by this ADR; candidate 4 is closed by the
  `session-open-diagnostic.sh` opt-out; candidate 6 stays open.
- `docs/retros/RETRO-PILOT-LOW-1.md`: proposals 1 and 3-7 are closed; proposal 2 (classify pre-deploy commands by
  action rather than by text) is fixed only when it blocks product work.

## Consequences

- Ordinary work stops paying x3-x17 wall-clock for the route; the human gates for irreversible actions stay.
- Not covered by the measurement: the executor's own defects, leaks after a commit and high-risk work (production
  data, money movement, migrations). The human gates remain for high-risk work; nothing here relaxes them.
- Six pairs and one run per arm are a small sample. The leak journal (item 7) is the signal for what to add next; a
  targeted check is added only when its threshold is crossed and is measured the same way before it becomes mandatory.
- The findings of the measurement go to BACKLOG with status "do not do unless it blocks product work".

## Rejected

- **Another, larger measurement**: the gain was zero on every one of the 16 defects and the low tier already failed
  the cost bound; more pairs cannot turn this into a gain that pays for the route.
- **Editing the managed methodology block** (`docs/templates/global-claude-md.md`): six tests read the template; the
  personal section reaches the same result without a cascade.
- **Disabling all hooks** (`disableAllHooks`): would also remove the deploy/egress confirmation and the memory hooks.
