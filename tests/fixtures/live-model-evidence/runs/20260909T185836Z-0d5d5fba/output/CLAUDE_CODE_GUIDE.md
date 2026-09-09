# Claude Code Implementation Guide: Nginx Pulse

This guide converts the approved blueprint into bounded implementation prompts. Run one prompt at a time in order. Before each prompt, read `CLAUDE.md`, `PRD.md`, `PROJECT_ARCHITECTURE.md`, and the matching section of `IMPLEMENTATION_PLAN.md`. Do not advance while verification is red.

## Global Guardrails

- Keep WIP at one implementation step and touch only the files listed for that step unless a prerequisite defect is documented.
- Keep the product one local Python 3.11 process using Click, Rich, and dataclasses.
- Do not add authentication, a database, HTTP API, server, cloud integration, Docker, or Kubernetes.
- Preserve streaming input: never retain raw log records or the entire file.
- Preserve the complete `0/1/2/3/4` contract: 0 complete success; 1 input/output or internal runtime failure; 2 usage error; 3 completed partial analysis after malformed lines; 4 unique-cardinality exhaustion.
- The lowercase failure label for code 4 is exactly `unique-cardinality exhaustion`.
- Keep stdout for normal results, stderr for diagnostics, and keep JSON/CSV free of ANSI output.
- Treat `PRD.md` and `PROJECT_ARCHITECTURE.md` as specifications. Change them first if approved behavior changes.
- End each step by running its exact checks and recording the evidence; do not infer passing results.

## Prompt 1: Package and CLI Contract Skeleton

```text
Implement STEP 1 from IMPLEMENTATION_PLAN.md only. Create pyproject.toml and the src/nginx_pulse package entry points, then define the Click command signature exactly as PROJECT_ARCHITECTURE.md documents. Do not implement parsing or metrics yet. Add subprocess-focused tests for help, version, invalid option combinations, positive cardinality validation, stdin selection, and file selection. Run every STEP 1 verification command and report changed files plus actual results. Stop if the package cannot install on Python 3.11.
```

## Prompt 2: Domain Models and Parser

```text
Implement STEP 2 from IMPLEMENTATION_PLAN.md only. Add the exact dataclasses and combined-log parser described in PROJECT_ARCHITECTURE.md sections 5 and 6. Cover IPv4, IPv6, escaped quoted fields, placeholders, timestamp offsets, status boundaries, malformed records, and a final line without newline. Do not add aggregation or rendering. Run parser tests and mypy exactly as specified; report evidence and unresolved format limitations.
```

## Prompt 3: Streaming Aggregation

```text
Implement STEP 3 from IMPLEMENTATION_PLAN.md only. Consume parser outcomes sequentially and produce the one immutable AnalysisResult. Implement deterministic top-10 sorting, status 400-599 URL filtering, all 24 hour buckets, the literal percentage formula from the PRD, and exact User-Agent cardinality with a pre-mutation ceiling check. Do not retain raw lines or records. Run the focused suite and branch-coverage check; include evidence that empty input and the ceiling boundary behave exactly as specified.
```

## Prompt 4: JSON and CSV

```text
Implement STEP 4 from IMPLEMENTATION_PLAN.md only. Build JSON schema version 1 and the documented long-form CSV from the shared AnalysisResult. Keep ordering deterministic and machine-readable stdout ANSI-free. Use standard serializers for escaping, create golden fixtures, and wire only --json/--csv. Run both focused suites and the JSON parse smoke test, then report their actual outputs at a concise level.
```

## Prompt 5: Rich Text

```text
Implement STEP 5 from IMPLEMENTATION_PLAN.md only. Create the Rich renderer with every required section, terminal-aware color, and --color/--no-color overrides. Do not alter any metric. Add golden no-color coverage and assertions for forced/automatic color behavior. Run the focused tests and redirected smoke command. Report whether redirected output contains any escape bytes.
```

## Prompt 6: Exit and Stream Semantics

```text
Implement STEP 6 from IMPLEMENTATION_PLAN.md only. Complete the exception and outcome mapping in the Click boundary. Add real subprocess tests for every code in 0/1/2/3/4 and for stdout/stderr separation. Code 3 must render a complete valid-record report; code 4 must mean unique-cardinality exhaustion and emit no normal report. Respect the documented precedence. Run both integration suites and the malformed-input smoke command; record actual return codes.
```

## Prompt 7: Performance Evidence

```text
Implement STEP 7 from IMPLEMENTATION_PLAN.md only. Add deterministic fixture generation, a benchmark runner, and a CI-safe streaming/resource test. Generate a representative 1 GB combined log, bind its digest in benchmark output, and measure wall time plus peak resident memory with output redirected. Profile before modifying the hot path. Preserve every correctness test and exact-cardinality behavior. Run all STEP 7 commands and report the machine/runtime metadata and pass/fail against 30 seconds.
```

## Prompt 8: Release Readiness

```text
Implement STEP 8 from IMPLEMENTATION_PLAN.md only. Reconcile README.md with observed behavior, add license and changelog, and verify the built wheel in isolation. Run Ruff, mypy, the complete branch-coverage suite, build, and package metadata checks exactly as listed. Confirm all P0 acceptance criteria and all 0/1/2/3/4 exit cases from real evidence. Do not publish a package or create external resources. Report any unmet gate as a blocker rather than declaring release readiness.
```

## Final Handoff Checklist

- [ ] P0 user stories and edge cases in `PRD.md` have executable coverage.
- [ ] Text, JSON, and CSV use one result model and agree on metric values.
- [ ] The performance claim has current reference-machine evidence.
- [ ] The isolated wheel invokes as both `nginx-pulse` and `python -m nginx_pulse`.
- [ ] Documentation matches observed behavior and no excluded infrastructure exists.
- [ ] Session state and the next action are saved according to `CLAUDE.md`.
