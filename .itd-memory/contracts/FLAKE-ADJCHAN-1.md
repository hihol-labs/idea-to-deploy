# Task Contract — FLAKE-ADJCHAN-1 receipt selection in the adjudication-channel oracle without the clock

- **Scope:** `tests/verify_adjudication_channel.py`: `newest_receipt(root, kind, before=frozenset())`
  returns the one receipt of `kind` that is on disk now and was not in the `before` snapshot;
  `receipts(root, kind)` is that snapshot (a frozenset, no order); `checker()` snapshots before it
  runs the checker command and returns `(process, minted receipt or None)`; every checker-receipt
  pick in the oracle goes through it. Nothing new is `None`; two new receipts since one snapshot
  raise (an ambiguity is a refusal, never "the last element"). File times and the clock do not
  enter the choice at all. New oracle `tests/verify_adjudication_channel_clock.py` (in run-all CORE)
  loads the helper from source without executing the oracle, stamps a receipt written second with
  an mtime older by the measured 5.366 s step, proves that an mtime sort reproduces the defect and
  that the helper does not; also covers tied mtimes, nothing new, an absent kind, an empty root,
  the two-new refusal, the static clock-free property of the code (AST, not text) and the
  snapshot binding of every checker pick.
- **Verification Standards:** the unit verificationCommand exits 0; the clock oracle is RED on the
  pre-fix helper (recorded: 10 failed / 4 passed, the 4 are fixture sanity) and GREEN after;
  `tests/verify_adjudication_channel.py` keeps its 65 checks green; `tests/build_impact_graph.py
  --check` exit 0; `tests/run-all.sh --quick` last line `DONE fails:none`; low route -
  machine-only checker, `/review` before the multi-file commit.
- **Exclusions:** the receipt writer and the Verification Loop CLI (they are correct: a BLOCKED
  checker is durable and exits non-zero before printing its path - the oracle searches the disk on
  purpose); other `st_mtime` orderings in `tests/` (BACKLOG, separate unit); Windows CI wiring of the
  new suite (run-all is stricter than CI by the drift-guard's rule).
