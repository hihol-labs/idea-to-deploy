# Task Contract — MEMORY-COLLISION-DENY-1 refuse a Write over a fresh session memory file

- **Root cause:** for a Write over an existing, fresh `session_*.md` memory file `main()` of
  `hooks/state-guard.sh` only called `memory_collision_context` (v1.84.0 P8), which returns warning
  text with exit 0 and never a deny decision, and shows it once per (session, file). The overwrite
  therefore always went through: on the TIER-WORDING-2 route the previous session's memory file was
  overwritten and restored from the harness backup (BACKLOG P2 2026-10-01, item e).
- **Scope:** `memory_collision_decision` gives the Write branch an allow/warn/deny decision: a Write
  over an existing `session_*.md` (project `.itd-memory/` or the legacy private `memory/`) younger
  than `MEM_FRESH_SECONDS` (6 h) is denied with a FAILED/WHY/FIX reason that names the first free
  `session_YYYY-MM-DD_N.md` (N >= 2) of that day; the refusal spends the per-session deny budget
  shared with the ledger gate (`MAX_DENIES` = 2), after which the Write passes with a warning. The
  file author is not checked (ownership is not attributable). The freshness check moved into
  `_fresh_session_memo`, shared with the unchanged soft warning of the shell channel.
- **Verification Standards:** the unit verificationCommand exits 0; the new oracle
  `tests/verify_memory_collision_deny.py` drives the hook through `main()` with a hermetic temp dir
  and is RED on the pre-fix bytes of d84532e (8 failed, 5 ok; log
  `.itd-memory/verification-loop/reports/MEMORY-COLLISION-DENY-1-red-first.log`, sha256
  9859a912ec8f2951) and GREEN after (13/0); mutations of the fix (no deny, no skip of a taken
  suffix, no budget bump, no freshness window, the file stem as the base) are lethal;
  `tests/verify_host_neutral_memory.py`, `tests/verify_all_hard_gate_host_parity.py` and
  `tests/verify_state_hardening.py` stay green; `tests/build_impact_graph.py --check` exit 0; low
  route - `/review` before the multi-file commit, machine-only adjudication with receipt legs
  `unit`, `meta-review`, `ledger-state` (equal to the `oracleIds` of the acceptance criteria).
- **Exclusions:** the shell channel (`mv`/`cp`/redirect stays a soft warning - remainder in
  BACKLOG), the ledger single-writer gate, `MAX_DENIES`, the heartbeat and the PostToolUse
  validation; the other pending units of the goal.
