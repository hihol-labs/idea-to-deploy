# ITD-PLAN-S13: final measurement and decision of the ADR-016 program, the REL-1.110.5 closure

## Current Task

- ITD-PLAN-S13: plan session 13 of the ADR-016 program - documents only. The before/after probe of the plan
  section 2 metrics with its protocol, the 30-day journal template, the protocol and the first baseline of one
  Harness2 pilot on the owner-chosen failure class ("a review round spent on a test gap"), the owner decision on the
  conditional sessions 14-16. The criteria and their verification commands live only in
  `.itd/ACCEPTANCE_CONTRACT.json` (ITD-PLAN-S13-AC1..AC3); this file references them and does not restate them.
- Start from merged main `10f970c5` (PR #391, v1.110.5). WIP=1: REL-1.110.5 is verified (rollout and runbook step 7a);
  this unit is the only open one.
- The same PR carries the REL-1.110.5 verified record (plan rule 5: no separate ledger-close PR).
- Risk tier medium: the diff changes no shipped skill, hook, agent, script or test; it adds measurement documents and
  ledger records. One owner confirmation: publication (push, PR, merge after green CI).

## Allowed Change Areas

- `docs/measurements/ITD-SIMPLIFY-PROBE.md`, `docs/measurements/ITD-JOURNAL-TEMPLATE.md`,
  `docs/measurements/ITD-PILOT-TESTGAP-PROTOCOL.md` - new documents.
- `.itd/IMPACT_GRAPH.json` and `docs/HARNESS_DOCS_STATE.json`, only if mechanically regenerated for the new documents.
- Ledgers: `.itd-memory/STATE.json` and `.itd-memory/events.jsonl` through `itd_unit_log.py` only,
  `.itd/ACCEPTANCE_CONTRACT.json`, `.itd/DECISIONS.md`, `BACKLOG.md`, this file.

## Forbidden Change Areas

- `HANDOFF.md` - a local untracked hand-over packet; it never enters the reviewed diff.
- Skills, hooks, agents, scripts, tests, the measurement tools under `docs/measurements/itd-simplify/`, the efficacy
  archive, trust policy and hook registrations; unit statuses by hand.
- Journal entries and raw measurements of the private projects (buying, invoices): they stay in the git-ignored
  `.itd-memory/`; the PR carries the template only. The invoices project is not changed.
- A new mandatory check, gate or `/retro` mode (ADR-012 item 5): the pilot adds text to a headless run only.
- Push, PR, merge and changes of the global configuration without the owner's explicit confirmation.

## Review Rule

One opposite-GPT review of the final candidate after a PASSED committed-head machine receipt; its one receipt under
the bare unit id is accepted by the commit cache, the pre-push gate, `itd pr create` and the closure. If the diff
touches an area outside the allowed scope, pause and reclassify the task before continuing.

## Declared limits

- The probe is a cheap step before A/B and proves no correctness; the baseline and the current install were measured
  on different days and no live agent task was compared (probe section 1.4).
- The pilot stops after its first baseline run until the owner approves the budget numbers (protocol section 9).
