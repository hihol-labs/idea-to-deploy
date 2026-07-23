# Operating loops

Idea to Deploy can run bounded, opt-in maintenance loops through a host's native
scheduler. It does not ship a daemon, queue, autonomous runtime, or second
project state store. The host schedules observation/report work; ITD supplies
contracts, routing, validation, budgets, telemetry, and evidence boundaries.

## Start safely

1. Run the readiness diagnostic. It reports binary `ready`, `missing`, or
   `degraded` dimensions with `WHY`/`FIX`; there is no scalar readiness gate.
2. Pick one of the registered recipes. Recipes route to existing lifecycle
   skills and preserve WIP=1.
3. Copy the disabled operating-loop contract into `.itd/`, select recipes and
   add host-native scheduler bindings in `observe` or `report` mode.
4. Explicitly initialize `.itd-memory/operating-loop-runs.jsonl`. The scheduled
   writer will not create project state from malformed input.
5. Keep scheduled work report-only. Any draft or external mutation moves to an
   on-demand session and requires the existing exact host approval boundary.

```text
python skills/_shared/itd_operating_loops.py readiness --root . --host codex
python skills/_shared/itd_operating_loops.py pick --job dependency-health
python skills/_shared/itd_operating_loops.py validate-contract \
  --contract .itd/OPERATING_LOOP_CONTRACT.json
```

## Recipes and trust

The registry contains six reusable patterns: state freshness, test regression,
dependency health, security posture, review drift, and documentation drift.
They compose existing skills; they do not introduce another lifecycle or
execution engine.

Authority progresses only as `observe → report → draft → approved_execute`.
There is no permanent L3. The last stage is an expiring lease bound to one
recipe, capability, exact action payload/targets, host session, and approval.
Scheduled runs never receive mutation authority, auto-merge, push, deploy, or
spending authority.

## Budgets, telemetry, and failures

Preflight decisions are computed under the append lock from the same-day
ledger: empty work exits early, soft limits downgrade to a report, and hard
limits pause. Records use closed JSONL evidence with host-observed duration and
tokens, invocation proof, preflight counters, outcomes, escalations, failure
signals, and verification receipt references. The writer rejects path/link
escapes, replacement races, duplicate IDs, malformed committed history, and
unattested scheduled records.

The closed failure catalog is: runaway, state rot, verifier theater, flake,
overreach, notification fatigue, comprehension debt, parallel collision, and
escalation failure. Signals classify deterministically; unknown or weakly typed
signals fail closed.

## Outcome stories

Success and failure stories follow
[`external-validation/OPERATING_LOOP_STORIES.md`](external-validation/OPERATING_LOOP_STORIES.md).
They remain `UNVERIFIED` until the existing external cohort evaluator accepts
the linked independent record and `validate-story` binds its digest, operators,
hashes, metrics, timestamp, and privacy fields. Stars, self-report, fixtures,
and methodology-owned projects never become external outcomes.

Canonical artifacts:

- `skills/_shared/OPERATING_LOOP_POLICY.json`
- `skills/_shared/OPERATING_LOOP_RECIPES.json`
- `docs/templates/itd/OPERATING_LOOP_CONTRACT*.json`
- `docs/templates/itd/OPERATING_LOOP_RUN.schema.json`
- `docs/templates/itd/OPERATING_LOOP_*_STORY.json`
- `tests/verify_operating_loops.py`
