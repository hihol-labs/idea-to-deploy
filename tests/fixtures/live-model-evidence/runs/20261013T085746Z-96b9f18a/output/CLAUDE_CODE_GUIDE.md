# Implementation Guide: Nginx Lens

This is a future execution guide, not evidence of implemented features. Read [CLAUDE.md](CLAUDE.md), [PRD.md](PRD.md), [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), and [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) before implementation. Product decisions are approved; external adversarial architecture review remains separate and pending.

## Global Execution Contract

Use Python 3.11, Click, Rich, dataclasses, and pip packaging. Work on one step at a time. Spec changes precede code changes. Preserve **0/1/2/3/4**: 0 success; 1 operational/internal failure; 2 usage error; 3 completed report with malformed input skipped; 4 unique-cardinality exhaustion.

The exact failure name is unique-cardinality exhaustion.

Use `100 × hourly_request_count / total_valid_requests` for hourly percentages and `100 × distinct_nonmissing_user_agents / total_valid_requests` for UA share. Zero denominators yield zero. Preserve UTC hours, query stripping, deterministic ties, exact key budgets, and schema version 1. No database, HTTP API, auth, server, cloud, Kubernetes, or product telemetry. Tests must demonstrate behavior using labeled synthetic data; don't claim target performance before measuring it.

## Step 1 Prompt

“Implement Step 1 of IMPLEMENTATION_PLAN.md only. Add pyproject.toml, the src/nginx_lens package, dataclass definitions, Click command skeleton, and tests/test_cli.py. Preserve all approved option and exit semantics. Run the documented installation and CLI checks. Record actual results and unresolved failures before marking this step done.”

## Step 2 Prompt

“Implement Step 2 only. Build bounded binary reading and the explicit combined-log parser in reader.py and parser.py. Cover nginx escapes, UTF-8 failures, final newline handling, IPv6, UTC offsets, malformed request lines, and oversize-line draining. Run reader/parser tests; show evidence that input is processed incrementally.”

## Step 3 Prompt

“Implement Step 3 only. Build exact IP/error-path counters, 24 UTC buckets, and the distinct nonmissing UA set. Enforce the shared cardinality budget before each record mutation. Test all metric examples in PRD.md, ties, zero denominators, and the boundary just below/at/above the budget. No eviction or approximation. Run aggregation tests and record results.”

## Step 4 Prompt

“Implement Step 4 only. Render all report sections with Rich; handle TTY, NO_COLOR, and --no-color. Treat log strings as data and escape terminal controls. Wire the processing path with sanitized stderr summaries. Run terminal tests and a file-based smoke check.”

## Step 5 Prompt

“Implement Step 5 only. Serialize the shared Report into the exact JSON object and normalized CSV schema in PROJECT_ARCHITECTURE.md. Check empty reports, quoting, six-decimal precision, row ordering, and stdout purity. Run export tests and compare independently calculated fixture values.”

## Step 6 Prompt

“Implement Step 6 only. Verify the complete 0/1/2/3/4 contract, including unique-cardinality exhaustion at code 4. Exercise malformed input, fatal reads, output errors, broken pipes, and handled interruption. Compare file/stdin semantics. Run integration tests and coverage; preserve failing results instead of marking incomplete work complete.”

## Step 7 Prompt

“Implement Step 7 only. Generate a declared synthetic 1,000,000,000-byte fixture within the default cardinality cap. Record laptop, software, fixture properties, each of three warm-cache timings, median, and peak RSS. Validate process status and report values. Test high-cardinality failure separately. If under 30 seconds is not achieved, report the gap and measured bottleneck; do not change exact semantics or the approved stack silently.”

## Step 8 Prompt

“Implement Step 8 only. Run the suite, build wheel/sdist, install the wheel into a clean Python 3.11 environment, and exercise the installed command. Reconcile docs with tested behavior and collect evidence in ITD_REPORT.md and .itd-memory/STATE.json. Record the real external review result if available; otherwise keep it pending. Prepare a local release candidate without publishing it.”

## Recovery and Session Handoff

On failure, retain evidence, keep the current step active, fix the underlying issue, and rerun relevant checks. Do not lower acceptance thresholds or add persistence/services to avoid a test failure. If the scope must change, update `.itd/SCOPE_LOCK.md` and canonical state before edits. Record current step, changed files, checks, limitations, and next action. At the end of each session or significant block, save context through `/session-save`; if that command is unavailable, record the same context directly in `.itd-memory/STATE.json` and the handoff report without claiming the command ran.

See [README.md](README.md) for intended usage and [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) for scope and release gates.
