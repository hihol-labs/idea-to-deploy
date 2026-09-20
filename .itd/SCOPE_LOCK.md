# CLOSE-BLOCKERS-1

Current unit: `CLOSE-BLOCKERS-1`, medium risk. The unit's code is merged
(PR #293, PR #294). The goal harness verified the unit against the tree of
`main` at `dce3208`; the resulting ledger transition is not yet on `main` and
is published by this candidate. At `dce3208` itself the ledger rows still read
`in_progress`. This candidate is the post-1.104.0 documentation follow-up +
CLOSE-BLOCKERS-1 ledger closure: it publishes the harness-written closure of
the unit together with the documentation debt of the cycle that followed
1.104.0. The active unit id stays `CLOSE-BLOCKERS-1` so the closure is
attributed to the unit it closes. The owner chose on 2026-09-20 to merge the
ledger closure into this docs PR instead of a separate ledger-close PR; the
reason is recorded in `.itd/DECISIONS.md`.

The diff contains no executable change: no code, no test, no hook, no skill,
no agent, no contract that a gate executes.

## Criterion

Unchanged and already met. The reviewer-provider freshness oracle is green with
the Anthropic row typed `unavailable-transport-not-enrolled` and a current
`checkedAt`; the session-close contract that the session-save resolver actually
applies in this repository declares `startupTimeoutSeconds` as an integer of at
least 600; and that guarantee is pinned by a RED-first check.

The sealed verification command:

```sh
sh skills/_shared/itd_py.sh tests/verify_reviewer_provider_freshness.py && sh skills/_shared/itd_py.sh tests/verify_session_hygiene_quality.py
```

Declared limit: the first leg is date-bound by design. The freshness record
expires 30 days after `checkedAt`, so a `--recheck` of this unit after
2026-10-15 regresses until the inventory is re-checked again. That is the
oracle's property, not a defect of this unit.

Declared limit of this candidate: docs-vs-history consistency is NOT bound
evidence. The maker checked each `CHANGELOG.md` claim with a scripted token
match against the messages of the merged commits `ac4ba46` (#280), `c15a8f3`
(#282), `2d50a12` (#284), `dee34a3` (#289), `cd9979c` (#291), `26794a6` (#293)
and `dce3208` (#294), plus the diff of `26794a6` for the status literal and the
timeout key. Those messages and diffs are not part of the bound review
material and the machine receipt does not validate `CHANGELOG.md` claims, so
the reviewer cannot establish that property and is not asked to.

Two further properties of `BACKLOG.md` are likewise NOT bound evidence. The
transferred entries were produced by a script that reads
`.itd-memory/BACKLOG-PENDING-goal-reporter.md` under the sha256 pin
`0a0d6e7e76ee361b6f1bdaebdd514e443c448b9ca7217221bb67b9cd14136a0b` and copies
its sections instead of retyping them; one section heading was reworded on
purpose. That pending file is git-ignored and is not part of the bound review
material. The added section about the CLOSE-BLOCKERS-1 close session records
what the maker observed in receipts and logs under the git-ignored
`.itd-memory/verification-loop/CLOSE-BLOCKERS-1/`, which is not bound either.
The reviewer cannot establish either property and is not asked to.

For this candidate the criterion adds nothing executable. What it must satisfy
is consistency: the documents agree with each other and with the ledger, and
the ledger rows agree with each other and with the event journal.

If evidence shows that a documented claim is inaccurate, stop and show the
exact proposed correction to the owner before writing it.

## Allowed change areas

- `CHANGELOG.md` - the new `## [Unreleased]` section only
- `BACKLOG.md` - the entries transferred from
  `.itd-memory/BACKLOG-PENDING-goal-reporter.md` and the route measurements of
  the CLOSE-BLOCKERS-1 close session
- `.itd/DECISIONS.md` - appended entries only; no existing text is edited
- `.itd/SCOPE_LOCK.md`
- `.itd-memory/GOAL.json`, `.itd-memory/STATE.json` and
  `.itd-memory/events.jsonl`, only as written by the goal harness: the
  CLOSE-BLOCKERS-1 closure (status `verified`, evidence, `verificationReceipt`,
  one `verified` event)

## Required evidence

- The diff contains no executable change; every touched path is in the list
  above.
- Ledger consistency: `GOAL.json`, `STATE.json` and `events.jsonl` agree on
  CLOSE-BLOCKERS-1 as `verified`; the event is a single harness-written
  `verified` row whose evidence is the two-line record of the sealed command.
- `.itd/DECISIONS.md` is append-only: the previous file is a byte prefix of the
  new one.
- The reviewer is asked to check internal consistency of the documents and
  ledger consistency, NOT to re-review the unit's code. That code is already merged
  and independently reviewed: PR #293 Sol r2/r3 PASSED, PR #294 Sol fix-r1
  PASSED, harness close Sol close2-r1 PASSED. Whole-unit code coverage is
  therefore not a property this candidate can or should establish.
- The quick mirror ends `DONE fails:none` and is bound as a command of the
  machine receipt, not narrated.

## Forbidden change areas

- Any code, test, hook, skill or agent.
- A version bump, release notes, manifests, badges or documentation pins.
- `PE5-008` and `PE5-009`.
- `ROUTE-REPAIR-3` or any other pending work; the route circle around
  ledger-close review and the other defects recorded here are recorded, not
  fixed.
- Accepted evidence in `.itd/ACCEPTANCE_CONTRACT.json`, and any accepted
  historical evidence, receipt, event, or verified timestamp.
- The sealed CLOSE-BLOCKERS-1 criterion or verification command.
- Existing text of `.itd/DECISIONS.md` and existing `CHANGELOG.md` sections.
- `--no-verify`, destructive Git recovery, force push, or merge without the
  owner's explicit command.

WIP remains one unit. Status transitions are written by
`skills/goal/scripts/itd_goal_verify.py`, never by hand.
