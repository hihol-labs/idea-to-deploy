# CLOSE-BLOCKERS-1

Current unit: `CLOSE-BLOCKERS-1`, medium risk. The owner approved this unit on
2026-09-19, after the candidate already existed: the two blockers of the red
explicit session close were diagnosed and repaired on 2026-09-15 on branch
`fix/session-close-blockers`, and the review gate then showed that, without a
unit of its own, the candidate would have been receipted under the identity and
scope of the already verified `RSI-DEBT-3`. This unit exists so the evidence is
attributed to what it actually covers.

## Criterion

The reviewer-provider freshness oracle is green with the Anthropic row typed
`unavailable-transport-not-enrolled` and a current `checkedAt`; the
session-close contract that the session-save resolver actually applies in this
repository declares `startupTimeoutSeconds` as an integer of at least 600; and
that guarantee is pinned by a RED-first check.

The sealed verification command:

```sh
sh skills/_shared/itd_py.sh tests/verify_reviewer_provider_freshness.py && sh skills/_shared/itd_py.sh tests/verify_session_hygiene_quality.py
```

Declared limit: the first leg is date-bound by design. The freshness record
expires 30 days after `checkedAt`, so a `--recheck` of this unit after
2026-10-15 regresses until the inventory is re-checked again. That is the
oracle's property, not a defect of this unit.

If implementation evidence shows that this criterion is inaccurate, stop and
show the exact proposed correction to the owner before writing it.

## Allowed change areas

- `.itd/REVIEW_PROVIDER_FRESHNESS.json` - `checkedAt` and the
  `anthropic-subscription` row only
- `tests/verify_reviewer_provider_freshness.py` - the one hardcoded status
  literal only
- `docs/SESSION_EXIT_CONTRACT.json` - the `startupTimeoutSeconds` key only
- `tests/verify_session_hygiene_quality.py` - the pin on that key only
- `BACKLOG.md` - the records of the two blockers, their measurements and the
  route defects measured while publishing them
- `.itd/ACCEPTANCE_CONTRACT.json`, only to mirror this criterion
- `.itd/SCOPE_LOCK.md`
- `.itd/DECISIONS.md` - the three durable decisions of 2026-09-15
- `.itd-memory/GOAL.json`, `.itd-memory/STATE.json` and
  `.itd-memory/events.jsonl`, only through the goal harness transitions

## Required evidence

- The sealed command exits 0 on the candidate; it binds the current
  `checkedAt`, the validity of the signed dual-host proofs, and the typed
  Anthropic row.
- The Anthropic route is NOT declared available: an unavailable row carries
  `unavailabilityEvidence`, never `requiredEvidence`.
- Exactly one assertion hardcodes the status literal, and it changed together
  with the record.
- The timeout pin follows the resolver, not a file name: the resolver lines of
  `skills/session-save/SKILL.md` are pinned verbatim and the applied contract
  is derived from them.
- RED-first is a property of the check itself: on every run the same predicate
  refuses a contract without the key and every too-tight or malformed limit.
- Each mutation targets one guarantee and runs only in a disposable git
  worktree; that worktree is compared with the candidate afterwards.
- The quick mirror ends `DONE fails:none` and is bound as a command of the
  machine receipt, not narrated.
- What the maker only observed - the 2026-09-15 diagnosis, CLI versions,
  reachable sources, wall-clock timings - is labelled as observation and is
  not offered as bound evidence.
- Independent review covers the whole CLOSE-BLOCKERS-1 unit against `main`; no
  delta review may satisfy the unit.

## Forbidden change areas

- `PE5-008` and `PE5-009`.
- The sealed CLOSE-BLOCKERS-1 criterion or verification command without prior
  owner approval.
- Any accepted historical evidence, receipt, event, or verified timestamp.
- `ROUTE-REPAIR-3` or any other pending work; the goal-reporter and
  completion-gate defects found on the way are recorded, not fixed here.
- `docs/templates/itd/itd_hygiene.py`, the session-save resolver, the
  completion gate and the signal classifier.
- Verification Loop receipt semantics, reviewer routing, round ceilings, or
  unrelated refactoring.
- `--no-verify`, destructive Git recovery, force push, or merge without the
  owner's explicit command.

WIP remains one unit. Status transitions are written by
`skills/goal/scripts/itd_goal_verify.py`, never by hand.
