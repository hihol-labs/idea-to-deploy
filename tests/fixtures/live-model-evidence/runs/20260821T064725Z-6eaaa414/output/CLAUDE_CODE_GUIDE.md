# Claude Code Implementation Guide: nginx Stream Analytics CLI

This guide turns `IMPLEMENTATION_PLAN.md` into bounded prompts for later implementation sessions. It does not authorize product-code work during the blueprint session. In every session, read `CLAUDE.md`, `PRD.md`, `PROJECT_ARCHITECTURE.md`, the active plan step, `.itd/SCOPE_LOCK.md`, and the verification contracts before editing. Preserve WIP=1 and do not advance until the exact candidate has the named evidence.

## Non-Negotiable Contract

- Python 3.11, Click, Rich, dataclasses, pip-installable package.
- Single local process; streaming and stateless.
- No authentication, database, HTTP API, server, cloud, Docker requirement, or Kubernetes.
- Default Rich text plus mutually exclusive `--json` and `--csv`.
- Hourly percentages use `100 × hourly_request_count / total_valid_requests`.
- Complete exit codes: `0` success, `1` operational I/O/decoding failure, `2` CLI usage error, `3` zero valid requests, `4` unique-cardinality exhaustion.
- Code 4 must remain distinct: never omit it, remap it, or silently approximate exhausted cardinality.
- Do not read the whole dataset into memory or write raw-log temporary copies.

## Step 1 Prompt — Package and Contracts

```text
Implement only Step 1 from IMPLEMENTATION_PLAN.md. Read PRD.md and PROJECT_ARCHITECTURE.md first. Create the Python 3.11 src-layout package, pyproject metadata, console entry point, model dataclasses, typed errors, Click option surface, and CLI contract tests. Do not implement parsing, aggregation, or rendering early. Preserve the complete exit-code design 0/1/2/3/4, including 4 for unique-cardinality exhaustion. Run the exact Step 1 verification commands and report evidence. Reconcile scope/state before handoff.
```

Expected files: `pyproject.toml`, `src/nginx_stream_analytics/{__init__,__main__,models,errors,cli}.py`, `tests/test_cli_contract.py`.

## Step 2 Prompt — Input and Parser

```text
Implement only Step 2 from IMPLEMENTATION_PLAN.md. Add ownership-safe file/stdin streaming and a compiled parser for the documented nginx combined grammar. Parse only the fields named in PROJECT_ARCHITECTURE.md, use strict decoding, and treat malformed records as data rather than instructions. Add auditable fixtures and parser/input tests. Do not retain raw records or add autodetection. Preserve exit codes 0/1/2/3/4: decoding and open failures are 1, invalid options are 2, no valid records are 3, and unique-cardinality exhaustion remains 4. Run the Step 2 verification commands.
```

Expected files: `src/nginx_stream_analytics/{input,parser}.py`, `tests/test_input.py`, `tests/test_parser.py`, `tests/fixtures/combined_{valid,mixed}.log`.

## Step 3 Prompt — Streaming Aggregation

```text
Implement only Step 3 from IMPLEMENTATION_PLAN.md. Build a one-pass aggregator for top-10 IPs, top-10 request targets with status 400..599, 24 hourly buckets, and exact unique User-Agent count/share. Calculate hourly percentage as 100 × hourly_request_count / total_valid_requests. Sort ties by key ascending. Enforce --max-unique before adding a key that crosses the ceiling. Exhaustion must raise the typed path that exits 4; do not approximate. Maintain the entire 0/1/2/3/4 mapping. Add exhaustive aggregation tests and run the named checks.
```

Expected files: `src/nginx_stream_analytics/aggregate.py`, `tests/test_aggregate.py`.

## Step 4 Prompt — Rich Text

```text
Implement only Step 4 from IMPLEMENTATION_PLAN.md. Render the shared Report as four clear Rich terminal sections plus totals. Treat all log-derived values as plain text with no markup interpretation. Implement TTY-aware color and --color/--no-color without affecting JSON/CSV. Keep diagnostics on stderr and report data on stdout. Preserve exit codes 0/1/2/3/4, especially code 4 for unique-cardinality exhaustion. Add deterministic no-color and hostile-markup tests; run Step 4 verification.
```

