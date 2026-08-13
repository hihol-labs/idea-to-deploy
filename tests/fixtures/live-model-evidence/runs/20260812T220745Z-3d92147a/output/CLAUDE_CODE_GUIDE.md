# Claude Code Implementation Guide: nginx-log-report

This guide turns [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) into bounded implementation prompts. Run one prompt at a time, keep WIP at one step, inspect existing changes before editing, and do not advance until the listed oracle passes. The durable behavior source is [PRD.md](PRD.md); the technical source is [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md).

## Invariants for Every Prompt

- Use Python 3.11, Click, Rich, dataclasses, and a single local process.
- Read inputs line by line and never retain raw events after aggregation.
- Do not add authentication, a database, HTTP API, server, cloud integration, Docker/Kubernetes deployment, telemetry, or hidden application environment configuration.
- Hourly percentage means exactly `100 × hourly_request_count / total_valid_requests`; for zero valid requests it is `0.0`.
- Keep terminal, JSON, and CSV semantics derived from one report model.
- Preserve this complete exit-code contract everywhere: `0` success; `1` unexpected internal failure; `2` CLI usage error; `3` input/data error; `4` unique-cardinality exhaustion.
- Never emit a partial report for exit `3` or `4`. Diagnostics go to stderr; reports go to stdout.
- Do not change specifications merely to make a test pass. If a contract is impossible, stop and report the exact conflict.

## Prompt 1: Public Contract and Package Skeleton

```text
Implement only Step 1 of IMPLEMENTATION_PLAN.md.

Read AGENTS.md, PRD.md, PROJECT_ARCHITECTURE.md (especially ## CLI Interface), and the Step 1 section before editing. Inspect the worktree and preserve unrelated user changes. Create the pyproject/package/test skeleton and freeze the Click help/options contract. Do not implement parsing, aggregation, or renderers yet. Keep both `nginx-log-report` and `python -m nginx_log_report` entry points thin and consistent.

Run exactly the Step 1 verification commands. Report changed files, command outcomes, and any contract ambiguity. Update the Step 1 status in CLAUDE.md only after verification passes. Do not begin Step 2.
```

## Prompt 2: Combined-Log Parser

```text
Implement only Step 2 of IMPLEMENTATION_PLAN.md.

Read the input contract and reliability boundaries in PROJECT_ARCHITECTURE.md plus FR-1/FR-2 in PRD.md. Build typed dataclasses and a compiled parser for the approved nginx combined format. Validate IP, timestamp, status, and the `METHOD request-target PROTOCOL` request field. Treat log content as untrusted data. Keep parsing free of Click, Rich, aggregation, and output concerns.

Add the specific parser fixtures and edge tests listed in Step 2. Run both Step 2 verification commands. If coverage or a case fails, fix within parser scope. Record evidence and update only Step 2 status; do not implement aggregation.
```

## Prompt 3: Single-Pass Aggregator

```text
Implement only Step 3 of IMPLEMENTATION_PLAN.md.

Read metric semantics, the state model, ADR-002, and user stories US-1 through US-4. Fold one LogRecord at a time into exact IP/error counters, a fixed 24-bucket array, and the User-Agent set. Never retain records. Freeze deterministic report rows with the documented tie rules. Compute hours with the literal formula `100 × hourly_request_count / total_valid_requests` and compute User-Agent share with its documented denominator.

Write tests for top-10 boundaries, tie ordering, 4xx/5xx splits, zero input, all hours, and repeated User-Agents. Run the Step 3 commands and update only Step 3 status after they pass.
```

## Prompt 4: Streaming Input and Data Errors

```text
Implement only Step 4 of IMPLEMENTATION_PLAN.md.

Wire the existing parser and aggregator through Click for one path or stdin. Iterate incrementally; add a test double that fails on bulk read/readlines. Default mode skips and counts malformed nonblank lines. --strict stops at the first malformed line, writes a sanitized source/line diagnostic to stderr, writes no report, and exits 3. Missing/unreadable paths and invalid UTF-8 are also code 3. Keep Click usage failures at code 2 and unexpected failures at code 1.

Run the Step 4 tests and manual exit assertion. Record evidence, update only Step 4 status, and do not add renderers beyond a minimal injectable seam needed by the tests.
```

