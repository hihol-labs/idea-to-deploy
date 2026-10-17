# Claude Code Implementation Guide: nginx-log-top

This guide turns `IMPLEMENTATION_PLAN.md` into bounded implementation prompts. Run one prompt at a time, review the diff, execute its listed checks, and update the status table in `CLAUDE.md`. Do not add a database, HTTP API, authentication, server, cloud service, Docker, or Kubernetes.

## Invariant Contract for Every Prompt

- Python 3.11, Click, Rich, dataclasses, and pip packaging only.
- Keep processing single-pass and do not retain raw records.
- Preserve deterministic ordering and keep diagnostics on stderr.
- Preserve the complete exit-code contract `0/1/2/3/4`: 0 success, 1 internal error, 2 usage/I/O error, 3 no valid records, 4 unique-cardinality exhaustion.
- Add or update tests with every behavior change and run the targeted tests before stopping.
- Do not implement P2 features unless a later task explicitly changes the PRD.

## Prompt 1 — Package Skeleton

Implement Step 1 from `IMPLEMENTATION_PLAN.md`. Read `PROJECT_ARCHITECTURE.md` first. Create only the package/CLI skeleton, project metadata, and help/version tests named in the step. Make the package installable on Python 3.11, expose `nginx-log-top`, and enforce `--json`/`--csv` mutual exclusion through Click. Run the three Step 1 verification commands and report their outcomes plus changed files.

## Prompt 2 — Models and Exit Codes

Implement Step 2. Define the exact dataclasses from the architecture and typed expected failures. Wire the CLI so user-caused failures never print tracebacks and unexpected exceptions map to code 1. Add subprocess tests proving all codes `0/1/2/3/4`; create minimal stubs or fixtures only where needed for the tests, without implementing later metrics early. Run the Step 2 checks.

## Prompt 3 — Streaming Parser

Implement Step 3. Parse nginx combined records and the common subset using a bounded, linear hot path. Read stdin or paths incrementally, use UTF-8 replacement for undecodable bytes, and count malformed lines without printing whole sensitive records. Cover quoted fields, query strings, timestamps, malformed bytes, and status validation. Run only the Step 3 checks plus any directly affected earlier tests.

## Prompt 4 — Aggregation

Implement Step 4. Update counters once per valid record, compute deterministic top-ten lists, all 24 hourly buckets, and exact User-Agent share. Use the literal hourly definition `100 × hourly_request_count / total_valid_requests`. Enforce the cap before inserting a new distinct User-Agent; on unique-cardinality exhaustion produce domain error code 4 and never emit an approximate or partial report. Run aggregation tests and coverage.

## Prompt 5 — Rich Text

Implement Step 5. Render summary and all four required views with Rich. Respect `--color=auto|always|never`, escape untrusted values, and ensure no-color output has no ANSI escapes. Rendering must consume only the `Report` model. Add snapshots or explicit assertions and run the Step 5 checks.

## Prompt 6 — JSON and CSV

Implement Step 6. JSON must carry `schema_version: 1`; CSV must use `section,rank,key,count,percentage`. Keep ordering deterministic and stdout free of ANSI and diagnostics. Add golden files and verify all expected errors preserve `0/1/2/3/4`, particularly code 4. Run the listed renderer, JSON parse, and exit-code checks.

## Prompt 7 — Follow Mode

Implement Step 7 without changing static-input semantics. Require exactly one regular file, wait without busy-spinning, consume only complete appended lines, and finalize the report on Ctrl-C. Treat invalid combinations as exit 2 and a normal downstream broken pipe as quiet success. Add deterministic tests that do not depend on long sleeps; run Step 7 checks.

## Prompt 8 — Benchmark

Implement Step 8. Generate the 1 GB fixture deterministically and outside version control, then record wall-clock time and peak RSS with hardware and Python metadata. Run a baseline before optimizing. If it exceeds 30 seconds, profile and make only measured hot-path changes while holding golden outputs fixed. Do not claim the target without recorded local evidence.

## Prompt 9 — Release Readiness

Implement Step 9. Finish user documentation and packaging metadata, then run the full suite, coverage gate, build, clean wheel installation, CLI smoke tests, and benchmark review. Search the documents and implementation for the full `0/1/2/3/4` mapping and correct discrepancies. Do not publish, push, or create a release; prepare local artifacts only and report any unmet criterion.

## Final Review Checklist

- [ ] `pytest` passes and package coverage is at least 90%.
- [ ] Text, JSON, and CSV report the same values.
- [ ] Machine outputs contain neither ANSI sequences nor diagnostics.
- [ ] Exact cardinality never degrades silently.
- [ ] The 1 GB benchmark evidence is reproducible and under 30 seconds.
- [ ] pip installation and the console entry point work in a clean Python 3.11 environment.

