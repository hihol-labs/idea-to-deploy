# Claude Code Implementation Guide: nginx-logtop

## How to Use This Guide

Execute one prompt at a time, in order, in a fresh or restored Idea to Deploy session. Each prompt corresponds exactly to a step in `IMPLEMENTATION_PLAN.md`. Preserve WIP=1, read the repository contracts before editing, update the active unit state, and do not proceed when the listed verification fails. These prompts authorize implementation only when a future user explicitly starts that step; this blueprint session remains documentation-only.

Before each step, reread the relevant portions of `PRD.md` and `PROJECT_ARCHITECTURE.md`. Never implement from this guide alone when a normative contract is more specific.

## Non-Negotiable Implementation Contract

- Architecture: one local synchronous Python 3.11 process, streaming and stateless.
- Dependencies: Click, Rich, dataclasses/standard library; package installation through pip/pipx.
- No authentication, database, HTTP API, server, cloud, Docker requirement, or Kubernetes.
- Hourly percentage formula: `100 × hourly_request_count / total_valid_requests`.
- Output modes share one report: Rich text by default, stable `--json`, stable `--csv`.
- Complete exit codes: `0` success/help/version; `1` operational I/O/output/internal failure; `2` invalid CLI usage; `3` input/data-format/empty/no-valid-record failure; `4` unique-cardinality exhaustion. Code `4` must never be omitted, remapped, or replaced by approximation.
- Do not emit a partial report on code `4`.
- Never claim the 1 GB / 30 s target without a current benchmark record from the exact candidate.

## Prompt 1 — Package and Verification Skeleton

```text
Use the repository's Idea to Deploy implementation workflow for Step 1 in IMPLEMENTATION_PLAN.md. Read AGENTS.md, .itd contracts, STRATEGIC_PLAN.md, PROJECT_ARCHITECTURE.md, PRD.md, and the full Step 1 first. Freeze scope to pyproject.toml, src/nginx_logtop/__init__.py, the minimal Click boundary in src/nginx_logtop/cli.py, tests/conftest.py, tests/test_package.py, and the small golden fixtures. Do not implement parsing or metrics yet.

Use Python 3.11, a src layout, Click, Rich, pytest, coverage, Ruff, and mypy. Expose the nginx-logtop console script. Establish the complete CLI exit contract as a documented invariant: 0 success/help/version, 1 operational failure, 2 usage failure, 3 input/data-format failure, and 4 unique-cardinality exhaustion; do not use placeholder meanings for code 4.

Run every Step 1 verification command. Record actual evidence, reconcile Idea to Deploy state, and stop in recovery if installation, import, help, or tests fail. Do not begin Step 2.
```

## Prompt 2 — Domain Models and Parser

```text
Implement only Step 2 from IMPLEMENTATION_PLAN.md using the adopted Idea to Deploy workflow. Read the exact AccessRecord and parsing contracts in PROJECT_ARCHITECTURE.md before editing. Create models.py, parser.py, and parser tests. Parse the complete nginx Combined Log Format with strict UTF-8, anchored quoted fields, timezone-aware timestamps, validated status/bytes fields, and query/fragment removal for the error-ranking path. Keep parsing pure: no Click exits, rendering, whole-file reads, or global state.

Preserve the complete eventual exit mapping at the typed-error boundary: 0 success, 1 operational failure, 2 CLI usage error, 3 input/data-format failure, 4 unique-cardinality exhaustion. The parser produces the typed data error that the future CLI maps to 3; it must not consume or redefine code 4.

Run Step 2 parser and coverage checks against the golden fixtures. Record evidence and reconcile the active unit. Do not continue if malformed quoting, timestamp offsets, strict decoding, or safe diagnostics remain unproved.
```

## Prompt 3 — Streaming Aggregation

```text
Implement only Step 3 from IMPLEMENTATION_PLAN.md. Read the in-memory state, metric definitions, determinism, and performance sections in PROJECT_ARCHITECTURE.md and US-2 through US-5 in PRD.md. Create aggregate.py and focused tests. Use one update per valid record to maintain exact IP counts, exact combined 4xx/5xx path counts, 24 logged-offset hour counters, and an exact User-Agent set.

Compute hourly percentages with exactly 100 × hourly_request_count / total_valid_requests and User-Agent share with 100 × distinct_user_agent_count / total_valid_requests. Enforce max_unique_user_agents before inserting an over-limit value and raise UniqueCardinalityExhausted; never approximate or finalize a partial report. Deterministic ranking is descending count then ascending key.

Preserve all exit semantics for later orchestration: 0 success, 1 operational, 2 usage, 3 input/data format, 4 unique-cardinality exhaustion. Explicitly test the at-limit success and first-over-limit code-4 domain path. Run all Step 3 checks, attach evidence, reconcile state, and stop before input/CLI integration.
```

## Prompt 4 — Streaming Input

