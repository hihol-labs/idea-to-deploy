# ITD-PILOT-TESTGAP: the test-gap pilot run, the REL-1.110.6 closure

## Current Task

- ITD-PILOT-TESTGAP: the pilot of `docs/measurements/ITD-PILOT-TESTGAP-PROTOCOL.md` (failure class «a review round
  spent on a test gap») - the OS-level isolation wrapper and the extended canary, the runs baseline -> A -> B ->
  A+B (conditional) -> held-out case H within the owner-approved budget, the owner's blind marks, the result by the
  decision rule of section 8, the lesson card and the owner's decision on plan session 16. The criteria and their
  verification commands live only in `.itd/ACCEPTANCE_CONTRACT.json` (ITD-PILOT-TESTGAP-AC1..AC3); this file
  references them and does not restate them.
- Start from merged main `3a770e2ff028455da60aaca60bebefa129825989` (PR #394). WIP=1: REL-1.110.6 is verified in
  this candidate; this unit is the only open one.
- The same PR carries the REL-1.110.6 closure by the ADR-016 closure convention (tree of 3a770e2 = reviewed tree of
  the a5 PASSED receipt) and its post-candidate DECISIONS (publication, rollout, step 7a, acceptance).
- Documents only; risk tier medium. The pilot evidence (run records, transcripts, proxy logs, blind files, tools)
  stays git-ignored in `.itd-memory/host-inputs/ITD-PILOT-TESTGAP*/` and enters the machine as an input.

## Allowed Change Areas

- `docs/measurements/ITD-PILOT-TESTGAP-PROTOCOL.md`: section 9 (amendment 4, the canary model deviation), section 10
  (results) and section 11 (lesson card). Sections 1-8 are not changed.
- Ledgers: `.itd-memory/STATE.json` and `.itd-memory/events.jsonl` through `itd_unit_log.py` only,
  `.itd/ACCEPTANCE_CONTRACT.json`, `.itd/DECISIONS.md`, `BACKLOG.md`, this file.

## Forbidden Change Areas

- Skills, hooks, agents, scripts, tests and their fixtures; the trust policy and hook registrations; the global
  Claude Code and ITD configuration; unit statuses by hand. The pilot's variant texts do not become a rule or a gate
  (ADR-012 item 5).
- `HANDOFF.md` - a local untracked hand-over packet; it never enters the reviewed diff.
- Push, PR, merge, the gate registry, the review proxy and removal of the trusted worktree without the owner's
  explicit confirmation.

## Review Rule

One opposite-GPT review of the final candidate after a PASSED committed-head machine receipt; its one receipt under
the bare unit id is accepted by the commit cache, the pre-push gate, `itd pr create` and the closure. If the diff
touches an area outside the allowed scope, pause and reclassify the task before continuing.

## Declared limits

- The pilot measures one case with a test gap (K1), one control (K0) and one held-out case (H), N = 3 per pair; the
  result is a basis for an A/B, not for a mandatory rule. K2 and K3 were dropped by the budget order of section 5.
- The blind marking is partial (section 10.4): run notifications showed the pattern result next to the variant.
- The canary ran on `claude-sonnet-5-5` by the owner's decision after the API filter refused it on `claude-opus-5-5`;
  all counted runs are `claude-opus-5-5`.
