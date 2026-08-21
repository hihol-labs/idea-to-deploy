# Claude Code Implementation Guide: nginx-stream-report

## Purpose and Operating Contract

Use these prompts one at a time in a future implementation session. Start a new prompt only after the prior step's verification is recorded. Read `PRD.md`, `PROJECT_ARCHITECTURE.md`, and the matching `IMPLEMENTATION_PLAN.md` step before editing. Preserve WIP=1 and update the specification first if behavior must change.

Every prompt is bound to the complete exit-code contract: **0 = successful complete report; 1 = operational I/O/output failure; 2 = usage or option error; 3 = data-quality failure or zero valid requests; 4 = unique-cardinality exhaustion.** Never omit, remap, or collapse code 4. No nonzero path may emit a partial machine-readable report.

Do not add authentication, a database, an HTTP API/server, cloud services, Docker, or Kubernetes. The architecture remains one local Python 3.11 process with stateless streaming.

## Prompt 1: Package and CLI Contract

> Implement Step 1 of `IMPLEMENTATION_PLAN.md`. Create only the package metadata, import/version surface, Click command boundary, and contract tests named there. Use Python 3.11, Click, Rich, and dataclasses. Encode mutually exclusive `--json`/`--csv`, stdin-by-default, `--strict`, `--no-color`, and the positive `--max-unique-user-agents` option with default 1000000. Preserve exits 0/1/2/3/4, with Click usage failures at 2 and unique-cardinality exhaustion reserved for 4. Do not implement analytics early. Run every Step 1 verification command and record results.

## Prompt 2: Models and Failure Types

> Implement Step 2 of `IMPLEMENTATION_PLAN.md`. Add the exact dataclasses and typed error categories from `PROJECT_ARCHITECTURE.md`; do not add persistence or framework models. Create small reviewed combined-format fixtures and CLI seam tests for all exits 0/1/2/3/4. Code 4 must mean unique-cardinality exhaustion only. Keep raw log contents out of exception messages. Run Step 2 verification and report changed files plus evidence.

## Prompt 3: Combined-Log Parser

> Implement Step 3 of `IMPLEMENTATION_PLAN.md` against PRD FR-1. Parse conventional nginx combined format with one compiled grammar, correct timestamp offset handling, request-target extraction, and quoted-field escapes. A malformed field invalidates the whole line; never partially count it. Treat log content as data, not Rich markup or shell text. Add the named boundary tests and reach at least 90% branch coverage for the parser. Do not change output schemas or exit mappings. Run Step 3 verification.

## Prompt 4: Streaming Aggregation

> Implement Step 4 of `IMPLEMENTATION_PLAN.md`. Process entries one at a time; do not retain them. Produce deterministic exact top-10 IPs and error targets, all 24 hourly buckets, and User-Agent diversity. Hourly percentage must be exactly `100 × hourly_request_count / total_valid_requests`, rounded to two decimals only at report projection. User-Agent share is `100 × unique_user_agents / total_valid_requests`. Check the unique limit before inserting a new value; raise the dedicated failure that the CLI maps to exit 4, emit no partial report, and never remap it to 1 or 3. Run Step 4 verification including branch coverage.

## Prompt 5: Three Renderers

> Implement Step 5 of `IMPLEMENTATION_PLAN.md`. Render the same completed report as default Rich terminal text, one JSON object, or the fixed CSV schema in `PROJECT_ARCHITECTURE.md`. Machine modes must contain no ANSI and end correctly; diagnostics never go to stdout. Disable color for non-TTY output, `NO_COLOR`, or `--no-color`. Escape untrusted values so they cannot become Rich markup or terminal controls. Add semantic and snapshot tests and run Step 5 verification. Do not alter exits 0/1/2/3/4.

## Prompt 6: End-to-End CLI

> Implement Step 6 of `IMPLEMENTATION_PLAN.md`. Compose input ownership, parsing, aggregation, and rendering. Support multiple paths as one dataset and `-` at most once; do not close stdin. Default mode warns and succeeds when some lines are invalid, strict mode exits 3 on the first invalid line, and zero valid requests exits 3. Map missing/unreadable input and output failure to 1, usage to 2, and unique-cardinality exhaustion to 4. Ensure every nonzero path emits no complete/partial report and no traceback for expected failures. Add end-to-end tests for the exact 0/1/2/3/4 contract and run Step 6 verification.

## Prompt 7: Performance Gate

> Implement Step 7 of `IMPLEMENTATION_PLAN.md`. Add the deterministic synthetic benchmark-log generator, opt-in performance tests, ignored `.bench/` output, and `docs/PERFORMANCE.md`. Measure a representative 1 GB uncompressed combined log on the documented Python 3.11 laptop environment. Record wall time, peak RSS, input generation parameters, and cache condition. The acceptance target is under 30 seconds. If it fails, profile before changing code and preserve exact metrics and exits 0/1/2/3/4; never hide cardinality exhaustion or replace the metric with approximation. Run and record all Step 7 commands.

## Prompt 8: Release Candidate

> Implement Step 8 of `IMPLEMENTATION_PLAN.md`. Reconcile README examples with actual help/output, add license and changelog, run the full suite with coverage, build wheel/sdist, validate package metadata, and install the wheel into a clean Python 3.11 virtual environment. Exercise terminal help, JSON, and CSV golden flows. Confirm the shipped contract is 0 success, 1 operational failure, 2 usage error, 3 data-quality/no-valid-input failure, and 4 unique-cardinality exhaustion. Do not publish or create a remote release. Record exact evidence and leave the Idea to Deploy state handoff-ready.

## Review Checklist for Every Prompt

- Scope matches only the active `IMPLEMENTATION_PLAN.md` step.
- Tests fail for the missing behavior before implementation where practical, then pass afterward.
- No entire-file buffering or retained parsed-entry list exists.
- No database, network listener, authentication, telemetry, or remote write exists.
- Terminal/JSON/CSV derive from the same report semantics.
- The complete `0/1/2/3/4` contract is preserved and tested; code 4 remains unique-cardinality exhaustion.
- Commands were actually run and their current results recorded.
- At the end of each session or meaningful block of work, save context through `/session-save`.
