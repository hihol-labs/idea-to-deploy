# Claude Code Implementation Guide: nginx-stream-report

## Purpose and Guardrails

Use these prompts one at a time, in order, after implementation is authorized. Each prompt is bounded to the matching step in `IMPLEMENTATION_PLAN.md`. Read `PROJECT_ARCHITECTURE.md` and `PRD.md` before changing files; when behavior must change, update the spec first. Do not add authentication, a database, an HTTP API, a server, cloud resources, Docker, or Kubernetes.

For every step, preserve the complete exit-code contract: `0` success; `1` unexpected internal or output-write failure; `2` CLI usage/validation failure; `3` input path/open/read/UTF-8 decoding failure; `4` unique-cardinality exhaustion. Code `4` means unique-cardinality exhaustion and must never be omitted, caught as `1`, or remapped.

## Prompt 1 — Package and CLI contract

```text
Implement only Step 1 of IMPLEMENTATION_PLAN.md. Create the Python 3.11 src-layout package, Click console entry, declared Click/Rich dependencies, help/version, mutually exclusive --json/--csv, TTY-aware --color/--no-color, and positive --max-unique-user-agents defaulting to 1000000. Add the named tests. Do not implement parsing or reports. Preserve exit codes 0/1/2/3/4 exactly, including 4 for unique-cardinality exhaustion. Run the Step 1 verification commands and report evidence and changed files.
```

## Prompt 2 — Parser and records

```text
Implement only Step 2 of IMPLEMENTATION_PLAN.md. Follow PROJECT_ARCHITECTURE.md's exact standard-combined input grammar. Add frozen dataclasses, compile parsing machinery once, retain query strings, parse timezone-aware timestamps, and return a typed invalid result without partial aggregation. Add all specified fixtures/tests. Do not read files or render output in the parser. Preserve exit codes 0/1/2/3/4 exactly, including 4 for unique-cardinality exhaustion. Run the Step 2 verification commands and report evidence.
```

## Prompt 3 — Streaming aggregates

```text
Implement only Step 3 of IMPLEMENTATION_PLAN.md. Build one-pass aggregation without storing raw lines or AccessRecord history. Implement deterministic top-10 IP/error-URL rankings, all 24 hour buckets, hourly percentages using exactly 100 × hourly_request_count / total_valid_requests, and exact unique User-Agent share. Enforce the configured UA cardinality cap before inserting a new distinct value; duplicates at the cap remain valid. Add specified tests, especially the cap boundary and zero input. Preserve exit codes 0/1/2/3/4 exactly, including 4 for unique-cardinality exhaustion. Run verification and report evidence.
```

## Prompt 4 — Terminal renderer

```text
Implement only Step 4 of IMPLEMENTATION_PLAN.md. Render the immutable Report through Rich in the documented four-section order. Auto-color only on TTY, honor the explicit color option, and ensure log-derived values cannot be interpreted as Rich markup. Add golden and TTY tests. Keep domain and aggregation modules independent of Rich. Preserve exit codes 0/1/2/3/4 exactly, including 4 for unique-cardinality exhaustion. Run verification and report evidence.
```

## Prompt 5 — JSON renderer

```text
Implement only Step 5 of IMPLEMENTATION_PLAN.md. Emit exactly one JSON schema-version-1 object matching PROJECT_ARCHITECTURE.md, with deterministic key/array order, correct escaping, finite numbers, and two-decimal percentages. Results belong on stdout and diagnostics on stderr; do not emit ANSI. Add golden/schema/integration tests. Preserve exit codes 0/1/2/3/4 exactly, including 4 for unique-cardinality exhaustion. Run verification and report evidence.
```

## Prompt 6 — CSV renderer

```text
Implement only Step 6 of IMPLEMENTATION_PLAN.md. Use the standard csv module to emit record_type,rank,key,count,percentage with documented row order and CRLF. Escape fields and neutralize formula-leading key cells. Add golden tests for quoting, Unicode, formula inputs, and deterministic order. Preserve exit codes 0/1/2/3/4 exactly, including 4 for unique-cardinality exhaustion. Run verification and report evidence.
```

## Prompt 7 — I/O and exit semantics

```text
Implement only Step 7 of IMPLEMENTATION_PLAN.md. Wire line-by-line strict-UTF-8 reading for one path, omitted stdin, and '-'. Do not close process-owned stdin. Count syntactically invalid lines, exclude them from metrics, and diagnose them on stderr. Complete report construction before JSON/CSV writes. Map success to 0, internal/output failure to 1, usage to 2, input/open/read/decode failure to 3, and unique-cardinality exhaustion to 4. Do not catch code 4 as code 1. Add explicit integration tests for every code 0/1/2/3/4 and stdout/stderr atomicity. Run verification and report evidence.
```

## Prompt 8 — Performance and release

```text
Implement only Step 8 of IMPLEMENTATION_PLAN.md. Add a deterministic external 1 GB fixture generator, benchmark protocol, package smoke test, Python 3.11 CI, and verified README results. Run the full suite and build checks, then benchmark the exact installed CLI while recording hardware, Python, storage, wall time, and peak RSS. The gate is under 30 seconds. Profile before changing architecture. Preserve and test exit codes 0/1/2/3/4 exactly, including 4 for unique-cardinality exhaustion. Do not claim the performance gate without measured evidence.
```

## Review Prompt

```text
Review the exact candidate against PRD.md and PROJECT_ARCHITECTURE.md. Look specifically for raw-line retention, unbounded cardinality, status boundary errors, an hourly fraction missing the factor 100, nondeterministic ties, output contamination, terminal/JSON/CSV injection, partial machine output, and incorrect exception ordering. Verify executable cases for all exit codes 0/1/2/3/4; code 4 must mean only unique-cardinality exhaustion. Report file/line findings before any summary and label anything not executed as unverified.
```

## Completion Protocol

After each prompt, record changed files, commands actually run, results, and remaining step. Never infer passing tests or performance. Do not advance when the current step's verification fails. At session end or after a significant block, save context with `/session-save` as required by `CLAUDE.md`.
