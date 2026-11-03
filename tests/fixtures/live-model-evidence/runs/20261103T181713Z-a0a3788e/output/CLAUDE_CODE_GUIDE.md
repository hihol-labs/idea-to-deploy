# Implementation Guide: Nginx Pulse

Use [CLAUDE.md](CLAUDE.md) as the single project instruction entry point. Read [PRD](PRD.md), [architecture](PROJECT_ARCHITECTURE.md), [plan](IMPLEMENTATION_PLAN.md) and [strategy](STRATEGIC_PLAN.md) before implementation. These prompts are future work, not evidence of executed code. Proceed only with the scope authorized for the implementation session. Do not publish or send logs externally.

## Nonnegotiable Interface
Python 3.11, Click, Rich, dataclasses. One local process, no database, HTTP API, auth, server, cloud or Kubernetes. Exact bounded aggregation. Preserve exit codes **0/1/2/3/4** throughout every step:

| Code | Contract |
|---|---|
| 0 | Complete successful report or help/version |
| 1 | I/O failure, including broken pipe |
| 2 | Usage error |
| 3 | No valid records, interrupt or processing failure |
| 4 | unique-cardinality exhaustion |

Code 4 covers both the combined distinct-key limit and retained-key-byte cap; emit no final report. Never remap it. Hourly percentages use `100 × hourly_request_count / total_valid_requests`. Unique-UA share uses distinct nonmissing strings divided by valid requests, multiplied by 100. Use architecture schema v1 and local-hour buckets exactly.

## Step 1 Prompt: Scaffold
“Implement plan step 1 only: create `pyproject.toml`, package init and package tests for Python 3.11, Click/Rich, pytest/build/coverage. Set the console entry-point contract without adding unrelated features. Keep owner identity unresolved until supplied rather than inventing legal metadata. Run `python -m pip install -e '.[dev]'`, `python -m pytest tests/test_package.py` and the full suite. Report actual results; suggest the step-1 commit without pushing.”

## Step 2 Prompt: Parser
“Implement plan step 2 in `reader.py`, `parser.py`, `models.py` and their tests. Read bounded binary lines, validate standard combined format, IP/status/timestamp, escape handling and missing UA. Drain oversize input without retaining it. Use synthetic fixtures; no production logs. Run `python -m pytest tests/test_reader.py tests/test_parser.py` then `python -m pytest`. Include malformed encodings, IPv6, CRLF, invalid dates and escaped quotes.”

## Step 3 Prompt: Aggregation
“Implement plan step 3 in `aggregate.py` and `models.py`. Compute exact deterministic top-ten IPs/error paths, hourly count/percentage and distinct-UA share. Preflight every record's new keys against combined slot and fixed byte budgets. Add independent expected-count tests, ties, mixed time offsets and boundary exhaustion tests. Run `python -m pytest tests/test_aggregate.py` and the full suite. Preserve the complete exit contract, especially 4.”

## Step 4 Prompt: CLI and Failures
“Implement step 4 in `cli.py` and CLI/process tests. Wire file/stdin, exclusive export flags, help/version, positive max-unique and no-color. Map 0/1/2/3/4 exactly as architecture specifies. Count malformed input, keep warnings on stderr and avoid final reports on processing failure. Test actual subprocess broken pipes and interrupts as well as Click runner cases. Run `python -m pytest tests/test_cli.py tests/test_process.py` then the full suite.”

## Step 5 Prompt: Terminal
“Implement step 5 in `render.py` and `tests/test_terminal.py`: all four views, totals, empty errors, deterministic rows and six-decimal percentages. Treat paths as literal text and escape control characters. Respect TTY, NO_COLOR and --no-color without changing metrics. Run `python -m pytest tests/test_terminal.py` and the full suite.”

## Step 6 Prompt: Exports
“Implement step 6 using JSON/CSV schema v1 in architecture. Extend `render.py` and add `tests/test_exports.py` plus independently authored expected fixtures. Round-trip with standard-library parsers; test quote/comma/newline keys and no ANSI or diagnostic prose on stdout. Run `python -m pytest tests/test_exports.py`, both documented export commands and the full suite. Preserve code 4 and write-failure code 1.”

## Step 7 Prompt: Performance
“Implement step 7 benchmark generator/runner and oracle tests. Generate exactly 1,000,000,000 bytes of valid synthetic combined records with known results. Run the documented benchmark command three times through its runner; capture laptop, OS/runtime/dependency versions, cache conditions, wall time, RSS and accuracy. Require every run <30 seconds and ≤512 MiB. Profile real bottlenecks; do not replace exact counters with sketches or omit code 4. Run `python -m pytest tests/test_benchmark_oracle.py` and the full suite. Record failure honestly if the target is missed.”

## Step 8 Prompt: Wheel and Handoff
“Implement step 8: build and install a wheel in a clean Python 3.11 venv; create `tests/test_wheel_smoke.py` to test installed help, file/stdin, terminal/JSON/CSV and codes 0/1/2/3/4. Run `python -m build`, the wheel smoke test, the documented core branch coverage check and full suite. Update README and plan status only from actual results. Keep publishing separate and authorization-gated. Save session context.”

## Debugging and Completion
For a discrepancy, first identify the PRD acceptance case, capture a minimal synthetic reproducer, write a failing behavior test, then fix the shared parser/aggregate/report path. Avoid separate per-format calculations. Do not weaken assertions to match an incorrect implementation. Record commands and actual results in continuity; any failed P0 check or benchmark blocks product readiness. The blueprint's adversarial review is external and has not run inside this session.
