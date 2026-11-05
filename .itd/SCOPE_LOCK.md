# REVIEWER-61SOL-1: the independent reviewer of a Claude maker is gpt-6.1-sol

## Current Task

- REVIEWER-61SOL-1 (risk tier high: the mandatory independent review is a critical ITD mechanism). The criteria and
  their verification commands live only in `.itd/ACCEPTANCE_CONTRACT.json` (REVIEWER-61SOL-1-AC1..AC3); this file
  references them and does not restate them.
- Start from main `808a60ed5da3a55861a06df745adfd8c7b191531` (v1.110.4). REL-1.110.4 is verified (published, rolled
  out, runbook 7a accepted on both hosts); this unit is the only open one (WIP=1).
- Owner 2026-11-04 ("нужен 6.1-sol ревьюером"), plan approved 2026-11-05 ("Утверждаю"), and 2026-11-05 ("API тоже на
  6.1-sol"): the subscription reviewer of a Claude maker defaults to `gpt-6.1-sol` with the `gpt-5.6-terra` degraded
  standby; the optional paid API Sol reviewer is `gpt-6.1-sol` at the published price; on the mandatory route a model
  never reviews its own output.

## Allowed Change Areas

- `skills/_shared/itd_free_reviewer_producer.py`: the cross-vendor reviewer set, its standby, the default reviewer and
  the degraded-origin check only.
- `skills/_shared/EXTERNAL_REVIEW_POLICY.json`, `skills/_shared/REVIEW_BROKER_POLICY.json`,
  `skills/_shared/REVIEW_BROKER_POLICY.schema.json`, `skills/_shared/itd_external_reviewer.py`: the Sol reviewer model,
  its published price and the Sol-maker rule only.
- Tests: `tests/verify_reviewer_model_compatibility.py`, `tests/verify_free_reviewer_producer.py`,
  `tests/verify_api_reviewer.py`, `tests/verify_review_broker_policy.py`, `tests/verify_review_broker_primitives.py`,
  `tests/verify_review_broker.py`,
  `tests/run-independent-review-efficacy.py` (recorder default), `tests/verify_independent_review_efficacy.py` (the
  pinned history entries of the new diagnostic snapshot).
- The efficacy archive: one new append-only `benchmarks/independent-review-efficacy/history/route-debts/diagnostic-*`
  snapshot, its manifest entries and the `results/` views; existing snapshots are never edited.
- Docs: `docs/API_REVIEWER.md`, `docs/VERIFICATION_LOOP.md`, `docs/CODEX_ADAPTER.md`,
  `skills/review/references/strict.md`, `skills/cross-review/SKILL.md`, `CHANGELOG.md` (Unreleased).
- `.itd/IMPACT_GRAPH.json`, only if mechanically regenerated; live-model evidence: one new run if the benchmark pin
  requires it.
- Ledgers: `.itd-memory/STATE.json` and `.itd-memory/events.jsonl` through `itd_unit_log.py` only,
  `.itd/ACCEPTANCE_CONTRACT.json`, `.itd/DECISIONS.md`, `BACKLOG.md`, this file.

## Forbidden Change Areas

- The independence class (`itd_reviewer_independence.py`), the Verification Loop policy, the broker budget caps and
  every other reviewer price; `gpt-6-astra` as a reviewer; the maker-side compatibility table.
- `HANDOFF.md`; unit statuses by hand; the efficacy keyring and the trust policy.
- Push, PR, merge, tag, release, rollout and global configuration changes without the owner's explicit confirmation.

## Review Rule

One opposite-GPT review of the final candidate after a PASSED committed-head machine receipt. The installed 1.110.4
runtime still knows only the 5.6 pair, so this unit's own review runs on `gpt-5.6-sol`; reviews run on `gpt-6.1-sol`
after the release that ships this unit is rolled out. If the diff touches an area outside the allowed scope, pause
and reclassify the task before continuing.

## Declared limits

- The `gpt-5.6-sol` and `gpt-5.6-terra` API prices in the policies are older observations (2026-07-28/29) and differ
  from the current OpenAI page; they are not changed in this unit (BACKLOG).
- The efficacy corpus is fixed; the cross-vendor leg measures the `gpt-6.1-sol` reviewer on it, not on real
  candidates.
- The files under tests/fixtures/live-model-evidence/runs/** are recorded model output pinned by hash (DECISIONS
  2026-09-23): findings about the content of those generated documents are outside this unit; editing them would
  break the pin and forge the evidence.
