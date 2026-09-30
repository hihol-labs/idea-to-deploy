# INSTALLED-PROOF-HEAD-1 installed-proof accepts committed-head canaries on one clean checkout

## Current Task

- INSTALLED-PROOF-HEAD-1: `tests/verify_route_debts.py --installed-proof` accepts native canary
  receipts minted in committed-head mode on a clean checkout whose HEAD tree equals the
  candidate, and still rejects foreign, stale or mismatched receipts; `docs/RELEASE_RUNBOOK.md`
  carries a release command template that runs the installed-proof leg and
  `verify_live_model_benchmark.py --require-evidence` on one clean checkout; the new oracle
  `tests/verify_installed_proof_head.py` is RED on the pre-fix validator and GREEN after, and
  `tests/verify_route_debts.py` stays green. The criterion and the verificationCommand live ONLY
  in `.itd-memory/GOAL.json`.

## Allowed Change Areas

- `tests/verify_route_debts.py` - `validate_native_canary` and a helper that reads the candidate
  mode of a canary receipt from its `baseCommit` against the checkout HEAD (HEAD = staged, parent
  of HEAD = committed-head, anything else = refusal) and passes it to `validate_machine` and
  `validate_adjudication`. No change to what the aggregate asserts about the runtime, wrappers,
  adapters or the native test log.
- `tests/verify_installed_proof_head.py` (new)
- `docs/RELEASE_RUNBOOK.md` - the release command template on one clean checkout.
- `tests/run-all.sh` - register the oracle in CORE.
- `.itd/IMPACT_GRAPH.json` - rebuilt by `tests/build_impact_graph.py`.
- `.itd-memory/contracts/INSTALLED-PROOF-HEAD-1.md` (new)
- `.itd-memory/GOAL.json`, `.itd-memory/STATE.json`, `.itd-memory/events.jsonl` - status
  transitions only through the goal harness.
- `.itd/DECISIONS.md`, `BACKLOG.md`, `.itd/SCOPE_LOCK.md` (this file) - records.
- `.itd/ACCEPTANCE_CONTRACT.json` - the INSTALLED-PROOF-HEAD-1 activeFollowup and criteria
  INSTALLED-PROOF-HEAD-1-1-oracle, INSTALLED-PROOF-HEAD-1-2-ledger.

## Forbidden Change Areas

- `HANDOFF.md` - a local untracked hand-over packet; it never enters the reviewed diff.
- `skills/_shared/itd_verification_loop.py` and every producer: committed-head minting already
  works there; the defect is in the installed-proof validator of the aggregate oracle.
- `tests/verify_live_model_benchmark.py` - the live-evidence leg is correct; the template only
  runs it on the checkout it already requires.
- The release oracle command of any future REL unit (BACKLOG item 4 "wrong reason on a dirty
  tree" stays a separate unit).
- The unit criterion and verificationCommand; editing unit statuses by hand.
- Merge and push - only on the owner's explicit command.

## Review Rule

High tier: full independent checker from a fresh session and a different model/provider
(gpt-5.6-sol pre-PR), plus a `/review` pass before the multi-file commit. If the diff touches an
area outside allowed scope, pause and reclassify the task before continuing.
