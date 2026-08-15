# Claude Code Implementation Guide: Nginx Stream Analyzer

## Purpose

This guide turns `IMPLEMENTATION_PLAN.md` into bounded prompts for a future implementation session. It does not authorize scope beyond `PRD.md` P0. Execute one prompt at a time, preserve WIP=1, inspect the current worktree first, and require the named commands to pass before advancing.

The architecture source of truth is `PROJECT_ARCHITECTURE.md`. The full exit-code contract in every step is: `0` success; `1` unexpected internal error; `2` CLI usage/configuration or input open/read/decode failure; `3` no valid request records; `4` unique-cardinality exhaustion. Code `4` means attempting to add another distinct User-Agent beyond `--max-unique-user-agents`; never omit, reuse, or remap it.

## Global Working Prompt

Use this prefix for every step:

> Read `CLAUDE.md`, `STRATEGIC_PLAN.md`, `PROJECT_ARCHITECTURE.md`, `PRD.md`, and the current step in `IMPLEMENTATION_PLAN.md`. Inspect the worktree and preserve unrelated changes. Work only on this one step and its named files. Use Python 3.11, Click, Rich, and dataclasses; do not add a database, authentication, HTTP API/server, cloud, Docker, or Kubernetes. Keep the input streaming and output transactional. Maintain exit codes 0 success, 1 internal error, 2 usage/configuration or input I/O/decode, 3 no valid records, and 4 unique-cardinality exhaustion. Run the step's verification commands and report actual evidence; do not mark the step complete from narration alone. Update documentation if and only if the implemented contract requires it. End the session or meaningful block by saving context through `/session-save`.

## Prompt 1: Contracts and Package Scaffold

> Execute Step 1 only. Create `pyproject.toml`, `src/nginx_stream_analyzer/__init__.py`, `models.py`, `errors.py`, the Click shell in `cli.py`, and `tests/test_package.py`. Model every final result field described under `PROJECT_ARCHITECTURE.md` → `## CLI Interface`; use frozen dataclasses where mutation is unnecessary. Expose `nginx-stream-analyzer`. Do not implement the parser or fabricate successful analysis. Keep the five exit meanings representable, including code 4 solely for unique-cardinality exhaustion. Run the three Step 1 verification commands. Stop after recording results and the next action.

## Prompt 2: Supported Nginx Parser

> Execute Step 2 only. Implement `parser.py` for the documented common and combined grammars. Compile grammar state once, handle quoted/escaped fields, parse the numeric timezone offset, and return structured malformed-line outcomes. Do not use naive whitespace splitting or infer arbitrary formats. Add focused fixtures/tests covering IPv4, IPv6, missing/empty User-Agent, quoting, invalid status/timestamp/request, blank lines, and Unicode. Do not change exit mapping: 0/1/2/3/4 retains the global meanings, with 4 only for unique-cardinality exhaustion. Run Step 2 verification and stop.

## Prompt 3: Streaming Aggregation

> Execute Step 3 only. Implement exact one-pass counters, 24 hour buckets, deterministic top-10 tie ordering, and the exact User-Agent set. Compute hourly percentages using the literal formula `100 × hourly_request_count / total_valid_requests`; do not use an unscaled fraction. Enforce the configured User-Agent ceiling before insertion and surface the typed condition that the CLI maps to exit 4. Test the N/N+1 boundary and never approximate or evict silently. Preserve codes 0 success, 1 internal, 2 usage/input, 3 no valid records, 4 unique-cardinality exhaustion. Run Step 3 verification and stop.

## Prompt 4: Streaming Orchestration

> Execute Step 4 only. Implement `service.py` and integrate path/stdin line iteration. Never read the whole stream, seek stdin, modify input, or emit a result before finalization. Count malformed lines, but map zero valid records to 3. Map expected open/read/decode failures to 2, exact User-Agent ceiling exhaustion to 4, unexpected exceptions to 1, and success to 0. Add service and CLI tests for every boundary named in the plan. Run Step 4 verification and stop.

## Prompt 5: Three Output Modes

> Execute Step 5 only. Build the Rich terminal, JSON, and long-form CSV renderers from one `AnalysisResult`. Match field names, ordering, rounding, 24-bucket behavior, and schemas in `PROJECT_ARCHITECTURE.md`. Escape untrusted log text and guarantee no ANSI in JSON/CSV. Enforce option exclusivity as exit 2. Do not alter the complete 0/1/2/3/4 mapping; code 4 remains unique-cardinality exhaustion. Test semantic equivalence rather than relying only on terminal snapshots. Run Step 5 verification and stop.

## Prompt 6: Failure and Safety Contract

> Execute Step 6 only. Complete narrow exception-to-exit mapping and add adversarial terminal/control fixtures. Test every code independently: 0 success, 1 forced unexpected internal failure, 2 usage/configuration or input I/O/decode, 3 no valid records, and 4 exact User-Agent cardinality exhaustion. For codes 1–4 assert empty stdout and a concise stderr diagnostic. Ensure no traceback appears by default and no log field is interpreted as markup, a shell fragment, or instructions. Run Step 6 verification and stop.

## Prompt 7: Performance Evidence

> Execute Step 7 only. Create the deterministic fixture generator, benchmark runner, and CI-safe performance smoke test. The release fixture must be exactly 1,000,000,000 bytes and bounded in key cardinality so the benchmark measures throughput rather than intentionally triggering code 4. Record wall time, peak RSS, hardware, OS, storage context, and Python version. Profile before optimizing; preserve exact results and exit codes 0/1/2/3/4. Do not claim the 30-second target unless the exact current candidate passes. Run all Step 7 commands and stop.

## Prompt 8: Build and Release Check

> Execute Step 8 only. Finish package metadata and user documentation, build wheel and sdist, check artifacts, install the wheel into a clean Python 3.11 environment, and smoke-test all public modes. Re-run the full suite and reconcile every P0 criterion. Search docs/tests for the complete contract: 0 success, 1 unexpected internal, 2 usage/configuration or input open/read/decode, 3 no valid records, 4 unique-cardinality exhaustion. Do not publish externally unless separately authorized. Run Step 8 verification and report actual evidence.

## Review Prompt After Each Step

> Review only the current step's diff against its `IMPLEMENTATION_PLAN.md` tasks and relevant PRD acceptance criteria. Look for whole-file reads, incorrect nginx quoting, non-deterministic ties, denominator mistakes, stdout contamination, terminal injection, and incomplete exit mapping. Specifically verify that code 4 still means unique-cardinality exhaustion. Run the step's tests. Return concrete findings with file/line references or state that no findings were identified; do not make unrelated changes.

## Completion Gate

Do not call the product complete until the exact release candidate passes all tests, the clean-wheel smoke run, semantic JSON/CSV checks, every exit path `0/1/2/3/4`, and the documented 1 GB benchmark on the recorded laptop. Save context with `/session-save` at the end of every session or significant work block.

