# Claude Code Implementation Guide: Nginx Stream Analyzer

## How to Use This Guide

Run one prompt at a time in order. Before editing, read `CLAUDE.md`, `PRD.md`, `PROJECT_ARCHITECTURE.md`, the current step in `IMPLEMENTATION_PLAN.md`, and the active `.itd/` contracts. Preserve WIP=1, update the active unit before scope changes, and verify the exact candidate rather than relying on narration.

This guide plans future implementation; it does not authorize implementation in the blueprint session.

## Non-Negotiable Contract

- Python 3.11, Click, Rich, dataclasses, pip installation.
- One local process, one streaming pass, no raw-record retention.
- No authentication, database, HTTP API, server, cloud, Docker, or Kubernetes.
- Default terminal output plus mutually exclusive `--json` and `--csv`.
- Hourly percentage formula: `100 × hourly_request_count / total_valid_requests`.
- Exit codes are complete and fixed: `0` success; `1` input/I/O failure; `2` CLI usage/configuration error; `3` no valid requests; `4` unique-cardinality exhaustion.
- Nonzero exits write no partial report to stdout.
- Never approximate exact User-Agent cardinality without first changing the PRD and architecture decision.

## Prompt 1: Package and CLI Skeleton

> Implement only Step 1 from `IMPLEMENTATION_PLAN.md`. Create the Python 3.11 `src/` package, `pyproject.toml`, console entry, module entry, and CLI option skeleton using Click and Rich. Write tests before or with behavior. Do not implement parsing or analytics. Run every Step 1 verification command and report actual results. Reconcile the active Idea to Deploy unit before handoff.

Expected files: `pyproject.toml`, `src/nginx_stream_analyzer/__init__.py`, `src/nginx_stream_analyzer/__main__.py`, `src/nginx_stream_analyzer/cli.py`, `tests/test_cli.py`.

## Prompt 2: Models and Exit Policy

> Implement only Step 2. Define the dataclasses and typed failures from the architecture, then map them once at the Click boundary. Test the complete `0/1/2/3/4` contract; code `4` must remain the exact User-Agent cardinality failure. Do not parse logs or render reports yet. Run Step 2 verification and record evidence.

Expected files: `src/nginx_stream_analyzer/models.py`, `src/nginx_stream_analyzer/errors.py`, updates to `cli.py`, `tests/test_errors.py`.

## Prompt 3: Parser

> Implement only Step 3. Build the supported nginx common/combined parser from the documented input contract. Treat log content as untrusted data, bound line length and diagnostic excerpts, and return structured outcomes without formatting output. Add the complete fixture matrix and reach the stated parser coverage. Run the exact Step 3 commands.

Expected files: `src/nginx_stream_analyzer/parser.py`, `tests/fixtures/access_valid.log`, `tests/fixtures/access_mixed.log`, `tests/test_parser.py`.

## Prompt 4: Streaming Aggregation

> Implement only Step 4. Consume an iterable once and compute all four metrics. Preserve deterministic tie ordering, all 24 hours, the literal hourly percentage formula, separate 4xx/5xx subtotals, and exact User-Agent behavior. Add red-to-green tests at the ceiling and ceiling+1. Ceiling+1 must fail with code `4` through the existing mapping and must never return a partial result. Run Step 4 verification.

Expected files: `src/nginx_stream_analyzer/aggregate.py`, `tests/test_aggregate.py`.

## Prompt 5: Rich Terminal Report

> Implement only Step 5. Render immutable `AnalysisResult` data using Rich. Match auto/forced/disabled color behavior, keep warnings on stderr, and disable markup for every log-derived value. Add and review a no-color golden file. Do not change metric semantics. Run Step 5 verification.

Expected files: `src/nginx_stream_analyzer/renderers/__init__.py`, `src/nginx_stream_analyzer/renderers/text.py`, `tests/golden/report.txt`, `tests/test_text_renderer.py`.

## Prompt 6: JSON and CSV

> Implement only Step 6. Add JSON schema version 1 and the exact normalized CSV header/order from `PROJECT_ARCHITECTURE.md`. Use standard serializers, six-decimal percentage values, deterministic ordering, UTF-8, and clean stdout. Make `--json` and `--csv` mutually exclusive. Run golden, parseability, and injection/quoting tests plus all Step 6 commands.

Expected files: `src/nginx_stream_analyzer/renderers/json.py`, `src/nginx_stream_analyzer/renderers/csv.py`, updates to `cli.py`, golden files, renderer tests.

## Prompt 7: Integration and Distribution

> Implement only Step 7. Exercise the installed CLI through subprocesses for file and stdin across all output modes. Prove failure stdout is empty and cover exits `0/1/2/3/4` without remapping. Build wheel and sdist, install into a clean Python 3.11 environment, and test both entry points. Run all Step 7 commands and report failures honestly.

Expected files: `tests/test_integration.py`, `tests/test_install.py` or an equivalent checked-in install smoke test, and necessary packaging/documentation updates.

## Prompt 8: Performance and Release Gate

> Implement only Step 8. Add deterministic benchmark utilities without checking in the generated 1 GB log. Validate correctness on a small oracle, then record wall time, environment, throughput, and peak RSS for 1 GB. Profile before optimizing and preserve every PRD semantic. Add resource/security guard tests. Freeze the exact staged candidate and use the repository's Verification Loop and risk-tier checker; do not claim acceptance without a current revalidated adjudication receipt.

Expected files: `benchmarks/generate_log.py`, `benchmarks/run.py`, `tests/test_resource_guards.py`, plus evidence/state artifacts required by `.itd/`.

## Per-Step Handoff Checklist

- [ ] Only the active step's declared files and necessary contract/state files changed.
- [ ] Acceptance behavior traces to a PRD ID or architecture contract.
- [ ] Listed commands were actually run and outputs summarized.
- [ ] No ignored/untracked overlay influenced verification unless explicitly declared with a content binding.
- [ ] `CLAUDE.md` status and `.itd-memory` active state agree.
- [ ] Failures remain open recovery items; they are not described as passed.
- [ ] At the end of the session or significant block, save context via `/session-save`.

## Release Review Prompt

> Review the exact release candidate against `PRD.md`, `PROJECT_ARCHITECTURE.md`, and `IMPLEMENTATION_PLAN.md`. Verify streaming behavior, stable schemas, terminal injection safety, the 1 GB/30-second evidence, and every exit outcome: `0` success, `1` I/O, `2` usage, `3` no valid data, `4` unique-cardinality exhaustion. Do not alter code during review. Return evidence-backed findings and the machine-readable verdict required by the active Idea to Deploy reviewer contract.
