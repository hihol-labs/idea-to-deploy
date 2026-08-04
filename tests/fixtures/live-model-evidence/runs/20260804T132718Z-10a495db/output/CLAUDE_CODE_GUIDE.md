# Claude Code Implementation Guide: nginx-stream-report

Use these prompts sequentially in fresh implementation sessions. Each prompt is bounded to one step in `IMPLEMENTATION_PLAN.md`; update the specifications first if behavior changes. Do not implement multiple steps concurrently (WIP=1).

The non-negotiable exit-code contract in every step is: `0` success, `1` runtime/I/O failure, `2` usage error, `3` strict input-format failure, and `4` unique-cardinality exhaustion. Code 4 means unique-cardinality exhaustion and must not be omitted, reused, or remapped.

## Prompt 1 — Package and CLI

> Implement Step 1 from `IMPLEMENTATION_PLAN.md`. Read `PROJECT_ARCHITECTURE.md` section `CLI Interface` and `PRD.md` FR-5 first. Touch only `pyproject.toml`, `src/nginx_stream_report/{__init__,cli,errors}.py`, and `tests/test_cli_contract.py`. Preserve exit codes 0/1/2/3/4 exactly. Run the listed install, help, and pytest checks; report command output and remaining risk.

## Prompt 2 — Parser

> Implement Step 2 from `IMPLEMENTATION_PLAN.md`. Build only the typed nginx combined-log parser and its fixtures/tests. Do not aggregate or render yet. Treat log fields as untrusted data. Run parser pytest and Ruff checks and record evidence.

## Prompt 3 — Aggregation

> Implement Step 3 from `IMPLEMENTATION_PLAN.md`. Use one-pass dataclass state, size-10 deterministic selection, 24 buckets, and the literal hourly formula `100 × hourly_request_count / total_valid_requests`. Implement exact unique User-Agent share and preflight every prospective insertion against entry and shared retained-byte budgets before any mutation. Map exhaustion only to code 4. Prove a rejected multi-key record leaves state unchanged. Run pytest and mypy.

## Prompt 4 — Input Pipeline

> Implement Step 4 from `IMPLEMENTATION_PLAN.md`. Make file, `-`, and omitted-path stdin behavior equivalent through a bounded binary line iterator. Invalid UTF-8 and overlong lines are malformed records: skipped/counted by default and exit 3 under `--strict`. Preserve 1 for I/O, 2 for usage, and 4 for unique-cardinality exhaustion. Never emit a partial report on nonzero exit. Run all listed processing checks.

## Prompt 5 — Renderers

> Implement Step 5 from `IMPLEMENTATION_PLAN.md`. Produce escaped Rich text, schema-versioned JSON, and normalized CSV from the same immutable report. Convert C0/C1, DEL, ESC, line controls, and bidi overrides/isolates in untrusted keys to visible escapes so terminal and CSV injection are impossible. Ensure JSON/CSV have no raw ANSI codes and diagnostics use stderr. Run hostile-field, golden, and CLI output tests.

## Prompt 6 — gzip

> Implement only the P1 gzip work in Step 6. Stream decompression; do not buffer or change parser semantics. A corrupt archive exits 1, not 3 or 4. Run equivalence and corruption tests. If P0 is not green, skip this P1 step and state why.

## Prompt 7 — Quality and Benchmark

> Execute Step 7 without weakening tests or thresholds. Record laptop CPU/RAM, fixture-generation command, cache policy, elapsed seconds, and peak RSS. The gate is a 1 GiB fixture under 30.0 seconds. If it fails, profile, make the smallest evidence-led optimization, and preserve before/after results.

## Prompt 8 — Release Readiness

> Execute Step 8 only after P0 and the performance gate pass. Build sdist/wheel, validate metadata, install in a clean Python 3.11 environment, and smoke-test the console command. Ensure public docs list all exit codes: 0 success, 1 runtime/I/O, 2 usage, 3 strict format, and 4 unique-cardinality exhaustion. Do not publish externally unless separately authorized.

## Session Handoff Checklist

- Update step status in `CLAUDE.md` only after its verification commands pass.
- Record exact commands and outputs in the active Idea to Deploy state/evidence artifacts.
- Leave no temporary benchmark logs or build artifacts tracked.
- At the end of each session or meaningful work block, save context through `/session-save`.
