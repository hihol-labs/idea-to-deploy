# Claude Code Implementation Guide: nginx-report

Use this guide after the blueprint is accepted. It does not authorize product
implementation during the blueprint session. Run one numbered prompt at a
time, keep WIP=1, inspect the current repository before editing, and stop when
that step's verification evidence is complete.

## Source-of-Truth Order

1. `PRD.md` defines required behavior and acceptance criteria.
2. `PROJECT_ARCHITECTURE.md` defines data flow, metric semantics, schemas, and CLI contract.
3. `IMPLEMENTATION_PLAN.md` defines dependency order, files, and verification.
4. `STRATEGIC_PLAN.md` defines scope, priorities, release gates, and risks.

If documents disagree, do not guess: reconcile the specs before code. Do not
add a database, HTTP API, server, authentication, cloud service, Docker, or
Kubernetes. Do not implement `DEVILS_ADVOCATE_REVIEW.md` or claim a reviewer ran.

## Non-negotiable Runtime Contract

Every implementation step preserves all five exit codes:

| Code | Required meaning |
|---:|---|
| `0` | Successful report, help, or version |
| `1` | Operational input/output/decode/gzip/unexpected failure |
| `2` | Click usage error |
| `3` | Finite input completed with zero valid records |
| `4` | Unique-cardinality exhaustion |

Failures emit no partial report. Report data goes to stdout; diagnostics go to
stderr. Hourly percentages always use
`100 × hourly_request_count / total_valid_requests`.

## Prompt 1 — Package Skeleton and Contracts

```text
Implement STEP 1 from IMPLEMENTATION_PLAN.md only. Read PRD.md and
PROJECT_ARCHITECTURE.md first. Create the Python 3.11 src-layout package,
pyproject configuration, console entry point, domain dataclasses, typed errors,
and initial package/CLI tests listed in the step. Do not add metric behavior or
any service/infrastructure. Keep the public failure contract reserved exactly:
0 success/help/version, 1 operational failure, 2 usage error, 3 no valid
records, 4 unique-cardinality exhaustion. Run every STEP 1 verification command
and report files changed plus actual command outcomes; do not proceed to STEP 2.
```

## Prompt 2 — Sources and Combined Parser

```text
Implement STEP 2 from IMPLEMENTATION_PLAN.md only, assuming STEP 1 evidence is
green. Build lazy file/stdin iteration and the exact combined-log parser from
PROJECT_ARCHITECTURE.md. Add the fixed fixtures and parser/source tests. Do not
buffer the input, add gzip yet, or reinterpret malformed lines as valid. Keep
exit codes fixed: 0 success/help/version, 1 operational input/output/decode/
gzip/unexpected failure, 2 Click usage error, 3 no valid records, and 4 unique-
cardinality exhaustion. Run all STEP 2 verification commands and stop.
```

## Prompt 3 — Streaming Aggregation

```text
Implement STEP 3 from IMPLEMENTATION_PLAN.md only. Create exact counters,
deterministic top-ten tie ordering, separate 4xx/5xx URL counts, all 24 hourly
buckets using `100 × hourly_request_count / total_valid_requests`, and the exact
User-Agent share/cap. Enforce the cap before inserting the cap-plus-one value.
Keep exit codes exactly 0 success, 1 operational failure, 2 usage error, 3 no
valid records, and 4 unique-cardinality exhaustion. Add every named aggregation
test, run STEP 3 verification, report evidence, and stop before presenters.
```

## Prompt 4 — Three Presenters

```text
Implement STEP 4 from IMPLEMENTATION_PLAN.md only. Render the immutable Report
through Rich terminal, schema-version-1 JSON, and normalized CSV exactly as
PROJECT_ARCHITECTURE.md specifies. Escape untrusted strings and ensure machine
formats contain no ANSI. Preserve the full mapping: 0 success/help/version,
1 operational failure, 2 usage error, 3 no valid records, 4 unique-cardinality
exhaustion. Add golden/cross-mode tests, run every STEP 4 check, and stop.
```

## Prompt 5 — CLI and Failure Mapping

```text
Implement STEP 5 from IMPLEMENTATION_PLAN.md only. Wire finite sources, parser,
aggregator, and one presenter; validate mutual exclusions, positive cap, and
single stdin. Emit report bytes only after successful finalization. Implement
and test precisely: 0 successful report/help/version; 1 operational input,
output, decode, gzip, broken-pipe, or unexpected failure; 2 Click usage error;
3 zero valid records; 4 unique-cardinality exhaustion. No failure may emit a
partial report. Run all STEP 5 commands and stop.
```

## Prompt 6 — End-to-End Contract Matrix

```text
Implement STEP 6 from IMPLEMENTATION_PLAN.md only. Add installed-command tests
for file/stdin equivalence, multi-file input, deterministic ordering, formulas,
24 hours, all three output modes, malformed counts, and stdout/stderr isolation.
Exercise the complete exit contract without remapping: 0 success/help/version,
1 operational failure, 2 usage error, 3 no valid records, 4 unique-cardinality
exhaustion. Run the full coverage/Ruff/mypy checks specified by STEP 6 and stop.
```

## Prompt 7 — Gzip and Performance

```text
Implement STEP 7 from IMPLEMENTATION_PLAN.md only. Add safe gzip suffix/
explicit selection and truncated-stream handling. Build deterministic benchmark
generation and a runner that records environment, wall time, and peak RSS.
Measure the representative 1 GB/<30 s gate; profile rather than weakening exact
semantics. Preserve: 0 success, 1 operational including gzip failure, 2 usage
error, 3 no valid records, 4 unique-cardinality exhaustion. Run every STEP 7
verification command, record actual results without inventing them, and stop.
```

## Prompt 8 — Release Readiness

```text
Implement STEP 8 from IMPLEMENTATION_PLAN.md only. Reconcile README/help/specs,
add only justified release metadata and CI, build distributions, install the
wheel into a clean Python 3.11 environment, and execute all Definition of Done
checks. Verify every public surface uses 0 success/help/version, 1 operational
failure, 2 Click usage error, 3 no valid records, and 4 unique-cardinality
exhaustion. Do not publish or deploy without separate authorization. Run every
STEP 8 command and report evidence and any unmet release gate.
```

## Final Acceptance Checklist

- [ ] All P0 stories in `PRD.md` have direct passing tests.
- [ ] `python3.11 -m pytest --cov=nginx_report --cov-fail-under=90` passes.
- [ ] Ruff and mypy pass for their documented scopes.
- [ ] JSON and CSV golden outputs contain no ANSI and match their schemas.
- [ ] Subprocess tests demonstrate exits `0/1/2/3/4` with empty report stdout on failures.
- [ ] The representative 1 GB benchmark is below 30 seconds on the recorded laptop.
- [ ] A clean Python 3.11 virtual environment installs and runs the wheel.
- [ ] No database, API, auth, server, cloud, Kubernetes, telemetry, or retained log copy was introduced.

## Recovery Guidance

If a step fails, keep that step active, capture the smallest reproducible
failure, and correct implementation or spec before rerunning its complete
checks. A performance miss requires profiling evidence. A conflict in behavior
requires a spec update first. Never silence a test, lower a gate, return a
partial report, or reuse code 4 for any condition other than unique-cardinality
exhaustion.
