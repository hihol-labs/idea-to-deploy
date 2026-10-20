# Claude Code Implementation Guide: nginx-log-top

## Purpose

Use these prompts sequentially to implement the approved blueprint. Each prompt is bounded to one `IMPLEMENTATION_PLAN.md` step and requires tests before advancing. Do not introduce a database, HTTP API, auth, server, cloud resource, Docker runtime, or Kubernetes manifest.

## Global Contract for Every Step

Before editing, read `STRATEGIC_PLAN.md`, `PROJECT_ARCHITECTURE.md`, `PRD.md`, `IMPLEMENTATION_PLAN.md`, and `CLAUDE.md`. Preserve Python 3.11, Click, Rich, dataclasses, the synchronous streaming architecture, and deterministic ranking/output behavior.

The complete exit-code contract is `0/1/2/3/4`:

- `0`: successful completed analysis, including empty input.
- `1`: input I/O failure.
- `2`: command usage or option-validation failure.
- `3`: strict parsing or internal format failure.
- `4`: unique-cardinality exhaustion.

Never omit or remap code 4. Fatal errors must not emit a completed or partial report. Result data belongs on stdout and diagnostics on stderr.

For every step: keep changes limited to the listed files, add or update tests, run the named verification commands, summarize evidence, and update the status table in `CLAUDE.md`. Do not claim the 1 GB target without a recorded benchmark on a named machine.

## Prompt 1: Package and CLI Skeleton

```text
Implement Step 1 from IMPLEMENTATION_PLAN.md only. Create the Python 3.11 src-layout package, Click command, module entry point, version/help behavior, and mutually exclusive --json/--csv validation. Keep analysis as an explicit temporary boundary; do not invent product behavior beyond the spec. Add CLI tests for help, version, stdin default, and usage errors. Run the Step 1 verification commands and report their outcomes. Update only Step 1 status in CLAUDE.md.
```

## Prompt 2: Domain Models and Errors

```text
Implement Step 2 from IMPLEMENTATION_PLAN.md only. Create the frozen dataclasses and typed errors exactly from PROJECT_ARCHITECTURE.md, then add small, privacy-safe log fixtures and invariant tests. Do not add parsing or aggregation yet. Run compile and model tests, summarize evidence, and update only Step 2 status in CLAUDE.md.
```

## Prompt 3: Streaming Parser

```text
Implement Step 3 from IMPLEMENTATION_PLAN.md only. Parse the documented nginx Combined Log Format one physical line at a time with a compiled pattern and offset-aware timestamp. Raise safe line-numbered MalformedLine errors without echoing full log contents. Cover IPv4, IPv6, request targets, timezone offsets, escaped/missing fields, Unicode, and invalid cases. Run parser tests, lint, and type checks; report evidence and update only Step 3 status in CLAUDE.md.
```

## Prompt 4: Aggregation

```text
Implement Step 4 from IMPLEMENTATION_PLAN.md only. Build the streaming Analyzer without retaining parsed records. Compute stable top-10 IP and 400-599 URL rankings, all 24 hourly buckets, and exact nonempty User-Agent cardinality. Use the percentage formula 100 × hourly_request_count / total_valid_requests and round only in renderers. Enforce the configured cardinality ceiling before adding an overflowing distinct value. Test boundaries, ties, empty input, all hours, and exhaustion; report evidence and update only Step 4 status in CLAUDE.md.
```

## Prompt 5: Rich Text Renderer

```text
Implement Step 5 from IMPLEMENTATION_PLAN.md only. Render the AnalysisResult through Rich with summary plus IP, error URL, hourly, and User-Agent sections. Enable style only on an interactive TTY and honor --no-color. Keep renderer code independent from Click and open streams. Add deterministic snapshots or structural assertions and ANSI tests. Run the named checks, report evidence, and update only Step 5 status in CLAUDE.md.
```

## Prompt 6: JSON and CSV

```text
Implement Step 6 from IMPLEMENTATION_PLAN.md only. Add JSON schema version 1 and normalized RFC 4180 CSV with section,rank,key,count,percentage. Preserve numeric JSON values, stable order, Unicode, and quoting. Connect the mutually exclusive flags without changing terminal defaults. Add structural tests rather than fragile whitespace-only snapshots. Run renderer and CLI verification, report evidence, and update only Step 6 status in CLAUDE.md.
```

## Prompt 7: Integration and Failures

```text
Implement Step 7 from IMPLEMENTATION_PLAN.md only. Integrate stream ownership, parser, analyzer, and selected renderer at the CLI boundary. Map all typed failures to the exact 0/1/2/3/4 contract, including code 4 for unique-cardinality exhaustion. Default malformed behavior counts and continues; --strict stops with code 3. Ensure fatal paths emit no completed report and BrokenPipeError is quiet. Add one independent CLI test for every code and stdout/stderr boundary. Run the full suite, report evidence, and update only Step 7 status in CLAUDE.md.
```

## Prompt 8: Performance and Packaging

```text
Implement Step 8 from IMPLEMENTATION_PLAN.md only. Add a deterministic streaming benchmark generator, opt-in performance test, complete packaging metadata, and user documentation. Run format, lint, typing, coverage, build, artifact validation, and fresh-install smoke checks. Generate the 1 GB fixture outside the repository, record Python/CPU/storage context, wall time, throughput, and maximum RSS, and require under 30 seconds on the documented laptop. Do not tune by changing metric semantics. Update Step 8 status in CLAUDE.md only when all release evidence passes.
```

## Final Acceptance Prompt

```text
Validate the finished implementation against every P0 acceptance criterion in PRD.md without adding features. Run the complete test and quality suite, inspect the built wheel in a fresh Python 3.11 environment, exercise file and stdin input in text/JSON/CSV modes, and independently trigger exit codes 0, 1, 2, 3, and 4. Re-run and record the 1 GB benchmark. If anything fails, leave the relevant CLAUDE.md step incomplete and report the failing command and next bounded action.
```

