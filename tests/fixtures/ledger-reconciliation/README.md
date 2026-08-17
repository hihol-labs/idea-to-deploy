# Frozen real-history fixture — ledger reconciliation

Read-only input for `tests/verify_ledger_reconciliation.py`. It mirrors the
shape of a real `.itd-memory/` directory so the oracle validates the
lifecycle invariants unconditionally, instead of silently skipping them when
the live, gitignored `.itd-memory/events.jsonl` is absent.

**Complete inventory of this directory** (stated here so a reviewer that sees
only part of the diff does not have to infer what the other files are — a
bound review unit may carry `events.jsonl` while the ledgers land in another):

| file | role |
|---|---|
| `GOAL-axis1.json` | ledger owning `G-001` and `G-002`, window 2026-07-05..06 |
| `GOAL-axis2.json` | a DIFFERENT ledger also owning `G-001`, window 2026-07-06 — the real id collision |
| `GOAL.json` | ledger owning `PE5-008` (externally blocked) and `PE5-015` (verified, then re-verified) |
| `LEDGER-RECONCILIATION.json` | explains the one historical row whose ledger no longer exists |
| `events.jsonl` | the unit events all of the above are attributed against |

What the fixture is built to prove: one id resolves to one lifecycle **per
owning ledger**; a repeated activation with no terminal between is idempotent;
a `blocked` terminal stays visible yet leaves the VCR denominator; a second
`verified` long after the cycle closed is a re-verification, not a writer bug;
and a row whose ledger is gone is attributed only through an explained
manifest entry.

Frozen: change it only together with the assertions in
`tests/verify_ledger_reconciliation.py` that read it.
