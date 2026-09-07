# Claude Code Implementation Guide: nginx-stream-report

## Purpose

Use these prompts one at a time in a future implementation session. This guide does not authorize changing the product specification. Before each step, read `AGENTS.md`, `.itd/`, `PRD.md`, `PROJECT_ARCHITECTURE.md`, `IMPLEMENTATION_PLAN.md`, and the current `.itd-memory/` state. Preserve WIP=1, use the repository’s Idea to Deploy lifecycle/verification workflow, and update the spec before changing behavior.

The mandatory exit-code contract in every step is: `0` success, `1` runtime I/O/output failure, `2` Click usage error, `3` strict parse/validation failure, and `4` unique-cardinality exhaustion. Never omit, remap, or silently downgrade code 4. On any nonzero exit, do not emit a partial report to stdout.

## Global Guardrails

- Implement only the current step and its named files; do not add a database, HTTP API, server, authentication, cloud, Docker, or Kubernetes.
- Runtime stack is Python 3.11, Click, Rich, and dataclasses/standard library. Any added runtime dependency requires a specification decision first.
- Preserve a single-process, one-pass pipeline and do not retain raw records.
- Hourly percentages use exactly `100 × hourly_request_count / total_valid_requests`.
- Treat log values as untrusted text. Keep reports on stdout and diagnostics on stderr.
- Use tests to establish behavior, then implement, then run the exact verification commands and record actual results.
- Do not claim the 1 GB / 30 s target until it is measured on the exact candidate.

## Prompt 1: Package Skeleton and CLI Contract

```text
Execute IMPLEMENTATION_PLAN.md Step 1 only. Establish the Python 3.11 src-layout package, Click console entry point, documented options, and typed exit categories. Write tests first for help, version, option conflicts, ranges, and stdin/path validation. The full exit contract is 0 success, 1 runtime I/O/output failure, 2 usage error, 3 strict parse/validation failure, and 4 unique-cardinality exhaustion. Do not implement parsing or rendering yet. Run the Step 1 verification commands and record exact results in the active Idea to Deploy state. Stop after the step is verified or explicitly report recovery evidence.
```

Expected files: `pyproject.toml`, `src/nginx_stream_report/{__init__,__main__,cli,errors}.py`, `tests/test_cli_contract.py`.

## Prompt 2: Models and Parser

```text
Execute IMPLEMENTATION_PLAN.md Step 2 only. Read the parsing and data-model contracts in PROJECT_ARCHITECTURE.md and FR-2/FR-3 in PRD.md. Add slots dataclasses and anchored precompiled parsers for nginx common and combined formats. Preserve the logged wall-clock hour, literal URL including query, status, IP, and combined User-Agent; use <missing> for common-format UA. Add synthetic fixtures and boundary tests before implementation. Keep exit codes 0/1/2/3/4 unchanged. Run parser tests, Ruff, and mypy, then record exact evidence. Do not add custom log formats.
```

Expected files: `src/nginx_stream_report/{models,parser}.py`, `tests/fixtures/access_*.log`, `tests/test_parser.py`.

## Prompt 3: Streaming Input and Parse Policy

```text
Execute IMPLEMENTATION_PLAN.md Step 3 only. Implement buffered line iteration for ordered files and stdin without whole-file reads or retained records. Make no-path and a single '-' mean stdin; reject invalid stdin combinations with code 2. Map open/read failures to code 1. Default malformed behavior skips and counts; --strict stops with code 3, a source/line diagnostic, and empty report stdout. Preserve code 4 for unique-cardinality exhaustion even though its producer arrives later. Add tests first, run all Step 3 verification commands, and record results.
```

Expected files: `src/nginx_stream_report/input.py`, updates to `cli.py`, `tests/test_input.py`, and CLI contract tests.

## Prompt 4: Streaming Aggregations

```text
Execute IMPLEMENTATION_PLAN.md Step 4 only. Implement a one-pass accumulator and immutable snapshot for client IP counts, URL counts limited to statuses 400-599, all 24 hourly buckets, and exact User-Agent distinct count/share. Top lists order by count descending then key ascending. Use the literal formula 100 × hourly_request_count / total_valid_requests for hourly percentages; zero valid requests yields 0.0 percentages in permissive mode. Add boundary and tie tests first. Preserve exit codes 0/1/2/3/4. Run the Step 4 tests and coverage check and record actual evidence.
```

Expected files: `src/nginx_stream_report/aggregate.py`, `tests/test_aggregate.py`.

## Prompt 5: Cardinality Guard

