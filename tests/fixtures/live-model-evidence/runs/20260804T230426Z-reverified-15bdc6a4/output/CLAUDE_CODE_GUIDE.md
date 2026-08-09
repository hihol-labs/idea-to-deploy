# Claude Code Implementation Guide: Nginx Stream Insights

## 1. How to Use This Guide

Run these prompts in order after blueprint approval. Each prompt is one bounded WIP=1 unit corresponding to `IMPLEMENTATION_PLAN.md`; do not combine steps. Before editing, read `AGENTS.md`, `.itd/` contracts, `PROJECT_ARCHITECTURE.md`, `PRD.md`, and the named plan step. Update the scope lock and active state, make only the requested changes, run the listed commands, freeze the exact staged candidate, and require the applicable Idea to Deploy verification receipt before marking the unit complete.

This guide does not authorize implementation during the blueprint phase. Throughout all steps, preserve the full exit-code contract unchanged: `0` success, `1` operational I/O failure, `2` usage/option error, `3` input-data failure or no valid requests, and `4` unique-cardinality exhaustion. Code `4` must not be omitted, reused, or remapped.

## 2. Global Engineering Contract

- Python 3.11, Click, Rich, dataclasses, `src/` layout, pip-installable wheel/sdist.
- One local process and one-pass input iteration; no authentication, database, HTTP API, server, cloud, Docker, or Kubernetes.
- Only valid parsed records contribute to metrics. Hourly percentage is exactly `100 × hourly_request_count / total_valid_requests`.
- Build one immutable `Report`; render terminal, JSON, and CSV from it.
- Keep data on stdout, diagnostics on stderr, and raw malformed records out of default diagnostics.
- Do not silently approximate exact metrics. Exceeding the distinct User-Agent limit exits `4`.
- Use dependency injection/temporary streams in tests; do not add production-only test branches.
- Update specifications first when observable behavior must change.

## Prompt 1 — Package Skeleton and Quality Baseline

```text
Execute only STEP 1 of IMPLEMENTATION_PLAN.md for Nginx Stream Insights.
Read AGENTS.md and the current .itd contracts first, set this as the sole active unit,
and keep changes limited to the package/test skeleton named by the step. Create an
installable Python 3.11 src-layout package with Click and Rich, a console script, and
Ruff/mypy/pytest configuration. The CLI may expose only help/version at this point,
but its help must document the immutable exit mapping: 0 success, 1 operational I/O,
2 usage, 3 input-data/no-valid-records, 4 unique-cardinality exhaustion. Do not add
analytics, a database, API, service, Docker, or cloud assets. Run every STEP 1 check,
report real evidence, and accept only the exact staged candidate under the repository
verification contract.
```

## Prompt 2 — Report Models and Golden Contracts

```text
Execute only STEP 2 of IMPLEMENTATION_PLAN.md. Preserve exit codes 0/1/2/3/4 exactly,
including 4 for unique-cardinality exhaustion. Add the frozen dataclasses and reviewed
golden fixtures/contracts described in PROJECT_ARCHITECTURE.md §§6-9. Express hourly
percentages on the 0-100 scale using 100 × hourly_request_count / total_valid_requests,
require 24 hour buckets, and define deterministic ties. Fixtures must be clearly test
data, not production data. Make no parser or renderer implementation beyond what the
step requires. Run the specified model/contract checks and exact-candidate verification.
```

## Prompt 3 — Streaming Parser and Input Boundary

```text
Execute only STEP 3 of IMPLEMENTATION_PLAN.md. Preserve the complete 0/1/2/3/4 exit
contract for later CLI mapping. Implement bounded line-by-line combined/common nginx
parsing and file/stdin ownership exactly as PROJECT_ARCHITECTURE.md specifies. Cover
IPv4/IPv6 text, escaped quotes, timestamp offsets, status bounds, query strings,
common-format User-Agent '-', malformed lines, decoding failures, and unreadable input.
Do not aggregate, render, or add alternate formats. Run the focused tests and coverage
command, then freeze and verify the exact staged candidate.
```

## Prompt 4 — Aggregation Core and Metric Safety

