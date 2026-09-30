# FLAKE-ADJCHAN-1 receipt selection in the adjudication-channel oracle without the clock

## Current Task

- FLAKE-ADJCHAN-1: `newest_receipt` in `tests/verify_adjudication_channel.py` selects the receipt
  deterministically without `st_mtime` - the minted receipt is the set difference against a
  snapshot taken before the minting command, an ambiguity is a refusal; the new oracle
  `tests/verify_adjudication_channel_clock.py` builds receipts with deliberately inverted mtimes,
  is RED on the pre-fix helper and GREEN after, and the adjudication-channel oracle stays green.
  The criterion and the verificationCommand live ONLY in `.itd-memory/GOAL.json`.

## Allowed Change Areas

- `tests/verify_adjudication_channel.py` - the helper, `checker()` returning the minted receipt,
  its call sites. No change to what the oracle asserts about the channel.
- `tests/verify_adjudication_channel_clock.py` (new)
- `tests/run-all.sh` - register the oracle in CORE.
- `.itd/IMPACT_GRAPH.json` - rebuilt by `tests/build_impact_graph.py`.
- `.itd-memory/contracts/FLAKE-ADJCHAN-1.md` (new)
- `.itd-memory/GOAL.json`, `.itd-memory/STATE.json`, `.itd-memory/events.jsonl` - status
  transitions only through the goal harness.
- `.itd/DECISIONS.md`, `BACKLOG.md`, `.itd/SCOPE_LOCK.md` (this file) - records.
- `.itd/ACCEPTANCE_CONTRACT.json` - the FLAKE-ADJCHAN-1 activeFollowup and criteria
  FLAKE-ADJCHAN-1-1-oracle, FLAKE-ADJCHAN-1-2-ledger.

## Forbidden Change Areas

- `HANDOFF.md` - a local untracked hand-over packet; it never enters the reviewed diff.
- `skills/_shared/itd_verification_loop.py` and every producer: the defect is in the test helper,
  not in the receipt writer. Other `st_mtime` sorts in `tests/` are a separate unit (BACKLOG).
- The unit criterion and verificationCommand; editing unit statuses by hand.
- Merge and push - only on the owner's explicit command.

## Review Rule

Low tier: machine-only checker (proportionality by default). A `/review` pass before the
multi-file commit. If the diff touches an area outside allowed scope, pause and reclassify the
task before continuing.
