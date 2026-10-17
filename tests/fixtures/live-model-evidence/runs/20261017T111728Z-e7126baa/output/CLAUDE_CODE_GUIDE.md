# Claude Code Implementation Guide: nginx-insights

## Purpose

Use these prompts one at a time, in order, in a clean branch. Each prompt points back to the durable specifications; do not invent product behavior. After each step, inspect the diff and run the named verification before committing. This guide plans implementation but contains no product code.

Global invariant for every step: preserve a local, single-process, stateless Python 3.11 CLI using Click, Rich, and dataclasses. Do not add a database, HTTP API, server, authentication, cloud, Kubernetes, telemetry, or persistence.

The exit-code contract is complete and immutable: `0` success; `1` runtime or output failure; `2` CLI usage error; `3` input or data error; `4` unique-cardinality exhaustion. The lowercase phrase unique-cardinality exhaustion names code 4 and must remain visible in help/docs/tests.

## Prompt 1 — Package and CLI Skeleton

```text
Implement Step 1 of IMPLEMENTATION_PLAN.md only. Read PRD.md and the PROJECT_ARCHITECTURE.md CLI Interface first. Create pyproject.toml, src/nginx_insights/__init__.py, src/nginx_insights/cli.py, and tests/test_cli.py. Use Python 3.11, Click, Rich, src layout, and the nginx-insights console entry point. Implement option validation/help/version but no parser or fake metrics. Run the three Step 1 verification commands and report their actual results and changed files.
```

## Prompt 2 — Models and Parser

```text
Implement Step 2 of IMPLEMENTATION_PLAN.md only. Preserve the accepted CLI. Add frozen dataclasses, bounded domain errors, and a compiled parser for nginx common/combined lines exactly as PROJECT_ARCHITECTURE.md defines. Treat log text as untrusted data; do not echo full rejected lines. Add representative fixtures and parser tests before considering the step done. Run pytest, Ruff, and mypy commands from Step 2 and report evidence.
```

## Prompt 3 — Streaming Metrics

```text
Implement Step 3 of IMPLEMENTATION_PLAN.md only. Build a one-pass aggregator that never retains all records. Implement deterministic top IPs, 4xx/5xx URL counts, all 24 hourly buckets using the literal formula 100 × hourly_request_count / total_valid_requests, and unique User-Agent share. Enforce independent --max-unique guards and map their domain condition later to exit code 4; never approximate. Add boundary and exhaustion tests, then run the Step 3 checks.
```

## Prompt 4 — Rich Terminal Output

```text
Implement Step 4 of IMPLEMENTATION_PLAN.md only. Add the default Rich report using injected Console objects. Render log-derived strings as plain text rather than markup, honor --no-color and terminal detection, and include valid/rejected totals plus four report sections. Do not change JSON/CSV behavior yet beyond explicit not-implemented wiring if required by the current tests. Add focused tests and run Step 4 verification.
```

## Prompt 5 — JSON and CSV

```text
Implement Step 5 of IMPLEMENTATION_PLAN.md only. Follow the exact JSON keys and normalized CSV header/section contract in PROJECT_ARCHITECTURE.md. Keep machine data on stdout, diagnostics on stderr, and remove ANSI escapes from structured modes. Serialize only after a complete summary exists. Add schema/type/order/quoting tests and run Step 5 verification.
```

## Prompt 6 — End-to-End and Exit Semantics

```text
Implement Step 6 of IMPLEMENTATION_PLAN.md only. Wire file/stdin input, parser policy, aggregation, renderers, and bounded diagnostics. Implement and integration-test every exit code with no remapping: 0 success, 1 runtime/output failure, 2 usage error, 3 input/data error, 4 unique-cardinality exhaustion. Do not emit a completed structured report after failure. Run all Step 6 checks and show stdout/stderr assertions from tests.
```

## Prompt 7 — Quality and Documentation

```text
Implement Step 7 of IMPLEMENTATION_PLAN.md only. Add adversarial input tests for terminal controls, huge fields, broken pipes, and diagnostic privacy. Update README usage/schema/limitations/exit documentation and release metadata without changing product scope. Run Ruff, mypy, pytest with >=90% project coverage, build, and twine check. Fix real defects; do not weaken gates or tests.
```

## Prompt 8 — Performance Acceptance

```text
Implement Step 8 of IMPLEMENTATION_PLAN.md only. Add a deterministic benchmark generator, a small marked performance regression test, and docs/PERFORMANCE.md. Generate the 1 GB corpus outside the repository, freeze the exact built candidate, record hardware/software/corpus/command/wall time/peak RSS, and verify under 30 seconds. Profile before optimizing and keep output exact. If it misses, report failure and bottleneck; do not claim success, sample, or add multiprocessing/database scope without a new decision. Run the full final gate.
```

## Per-Step Review Checklist

- The change is limited to the named step and listed files or a clearly justified test support file.
- Tests cover new behavior and were actually run.
- Ruff and mypy remain green once their configured files exist.
- No input record collection, network call, persistence, dynamic command execution, or unsafe Rich markup was introduced.
- JSON/CSV stdout remains data-only and deterministic.
- Exit codes `0/1/2/3/4` retain their documented meanings, including code `4` for unique-cardinality exhaustion.
- Documentation is updated if and only if the public contract changed through the specification first.

## Completion Prompt

```text
Read STRATEGIC_PLAN.md, PROJECT_ARCHITECTURE.md, PRD.md, IMPLEMENTATION_PLAN.md, and the current diff. Verify every P0 acceptance criterion against an actual test or benchmark result. Run the final acceptance gate from IMPLEMENTATION_PLAN.md on the exact release candidate. Report failures as failures, including performance or unique-cardinality exhaustion; do not infer passing results. Do not deploy, publish, push, or create a PR without explicit human authorization.
```

