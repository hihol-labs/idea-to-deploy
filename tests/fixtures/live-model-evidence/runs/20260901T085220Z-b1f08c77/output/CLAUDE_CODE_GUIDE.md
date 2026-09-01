# Claude Code Implementation Guide: nginx-stream-insights

## Purpose

This guide turns `IMPLEMENTATION_PLAN.md` into bounded prompts for a later implementation session. It does not authorize implementation during the blueprint session. Work in order with WIP=1, update the specification before changing observable behavior, and preserve the architecture in `PROJECT_ARCHITECTURE.md`.

## Non-Negotiable Contract

- Runtime and stack: Python 3.11, Click, Rich, dataclasses, standard pip packaging.
- Product shape: local single-process streaming CLI only; no authentication, database, HTTP API, server, cloud, Docker runtime dependency, or Kubernetes.
- Metrics: top 10 IPs, top 10 URLs for 4xx/5xx, 24 hourly percentages using `100 × hourly_request_count / total_valid_requests`, and exact bounded unique User-Agent count/share.
- Output: terminal by default, with mutually exclusive `--json` and `--csv` pipeline modes.
- Performance: a representative 1 GB log must complete in under 30 seconds on a documented laptop.
- Exit codes: `0` success, `1` input/read/runtime failure, `2` CLI usage error, `3` no valid requests, `4` unique-cardinality exhaustion. Preserve the complete `0/1/2/3/4` mapping in implementation, tests, and documentation.

## Session Protocol

Before each step:

1. Read `CLAUDE.md`, the named implementation-plan step, its linked architecture/PRD sections, and the current working-tree status.
2. Confirm only that step is active; do not start a second step.
3. Add or update tests that encode the step's acceptance criteria.
4. Implement only the planned files, run the exact verification commands, and report actual evidence.
5. Reconcile the status table in `CLAUDE.md` and save session context with `/session-save` after the meaningful block.

## Prompt 1: Package and Verification Skeleton

```text
Execute only Step 1 of IMPLEMENTATION_PLAN.md. Read CLAUDE.md, PRD.md, and the Package and File Layout plus Testing Strategy sections of PROJECT_ARCHITECTURE.md first. Create the Python 3.11 pyproject, src package, console entry point, help/version scaffold, and initial CLI tests. Do not implement parsing or metrics. Run every Step 1 verification command and report command evidence; update only the Step 1 status in CLAUDE.md.
```

Expected evidence: clean editable install, passing focused tests, and working `--help`.

## Prompt 2: Domain Models and Errors

```text
Execute only Step 2 of IMPLEMENTATION_PLAN.md after Step 1 is verified. Implement the frozen dataclasses and typed error taxonomy exactly as PROJECT_ARCHITECTURE.md specifies. Centralize the complete exit mapping 0/1/2/3/4 and test code 4 explicitly. Do not parse files or render output. Run the focused tests and mypy command, then update the Step 2 status in CLAUDE.md.
```

Expected evidence: model-invariant tests and type checks pass.

## Prompt 3: Streaming Parser

```text
Execute only Step 3 of IMPLEMENTATION_PLAN.md. Implement one-line nginx combined-log parsing with a compiled parser, maximum line-length protection, and explicit malformed results. Add the specified fixtures and boundary tests. Do not open input files in parser.py and do not aggregate records. Run the Step 3 pytest and ruff commands and record actual results.
```

Expected evidence: parser cases cover IPv4/IPv6, offsets, quoting, status bounds, malformed and overlong lines.

## Prompt 4: One-Pass Aggregation

```text
Execute only Step 4 of IMPLEMENTATION_PLAN.md. Build the single-pass aggregator over parsed records. Enforce all invariants, deterministic top-10 ties, 4xx/5xx filtering, the percentage formula 100 × hourly_request_count / total_valid_requests, and exact User-Agent cardinality with a hard ceiling. Crossing the ceiling must fail with code 4 via the typed boundary; never approximate silently. Run focused tests and coverage before updating status.
```

