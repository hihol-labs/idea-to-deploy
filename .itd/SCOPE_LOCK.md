# Scope Lock — GPG-001 global PR/API gate

## Current Task

Preserve the accepted broker/bootstrap slice while repairing the confirmed
MEM-8 prompt-supply-chain trust regression introduced by commit `954a3b6`.
After a clean exact-candidate review, implement the next bounded slice of the
approved nine-point plan: an isolated fresh-model free reviewer producer,
signed two-phase receipt, and GitHub App live-coordinate revalidation. WIP=1.
Live App/ruleset deployment, negative canaries, release publication, and
global installation remain later GPG-001 slices.

## Allowed Change Areas

- restore the closed tool trust registry schema/validator and MEM-8 mutation
  coverage without rolling back the accepted GPG bootstrap
- restore read-only `/adopt` prompt-bearing provider inventory and the
  security-audit MEM-8 control
- free fresh-session/different-model reviewer producer and strict isolation
- signed exact-candidate review receipt and App-side live revalidation
- free-primary routing with paid provider only behind explicit consent/budget
- global gate registry, ruleset payload/drift checks, adoption, and doctor
- central broker, protected machine oracle, Windows/WSL guarded PR transport
- focused mutation, security, release, and host-adapter tests and docs
- `.itd/` and `.itd-memory/` records for `GPG-001`

## Forbidden Change Areas

- rollback/reset of the existing WIP or removal of accepted broker/oracle
  guarantees as a shortcut to restoring MEM-8
- storing API/App private keys in repository, plugin cache, prompts, logs,
  receipts, Windows user environment, or WSL shell profiles
- using the previously exposed OpenAI API key or automatically dispatching a
  paid reviewer without separate explicit user consent and budget
- executing candidate code in a process that can read reviewer credentials
- treating generic CLI/OAuth, inherited-context/same-session review, caller
  status, outage, zero balance, stale coordinates, incomplete review, generic
  binary, unknown maker, or missing oracle as satisfying the cloud gate
- weakening WIP=1, MEM-8, exact-candidate binding, maker/checker separation,
  App-owned checks, human merge authority, or Verification Loop gates
- editing an installed plugin cache instead of publishing a new ITD release

## Acceptance Boundary

The next repair is accepted only when `verify_tool_trust_inventory.py`, the
affected adoption/security tests, meta-review, host-adapter checks, and quick
suite pass on one exact candidate, secret scrub is clean, and a fresh
different-model bound `/review` returns no Critical/Important findings or
unverified contours and is adjudicated. Only then may the free-review producer
slice begin. Neither repair nor producer slice completes GPG-001.