## Prompt 5: Rich Terminal Output

```text
Implement only Step 5 of IMPLEMENTATION_PLAN.md.

Build the default Rich renderer from the immutable report model. Include summary, top IPs, error URLs with combined/4xx/5xx counts, all 24 hours, and User-Agent count/share. Preserve useful plain text under --no-color or non-TTY output. Disable or escape Rich markup for all log-derived strings and ensure long values do not alter data.

Add normal, empty, hostile-markup, long-value, no-color, and color-enabled tests. Run the Step 5 oracle and update only its CLAUDE.md status after it passes.
```

## Prompt 6: JSON and CSV Pipeline Output

```text
Implement only Step 6 of IMPLEMENTATION_PLAN.md.

Read the complete JSON/CSV output contract and ADR-003 before editing. Implement schema_version 1 JSON and the exact tidy CSV columns/row order using the standard csv module. Both outputs must be UTF-8, deterministic, and ANSI-free. JSON and CSV must consume the same report object as terminal output. Make --json and --csv mutually exclusive through Click so the conflict exits 2.

Create byte-level golden tests for normal and empty reports, validate JSON with the standard parser, and test CSV fields containing commas/quotes/newlines. Run the Step 6 commands and update only Step 6 status when green.
```

## Prompt 7: Cardinality Guard and Exit Matrix

```text
Implement only Step 7 of IMPLEMENTATION_PLAN.md.

Enforce --max-unique-user-agents before inserting a new distinct User-Agent. Repeated values at the limit remain valid; the first new value above it raises the domain exhaustion signal. Map it to exit 4 with a concise stderr diagnostic and empty stdout. Validate a positive option value via Click, which remains code 2.

Create controlled CLI tests covering every mapping without remapping: 0 success, 1 unexpected internal failure, 2 CLI usage error, 3 input/data error, 4 unique-cardinality exhaustion. Also test no partial report on 3/4. Run Step 7 verification and update only Step 7 status.
```

## Prompt 8: Correctness, Security, and 1 GB Gate

```text
Implement only Step 8 of IMPLEMENTATION_PLAN.md.

Build an end-to-end expected-result oracle independent of production aggregation. Add a deterministic fixture generator with seed and controlled valid/malformed/cardinality distributions. Generate the 1 GB artifact outside Git. Benchmark on the documented reference laptop and record wall time, peak RSS, Python, OS, CPU, storage/cache protocol, fixture size, and seed. The release gate is under 30 seconds; do not extrapolate from a smaller file.

Run the full coverage, benchmark, and dependency checks in Step 8. Profile before optimizing and preserve exact semantics. If the target fails, leave Step 8 incomplete and report measurements and hotspots; do not introduce multiprocessing, approximation, or a stack change without a spec decision.
```

## Prompt 9: Installable Release Candidate

```text
Implement only Step 9 of IMPLEMENTATION_PLAN.md.

Reconcile README examples with the actual frozen CLI. Complete license, changelog, metadata, executable documentation checks, and clean-environment wheel installation. Verify console-script and module entry points. Do not publish, tag, upload, or contact an external service without explicit authorization.

Run build, artifact validation, and the clean Python 3.11 smoke test from Step 9. Re-run the full suite if packaging changes imports. Update Step 9 and project status only with current evidence; report remaining release action explicitly.
```

## Final Reconciliation Prompt

```text
Review the exact candidate against PRD.md, PROJECT_ARCHITECTURE.md, and STRATEGIC_PLAN.md Definition of Done. Run the full test suite and the current 1 GB benchmark evidence path. Confirm all three output modes agree, the literal hourly formula is preserved, and exit codes 0/1/2/3/4 have tests. Inspect for placeholders and forbidden architecture additions. Reconcile CLAUDE.md and hand off the next explicit action. Do not publish.
```