```text
Execute IMPLEMENTATION_PLAN.md Step 5 only. Before adding a previously unseen User-Agent, enforce --max-unique-user-agents. At/below the limit results remain exact; the first new value beyond it raises the typed failure mapped only to exit code 4. The stderr diagnostic must contain the exact lowercase phrase 'unique-cardinality exhaustion', and stdout must remain empty. Codes 0 success, 1 runtime I/O/output failure, 2 usage error, and 3 strict parse/validation failure retain their meanings. Add below/at/over/repeated-value tests first, run Step 5 verification, and record results.
```

Expected files: updates to `aggregate.py` and `cli.py`, plus `tests/test_cardinality.py` and its small fixture.

## Prompt 6: Rich Terminal Output

```text
Execute IMPLEMENTATION_PLAN.md Step 6 only. Build the default Rich renderer with four sections: top IPs, top error URLs, 24 hourly percentage rows/bars, and exact unique User-Agent summary. Implement color auto-detection plus --color/--no-color. Escape or neutralize log-derived markup and terminal controls. Rendering consumes ReportSnapshot and must not recalculate metrics. Preserve complete exit behavior 0/1/2/3/4 and stdout/stderr separation. Add snapshots and malicious-string cases first, run Step 6 verification, and record results.
```

Expected files: `src/nginx_stream_report/renderers/{__init__,terminal}.py`, `tests/test_terminal_output.py`.

## Prompt 7: JSON and CSV Outputs

```text
Execute IMPLEMENTATION_PLAN.md Step 7 only. Implement JSON schema_version 1 and the long-form CSV schema exactly as defined in PROJECT_ARCHITECTURE.md. Use standard serializers, deterministic ordering/precision, all 24 hourly rows, and spreadsheet-formula neutralization for CSV keys. Machine data goes to stdout and diagnostics to stderr. --json and --csv remain mutually exclusive with code 2. Preserve 0/1/2/3/4 including code 4 for unique-cardinality exhaustion. Add golden files and schema/escaping tests first, run all Step 7 commands, and record exact results.
```

Expected files: `renderers/{json_output,csv_output}.py`, `tests/golden/report.{json,csv}`, `tests/test_machine_output.py`.

## Prompt 8: End-to-End Quality and Packaging

```text
Execute IMPLEMENTATION_PLAN.md Step 8 only. Add end-to-end tests that exercise common/combined input, files/stdin/multiple inputs, terminal/JSON/CSV, and every exit code: 0 success; 1 runtime I/O/output failure; 2 usage error; 3 strict parse/validation failure; 4 unique-cardinality exhaustion. Configure Ruff, mypy, and >=90% package line coverage. Build sdist/wheel, validate metadata, and install the wheel in a clean Python 3.11 environment for a console-script smoke test. Update README only with commands actually observed to work. Record exact verification evidence; leave failures in recovery.
```

Expected files: `tests/test_end_to_end.py`, `pyproject.toml` quality configuration, verified README updates, build artifacts excluded by `.gitignore`.

## Prompt 9: Performance Gate and Handoff

```text
Execute IMPLEMENTATION_PLAN.md Step 9 only. Create a deterministic streaming generator for a 1 GiB combined-format, non-sensitive fixture and document benchmark metadata. Measure the unmodified candidate first, record wall time, peak RSS, hardware, Python version, input shape/hash, cache state, and golden summary. If the result misses 30.0 seconds, profile before one bounded architecture-preserving optimization pass; rerun the full suite after changes. Freeze the exact staged candidate and run the project Verification Loop machine oracle and risk-tier checker. Accept only a current revalidated adjudication receipt. Do not change exit codes 0/1/2/3/4, use approximate cardinality, or introduce multiprocessing without changing the architecture and PRD first.
```

Expected files: `benchmarks/generate_access_log.py`, `benchmarks/README.md`, verification evidence in canonical `.itd-memory/` state.

## Completion Handoff Checklist

- [ ] Nine implementation steps have individually recorded verification evidence.
- [ ] Clean wheel installation works on Python 3.11.
- [ ] Golden terminal, JSON, and CSV outputs match the PRD.
- [ ] Exit codes `0/1/2/3/4` are covered end to end, including code 4.
- [ ] The deterministic 1 GiB fixture completes correctly in under 30.0 seconds on the declared laptop.
- [ ] Exact-candidate verification and the risk-tier adjudication receipt are current and revalidated.
- [ ] `PRD.md`, `PROJECT_ARCHITECTURE.md`, `README.md`, and Idea to Deploy state match implemented behavior.

