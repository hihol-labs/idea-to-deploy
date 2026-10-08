# Claude Code Implementation Guide: `nginx-top`

## 1. How to Use This Guide

Run one prompt at a time in the same order as `IMPLEMENTATION_PLAN.md`. Keep WIP=1. Before each step, read `PROJECT_ARCHITECTURE.md`, the relevant `PRD.md` acceptance criteria, and the named implementation-plan step. Do not change the architecture or user-visible schema implicitly; update the specification first.

Every prompt must preserve this complete contract:

- `0`: success, including a truly empty input;
- `1`: operational or unexpected internal failure;
- `2`: CLI usage error;
- `3`: non-empty input with zero valid records;
- `4`: unique-cardinality exhaustion.

The lowercase phrase required for the final failure mode is: unique-cardinality exhaustion.

## 2. Step Prompts

### Prompt 1 — Package and CLI shell

> Implement Step 1 from `IMPLEMENTATION_PLAN.md`. Create only `pyproject.toml`, `src/nginx_top/__init__.py`, `src/nginx_top/cli.py`, and `tests/integration/test_cli_contract.py`. Use Python 3.11, Click, Rich, and a `src` layout. Add the console entry point and validate all option conflicts. Preserve exit codes `0/1/2/3/4`, even where later steps will implement the corresponding runtime branches. Run every verification command in Step 1 and report evidence, remaining limitations, and the next single step.

### Prompt 2 — Models, errors, and fixtures

> Implement Step 2 from `IMPLEMENTATION_PLAN.md`. Use frozen dataclasses matching `PROJECT_ARCHITECTURE.md`; define typed errors that can later map to `0/1/2/3/4`; add the four minimal fixtures and model tests. Do not implement parsing or aggregation yet. Run Step 2 verification and keep WIP=1.

### Prompt 3 — Streaming input and parser

> Implement Step 3 from `IMPLEMENTATION_PLAN.md`. Read regular UTF-8 files and stdin line by line, use one precompiled combined-log parser, create timezone-aware timestamps, and count malformed/undecodable lines without retaining full records. Do not add gzip or alternate formats. File/read errors must be compatible with code 1, usage with code 2, all-invalid data with code 3, and later cardinality failure with code 4. Run the named parser and input tests.

### Prompt 4 — Aggregation and limits

> Implement Step 4 from `IMPLEMENTATION_PLAN.md`. Compute top IPs, 400–599 URL rankings, all 24 hour buckets, and exact non-missing User-Agent cardinality in one pass. Use `100 × hourly_request_count / total_valid_requests` for hourly percentages. Enforce `--max-unique` before inserting a new IP, error URL, or User-Agent and raise the typed code-4 failure. Apply deterministic count-descending/label-ascending ties. Run all Step 4 tests.

### Prompt 5 — JSON renderer

> Implement Step 5 from `IMPLEMENTATION_PLAN.md`. Emit exactly the stable versioned JSON schema in `PROJECT_ARCHITECTURE.md`; include diagnostics and all 24 hours; use standard encoding and no ANSI output. Do not calculate business metrics in the renderer. Run tests plus the `json.tool` verification. Preserve `0/1/2/3/4` orchestration compatibility.

### Prompt 6 — CSV renderer

> Implement Step 6 from `IMPLEMENTATION_PLAN.md`. Emit the exact columns `schema_version,report,rank,key,count,percentage` using the standard CSV writer and the documented discriminators. Add quoting and six-field round-trip tests. Do not change metric semantics or the complete `0/1/2/3/4` exit contract. Run Step 6 verification.

### Prompt 7 — Rich terminal renderer

> Implement Step 7 from `IMPLEMENTATION_PLAN.md`. Render the five documented terminal sections with Rich, escape all log-derived values, auto-enable color only on a TTY, and honor explicit color options. Render no ANSI in no-color mode. Keep calculations in `report.py`, preserve `0/1/2/3/4`, and run terminal security/golden tests.

### Prompt 8 — End-to-end CLI

> Implement Step 8 from `IMPLEMENTATION_PLAN.md`. Connect input, parser, aggregator, report snapshot, and exactly one renderer. Keep stdout machine-parseable and send diagnostics/errors to stderr. Prove every exit: 0 success/empty input, 1 operational/internal failure, 2 usage error, 3 non-empty all-invalid input, 4 cardinality exhaustion. Treat normal downstream broken pipe as success without a traceback. Run all integration cases named in the plan.

### Prompt 9 — Quality and performance

> Implement Step 9 from `IMPLEMENTATION_PLAN.md`. Add deterministic adversarial fixtures, coverage/lint/type gates, and a reproducible 1 GB benchmark that records fixture checksum, laptop specification, elapsed time, peak RSS, and result checksum. Do not claim the under-30-second target without a real run. Verify the exact candidate and preserve all documented CLI semantics and exit codes `0/1/2/3/4`.

### Prompt 10 — Packaging and documentation

> Implement Step 10 from `IMPLEMENTATION_PLAN.md`. Write user documentation from the existing specification, choose and record an open-source license, test the built wheel in a clean Python 3.11 environment, and inspect artifact contents. The README must state the supported grammar, both percentage formulas, cardinality limit, JSON/CSV schemas, and exact exits `0/1/2/3/4`. Run build, wheel smoke, and artifact validation commands. Do not publish externally.

## 3. Per-Step Completion Response

After each prompt, report:

1. Files changed and why.
2. Exact verification commands and observed outcomes.
3. Acceptance criteria now satisfied.
4. Any failure or recovery state without relabeling it success.
5. The next single step; do not start it automatically unless instructed.

Do not claim release completion until the exact candidate passes the full suite, security review, clean-wheel smoke test, and measured 1 GB performance gate.

