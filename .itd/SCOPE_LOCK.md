# G-005 PILOT-LOW-1 - external pilot evidence, retro and route observations

Evidence and documentation unit `G-005` (medium) of goal PROPORTIONALITY-DEFAULT. The pilot ran
on an external public repository of the owner (pseudonym `proj_320bb41855b2`, consent given
2026-09-25): 5 comparable pairs of low units, baseline without the `/task` pipeline and followup
through `/task` -> `/test` on the low route. Review claim id: `G-005:general-review`, risk tier
`medium`. No production module, hook, skill, script or oracle changes.

## In scope

- `docs/evidence/external-outcomes/PILOT-LOW-1.jsonl`: the pseudonymous pilot ledger written only
  by `scripts/itd_external_pilot.py` (metadata + 10 verified units, no names, paths or code).
- `docs/retros/RETRO-PILOT-LOW-1.md`: method, facts, comparison with the historical high units,
  observations, limitations and proposals.
- `.itd-memory/measurements/pilot-low-1/`: `measure_window.py` (window metrics from transcripts),
  `mutate.py` (mutation runner used by the followup units), `historical.jsonl` (high-unit windows).
- `.itd/DECISIONS.md`: pilot decisions (token metric, repository class, excluded module, goal text
  rule).
- `BACKLOG.md`: route findings of the pilot.
- `.itd/ACCEPTANCE_CONTRACT.json`: closes the G-004 follow-up, opens G-005 with two criteria.
- `.itd-memory/GOAL.json`, `.itd-memory/STATE.json`, `.itd-memory/events.jsonl`: harness
  transitions for G-005.
- `.itd/SCOPE_LOCK.md`: this file.

## Out of scope

- Any change to skills, hooks, agents, scripts, tests or the strict-class policy (proposals only).
- The pilot project's own code, commits and backlog (they live in its repository).