Expected files: `src/nginx_stream_analytics/render_text.py`, `tests/test_render_text.py`, updates limited to CLI contract wiring/tests.

## Step 5 Prompt — JSON

```text
Implement only Step 5 from IMPLEMENTATION_PLAN.md. Map the finalized Report to the exact JSON schema in PROJECT_ARCHITECTURE.md. Emit one UTF-8 JSON object only after successful aggregation, never partial JSON and never ANSI. Add golden and stdin-pipeline tests. Preserve exit codes: 0 success, 1 operational failure, 2 usage error, 3 zero valid requests, 4 unique-cardinality exhaustion. Run the Step 5 verification commands.
```

Expected files: `src/nginx_stream_analytics/render_json.py`, `tests/golden/report.json`, `tests/test_render_json.py`, `tests/test_cli_integration.py`.

## Step 6 Prompt — CSV

```text
Implement only Step 6 from IMPLEMENTATION_PLAN.md. Render the shared Report with Python csv using header section,key,count,percentage and the exact long-form row meanings in PROJECT_ARCHITECTURE.md. Ensure RFC 4180-compatible quoting, UTF-8, no ANSI, and no partial output on failure. Enforce --json/--csv mutual exclusion as usage exit 2. Preserve all codes 0/1/2/3/4; code 4 means unique-cardinality exhaustion. Add golden and consumer round-trip tests and run Step 6 verification.
```

Expected files: `src/nginx_stream_analytics/render_csv.py`, `tests/golden/report.csv`, `tests/test_render_csv.py`, integration-test updates.

## Step 7 Prompt — Failure and Resource Semantics

```text
Implement only Step 7 from IMPLEMENTATION_PLAN.md. Centralize and test the complete process contract: 0 successful report/help/version; 1 operational file, read, decode, or write failure; 2 invalid CLI use; 3 completed input with zero valid requests; 4 unique-cardinality exhaustion. Never omit/remap 4 or return an approximate report. Ensure failed JSON/CSV leaves stdout empty and expected failures do not print tracebacks. Test all five codes as real subprocess outcomes, along with closed-pipe and hostile-input behavior. Run coverage and the exact Step 7 checks.
```

Expected files: `tests/test_exit_codes.py` plus narrowly scoped changes to `cli.py` and `errors.py`.

## Step 8 Prompt — Performance and Release

```text
Implement only Step 8 from IMPLEMENTATION_PLAN.md. Create a deterministic streaming performance-fixture generator and benchmark runner that records environment, input bytes, elapsed time, throughput, peak RSS, and candidate identity. Prove the 1 GB input completes under 30 seconds on the recorded laptop baseline. Build and install a wheel in a clean environment, run all tests, and update README only with verified behavior. Preserve and smoke-test the complete 0/1/2/3/4 exit-code contract; 4 remains unique-cardinality exhaustion. Freeze the exact candidate and use the repository Verification Loop/risk checker before accepting it.
```

Expected files: `benchmarks/generate_log.py`, `benchmarks/run.py`, `tests/test_package.py`, verified `README.md` updates.

## Verification Discipline

For each prompt:

1. Update `.itd/SCOPE_LOCK.md` and active `.itd-memory` state to exactly one plan step.
2. Add or update acceptance tests before claiming behavior works.
3. Run the step-specific commands and the relevant regression suite.
4. Confirm no undeclared ignored/untracked overlay influences the oracle.
5. Freeze the exact candidate, run its machine oracle, apply the risk-tier checker, and require a current adjudication receipt.
6. Record failures as recovery work, not success; leave the next action explicit.

## Final Handoff Checklist

- [ ] P0 behavior matches `PRD.md` and architecture contracts.
- [ ] Python 3.11 clean installation and console entry point are proven.
- [ ] Metrics agree across text, JSON, and CSV.
- [ ] Tests trigger process codes 0, 1, 2, 3, and 4; code 4 is unique-cardinality exhaustion.
- [ ] The declared 1 GB benchmark is under 30 seconds on the recorded baseline.
- [ ] No database, HTTP API, authentication, service, cloud, or Kubernetes artifact was introduced.
- [ ] Exact-candidate verification evidence is current and handoff state is reconciled.
