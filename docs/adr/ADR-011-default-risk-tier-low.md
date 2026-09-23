# ADR-011: The target-project default risk tier is `low`; five classes are `high` by construction

- **Status:** accepted (G-001 RISK-TIER-1, goal "proportionality by default", 2026-09-22)
- **Supersedes:** the `defaultRiskTier: medium` template default introduced with the
  calibrated completion policy (v1.51.0); does not touch ADR-003/ADR-005 (evidence-first
  review) or `.itd/STOP_RULE_POLICY.json`.

## Context

The advisor audit of 2026-09-22 (three perspectives: measurements, business-analyst,
devils-advocate) found that the proportionality machinery already exists -
`skills/_shared/PROPORTIONALITY_POLICY.json` risk routes, the risk table in
`docs/VERIFICATION_LOOP.md` (for `low` the independent checker is "forbidden as unnecessary
cost"), the calibrated mode of `hooks/completion-gate.sh` - but is not applied: the ledgers
carry 30 high / 21 medium / 5 low units, the project template shipped `defaultRiskTier:
medium`, and nothing forced `high` where it is non-negotiable. The methodology's own A/B
(`docs/retros/RETRO-2026-07-08.md`) measured x3.5 wall-clock and x7 tool calls for the
strict route at an identical verified-completion rate on an ordinary unit. Hooks were
measured at 1.44% of active wall (devils-advocate, 30 746 tool calls) and are not the
lever; the route is.

## Decision

1. `docs/templates/itd/COMPLETION_POLICY.json` - what `/adopt` and `/project` install into
   a target project - carries **`defaultRiskTier: low`**. The methodology repository keeps
   no `.itd/COMPLETION_POLICY.json` (the oracle asserts its absence); its completion gate runs on the built-in `medium`
   defaults in `hooks/completion-gate.sh` and `docs/templates/itd/itd_hygiene.py`, which
   stay `medium` as the fail-closed fallback for any project without a policy file.
2. `PROPORTIONALITY_POLICY.json` gains a machine-readable **`strictClasses`** object with
   exactly five classes - `money`, `prod-config`, `db-schema`, `auth`, `secrets` - each
   with `keywords`, `paths` and `tier: high`. `skills/_shared/itd_risk_classes.py` is the
   only reader; a missing or malformed block is a fail-closed error.
3. `skills/task/scripts/itd_unit_log.py activate` (the /task writer of
   `STATE.currentUnit.riskTier`; `/goal --activate` projects the owner-approved tier from
   `GOAL.json` and does not run the matcher) matches the unit goal and the Allowed Change Areas of
   `.itd/SCOPE_LOCK.md` against `strictClasses`; on a hit it prints the class and pattern
   and records `riskTierMatch{class,match}` in STATE whatever the declared tier; when the
   declared tier is below `high` it also **forces `riskTier=high`** and records
   `riskTierForced{declared,class,match}`. `--risk-tier` stays mandatory (unchanged since
   LPD-002 R4c). An existing but unreadable SCOPE_LOCK fails the activation closed.

## Consequences

- The template default is the FALLBACK tier: `active_risk_tier` reads
  `STATE.currentUnit.riskTier` first (which `/task` makes mandatory at activation) and
  the goal unit tier next, and only then `defaultRiskTier`; in `calibrated` mode the
  completion gate treats `low` and `medium` alike. The flip therefore changes the intent
  a target project starts from - an unclassified unit is `low`, not `medium` - and the
  documented default in `/adopt`; the route cost itself is decided by the declared tier
  and the forced strict classes (checker c5). The expensive reviewer contour is spent
  where the A/B showed it pays - tails and the five strict classes.
- The matcher is a lexical floor, not a classifier: a goal that hides its money/auth
  nature is not detected. The reviewer contour on high units and the human gate on
  irreversible actions remain the backstop; this ADR lowers the default, not the ceiling.
- The Allowed Change Areas are read from `.itd/SCOPE_LOCK.md` at activation time and are
  not bound to the unit: in the `/task` flow the routed skill may rewrite SCOPE_LOCK after
  activation, so a stale scope can force a tier and a fresh one is not re-matched. The goal
  text is the primary input; SCOPE_LOCK is a second net, not a contract (checker c3).
- Accepted false positives (raise review cost, never lower safety): `*.env.*` on the JS
  expression `process.env.NODE_ENV`, `*production*` on docs such as
  `production-checklist.md`, `авториз*` on `авторизованном`, `migration` on "route
  migration", `касс*` on "кассета", `*checkout*` on the git hook name `hooks/post-checkout`,
  `*/migrate/*` on `skills/migrate/`, `authoriz*` on "user-authorized", `*/signin*` on
  "signing", `*auth*.ts` on `useAuthorStore.ts`; measured by checker rounds c5-c7 on the 61
  unit goals recoverable from `events.jsonl` + `GOAL*.json`, 5 would be forced to high
  (G-001, G-005, HDX-009, HDX-010, RSI-DEBT-1).
- No CLI escape hatch: to change a class the owner edits the policy file, which the oracle
  `tests/verify_risk_tier_default.py` pins (shape, exact class set, tier high, wiring,
  four lethal mutations).
- `/goal --activate` writes `riskTier` from `GOAL.json` through the same STATE writer but
  does not run the matcher (goal units carry an owner-approved tier at decomposition);
  recorded as a follow-up in BACKLOG, not claimed here.
- Rejected: merging hooks into one process (1.44% of wall; single timeout, single point of
  failure), a review-round budget (forbidden by `STOP_RULE_POLICY.json`, measured S04b/R6),
  new lite/strict profiles (duplicate of the existing risk table).
