# RSI-DEBT-3

Current unit: `RSI-DEBT-3`, low risk. The owner approved this sealed unit after
the ROUTE-REPAIR-2 ledger-close merged as `e97fc7c` through PR #290.

## Criterion

`itd_goal_verify.py` records the unit evidence as one line per top-level command
of an `A && B` `verificationCommand` in the form `<command>: exit <code>, stdout
sha256 <16 hex>, <last line>`; the terminal event repeats the same summary; a
single command keeps its current form; and the compound case is a RED-first
regression.

The sealed verification command remains unchanged:

```sh
sh skills/_shared/itd_py.sh tests/verify_goal_tools.py && sh skills/_shared/itd_py.sh tests/verify_goal_bounded_autonomy.py
```

If implementation evidence shows that this criterion is inaccurate, stop and
show the exact proposed correction to the owner before writing it.

## Allowed change areas

- `skills/goal/scripts/itd_goal_verify.py`
- `tests/verify_goal_tools.py`
- `tests/verify_goal_bounded_autonomy.py`
- `.itd/RSI-DEBT-3_ROOT_CAUSE.md`
- `.itd/ACCEPTANCE_CONTRACT.json`, only to mirror and close this sealed criterion
- `.itd/SCOPE_LOCK.md`
- `.itd-memory/contracts/RSI-DEBT-3.md`
- `.itd-memory/GOAL.json`, `.itd-memory/STATE.json`, and
  `.itd-memory/events.jsonl`, only through the goal harness transitions
- `.itd/IMPACT_GRAPH.json`, only as the mechanical regeneration
  `tests/build_impact_graph.py` demands after `tests/verify_goal_tools.py`
  changed (measured: the full mirror's only candidate-attributed red was
  `verify_verification_profiles`, whose freshness check names exactly that
  regeneration as the fix)

## Required evidence

- RED-first regression for the compound command before implementation.
- A compound success records one ordered line for each top-level command.
- The terminal unit event repeats the exact same multiline evidence.
- A single command retains its existing evidence form.
- Failure preserves shell `&&` short-circuit behavior and does not claim an
  unexecuted command.
- Each mutation targets one guarantee and runs only in a disposable git
  worktree; verify that worktree's status after every run.
- Any temporary root compared for containment is normalized with `.resolve()`
  before comparison so native Windows 8.3 path forms remain valid.
- The sealed verification command and relevant focused tests pass on WSL and
  native Windows.
- Independent review covers the whole RSI-DEBT-3 unit against `main`; no delta
  review may satisfy the unit.

## Forbidden change areas

- `PE5-008` and `PE5-009`.
- The sealed RSI-DEBT-3 criterion or verification command without prior owner
  approval.
- Any accepted historical evidence, receipt, event, or verified timestamp.
- ROUTE-REPAIR-3 or any other pending unit.
- Verification Loop receipt semantics, reviewer routing, round ceilings, or
  unrelated refactoring.
- `--no-verify`, destructive Git recovery, force push, or merge without the
  owner's explicit command.

WIP remains one unit. Status transitions are written by
`skills/goal/scripts/itd_goal_verify.py`, never by hand.
