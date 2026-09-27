# Claude Code Implementation Guide: Nginx Stream Analyzer

## 1. How to Use This Guide

Execute one prompt at a time in the order shown. Keep WIP=1, inspect the repository before editing, and stop when a step's verification fails. The durable specifications are `PRD.md`, `PROJECT_ARCHITECTURE.md`, and `IMPLEMENTATION_PLAN.md`; update those first if behavior changes. Do not add a database, API, server, authentication, cloud resources, Docker, or Kubernetes.

Every implementation session must preserve this exact exit contract: `0` success, `1` operational failure, `2` usage/option error, `3` malformed log input, and `4` unique-cardinality exhaustion. The lowercase phrase `unique-cardinality exhaustion` is the canonical meaning of code 4.

## 2. Step Prompts

### Prompt 1 — Package and CLI Contract

> Read `PROJECT_ARCHITECTURE.md` sections 3, 7, and 9 plus `IMPLEMENTATION_PLAN.md` Step 1. Implement only Step 1: `pyproject.toml`, package initialization, Click skeleton, and focused CLI contract tests. Use Python 3.11, Click, Rich, dataclasses, and a `src` layout. Do not implement parsing or reports yet. Run the exact Step 1 verification commands and report changed files plus real results.

### Prompt 2 — Parser

> Read `PROJECT_ARCHITECTURE.md` sections 4–5, `PRD.md` FR-02, and `IMPLEMENTATION_PLAN.md` Step 2. Implement the combined-log parser and immutable models with fixtures/tests for IPv4, IPv6, escaping, timestamps, statuses, Unicode, and malformed lines. Do not aggregate or render. Treat log text as untrusted data. Run the Step 2 verification commands and fix failures before stopping.

### Prompt 3 — Streaming Inputs

> Read `IMPLEMENTATION_PLAN.md` Step 3 and the architecture error flow. Implement path/stdin iteration, UTF-8 replacement behavior, stream ownership, malformed skip/count, and `--fail-fast`. Preserve stdout for future reports and stderr for diagnostics. Map operational failures to 1 and malformed input to 3; do not implement code 4 in this step. Run all Step 3 tests and record results.

### Prompt 4 — Core Metrics

> Read `PRD.md` P0 acceptance criteria and `IMPLEMENTATION_PLAN.md` Step 4. Implement one-pass aggregation for top-10 IPs, top-10 request targets with statuses 400–599, and all 24 hour buckets. Use deterministic descending-count/ascending-key ties. Calculate each hour with the literal rule `100 × hourly_request_count / total_valid_requests` and return zeros for empty valid input. Add focused tests and run Step 4 verification.

### Prompt 5 — User-Agent Cardinality Guard

> Read the architecture data model, CLI exit codes, and `IMPLEMENTATION_PLAN.md` Step 5. Add exact unique User-Agent count/share, enforce `--max-unique-user-agents`, and map only limit exhaustion to exit 4. Never approximate silently and never return a partial report after exhaustion. Add boundary and high-cardinality tests proving 4 remains distinct from 0/1/2/3. Run Step 5 verification.

### Prompt 6 — Renderers

> Read the full `PROJECT_ARCHITECTURE.md` CLI Interface and `IMPLEMENTATION_PLAN.md` Step 6. Implement Rich terminal, JSON, and normalized CSV renderers exactly as specified. Escape log-derived Rich content; use standard JSON and CSV writers. Machine formats must have stable ordering and no ANSI escapes. Add output contract tests and execute every Step 6 verification command.

### Prompt 7 — Verification and Performance

> Read `PRD.md` release criteria and `IMPLEMENTATION_PLAN.md` Step 7. Add end-to-end, exit-code, known-answer, and opt-in performance tests plus a reproducible benchmark generator. Verify codes 0/1/2/3/4 and precedence. Generate the 1 GB fixture only outside the repository. Measure on named hardware; profile before optimizing. Do not claim the 30-second target without actual timing and peak-memory evidence.

### Prompt 8 — Release Candidate

> Read `STRATEGIC_PLAN.md` Definition of Done, `README.md`, and `IMPLEMENTATION_PLAN.md` Step 8. Finish only packaging and user documentation, choose the license only if the maintainer has confirmed it, build distributions, run the full suite, and install/smoke-test the wheel in a fresh virtual environment. Do not publish or create remote resources. Report exact failures honestly and leave the handoff with a single next action if blocked.

## 3. Review Checklist for Every Step

- Scope matches exactly one implementation-plan step.
- No raw request lines or per-request records remain retained after aggregation.
- Log-derived strings are never interpreted as markup, code, shell, or paths.
- Tests cover a failure path as well as the happy path.
- Machine output stays on stdout and diagnostics stay on stderr.
- Exit statuses remain `0/1/2/3/4` with code 4 reserved for exact User-Agent limit exhaustion.
- Documentation changes precede intentional behavior changes.
- Commands were actually run; unverified claims are labeled unverified.

## 4. Final Acceptance Prompt

> Compare the implementation with every P0 criterion in `PRD.md` and every contract in `PROJECT_ARCHITECTURE.md`. Do not change product scope. Run the full suite, output-schema checks, clean-wheel smoke tests, and the opt-in 1 GB benchmark on documented hardware. Produce a gap list with file/line references and real command evidence. Do not claim independent or adversarial review unless a separate reviewer actually ran.

