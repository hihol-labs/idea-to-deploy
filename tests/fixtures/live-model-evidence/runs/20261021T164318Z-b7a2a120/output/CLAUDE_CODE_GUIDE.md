# Claude Code Implementation Guide: nginx-stream-report

## Purpose

This guide turns [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) into bounded prompts for a coding agent. Run one prompt at a time, inspect its diff and evidence, and do not start the next step until the current verification commands pass. [PRD.md](PRD.md) is the behavior source of truth and [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) is the design source of truth.

Global invariant for every prompt: preserve the complete exit-code contract `0/1/2/3/4`: `0` success, `1` input/runtime I/O failure, `2` usage error, `3` no valid records, and `4` unique-cardinality exhaustion. Never remap or omit code `4`. Hourly distribution always uses `100 × hourly_request_count / total_valid_requests`.

## Working Rules

1. Read the three source documents and the current tests before editing.
2. Implement only the named step; do not pull P1/P2 features forward.
3. Add or update tests in the same change as behavior.
4. Treat log content as untrusted data and never make network calls.
5. Run the listed commands and report actual results, not expected results.
6. Stop on a contract conflict and update the specification before changing behavior.

## Prompt 1: Package Skeleton and CLI Boundary

```text
Implement Step 1 from IMPLEMENTATION_PLAN.md only. Create the Python 3.11 src-layout package, pyproject metadata, Click console entry point, and tests for help/version/option validation. Use Click and Rich as runtime dependencies and pytest tooling for development. Enforce mutual exclusion of --json and --csv and positivity of --max-unique-user-agents. Do not implement log parsing or reports yet. Run the Step 1 verification commands and summarize changed files and actual results.
```

Acceptance gate: editable install succeeds, help/version work, and conflicting/invalid options return `2`.

## Prompt 2: Domain Models and Parser

```text
Implement Step 2 from IMPLEMENTATION_PLAN.md only. Add frozen dataclasses and a precompiled parser for the supported nginx combined-log grammar. Return a clear invalid result for malformed records without retaining lines or exposing their content in diagnostics. Add fixtures and exhaustive parser tests for the cases listed in the plan. Do not aggregate or render yet. Run the Step 2 verification commands and report actual coverage.
```

Acceptance gate: supported fields parse exactly, malformed cases are rejected safely, and parser branch coverage is at least 90%.

## Prompt 3: Streaming Aggregation

```text
Implement Step 3 from IMPLEMENTATION_PLAN.md only. Add one-pass aggregation for top-10 IPs, top-10 URLs with status 400..599, 24 hourly buckets, and exact unique User-Agent count/share. Use deterministic tie order (count descending, key ascending). Compute hourly percentages with the literal formula 100 × hourly_request_count / total_valid_requests. Enforce the configured unique User-Agent ceiling before exceeding it and raise the domain exception mapped later to code 4. Add the specified unit tests and run Step 3 verification.
```

Acceptance gate: all aggregation edge cases pass, exact cardinality is bounded, and no input records are retained.

## Prompt 4: JSON and CSV Renderers

```text
Implement Step 4 from IMPLEMENTATION_PLAN.md only. Add the exact JSON schema_version 1 structure and fixed long-form CSV schema from PROJECT_ARCHITECTURE.md. Use standard serializers, deterministic ordering, UTF-8, and numeric JSON percentages. Machine output must contain no ANSI escapes or diagnostics. Add golden fixtures and parser-based tests, then run all Step 4 verification commands.
```

Acceptance gate: JSON and CSV parse successfully and match the documented schemas byte-for-byte where golden output applies.

## Prompt 5: Rich Text Renderer

```text
Implement Step 5 from IMPLEMENTATION_PLAN.md only. Build the Rich report with all documented sections and values. Treat IPs, URLs, and User-Agents as data rather than Rich markup. Color must be non-semantic and disabled for redirected output, NO_COLOR, or --no-color. Add golden and edge-case tests and run Step 5 verification.
```

Acceptance gate: interactive and plain modes contain equivalent information, unsafe markup is escaped, and plain output has no ANSI escapes.

## Prompt 6: End-to-End CLI

```text
Implement Step 6 from IMPLEMENTATION_PLAN.md only. Wire file/stdin iteration, parsing, aggregation, and the selected renderer without materializing or rereading input. Keep stdout pure report data and stderr for diagnostics. Implement and integration-test every exit: 0 success; 1 input/runtime I/O failure; 2 usage error; 3 no valid records; 4 unique-cardinality exhaustion. Fatal paths must emit no partial report. Run the full Step 6 verification suite.
```

Acceptance gate: file/stdin results match, output channels remain clean, and integration tests exercise the full `0/1/2/3/4` matrix.

## Prompt 7: Performance Proof

```text
Implement Step 7 from IMPLEMENTATION_PLAN.md only. Add deterministic benchmark fixture generation and a runner that validates output, wall time, peak RSS, and environment metadata. Generate a representative 1 GB log outside the repository and measure the installed CLI against the under-30-second target. Profile before optimizing and preserve all report semantics. Record the real reference result in benchmarks/README.md. Do not commit the generated large file.
```

Acceptance gate: a reproducible run on the documented reference laptop processes 1 GB in under 30 seconds and records sufficient metadata to repeat it.

## Prompt 8: Release Validation

```text
Implement Step 8 from IMPLEMENTATION_PLAN.md only. Reconcile README examples with implemented CLI help and schemas, add changelog/license, test executable documentation examples, build wheel and sdist, validate artifacts, install the wheel into a clean Python 3.11 virtual environment, run the full suite, and rerun the benchmark. Do not publish, push, deploy, or create a PR. Report actual command results and any remaining release blockers.
```

Acceptance gate: all tests pass, artifacts validate, the wheel runs in a clean environment, and the performance target still passes.

## Final Handoff Checklist

- [ ] P0 acceptance criteria in PRD are linked to passing tests.
- [ ] Default text, JSON, and CSV outputs contain the same metric values.
- [ ] Hourly percentages follow `100 × hourly_request_count / total_valid_requests`.
- [ ] Integration evidence covers exit codes `0/1/2/3/4`.
- [ ] The 1 GB benchmark is below 30 seconds on documented hardware.
- [ ] No authentication, database, HTTP API, server, cloud, Docker, or Kubernetes scope was introduced.
- [ ] No publish, push, PR, or deployment action occurred without human approval.
