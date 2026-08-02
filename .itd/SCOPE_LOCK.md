# Scope Lock — GPG-002 Windows UNC doctor reliability

## Current Task

Fix the native-Windows `itd gate doctor` false `UNAVAILABLE` result on WSL UNC
checkouts without weakening exact-candidate validation. The bounded slice may
change only the local-adjudication outer timeout policy, its regression test,
release notes and GPG-002 state/contracts. It also records the authorized local
Git-config cleanup: the legacy PAT must be invalid before cleanup and all
credential-bearing GitHub URLs must be removed without persisting the token.
WIP=1.

## Allowed Change Areas

- `skills/_shared/itd_gate_control.py` timeout selection for local adjudication
- `tests/verify_gate_profile_doctor.py` native-Windows UNC and local-path guards
- root-cause, acceptance, verification, state, changelog and handoff records
- standard version/release metadata only in the separate release candidate
- local `.git/config` branch remote URL sanitation outside the PR

## Forbidden Change Areas

- changing receipt/path/candidate binding, accepted verdicts or risk routing
- increasing child Git-probe bounds or making any timeout unbounded
- applying the longer timeout to ordinary local/native paths
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

GPG-002 is accepted only when RED proves the previous 30-second false timeout;
the focused test proves exactly 180 seconds for native Windows UNC and 30
seconds elsewhere; stale/foreign/mismatch canaries, Windows-native execution,
meta-review, host adapters and quick suites pass; a fresh independent full
checker and exact adjudication accept the candidate; the clean release is
installed on Windows/WSL; and a Windows-bound current receipt makes the real
UNC doctor report `LOCAL_REVIEWED`. Local credential cleanup is complete only
when GitHub returns 401 for the legacy PAT and a secret-safe config scan finds
zero credential-bearing GitHub URLs. No `PROTECTED` claim is added.

## Completion

GPG-002 satisfied this boundary on 2026-08-02. PR #180 and release PR #181
merged with both required GitHub checks green; version 1.95.1 is installed on
both hosts; and the real Windows-native UNC doctor returned `LOCAL_REVIEWED`
in 32.57 seconds from a current Windows-bound adjudication receipt. The local
credential cleanup also completed with the legacy credential returning 401
before removal and zero credential-bearing GitHub URLs afterward. The next
unit must open a new scope lock and may not reinterpret this result as
`PROTECTED`.
