# Claude Code Implementation Guide: nginx-stream-insights

This guide turns the approved specifications into eight bounded implementation prompts. Run one prompt at a time, preserve WIP=1, and do not begin the next step until the listed verification succeeds. The durable source of truth is `PRD.md`; architectural details and schemas are in `PROJECT_ARCHITECTURE.md`; sequencing is in `IMPLEMENTATION_PLAN.md`.

## Non-Negotiable Contract

- Build a local Python 3.11 CLI using Click, Rich, and dataclasses.
- Keep a single-process, stateless, one-pass design. Add no database, authentication, HTTP API, server, cloud service, Docker/Kubernetes asset, telemetry, or network call.
- Retain no raw log line after aggregation.
- Calculate hourly percentage using `100 × hourly_request_count / total_valid_requests`.
- Preserve the complete public exit contract: `0` success/help/version; `1` unexpected runtime or stdout-write failure; `2` CLI usage/configuration error; `3` input/read/decode/gzip failure or zero valid records; `4` unique-cardinality exhaustion.
- Emit no partial stdout on an unsuccessful analysis. Keep JSON/CSV stdout free of diagnostics and ANSI escapes.
- Do not silently approximate exact metrics or remap exit codes.

## Working Protocol

For each step:

1. Read the named specification sections and inspect the current repository state.
2. State the bounded file changes before editing; stop if they conflict with the specifications.
3. Implement only the active step and its tests.
4. Run the exact verification commands plus any narrower test needed for a discovered edge case.
5. Report changed files, command results, remaining risk, and the next step. Never describe unrun checks as passed.

## Prompt 1: Package and CLI Contracts

```text
Implement Step 1 of IMPLEMENTATION_PLAN.md only. Read PROJECT_ARCHITECTURE.md sections “Component Model,” “CLI Interface,” and “Packaging and Deployment,” plus all P0 requirements in PRD.md. Create pyproject.toml, the src/nginx_stream_insights package skeleton, frozen/slots domain dataclasses, typed expected errors, the Click command/options, and CLI contract tests. The console command must be nginx-insights and require Python 3.11+. Add no parser or aggregator behavior beyond a testable boundary. Run the three Step 1 verification commands and report evidence without beginning Step 2.
```

## Prompt 2: Streaming Input and Parser

```text
Implement Step 2 of IMPLEMENTATION_PLAN.md only. Read PRD.md Input Contract and PROJECT_ARCHITECTURE.md “Data Model and Algorithms,” “CLI Interface / Inputs,” and “Error Handling and Resource Limits.” Add lazy stdin/sequential-file iteration, the documented nginx combined-log parser, representative fixtures, and focused tests. Compile the parse pattern once, preserve the logged timezone/hour, do not buffer the corpus, and treat malformed individual lines as recoverable data. Do not add gzip support yet. Run every Step 2 verification command and report evidence without beginning Step 3.
```

## Prompt 3: Exact Core Aggregation

```text
Implement Step 3 of IMPLEMENTATION_PLAN.md only. Read PRD.md FR-02 through FR-04 and PROJECT_ARCHITECTURE.md “Streaming state” and “Performance Design.” Add exact IP and 4xx/5xx URL counters, deterministic top-10 selection, fixed 24-hour counts, and percentages calculated with 100 × hourly_request_count / total_valid_requests. Include all 24 hours and preserve query strings. Add focused tests for 399/400/499/500/599 boundaries, ties, top-10 truncation, empty hours, and totals. Run the Step 3 verification commands and report evidence without beginning Step 4.
```

## Prompt 4: Cardinality and Exit Codes

```text
Implement Step 4 of IMPLEMENTATION_PLAN.md only. Read PRD.md FR-05 and FR-09 plus PROJECT_ARCHITECTURE.md ADR-003 and “Exit codes.” Track exact non-missing User-Agent values, enforce the configured limit before adding an over-limit value, and calculate the documented share. Map expected failures in the Click boundary and guarantee empty stdout on failure. Add tests that prove all exit codes 0, 1, 2, 3, and 4 with their documented meanings, including repeated and missing agents. Run the Step 4 commands and report evidence without beginning Step 5.
```

## Prompt 5: Terminal Renderer

```text
Implement Step 5 of IMPLEMENTATION_PLAN.md only. Read PRD.md FR-06 and PROJECT_ARCHITECTURE.md “CLI Interface / Outputs” and “Security and Privacy.” Add the default Rich report and --no-color behavior. Render every required section, escape untrusted log values so Rich never interprets them as markup, and snapshot deterministic no-color output. Keep machine renderers out of this step. Run the Step 5 commands and report evidence without beginning Step 6.
```

## Prompt 6: JSON and CSV Renderers

```text
Implement Step 6 of IMPLEMENTATION_PLAN.md only. Read PRD.md FR-07 and FR-08 and the exact JSON/CSV schemas in PROJECT_ARCHITECTURE.md. Add schema_version 1 JSON and normalized metric,rank,key,count,percentage CSV. Use the standard csv module, mitigate spreadsheet formulas as specified, keep warnings on stderr, and ensure no ANSI escapes or locale-dependent numbers. Add parse-based tests and snapshots. Run all Step 6 commands and report evidence without beginning Step 7.
```

## Prompt 7: Robust Inputs and Gzip

```text
Implement Step 7 of IMPLEMENTATION_PLAN.md only. Read PRD.md FR-01, FR-09, FR-10, and FR-13 plus PROJECT_ARCHITECTURE.md input/error contracts. Add streamed .gz path support, encoding diagnostics, and end-to-end cases for stdin, ordered files, mixed malformed input, zero valid records, unreadable/undecodable data, corrupt gzip, and output failure. Preserve no-partial-stdout behavior and the complete exit-code contract. Run all Step 7 commands and report evidence without beginning Step 8.
```

## Prompt 8: Performance and Release Candidate

```text
Implement Step 8 of IMPLEMENTATION_PLAN.md only. Read STRATEGIC_PLAN.md KPIs and Definition of Done, PRD.md release gate, and PROJECT_ARCHITECTURE.md performance/test boundaries. Add deterministic benchmark generation and measurement, then profile before optimizing. Record hardware, Python version, byte/line counts, peak RSS, wall time, and input checksum. Complete README usage/schema/privacy documentation, build wheel and sdist, install the wheel in a clean Python 3.11 environment, and smoke-test terminal, JSON, and CSV. Run the full tests, coverage, lint, build, clean-wheel smoke tests, and representative 1 GB benchmark. Do not claim the <30 second target unless the recorded candidate passes it.
```

## Final Release Checklist

- [ ] All P0 acceptance criteria in `PRD.md` have executable evidence.
- [ ] `nginx-insights --help` accurately describes defaults and option conflicts.
- [ ] Terminal, JSON, and CSV output match `PROJECT_ARCHITECTURE.md`.
- [ ] Codes `0/1/2/3/4` are proven by subprocess-level tests, including code `4` for unique-cardinality exhaustion.
- [ ] Malformed-line behavior and empty stdout on fatal failures are proven.
- [ ] The installed wheel, not only the source tree, passes smoke tests.
- [ ] The representative 1 GB candidate completes under 30 seconds on recorded laptop hardware.
- [ ] No forbidden infrastructure or raw-log persistence was introduced.

If a contract needs to change, edit and approve the specification first, then update implementation and tests; do not let generated code become the source of truth.
