# Claude Code Implementation Guide: Nginx Lens

Read [CLAUDE.md](CLAUDE.md), [PRD](PRD.md), [architecture](PROJECT_ARCHITECTURE.md) and [implementation plan](IMPLEMENTATION_PLAN.md) first. This is a future implementation guide; no product code has been written or tested in the blueprint session. Specs govern behavior; update them before changing behavior.

## Invariants for Every Prompt
Python 3.11, Click, Rich, dataclasses, pip packaging; single-process stateless streaming. No database, HTTP API, auth, server, cloud or Kubernetes. Exact metrics with bounded distinct state, no approximations. Hourly percentage is `100 × hourly_request_count / total_valid_requests`. UTC hour-of-day, denominator excludes malformed lines. Preserve exact top-10 tie ordering and the architecture's machine-output schema.

Exit contract: 0 success; 1 I/O/runtime error; 2 CLI usage error; 3 nonempty all-invalid input; 4 unique-cardinality exhaustion.
The literal unique-cardinality exhaustion describes exceeding the configured aggregate distinct-entry budget; it must never become partial success.

## Step Prompts
### 1. Packaging
“Implement plan step 1 in pyproject.toml, src/nginx_lens/__init__.py and cli.py. Add tests/test_cli.py for help/version, flag conflicts and usage errors. Run its verification commands and report actual results. Keep the 0/1/2/3/4 contract.”

### 2. Parsing
“Implement step 2 in reader.py, parser.py and models.py with the specified combined format and bounded physical-line reader. Add escaped-field, Unicode, malformed, UTC-offset and overlong-line tests. Run parser/reader tests. Never retain the entire stream.”

### 3. Rankings and Limits
“Implement step 3 in aggregate.py and errors.py. Exact IP and 400–599 URL counts; deterministic count/key sorting; atomic admission against the sum of three distinct namespaces. Add cap-boundary and tie fixtures, run tests, and preserve exhaustion exit 4.”

### 4. Percentages
“Implement step 4. Always emit 24 UTC hour buckets. Test two of four requests gives 50%, empty denominators give zero, duplicate and sentinel UAs obey exact equality, and timezone conversion crosses dates correctly. Run metric and aggregation tests.”

### 5. Rendering
“Implement step 5 in render.py. Freeze schema-v1 JSON and normalized CSV golden files. Test numeric rounding, CSV quoting, no ANSI in machine output, TTY/NO_COLOR and untrusted terminal strings. Run render tests.”

### 6. Integration
“Implement step 6, wiring file/stdin to complete-only report rendering. Use stderr for diagnostics without raw input. Run CLI integration tests for 0 success, 1 I/O/runtime, 2 usage, 3 all-invalid and 4 cardinality exhaustion, including broken pipe and input failure.”

### 7. Qualification
“Implement step 7's deterministic benchmark generator and measurement runner. Verify fixture counts, benchmark 1,000,000,000 bytes three times outside generation/install time, record hardware/software, cache conditions and RSS in docs/BENCHMARK.md. Build/install a wheel locally. Report failures honestly; do not claim the target from estimates.”

### 8. Handoff
“Complete step 8. Run the complete suite with branch coverage >=85%, smoke-test the installed CLI in each format, review security handling, reconcile docs and statuses, save context through /session-save. Keep publication and external actions pending explicit confirmation.”

## Working Protocol
One step at a time; test new behavior and run checks before commits. Preserve WIP=1. Avoid real sensitive logs in fixtures and output. If a check fails, record the failure and next corrective step; do not mark implementation complete. [README](README.md) provides the intended user quick start. Adversarial architecture review for this blueprint is external and is not represented as an in-session review.
