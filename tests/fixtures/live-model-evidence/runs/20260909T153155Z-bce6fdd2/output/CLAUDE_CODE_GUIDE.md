# Claude Code Implementation Guide: nginx-insight

## How to Use This Guide

This guide is for later implementation sessions; the blueprint itself creates no product code. Execute one numbered prompt at a time, preserve WIP=1, and require the verification listed in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) before advancing. Read [PRD.md](PRD.md), [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), `.itd/SCOPE_LOCK.md`, and current `.itd-memory/` state at the start of every session.

The non-negotiable result mapping is: code `0` complete success, code `1` input/output operational failure, code `2` usage/configuration error, code `3` partial-data report after malformed records are skipped, and code `4` unique-cardinality exhaustion with no report. Preserve the complete `0/1/2/3/4` contract in every step; never omit, remap, or merge code 4.

## Prompt 1: Package and CLI Contract

```text
Implement STEP 1 from IMPLEMENTATION_PLAN.md only. Create the Python 3.11
pyproject package skeleton and Click command at the specified paths. Pin the
documented options, validation, help, version behavior, and the complete exit
contract 0/1/2/3/4. Do not implement parsing or metrics. Add tests first, run
the exact STEP 1 verification commands, and report evidence plus changed files.
Stop after STEP 1; update project status only from real results.
```

## Prompt 2: Golden Contract Fixtures

```text
Implement STEP 2 from IMPLEMENTATION_PLAN.md only. Create representative
combined/malformed fixtures and an independently calculated schema-v1 golden
report. Cover status boundaries, ties, query strings, timezones, missing UAs,
and the exact hourly percentage formula from PRD.md. Do not implement product
logic. Run the exact STEP 2 verification commands and stop with evidence.
```

## Prompt 3: Streaming Parser

```text
Implement STEP 3 from IMPLEMENTATION_PLAN.md only using the grammar and typed
boundaries in PROJECT_ARCHITECTURE.md. Write failing parser/input tests first.
Iterate binary file/stdin input without retaining raw lines; validate timestamps
and statuses; normalize only the documented missing UA. Diagnostics must avoid
full raw lines. Run STEP 3 tests and mypy, then stop with evidence.
```

## Prompt 4: Aggregation Core

```text
Implement STEP 4 from IMPLEMENTATION_PLAN.md only. Consume ParsedRecord values
once, compute exact counters and 24 hourly buckets, use deterministic top-10
tie-breaking, and enforce --max-unique independently before new-key insertion.
Exhaustion must fail closed via exit-code domain error 4 with no final report.
Test empty, boundary, ties, missing-UA, at-limit, and cap-plus-one cases. Run
the specified verification and stop with evidence.
```

## Prompt 5: JSON and CSV

```text
Implement STEP 5 from IMPLEMENTATION_PLAN.md only. Render the immutable Report
to the exact JSON-v1 and normalized CSV-v1 contracts. Use standard serializers,
stable order, numeric counts/percentages, and no ANSI output. Test commas,
quotes, newlines, Unicode, formula-shaped input, and the golden oracle. Run the
STEP 5 verification commands and stop with evidence.
```

## Prompt 6: Rich Terminal Output

```text
Implement STEP 6 from IMPLEMENTATION_PLAN.md only. Add the four documented Rich
views, totals, and explicit empty states. Enable style only for an eligible TTY
and honor --no-color. Never alter report values in the renderer. Use a fixed
test console width, run the STEP 6 checks, and stop with evidence.
```

## Prompt 7: CLI Integration and Failures

```text
Implement STEP 7 from IMPLEMENTATION_PLAN.md only. Wire input, parser,
aggregation, and renderer selection. Keep report data on stdout and diagnostics
on stderr. Add end-to-end tests for file/stdin and terminal/JSON/CSV. Assert all
five mappings exactly: 0 success, 1 operational I/O, 2 usage/configuration,
3 partial report, 4 cardinality exhaustion without report. Handle normal pipe
closure and interruption without tracebacks. Run STEP 7 checks and stop.
```

## Prompt 8: Performance Gate

```text
Implement STEP 8 from IMPLEMENTATION_PLAN.md only. Build a deterministic log
generator and benchmark runner that records hardware, OS, Python, input hash and
size, expected aggregate correctness, three timings, median, and peak RSS.
Measure before optimizing. Prove representative 1 GB input is under 30 seconds
or report the real failure; prove cap-plus-one exits 4. Do not weaken data or
thresholds. Run the listed commands and stop with evidence.
```

## Prompt 9: Quality and Security Gate

```text
Implement STEP 9 from IMPLEMENTATION_PLAN.md only. Add hostile-value tests and
complete Ruff, mypy, coverage, and dependency checks. Verify no network,
persistence, terminal injection, serializer corruption, or raw-record leakage.
Do not suppress findings without root-cause justification. Run every STEP 9
command and reconcile status from evidence before stopping.
```

## Prompt 10: Package the Candidate

```text
Implement STEP 10 from IMPLEMENTATION_PLAN.md only. Finalize release docs,
license, and metadata; build wheel and sdist; inspect them; install the wheel in
a clean Python 3.11 environment; run golden file/stdin checks in every format.
Then use the repository Verification Loop on the frozen exact candidate and
require its current risk-tier adjudication receipt. Do not publish or tag unless
separately authorized. Report the real verification outcome and next action.
```

## Session Handoff Checklist

- Record commands, exit statuses, and relevant output; do not summarize unrun checks as passing.
- Keep `.itd/SCOPE_LOCK.md` and the active `.itd-memory/` unit reconciled.
- Do not start a second step while one is active.
- Treat PRD acceptance criteria and the architecture’s CLI/schema contracts as source specifications.
- Do not add a database, API, server, authentication, cloud, Docker, or Kubernetes.
- At a meaningful boundary, save the session context as required by [CLAUDE.md](CLAUDE.md).
