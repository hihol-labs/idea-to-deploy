# No active unit — /retro report of 2026-09-13

No unit is in progress. ROUTE-REPAIR-1 is verified and merged (code `2d50a12` through PR #284, ledger close `abaf1d1` through PR #285), WIP is free, and the queue approved by the owner on 2026-09-12 is ROUTE-REPAIR-2 (claim-id circle, post-merge transition circle, live-benchmark pin cascade) -> ROUTE-REPAIR-3 (the metric sees the route) -> RSI-DEBT-3. One plan item is one session, so the next unit is activated by its own session, not by this candidate.

This candidate is the output of `/retro`, which by its own contract never modifies the methodology: it writes a report and hands the merge decision to the owner. Nothing here changes a skill, a hook, a counter, a gate or a doc that a gate reads.

Allowed: `docs/retros/RETRO-2026-09-13.md` (the report: scan output as-is, six evidence-backed candidates, one rejection recorded as Goodhart) and this scope lock, rewritten because the previous text still named ROUTE-REPAIR-1 as the current unit after that unit closed. That staleness was found by the third independent review round of this very candidate, which returned BLOCKED with one `specification-compliance` finding: a documentary file outside every allowed zone of a sealed scope that had already been discharged. The defect is in the route, not in the report - a scope lock pinned to a closed unit cannot admit any inter-unit commit - and it is recorded in the report's closing note as the seventh route defect measured in this series.

Required: the report carries the scan output verbatim with the command that produced it; every proposal names an external signal, an effort and a risk with the suite that would pin it; no proposal is justified by improving the methodology's own metric. A `/review` route before the commit, then the cross-vendor producer. Existing accepted evidence stays immutable.

Forbidden: implementing any candidate here (each is a separate release through the normal pipeline); touching `PE5-008` or `PE5-009`; activating the next unit; editing any ledger, acceptance contract or test; `--no-verify` (if a gate refuses, the exact command goes to the owner).
