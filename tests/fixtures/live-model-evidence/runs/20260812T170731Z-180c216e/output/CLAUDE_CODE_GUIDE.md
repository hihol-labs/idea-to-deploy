# Claude Code Implementation Guide: Nginx Stream Insights

Use this guide after the blueprint is accepted. It does not authorize implementation during blueprint generation. Execute one prompt at a time, keep WIP=1, and verify before continuing.

## Non-Negotiable Contract

- Python 3.11, Click, Rich, and dataclasses; pip-installable.
- Single-process stateless streaming; no database, HTTP API, auth, server, cloud, or Kubernetes.
- Hourly percentage is exactly `100 × hourly_request_count / total_valid_requests`.
- Public exit codes are always: `0` success, `1` internal/runtime failure, `2` CLI usage error, `3` input/data error, `4` unique-cardinality exhaustion. Never omit, reuse, or remap code 4.
- Structured data goes to stdout; diagnostics go to stderr.
- Specifications are source: change `PRD.md` and `PROJECT_ARCHITECTURE.md` before changing a public behavior.

## Prompt 1 — Freeze Contracts and Fixtures

> Read `PRD.md`, `PROJECT_ARCHITECTURE.md`, and Step 1 of `IMPLEMENTATION_PLAN.md`. Create only the synthetic fixtures, golden JSON/CSV snapshots, and contract tests named there. Encode all four metrics, deterministic ties, 24 hours, strict/permissive input, and exit codes `0/1/2/3/4`, where 4 means unique-cardinality exhaustion. Run the specified test command and report actual evidence. Do not implement product logic merely to force green; this step establishes executable expectations.

Expected evidence: test collection succeeds and failures are attributable to missing implementation, with golden artifacts reviewed against the specs.

## Prompt 2 — Package Skeleton

> Implement Step 2 of `IMPLEMENTATION_PLAN.md` only. Create the Python 3.11 `src/` package, build metadata, dependencies, and console entry point. Keep analytics unimplemented. Ensure Click owns usage failures as exit 2 and reserve 0/1/3/4 for success, internal/runtime, input/data, and unique-cardinality exhaustion. Run build and packaging smoke tests. Do not add services, persistence, Docker, or network behavior.

Expected evidence: wheel/sdist builds and `--help`/`--version` work from the package.

## Prompt 3 — Parser and Domain Models

> Implement Step 3 only. Add frozen/slot dataclasses and a compiled parser for the explicitly supported nginx combined format. Keep file I/O out of the parser. Add typed domain errors that allow the CLI boundary to preserve `0` success, `1` internal/runtime, `2` usage, `3` input/data, and `4` unique-cardinality exhaustion. Do not echo full sensitive log lines in errors. Run parser tests and lint; show evidence.

Expected evidence: valid variants parse, malformed/status/timestamp cases fail deterministically, and no product output formatting enters the parser.

## Prompt 4 — Streaming Aggregation

> Implement Step 4 only. Consume an iterator once and produce the immutable snapshot from `PROJECT_ARCHITECTURE.md`. Do not retain raw lines or parsed records. Implement top-10 deterministic ties, the 400–599 URL filter, all 24 hours, `100 × hourly_request_count / total_valid_requests`, and exact User-Agent share. Enforce the exact-cardinality safety limit with exit-path code 4; retain 0/1/2/3 meanings. Run aggregate tests and include measured evidence.

Expected evidence: metric fixtures pass, cardinality failure is explicit, and inspection shows only aggregate state persists.

## Prompt 5 — Input and Error Boundary

> Implement Step 5 only. Wire sequential file/stdin input, strict UTF-8, permissive malformed-line accounting, `--strict`, and zero-valid-input behavior. Centralize exception-to-exit mapping: 0 success, 1 internal/runtime, 2 usage, 3 input/data, 4 unique-cardinality exhaustion. Preserve caller-owned stdin and do not shell-evaluate paths. Run the input tests and report stdout, stderr, and exit evidence.

Expected evidence: file/stdin and every error class produce the specified stream and exit behavior.

## Prompt 6 — Rich Terminal Renderer

> Implement Step 6 only. Render the existing snapshot as four clear Rich sections plus totals. Do no calculation in the renderer. Respect TTY behavior and `--no-color`; keep structured modes color-free. Test fixed snapshots. Confirm the renderer cannot alter exit meanings `0/1/2/3/4`, especially code 4 for unique-cardinality exhaustion.

Expected evidence: golden/plain output tests and color control tests pass.

## Prompt 7 — JSON Renderer

> Implement Step 7 only. Emit exactly one deterministic JSON object with the architecture's `schema_version` and sections. Keep warnings/errors on stderr. Add schema, ordering, type, and CLI integration tests across exits `0/1/2/3/4`; code 4 remains unique-cardinality exhaustion. Validate real output with `python -m json.tool`.

Expected evidence: golden JSON and parsing checks pass without terminal markup.

## Prompt 8 — CSV Renderer

> Implement Step 8 only. Use Python's CSV writer and the exact `report,rank,key,count,percentage` schema. Emit deterministic ranking, hourly, and User-Agent rows. Make `--csv` and `--json` conflict through Click with exit 2. Test escaping and all exits `0/1/2/3/4`, where 4 means unique-cardinality exhaustion.

Expected evidence: golden CSV reparses with the standard library and stdout remains clean.

## Prompt 9 — End-to-End Verification

> Implement no new features. Execute Step 9 as a verification and defect-fix loop. Cover terminal/JSON/CSV, file/stdin, malformed/empty/unreadable input, option conflict, unexpected failure, and cardinality exhaustion. Demonstrate the complete exit mapping `0/1/2/3/4`, with 4 uniquely assigned to unique-cardinality exhaustion. Run lint, tests with coverage, package build, and a clean install smoke test. Fix only spec deviations, rerunning evidence after each candidate change.

Expected evidence: current commands pass and parser/aggregation coverage is at least 90%.

## Prompt 10 — Performance and Release Gate

> Execute Step 10. Add only the deterministic synthetic benchmark generator, runner, and benchmark documentation. Measure a 1 GB run on the reference Python 3.11 laptop including elapsed time and peak RSS. Do not fabricate results and do not weaken exactness or exit behavior for speed. Recheck `0/1/2/3/4`; code 4 must remain unique-cardinality exhaustion. If the run exceeds 30 seconds, profile first and return a measured optimization proposal instead of claiming completion.

Expected evidence: recorded environment and real benchmark result, bounded-memory analysis, full suite, build, and clean install.

## Final Handoff Checklist

- [ ] P0 and P1 acceptance criteria in `PRD.md` pass.
- [ ] All `IMPLEMENTATION_PLAN.md` verification commands have current evidence.
- [ ] The public `0/1/2/3/4` contract is tested; 4 means unique-cardinality exhaustion.
- [ ] The 1 GB run is below 30 seconds on the named reference laptop.
- [ ] No database, HTTP API, authentication, daemon, cloud, or Kubernetes artifacts were introduced.
- [ ] README commands match a clean installed wheel.
- [ ] At the end of every session or meaningful work block, preserve context with `/session-save`.
