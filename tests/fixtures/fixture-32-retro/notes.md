# Fixture 32 — /retro — manual verification notes

`/retro` is the self-improvement loop of the methodology, deliberately split so
autonomy never eats the merge gate:

- **FACTS** — `skills/retro/scripts/itd_retro_scan.py` (stdlib, deterministic):
  covered by automated `tests/verify_retro_scan.py` (both interpreters + the
  windows-verify CI leg), NOT manual.
- **PROPOSALS** — the model; manual contract below.
- **MERGE** — the human, via the ordinary release pipeline. `/retro` never
  edits skills/hooks/docs itself.

Validation of the model part deferred (status: pending) — same
read-and-advise bucket as fixture-15-advisor / fixture-19-grill-me; Phase 1
snapshot schema cannot assert a scan→proposals→approval flow.

## Contract to verify manually

`/retro` MUST:
- Run the scan script and paste its output verbatim (facts come from the
  harness, not from conversation memory).
- Attach evidence to EVERY proposal — a number or quoted reason from the scan,
  a review finding, a CI catch. No evidence — no proposal.
- Rank proposals and estimate effort; respect the signal-gated discipline
  (ROADMAP): one weak signal → backlog note, not a release demand.
- Anti-Goodhart: never propose changes whose only justification is improving
  the methodology's own metric (VCR, meta_review pass-rate); signals must be
  external (live-run failures, trigger false positives, bypass reasons,
  cost anomalies).
- Treat an EMPTY scan as a finding in itself («телеметрия не пишется — почему?»),
  not as a reason to invent signals.
- Write the report to `docs/retros/RETRO-YYYY-MM-DD.md` (methodology repo) or
  project memory, and STOP — the user decides what enters the backlog.

`/retro` MUST NOT:
- Modify skills/hooks/docs/counters itself (no self-merge — the whole point).
- Fabricate telemetry or cite unverifiable "observations".
- Act as a gate or block any other flow.