```text
Implement only Step 4 from IMPLEMENTATION_PLAN.md. Create input.py and test_input.py. Stream stdin or regular UTF-8 files line by line, carry source/line metadata, process multiple paths in order, reject repeated stdin and invalid named-input types, and keep invalid-line diagnostics aggregate-only. Demonstrate incremental reads in a test; do not read whole files.

Preserve and test the boundary required by the complete contract: 0 success; 1 open/read and operational failures; 2 invalid CLI usage such as repeated '-' once the CLI validates it; 3 strict decode, empty, or no-valid-record data failures; 4 exact unique User-Agent cardinality exhaustion passed through from aggregation. Do not catch code-4 domain errors as generic code 1.

Run the exact Step 4 commands and existing Steps 1-3 tests. Reconcile Idea to Deploy evidence and do not start renderer work if source lifetime, incremental reading, or typed errors are ambiguous.
```

## Prompt 5 — Renderers

```text
Implement only Step 5 from IMPLEMENTATION_PLAN.md. Create the renderer package and golden renderer tests. Render one immutable report as Rich terminal text, versioned JSON, or tidy CSV. Escape log-derived Rich markup. Machine outputs must have deterministic order, no ANSI, documented newlines, locale-independent numbers, and exactly the schemas in PROJECT_ARCHITECTURE.md. Do not recalculate metrics in a renderer.

Keep the complete process contract visible in tests and interfaces: 0 success, 1 operational/output/internal failure, 2 invalid format-option usage, 3 input/data failure, 4 unique-cardinality exhaustion. Renderers must not swallow output errors or produce output after a cardinality-exhaustion failure.

Run all Step 5 commands plus prior unit tests. Record golden-output evidence and reconcile state. Do not integrate Click options in this unit.
```

## Prompt 6 — CLI Integration and Exit Codes

```text
Implement only Step 6 from IMPLEMENTATION_PLAN.md. Treat PROJECT_ARCHITECTURE.md's exact 'CLI Interface' section as normative. Compose input, parser, aggregation, and renderer in cli.py. Implement file/stdin behavior, --json, --csv, --color/--no-color, --max-unique-user-agents, --help, and --version. Keep stdout report-only and stderr diagnostic-only.

Implement and integration-test the complete mapping without gaps: 0 successful report/help/version; 1 input open/read, non-pipeline output, or unexpected internal runtime failure; 2 invalid options/arguments or mutually exclusive formats; 3 invalid UTF-8, empty input, or no valid combined-log records; 4 unique-cardinality exhaustion. Force a small ceiling in a subprocess test to prove exact exit 4 and absence of a partial report. Do not remap UniqueCardinalityExhausted through a generic exception handler.

Run every Step 6 command and the entire unit suite. Capture actual stdout, stderr, and exit evidence, reconcile the active Idea to Deploy unit, and stop on any schema or mapping drift.
```

## Prompt 7 — Quality and Performance Gates

```text
Implement only Step 7 from IMPLEMENTATION_PLAN.md. Add the deterministic benchmark generator, marked performance test, robustness cases, and docs/BENCHMARK.md. Generate the 1 GB fixture outside Git with bounded cardinality and known results. Measure the exact candidate on documented hardware using the plan command; record Python, CPU, memory, storage, wall time, peak RSS, fixture seed/size, and result validation. Profile before optimizing and keep every golden test green.

Stress malformed input, long fields, markup payloads, huge query strings, and cardinality exhaustion. The full mapping remains mandatory under stress: 0 success, 1 operational/internal failure, 2 usage, 3 input/data failure, and 4 unique-cardinality exhaustion. Never convert a performance or memory problem into silent approximation and never omit the code-4 test.

Run pytest with coverage, Ruff, mypy, and the benchmark commands exactly as documented. Freeze and adjudicate the exact candidate using the repository verification loop. If 1 GB is not under 30 seconds, report recovery with measurements; do not claim completion or skip the gate.
```

## Prompt 8 — Package and Release Handoff

```text
Implement only Step 8 from IMPLEMENTATION_PLAN.md. Reconcile README.md with actual tested behavior, add the chosen permissive LICENSE, finalize package metadata, build source/wheel artifacts, inspect them, and install the wheel in a fresh Python 3.11 virtual environment. Do not publish or create external releases without separate user authorization.

Smoke-test terminal, JSON, CSV, invalid usage, unusable data, operational failure, and forced cardinality exhaustion. The release documentation and artifact must expose exactly: 0 success/help/version, 1 operational failure, 2 CLI usage error, 3 input/data-format failure, 4 unique-cardinality exhaustion. Code 4 cannot be omitted or remapped.

Run every Step 8 command and all Definition of Done gates, including the current 1 GB benchmark. Use the exact-candidate Idea to Deploy adjudication required by the repository; reconcile state and hand off the next explicit action. Do not describe a standalone PASSED message as sufficient acceptance evidence.
```

## Completion Checklist for Every Prompt

- Scope remained inside the named step and no next step started.
- Tests were run, not merely described.
- Generated/temporary benchmark data is excluded from version control.
- `PROJECT_ARCHITECTURE.md` and `PRD.md` remain the source of truth.
- The complete `0/1/2/3/4` contract, including code `4` unique-cardinality exhaustion, remains intact.
- Idea to Deploy state and evidence identify the next action or recovery path.