Expected evidence: aggregate tests exercise every metric, all 24 buckets, zero data, ties, and exhaustion.

## Prompt 5: Rich Terminal Renderer

```text
Execute only Step 5 of IMPLEMENTATION_PLAN.md. Implement the default Rich report from an immutable AnalysisResult. Keep calculations out of the renderer. Make color controllable and ensure no-color output is deterministic for golden tests. Include every required metric and summary count. Run the focused renderer tests and ruff command.
```

Expected evidence: golden no-color terminal output passes and empty sections remain explicit.

## Prompt 6: JSON and CSV Renderers

```text
Execute only Step 6 of IMPLEMENTATION_PLAN.md. Implement the exact JSON object and normalized CSV schema from PROJECT_ARCHITECTURE.md and PRD.md. Preserve deterministic ordering, two-decimal presentation, RFC-compatible quoting, formula-injection mitigation, and ANSI-free output. Do not change metric definitions. Run all JSON/CSV golden and coverage checks.
```

Expected evidence: both outputs parse, match golden fixtures, and contain no ANSI escapes.

## Prompt 7: CLI Orchestration

```text
Execute only Step 7 of IMPLEMENTATION_PLAN.md. Wire file/stdin iteration, parser, aggregator, and exactly one renderer through Click. Implement mutually exclusive --json/--csv, --no-color, and a positive --max-unique-user-agents. Keep diagnostics on stderr and reports on stdout. Exercise every exit code 0/1/2/3/4; code 4 means unique-cardinality exhaustion and may not produce a partial report. Run all Step 7 commands.
```

Expected evidence: file/stdin parity, flag validation, output separation, and all exit statuses pass integration tests.

## Prompt 8: Performance Gate

```text
Execute only Step 8 of IMPLEMENTATION_PLAN.md. Create a reproducible representative-log generator, a small CI performance check, and a 1 GB three-run benchmark that records wall time and peak RSS. Measure before optimizing. If the slowest run is not under 30 seconds, profile and change only measured hotspots without changing outputs or formulas. Record machine and fixture details in BENCHMARK.md and run the full correctness suite afterward.
```

Expected evidence: reproducible command, three timings, peak RSS, environment description, and a green correctness suite.

## Prompt 9: Package and Release

```text
Execute only Step 9 of IMPLEMENTATION_PLAN.md. Write user-facing README, license, and changelog; build wheel and sdist; install the wheel in a clean Python 3.11 environment. Run full tests with at least 90% product-module coverage, ruff, mypy, installation smoke tests, and the 1 GB benchmark. Verify README documents 0/1/2/3/4 including code 4. Do not tag or publish unless separately authorized.
```

Expected evidence: all gates pass against the exact release candidate and the artifact installs cleanly.

## Recovery Rules

- If a test fails, keep the current step active, record the failure, make the smallest in-scope correction, and rerun the failing gate plus relevant regression suite.
- If the 1 GB target fails, profile; do not guess, introduce multiprocessing, or weaken correctness without changing the architecture and PRD first.
- If a schema or metric must change, stop implementation and update `PRD.md`, then reconcile architecture, tests, and guide prompts.
- If a requested change introduces persistence, a network service, or authentication, treat it as a new product scope requiring a new blueprint.
- Never claim a step complete from narration alone; retain the exact commands and results required by the active Idea to Deploy verification contract.

## Final Acceptance Checklist

- [ ] All P0 user stories and acceptance criteria pass.
- [ ] Output modes are equivalent in meaning and stable in structure.
- [ ] Hourly distribution is a percentage, not an unscaled fraction.
- [ ] Every `0/1/2/3/4` exit path has integration evidence.
- [ ] The unique-cardinality ceiling fails closed with code 4.
- [ ] The slowest documented 1 GB benchmark run is under 30 seconds.
- [ ] Clean Python 3.11 wheel installation succeeds.
- [ ] No forbidden infrastructure or product scope was introduced.
