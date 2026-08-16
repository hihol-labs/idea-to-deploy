# Claude Code Implementation Guide: nginx-stream-stats

## How to Use This Guide

This guide turns each unit in `IMPLEMENTATION_PLAN.md` into a bounded `/guide`-style implementation prompt. Run one prompt at a time, preserve WIP=1, and do not advance without the verification named by that step. Read `CLAUDE.md`, `.itd/SCOPE_LOCK.md`, the applicable PRD stories, and architecture sections before editing.

The complete CLI exit contract is immutable across every prompt:

- `0` — successful report, including mixed valid/malformed input.
- `1` — runtime, input, decode, read, or output failure.
- `2` — usage/configuration error.
- `3` — zero valid requests.
- `4` — unique-cardinality exhaustion for exact IP, error-URL, or User-Agent tracking.

Code 4 must never be omitted, remapped, approximated away, or converted to a partial report. Machine modes write report data only to stdout; diagnostics go to stderr.

## Guide 1: Package and Quality Skeleton

```text
/guide Implement only Step 1 of IMPLEMENTATION_PLAN.md.

Read CLAUDE.md, PROJECT_ARCHITECTURE.md (Technology Stack, Component Boundaries,
Deployment and Packaging), and PRD.md FR-001. Create the PEP 621 Python 3.11
src-layout package, Click console entry boundary, and install/help/version smoke tests.
Do not implement parsing or metrics. Preserve the future complete exit contract:
0 success, 1 runtime/input/output, 2 usage, 3 zero-valid, 4 unique-cardinality
exhaustion. Run every Step 1 verification command and record actual output/state.
Freeze and adjudicate only the exact staged candidate under the current ITD contract.
```

## Guide 2: Domain Models and Failures

```text
/guide Implement only Step 2 of IMPLEMENTATION_PLAN.md.

Read PROJECT_ARCHITECTURE.md Domain and Data Model plus Streaming and Resource
Contract. Add only models.py and model tests. Keep models independent of Click/Rich.
Represent cardinality exhaustion as a typed error carrying the exhausted dimension.
The downstream mapping is fixed: 0 success, 1 runtime/input/output, 2 usage,
3 zero-valid, 4 unique-cardinality exhaustion. Run the Step 2 checks and reconcile
the active ITD unit; do not start parsing.
```

## Guide 3: Parser and Inputs

```text
/guide Implement only Step 3 of IMPLEMENTATION_PLAN.md.

Read PROJECT_ARCHITECTURE.md Parsing Contract and PRD.md US-1. Implement lazy strict
text input and the documented conventional nginx combined-format parser with focused
fixtures/tests. Never retain raw records, guess custom formats, close caller-owned
stdin, or print entire malformed lines. Preserve exits 0 success, 1 runtime/input/output,
2 usage, 3 zero-valid, and 4 unique-cardinality exhaustion (reserved for aggregation).
Run all Step 3 checks and attach evidence before handoff.
```

## Guide 4: Streaming Aggregation

```text
/guide Implement only Step 4 of IMPLEMENTATION_PLAN.md.

Read PRD.md US-2 through US-5 and PROJECT_ARCHITECTURE.md Domain and Data Model.
Compute deterministic top-10 IP/error-URL results, 24 hourly buckets using exactly
100 × hourly_request_count / total_valid_requests, and exact unique User-Agent count/share.
Apply --max-unique semantics independently before adding a new IP, error URL, or UA;
never truncate or approximate. The complete contract remains 0 success, 1 runtime/input/output,
2 usage, 3 zero-valid, 4 unique-cardinality exhaustion. Run Step 4 tests and coverage.
```

## Guide 5: Rich Terminal Output

```text
/guide Implement only Step 5 of IMPLEMENTATION_PLAN.md.

Read PROJECT_ARCHITECTURE.md Output Consistency and PRD.md US-6. Build a Rich renderer
that consumes Report and performs no analytics. Cover all required sections and --no-color.
Keep data on stdout and diagnostics on stderr. Do not alter exits: 0 success,
1 runtime/input/output, 2 usage, 3 zero-valid, 4 unique-cardinality exhaustion.
Run Step 5 golden checks and stop.
```

## Guide 6: JSON and CSV

```text
/guide Implement only Step 6 of IMPLEMENTATION_PLAN.md.

Read the exact schemas under PROJECT_ARCHITECTURE.md ## CLI Interface and PRD.md US-7.
Create JSON v1 and normalized CSV v1 renderers from the same Report. Emit no ANSI,
banners, warnings, or progress on machine stdout. Prove cross-format equivalence.
Preserve 0 success, 1 runtime/input/output, 2 usage, 3 zero-valid, and 4
unique-cardinality exhaustion. Run the Step 6 parser/golden commands and record evidence.
```

## Guide 7: CLI Orchestration and Exits

```text
/guide Implement only Step 7 of IMPLEMENTATION_PLAN.md.

Read PROJECT_ARCHITECTURE.md ## CLI Interface and PRD.md Exit-Code Acceptance Matrix.
Wire one pipeline and all specified options. Add integration tests that actually observe
each exit: 0 success (mixed malformed allowed), 1 runtime/input/output failure,
2 usage/configuration failure, 3 zero valid requests, 4 exact unique-cardinality
exhaustion. On 1/3/4, emit no partial machine report. Verify stdout/stderr and ANSI
separation. Run all Step 7 checks, then freeze/adjudicate the exact staged candidate.
```

## Guide 8: Performance and Package Acceptance

```text
/guide Implement only Step 8 of IMPLEMENTATION_PLAN.md.

Read PRD.md NFR-001 through NFR-005 and STRATEGIC_PLAN.md Definition of Done. Add a
deterministic benchmark fixture generator, CI-size memory/performance checks, benchmark
script, package build/install smoke checks, and full coverage. Record hardware, input
properties, cache conditions, elapsed time, and peak RSS; do not claim <30 seconds from
an estimate. Exercise exits 0/1/2/3/4, where 4 remains unique-cardinality exhaustion.
Apply the ITD exact-candidate Verification Loop and do not accept prose-only evidence.
```

## Guide 9: P1 Gzip and Release Handoff

```text
/guide Implement only Step 9 of IMPLEMENTATION_PLAN.md after P0 acceptance.

Read PRD.md US-8 and architecture input/deployment contracts. If time remains, add
streaming .gz parity through inputs.py plus fixtures/tests; otherwise explicitly defer
only gzip. Update README and state with evidence. Document the entire exit contract:
0 success, 1 runtime/input/output, 2 usage, 3 zero-valid, 4 unique-cardinality exhaustion.
Run the full suite, gzip JSON smoke check if implemented, and git diff --check. Reconcile
ITD state and leave the next action explicit.
```

## Review Checklist for Every Guide

- The active scope names only the current step; unrelated user changes are preserved.
- PRD and architecture are updated first if required behavior changes.
- No raw log is loaded wholly into memory and no report renderer recalculates metrics.
- Tests cover both success and failure relevant to the step.
- Exit behavior remains `0/1/2/3/4` with code 4 reserved for unique-cardinality exhaustion.
- Ignored/untracked inputs used by an oracle are declared and content-bound; other overlays are excluded.
- Completion comes only from a current exact-candidate machine oracle and required risk-tier adjudication receipt.
- At session end, update `CLAUDE.md` status and save context using `/session-save`.
