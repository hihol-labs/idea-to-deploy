# Implementation Guide: Nginx Stream Analytics CLI

## 1. How to Use This Guide

Execute one prompt at a time in order. Keep WIP=1, review the named specifications before editing, and do not start the next step until the verification commands pass. Each prompt is bounded to the corresponding step in `IMPLEMENTATION_PLAN.md`; it must not introduce a database, HTTP API, server, authentication, cloud service, Docker, or Kubernetes.

Specifications are the durable source of truth. If implementation reveals a behavioral ambiguity, update `PROJECT_ARCHITECTURE.md` and `PRD.md` first, then implement and test the clarified contract.

## 2. Non-Negotiable Runtime Contract

Every prompt must preserve and test the complete exit-code mapping:

| Code | Meaning |
|---:|---|
| `0` | Success, help, or version |
| `1` | Unexpected internal processing/rendering failure |
| `2` | Invalid CLI usage/options |
| `3` | Input/data failure, including unreadable input or zero valid requests |
| `4` | Unique-cardinality exhaustion; emit no partial report |

Hourly percentages always use the literal formula `100 × hourly_request_count / total_valid_requests`. Do not replace it with an unscaled fraction. Unique User-Agent share is `100 × distinct_nonempty_user_agent_count / total_valid_requests`.

## Prompt 1 — Package and CLI skeleton

```text
Implement STEP 1 from IMPLEMENTATION_PLAN.md only. Read PRD.md and the CLI Interface in PROJECT_ARCHITECTURE.md first. Create pyproject.toml, the src package, initial Click boundary, and tests for --help and --version. Use Python 3.11, Click, Rich, and dataclasses. Make the package installable with the console name nginx-stream-report. Do not implement parsing or reports yet, and do not leave placeholder output that could be mistaken for a report. Run the exact STEP 1 verification commands and report evidence plus changed files.
```

## Prompt 2 — Models and failures

```text
Implement STEP 2 from IMPLEMENTATION_PLAN.md only. Add immutable typed dataclasses matching PROJECT_ARCHITECTURE.md and a domain failure taxonomy that can express exit codes 0/1/2/3/4 without importing Click into the domain. Assert model invariants in tests. Do not parse input or render output. Run the STEP 2 verification commands and report evidence plus changed files.
```

## Prompt 3 — Input and parser

```text
Implement STEP 3 from IMPLEMENTATION_PLAN.md only. Build ordered lazy input iterators and the documented nginx combined-log parser. Support stdin when no path is supplied and '-' at most once. Compile parsing machinery once, produce timezone-aware AccessRecord objects, and classify malformed lines without retaining raw input. Treat log data as untrusted. Add all named fixtures and boundary tests. Input/data failures must remain exit-3 domain failures; usage validation remains exit 2. Run the STEP 3 verification commands and report evidence plus changed files.
```

## Prompt 4 — Streaming aggregation

```text
Implement STEP 4 from IMPLEMENTATION_PLAN.md only. Build one-pass exact aggregation for top IPs, 4xx/5xx URLs, 24 hour buckets, and distinct nonempty User-Agents. Use deterministic tie-breaking. Compute hourly percentage exactly as 100 × hourly_request_count / total_valid_requests. Enforce the combined unique-key ceiling before admitting a new IP, error URL, or User-Agent. Exceeding it must yield exit 4 later and must never allow a partial report. Add focused tests for every formula, boundary, tie, malformed exclusion, and cardinality edge. Run the STEP 4 verification commands and report evidence plus changed files.
```

## Prompt 5 — Rich text output

```text
Implement STEP 5 from IMPLEMENTATION_PLAN.md only. Render the immutable Report as four labeled Rich sections plus summary. Display all 24 hours and percentages to two decimals. Implement color auto/always/never, honor safe non-TTY behavior, and prevent logged values from being interpreted as Rich markup. Do not change metric semantics. Run the STEP 5 verification commands and report evidence plus changed files.
```

## Prompt 6 — JSON and CSV output

```text
Implement STEP 6 from IMPLEMENTATION_PLAN.md only. Match the exact JSON schema_version 1 and normalized CSV schema in PROJECT_ARCHITECTURE.md. Use standard encoders, deterministic ordering, numeric JSON percentages, and RFC 4180-compatible CSV. Emit no ANSI sequences or diagnostics in either machine format. Add golden and adversarial escaping tests. Run the STEP 6 verification commands and report evidence plus changed files.
```

## Prompt 7 — End-to-end CLI composition

```text
Implement STEP 7 from IMPLEMENTATION_PLAN.md only. Compose input, parser, aggregator, and the selected renderer in cli.py. Validate mutually exclusive --json/--csv, --top 1..100, positive --max-cardinality, and stdin-at-most-once. Keep machine output on stdout and diagnostics on stderr. Map complete success to 0, unexpected internal/rendering failure to 1, usage failure to 2, input/data or zero-valid failure to 3, and unique-cardinality exhaustion to 4. Suppress broken-pipe tracebacks. Add subprocess/Click tests proving every code 0/1/2/3/4 and no partial report on 4. Run the STEP 7 verification commands and report evidence plus changed files.
```

## Prompt 8 — Performance gate

```text
Implement STEP 8 from IMPLEMENTATION_PLAN.md only. Create a deterministic representative 1 GiB benchmark-log generator and a separately marked end-to-end benchmark. Measure the installed CLI on a documented Python 3.11 laptop, including command, fixture recipe, cache condition, elapsed wall time, and peak RSS. The threshold is under 30 seconds. Profile before optimizing; retain exact metrics and exit-4 safety. If the target is missed after evidence-based tuning, invoke the documented kill/re-scope decision rather than changing stack or semantics silently. Run the STEP 8 verification commands and report the evidence plus changed files.
```

## Prompt 9 — Release acceptance

```text
Implement STEP 9 from IMPLEMENTATION_PLAN.md only. Complete user documentation and build wheel/sdist. Verify a clean Python 3.11 environment can install the wheel, run --help, analyze stdin/file input, and produce text/JSON/CSV. Run lint, type checks, the full suite with branch coverage, package checks, and smoke tests against the exact candidate. Reconcile every observable behavior with PRD.md and PROJECT_ARCHITECTURE.md. The documented exit contract must be 0 success, 1 internal failure, 2 usage failure, 3 input/data failure, and 4 unique-cardinality exhaustion with no partial report. Do not claim P1 gzip support unless separately implemented and accepted. Report command evidence plus changed files.
```

## 3. Review Checklist for Every Step

- Scope matches exactly one plan step and unrelated user work is preserved.
- Tests exercise new behavior, not just implementation details.
- No raw log collection, network call, persistent state, privilege elevation, or shell interpolation exists.
- Renderer values derive from the same immutable report and cannot alter metric semantics.
- Any failed command is reported as unresolved; narration is not evidence.
- The next step starts only after current checks and state are reconciled.

## 4. Final Acceptance Checklist

- P0 acceptance criteria in `PRD.md` are traceable to passing tests.
- The reference 1 GB run is below 30 seconds with recorded peak RSS.
- `0/1/2/3/4` are exercised end to end, especially exit 4 at the exact cardinality boundary.
- JSON schema v1, CSV header/order, and stdout/stderr separation are pinned.
- Wheel/sdist and a clean wheel install pass.
- Documentation and `--help` describe only verified behavior.
