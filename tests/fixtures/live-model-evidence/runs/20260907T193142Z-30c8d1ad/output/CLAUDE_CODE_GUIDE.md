# Claude Code Implementation Guide: Nginx Stream Analytics CLI

## 1. Purpose and Operating Rules

Use this guide after the blueprint is accepted to execute `IMPLEMENTATION_PLAN.md` one step at a time. This document is guidance only; it does not authorize implementation during the blueprint session.

At the start of every implementation session, read `CLAUDE.md`, `PRD.md`, `PROJECT_ARCHITECTURE.md`, `IMPLEMENTATION_PLAN.md`, `.itd/SCOPE_LOCK.md`, and the active `.itd-memory` state. Preserve WIP=1. Update the spec before behavior if a contract must change. Use the repository Verification Loop and accept only a current receipt for the exact candidate.

Non-negotiable constraints:

- Python 3.11, Click, Rich, dataclasses, pip installation.
- Local single-process streaming; no database, HTTP API, auth, server, cloud, Docker runtime, or Kubernetes.
- No raw-record retention and no silent approximation.
- The hourly percentage formula is `100 × hourly_request_count / total_valid_requests`.
- Exit codes are exactly `0/1/2/3/4`: 0 success/help/version; 1 unexpected internal/runtime failure; 2 usage or unreadable input; 3 decode/parse failure; 4 unique-cardinality exhaustion.
- The exact lowercase failure phrase `unique-cardinality exhaustion` denotes code 4 and must remain stable in tests and documentation.

## 2. Session Prompt Template

Prepend this to each step prompt:

```text
Read CLAUDE.md and the current Idea to Deploy state. Work only on the named implementation-plan step and keep WIP=1. Before editing, inspect existing files and preserve user changes. Follow PRD.md and PROJECT_ARCHITECTURE.md as the durable contract. Use apply_patch for edits. Run every verification listed for the step, record evidence, reconcile state, and stop if a contract change is required. Do not begin the next step. Do not claim success without a current exact-candidate adjudication receipt required by the repository contract.
```

## 3. Step-by-Step Prompts

### Prompt 1 — Packaging and CLI surface

```text
Execute IMPLEMENTATION_PLAN.md Step 1 only. Create the Python 3.11 src-layout packaging metadata, dependencies, console script, package initializer, and Click command surface. Do not emit fake analytics. Add packaging tests first, then make them pass. Run the four Step 1 verification commands. Confirm the package supports only the approved local CLI architecture.
```

Expected evidence: build artifacts validate, editable install succeeds, packaging tests pass, and `nginx-stream-analytics --help` exposes the documented arguments.

### Prompt 2 — Models, errors, and fixtures

```text
Execute IMPLEMENTATION_PLAN.md Step 2 only. Implement frozen dataclass models and typed error boundaries, then create minimal manually auditable fixtures. Encode all five exit meanings without remapping: 0 success, 1 internal failure, 2 usage/input-open failure, 3 parse/decode failure, 4 unique-cardinality exhaustion. Add tests proving the mapping. Run the listed pytest and mypy commands.
```

Expected evidence: models/errors tests and type checking pass, and fixture expectations can be checked by hand.

### Prompt 3 — Strict Combined Log parser

```text
Execute IMPLEMENTATION_PLAN.md Step 3 only. Test-drive a strict streaming parser for the documented nginx Combined Log Format. Preserve source timestamp offset, report one-based malformed line numbers, and do not retain raw lines. Cover valid edge cases and decoding/parsing failures. Run the parser suite under both listed TZ settings and show that results do not depend on host timezone.
```

Expected evidence: parser tests pass in both timezones and failure output identifies the correct line without a traceback.

### Prompt 4 — Aggregation and bounds

```text
Execute IMPLEMENTATION_PLAN.md Step 4 only. Test-drive StreamingAggregator and finalize into the immutable report. Compute top IPs, 4xx/5xx URL counts, all 24 hour buckets, and exact User-Agent cardinality in one pass. Hourly percentage must be 100 × hourly_request_count / total_valid_requests. Enforce max-unique independently for IPs, error URLs, and User-Agents and fail before adding the over-limit key. Never return a partial report. Run the listed tests and coverage gate.
```

Expected evidence: deterministic ranking/tie tests, exact percentage tests, empty-input tests, and three distinct cardinality-boundary tests pass.

### Prompt 5 — Terminal, JSON, and CSV

```text
Execute IMPLEMENTATION_PLAN.md Step 5 only. Implement renderer modules over AnalysisReport without reparsing or recomputing domain metrics. Escape or disable Rich markup for untrusted values. Keep JSON schema 1.0 and CSV report,rank,key,count,percentage stable. Add round-trip assertions showing all formats agree. Run renderer tests and coverage.
```

Expected evidence: JSON and CSV parse cleanly, contain no ANSI escapes, all 24 hours exist, and report values agree across formats.

### Prompt 6 — CLI integration and exits

```text
Execute IMPLEMENTATION_PLAN.md Step 6 only. Integrate file/stdin reading, parser, aggregator, and selected renderer in cli.py. Preserve stdout for report data and stderr for diagnostics. Ensure --json and --csv are mutually exclusive and --max-unique is positive. Exercise every code in the complete 0/1/2/3/4 contract, including an injected unexpected failure for 1. A parse or cardinality failure must emit no partial report. Run all listed commands.
```

Expected evidence: file/stdin equivalence, clean pipeline formats, expected stream separation, and subprocess-observed codes 0 through 4.

### Prompt 7 — Performance evidence

```text
Execute IMPLEMENTATION_PLAN.md Step 7 only. Create a deterministic external 1 GB fixture generator and benchmark runner. Record fixture description, size/hash in the benchmark artifact, Python and machine context, wall time, throughput, and peak RSS. Run three measured warm-cache passes plus a cold-cache observation. If the under-30-second target fails, profile and report the measured bottleneck before proposing a change. Do not introduce multiprocessing without changing the architecture spec first.
```

Expected evidence: reproducible benchmark metadata, three measured runs, peak RSS, and a clear pass/fail against 30 seconds on the named laptop.

### Prompt 8 — Release and handoff

```text
Execute IMPLEMENTATION_PLAN.md Step 8 only. Bring README, license, changelog, CI, audits, coverage, types, and wheel installation into alignment with the implemented contract. Run all quality/build/smoke commands. Freeze the exact staged candidate and run the repository machine oracle and risk-tier checker. Revalidate the adjudication receipt before accepting the unit. Do not publish a package or create an external release unless separately authorized.
```

Expected evidence: lint/type/test/coverage pass, distribution checks pass, fresh-wheel smoke tests pass in all formats, audit findings are resolved or explicitly blocking, and state is handoff-ready.

## 4. Contract Regression Checklist

Before closing any implementation step, verify that the change has not introduced:

- a database, HTTP API, auth, daemon, network call, cloud resource, or Kubernetes artifact;
- a second input pass or retained raw records;
- a fraction where a percentage is required;
- nondeterministic ranking ties;
- ANSI/diagnostic contamination in JSON or CSV stdout;
- partial output on code 3 or 4;
- an exit-code omission or remapping from `0/1/2/3/4`.

## 5. Escalation Rules

Stop and update the relevant source specification before implementing any requested change to supported log formats, output schema, percentage meaning, error policy, top-N, timestamp normalization, process model, or exactness. Record the decision in `PROJECT_ARCHITECTURE.md`, acceptance consequences in `PRD.md`, and reordered work in `IMPLEMENTATION_PLAN.md`.

At the end of every session or significant block of work, save context through `/session-save` as required by `CLAUDE.md`.
