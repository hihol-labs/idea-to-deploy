# PRODUCER-FALLBACK-LEDGER-1

## Current Task

- PRODUCER-FALLBACK-LEDGER-1: let a degraded (Sol -> Terra transport fallback) review bind both direct sends of its
  prompt ledger instead of refusing its own receipt (owner 2026-10-15, "исправь продюсер отдельным юнитом").

## Allowed Change Areas

- `skills/_shared/itd_free_reviewer_producer.py` - the prompt ledger binding (`_direct_sends`,
  `_prompt_ledger_binding`, `_bind_prompt_ledger`, `verify_prompt_ledger`, `phase_one_receipt`, `verify_phase_one`).
- `tests/verify_free_reviewer_producer.py` - the fallback ledger cases.
- `CHANGELOG.md`, `BACKLOG.md`, `.itd/ACCEPTANCE_CONTRACT.json`, `.itd/DECISIONS.md`, `.itd/SCOPE_LOCK.md`,
  `.itd/IMPACT_GRAPH.json` - records.

## Forbidden Change Areas

- `HANDOFF.md`; the fallback policy itself (`transport_fallback_permitted`, the Sol/Terra pair); other skills, hooks,
  agents and scripts; the ledger stays append-only and records every send.

## Review Rule

One independent checker (gpt-5.6-sol) on the exact committed candidate before `itd pr create`.