```text
Execute only STEP 4 of IMPLEMENTATION_PLAN.md. Preserve exit codes 0/1/2/3/4; the
CardinalityLimitError created here must map to 4 and no other condition. Implement
incremental top IP, 4xx/5xx URL, 24-hour, and exact User-Agent aggregations. Exclude
malformed records from every denominator. Use the literal hourly formula
100 × hourly_request_count / total_valid_requests and stop before inserting a distinct
User-Agent beyond the cap. Test boundaries, deterministic ties, zero valid records,
and exhaustion. Run the focused checks and exact-candidate verification.
```

## Prompt 5 — Terminal Renderer

```text
Execute only STEP 5 of IMPLEMENTATION_PLAN.md. Preserve the normative 0/1/2/3/4 exit
mapping even though this unit only renders a Report. Add the Rich terminal renderer,
with all four metrics, valid/malformed totals, TTY-aware color, explicit color controls,
and literal treatment of untrusted log-derived strings. Never recompute analytics in
the renderer and never emit ANSI when redirected unless forced. Run the renderer tests
and manual no-color command, then verify the exact staged candidate.
```

## Prompt 6 — JSON and CSV Renderers

```text
Execute only STEP 6 of IMPLEMENTATION_PLAN.md. Preserve exit codes 0/1/2/3/4 exactly.
Implement JSON schema_version 1 and CSV section,key,count,percentage from the same
immutable Report used by terminal output. Keep machine stdout free of ANSI and prose,
quote through standard libraries, and round display percentages to two decimals without
changing internal values. Add semantic-equivalence tests across formats. Run all STEP 6
checks and exact-candidate verification.
```

## Prompt 7 — Complete CLI and Exit Codes

```text
Execute only STEP 7 of IMPLEMENTATION_PLAN.md and treat PROJECT_ARCHITECTURE.md's
"CLI Interface" as normative. Wire every approved option and enforce this complete
mapping with integration tests: 0 successful report; 1 operational I/O failure;
2 Click usage/option error; 3 input-data failure or no valid requests; 4 exact unique-
cardinality exhaustion. Do not omit or remap 4. Keep diagnostics on stderr and report
data on stdout; handle normal pipe closure without traceback. Do not add unapproved
services or persistence. Run focused and coverage checks, then exact-candidate verification.
```

## Prompt 8 — Performance and Robustness Gate

```text
Execute only STEP 8 of IMPLEMENTATION_PLAN.md. Preserve observable output and the full
0/1/2/3/4 exit contract, especially 4 for unique-cardinality exhaustion. Add a seeded,
clearly synthetic benchmark generator and a runner that records environment, median
wall time, peak RSS, and report digest. Run the fixed 1 GB protocol and require a median
under 30 seconds on the documented laptop. Add hostile-input and broken-output tests.
Profile before optimizing; do not switch to sampling or approximation silently. Freeze
and verify the exact staged candidate with the measured evidence attached.
```

## Prompt 9 — Packaging and Release Candidate

```text
Execute only STEP 9 of IMPLEMENTATION_PLAN.md. Preserve and document the complete exit
contract everywhere: 0 success, 1 operational I/O, 2 usage/options, 3 input-data/no
valid requests, 4 unique-cardinality exhaustion. Finalize user docs, licensing,
distribution metadata, and a clean-environment wheel smoke test. Run lint, type checks,
full tests with coverage, dependency/license review, packaging smoke test, and confirm
current benchmark evidence. Freeze the exact staged release candidate and accept it
only through the repository's current risk-tier adjudication receipt. Do not publish or
tag unless separately authorized.
```

## 3. Handoff Checklist for Every Prompt

- [ ] Only the active step's files and explicit contract/state updates changed.
- [ ] Required commands ran and their real outcomes were recorded.
- [ ] Exit codes remain `0/1/2/3/4`, with `4` meaning unique-cardinality exhaustion.
- [ ] No database, API, auth, server, cloud, Docker, or Kubernetes was introduced.
- [ ] The staged candidate is the candidate tested and adjudicated.
- [ ] Persistent Idea to Deploy state is reconciled and the next step is explicit.
- [ ] Session context is saved through `/session-save` at the end of the work block.

## 4. Source Documents

Use `PROJECT_ARCHITECTURE.md` for technical truth, `PRD.md` for observable behavior, `IMPLEMENTATION_PLAN.md` for file-level sequencing, and `STRATEGIC_PLAN.md` for scope, priority, and release success criteria.
