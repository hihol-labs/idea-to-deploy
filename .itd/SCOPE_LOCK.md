# Scope Lock — GPG-001 global PR/API gate

## Current Task

Reconcile the completed GPG-001 release with its authoritative plan, state and
handoff after the implementation and release candidates were independently
accepted, merged and deployed. This bounded closure slice may update only
GPG-001 contracts/state/handoff and add durable copies of the already-produced
exact evidence. It must not change runtime behavior, retroactively strengthen
the selected `local-submission/local-review` claim, or present an optional App
profile as live. WIP=1.

## Allowed Change Areas

- restore the closed tool trust registry schema/validator and MEM-8 mutation
  coverage without rolling back the accepted GPG bootstrap
- restore read-only `/adopt` prompt-bearing provider inventory and the
  security-audit MEM-8 control
- free fresh-session/different-model reviewer producer and strict isolation
- signed exact-candidate review receipt and App-side live revalidation
- free-primary routing with paid provider only behind explicit consent/budget
- portable role/deployment/protection profile contract
- bounded profile-doctor inventory and executable
- canonical `gates.json` v2 profile registry plus explicit profile registration
- local-review guarded push/PR routing backed by current exact adjudication
- fail-closed staged-to-single-parent-commit review bridge with no second-commit borrowing
- legacy v1 registry read/doctor/PR compatibility without silent migration
- local/App/organization claim routing with non-overclaiming fleet aggregation
- forged/stale/foreign and profile-incompatibility negative canaries
- self-hosted and managed GitHub App manifest registration for user or
  organization owners with profile-valid visibility
- global gate registry, ruleset payload/drift checks, adoption, and doctor
- central broker, protected machine oracle, Windows/WSL guarded PR transport
- focused mutation, security, release, and host-adapter tests and docs
- `.itd/` and `.itd-memory/` records for `GPG-001`
- post-release reconciliation of the GPG-001 plan, scope, acceptance status,
  handoff and durable exact-evidence bundle

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
- requiring maker, maintainer, and deployer to be different people, or giving
  the reviewer App contents/pull-request/deployment write authority
- claiming `PROTECTED` for local-review or App-check-only profiles
- editing an installed plugin cache instead of publishing a new ITD release

## Acceptance Boundary

GPG-001 closure is accepted only when the selected local-review result is
stated consistently in the plan, acceptance contract, state and handoff; the
implementation/release merge coordinates and exact receipt dependencies are
durable in Git; the current reconciliation candidate passes session hygiene,
operational continuation, meta-review, host-adapter and quick suites; and a
fresh independent full checker reports no Critical/Important findings or
unverified contours before exact adjudication. This slice does not claim live
App/broker enrollment, `PROTECTED`, credential rotation, or a passing Windows
doctor for the known UNC-timeout contour.
