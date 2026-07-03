# Fixture 32 — /retro

The maintainer wants the methodology to propose its own improvements from
telemetry — without giving up the human merge gate. The loop is split:
FACTS (script) → PROPOSALS (model, evidence-required) → MERGE (human, ordinary
PR pipeline).

Sample prompts that should route here:
- "проведи ретроспективу методологии"
- "методологическое ретро за месяц"
- "что улучшить в методологии по телеметрии?"
- "предложи улучшения методологии"
- "run a methodology retro / itd retro"

Expected behavior: `/retro` runs `skills/retro/scripts/itd_retro_scan.py` over
the workspace (VCR + regressions from events.jsonl, active goals/backpressure
from GOAL.json, pending gates from STATE.json, SKILL_BYPASS ledger, cost
ledgers), pastes the scan output verbatim (facts are script-generated, never
recalled from memory), then turns facts into RANKED proposals where every
proposal cites a number or a quoted reason from the scan (no evidence — no
proposal; anti-Goodhart: signals must be external — live-run failures, false
positives, bypass reasons — not "improve our own metric"). Proposals land in
`docs/retros/RETRO-YYYY-MM-DD.md` (methodology repo) or project memory; the
user picks what enters the next release backlog. NO self-merge: every change
still goes through the ordinary branch → /review → PR → human merge pipeline.
