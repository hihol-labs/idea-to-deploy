# Claude Code Guide: Nginx Stream Analyzer

## 1. How to Use This Guide

Execute one prompt at a time, in order, and preserve WIP=1. Start each session by reading `CLAUDE.md`, `PRD.md`, `PROJECT_ARCHITECTURE.md`, and the active step in `IMPLEMENTATION_PLAN.md`. Do not expand P0 scope or implement P1/P2 work early. Update the specification before changing a behavioral contract.

Every prompt inherits the complete exit-code contract: `0` success, `1` operational I/O failure, `2` CLI usage/configuration error, `3` input/data failure or zero valid requests, and `4` unique-cardinality exhaustion. The exact lowercase failure label is `unique-cardinality exhaustion`; do not omit, capitalize, or remap it in diagnostics/tests.

After each step, run the named checks, show changed files and evidence, and stop if a check fails. Do not claim completion based on prose. Do not add a database, HTTP API, server, authentication, cloud, Docker runtime requirement, or Kubernetes.

## 2. Step Prompts

### Prompt 1 — Package and CLI skeleton

```text
Implement only Step 1 of IMPLEMENTATION_PLAN.md. Read CLAUDE.md, PRD.md FR-1/FR-6/FR-7, and PROJECT_ARCHITECTURE.md sections 3, 4, and CLI Interface first. Create the Python 3.11 src-layout package, Click console entry point, dependencies/tool configuration, help/version/options, and central error types. Preserve the exact options and 0/1/2/3/4 mapping; do not implement parsing or metrics yet. Add the specified CLI tests, run all Step 1 verification commands, and report files plus command outcomes. Keep WIP=1 and do not proceed to Step 2.
```

### Prompt 2 — Models and parser

```text
Implement only Step 2 of IMPLEMENTATION_PLAN.md. Use immutable dataclasses and a compiled parser for the documented supported nginx combined format. Parse only client IP, timestamp/hour and offset, URL target, status, and User-Agent. Never retain or echo raw malformed lines. Add the exact fixtures and boundary tests named in the plan. Run pytest, Ruff, and mypy commands from Step 2 and stop on failure. Do not aggregate or render yet.
```

### Prompt 3 — Streaming aggregation

```text
Implement only Step 3 of IMPLEMENTATION_PLAN.md against the existing parser contract. Build the one-pass aggregator for top 10 IPs, top 10 URLs with status 400–599, all 24 hourly buckets, and exact nonempty User-Agent cardinality bounded by --ua-limit. Deterministically break ranking ties by key ascending. Calculate hourly percentages with the literal formula 100 × hourly_request_count / total_valid_requests, not an unscaled fraction. User-Agent exhaustion must take exit path 4 and must never silently approximate. Add the named tests and run Step 3 verification only.
```

### Prompt 4 — JSON and CSV

```text
Implement only Step 4 of IMPLEMENTATION_PLAN.md. Add a schema-versioned single JSON object and CSV with the exact columns metric,rank,key,count,percentage,unit. Keep numeric values numeric, deterministic ordering, all 24 hours, and diagnostics off stdout. Add golden fixtures/tests and run every Step 4 verification command. Do not add terminal rendering in this step.
```

### Prompt 5 — Terminal rendering

```text
Implement only Step 5 of IMPLEMENTATION_PLAN.md. Add the Rich terminal report with input counts and all four report sections. Escape untrusted log-derived strings, honor --no-color, and disable color when stdout is not a TTY. Wire renderer selection without changing JSON/CSV schemas. Run the listed tests and manual no-color command; stop after reporting evidence for Step 5.
```

### Prompt 6 — End-to-end process contract

```text
Implement only Step 6 of IMPLEMENTATION_PLAN.md. Complete file/stdin resource ownership, diagnostics, renderer dispatch, malformed-data behavior, and safe broken-pipe handling. Add subprocess/integration coverage that actually observes all five exits: 0 success; 1 I/O; 2 usage/config; 3 data/no valid requests; 4 unique-cardinality exhaustion. Keep stderr/stdout boundaries exact. Run the Step 6 commands and do not continue on any failure.
```

### Prompt 7 — Performance and hardening

```text
Implement only Step 7 of IMPLEMENTATION_PLAN.md. First create the deterministic benchmark generator and security-boundary tests. Generate a 1 GB fixture outside Git, record its checksum and the required hardware/OS/Python/cache metadata, then measure installed-command wall time and peak RSS. Profile before optimizing; preserve all behavior and golden tests. Acceptance is under 30 seconds on the designated laptop. Never execute log content, perform network I/O, or echo raw malformed lines. Run and record all Step 7 checks.
```

### Prompt 8 — Release readiness

```text
Implement only Step 8 of IMPLEMENTATION_PLAN.md. Write the user README, license, final package metadata, and release checklist without expanding scope. Run formatting, lint, types, the full suite with at least 90% src coverage, build/twine checks, and a freshly installed wheel smoke test for file/stdin and terminal/JSON/CSV. Confirm the exact 0/1/2/3/4 contract and attach benchmark evidence. Freeze the staged candidate and follow .itd/VERIFICATION_CONTRACT.json; accept only a current adjudication receipt. Save session context as required by CLAUDE.md.
```

## 3. Cross-Step Review Checklist

- The implementation matches P0 acceptance criteria and no P1/P2 feature slipped in.
- Raw input is streamed once; no database, HTTP API, server, auth, network, cloud, or Kubernetes exists.
- Top lists are deterministic and hourly output contains 24 buckets.
- `100 × hourly_request_count / total_valid_requests` is tested as a percentage.
- Unique User-Agent share uses all valid requests as its denominator and exact nonempty distinct agents as its numerator.
- Exit codes `0/1/2/3/4` are exercised through the installed process boundary; code 4 retains its required meaning.
- JSON/CSV stdout is machine-clean; log-derived terminal text is escaped.
- The 1 GB/<30 s claim has current reproducible evidence rather than an estimate.
- All source and documentation changes are within the active `.itd/SCOPE_LOCK.md`.

## 4. Recovery Prompt

```text
The active implementation step failed verification. Do not start another step or weaken the test. Summarize the failing command and smallest reproducible symptom, inspect only the active step's files and contracts, identify the root cause, and propose the narrowest correction. After the correction, rerun the failed check and then every verification command for the active step. Record failure as recovery, not success, until all evidence is green.
```

## 5. Completion Boundary

Implementation is ready for release consideration only after Step 8 and the external Idea to Deploy verification path accept the exact staged candidate. This guide provides prompts; it is not itself test or review evidence. The external Devil's Advocate architecture review is a separate harness activity and was not run while producing this guide.
