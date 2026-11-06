# Implementation Guide: Nginx Lens

Read [CLAUDE.md](CLAUDE.md), [PRD](PRD.md), [architecture](PROJECT_ARCHITECTURE.md) and [implementation plan](IMPLEMENTATION_PLAN.md) before implementation. This guide contains future prompts; no product code or product tests were produced in the blueprint session.

## Fixed Contract
Use Python 3.11, Click, Rich and dataclasses, installable with pip. One process, local input, no database or HTTP API. Preserve exits 0/1/2/3/4: 0 success, 1 I/O/internal failure, 2 invalid usage, 3 nonempty input with zero valid requests, 4 unique-cardinality exhaustion.

On unique-cardinality exhaustion, fail with code 4 and no partial report; never substitute approximation.

Hourly percentages use `100 × hourly_request_count / total_valid_requests`. UA share uses `100 × unique_user_agents / total_valid_requests`, excluding absent UA from numerator only. Architecture defines all remaining details and output schema. Update the specification before changing behavior.

## Step Prompts
1. “Implement plan step 1 only: create pyproject metadata, package models/errors, pytest scaffold and deterministic benchmark generator. Declare pytest-cov/build as development dependencies. Verify editable installation and model tests. Record evidence; do not publish.”
2. “Implement step 2: bounded combined reader/parser in reader.py and parser.py. Add tests for escapes, invalid UTF-8, IPv6, UTC rollover, oversized records and final line without newline. Run the reader/parser suite and report actual results.”
3. “Implement step 3: exact counters, distinct UAs, cap preflight and deterministic top-10 in aggregate.py. Test denominators and ties using the PRD fixture. Add aggregate benchmark mode; measure before optimizing. Run aggregate tests.”
4. “Implement step 4: Click entry point, file/stdin ownership and full 0/1/2/3/4 failure mapping. Add test_cli.py including option conflicts and cap failure. Preserve stderr diagnostics and no stdout report on read/aggregate failure. Run CLI tests.”
5. “Implement step 5: Rich terminal output in render.py, literal field handling and color controls. Add text tests for TTY, redirection, NO_COLOR and malicious terminal content. Run text tests and sample command.”
6. “Implement step 6: schema-v1 JSON/CSV writers exactly as architecture specifies. Add golden exports and roundtrip CSV tests. Verify format parity and no ANSI. Run export tests.”
7. “Implement step 7: subprocess acceptance and all exit statuses, cap boundaries, empty/all-invalid input and write failures. Run the full suite and branch coverage; fix failures before proceeding. Do not mark done from test code alone.”
8. “Implement step 8: measure actual CLI across output modes on the declared 1 GB fixture. Record three runs, RSS, fixture cardinalities and laptop details. Run suite, build wheel and smoke-test clean installation. Report missed thresholds honestly. Update documents and session memory; do not push, publish or deploy.”

## Verification and Recovery
Use each step's exact file list and verification commands from IMPLEMENTATION_PLAN.md. On regression, retain the failing fixture, fix the implementation and rerun the affected suite then the full suite. A local build is not a publication. The independent architecture review belongs to the external harness and has not run in this session. Keep implementation steps pending until their tests actually pass.
