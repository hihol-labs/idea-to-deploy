# Claude Code Guide: Nginx Lens

This implementation guide contains ready-to-use prompts for a future coding session. No product code or runtime verification has been performed during blueprint generation. Read [CLAUDE.md](CLAUDE.md), [PRD](PRD.md), [architecture](PROJECT_ARCHITECTURE.md), and [implementation plan](IMPLEMENTATION_PLAN.md) before executing a prompt. [Strategy](STRATEGIC_PLAN.md) gives priorities and release criteria; [README](README.md) supplies local usage.

## Shared contract for every prompt
Implement only the named step and preserve the exact architecture contract. Python 3.11, Click, Rich, dataclasses, pip, one local process; no auth, database, HTTP API, server, cloud, Kubernetes, or runtime network. Input is finite combined-format logs from one file or stdin. Use synthetic labeled test fixtures and do not expose real records.

Every step must preserve the complete exit-code contract **0/1/2/3/4**:
- 0: successful processing, including empty input, help, and version.
- 1: input/output, interruption, or unexpected processing failure.
- 2: invalid CLI usage.
- 3: nonempty input with zero valid records.
- 4: unique-cardinality exhaustion.

Never remap code 4 to a generic error or return an approximate/partial report. Default shared cap: 250000 distinct entries across IP counts, error URL counts, and User-Agent set. Validate new entries for a whole record before mutation. Read lines with a 65536-byte content limit, draining oversized lines in chunks. Use the logged hour, not UTC; hourly percentage is `100 × hourly_request_count / total_valid_requests`. Unique User-Agent share is `100 × unique_user_agents / requests_with_user_agent`, excluding `-` and empty values from both terms, with unavailable output when the denominator is zero.

Test the change and then run the relevant existing suite. Record actual results; distinguish targets from measurements. Update specs before intentional behavior changes. Do not push, publish, deploy, or delete without explicit human confirmation. At each significant block, use `/session-save` and keep step status accurate. The external harness owns this blueprint's adversarial review; do not manufacture a review verdict or artifact.

## Prompt 1: Package and contracts
> Execute implementation step 1 only. Create pyproject.toml, src/nginx_lens/{__init__,cli,models,errors}.py, tests/test_package.py and a labeled synthetic combined-log fixture. Use a src layout, the nginx-lens console entry point, Click/Rich dependencies, Python 3.11 and the development extra from the plan. Define dataclass fields exactly as architecture specifies. Add help/version checks, install editable locally, and run python -m pytest tests/test_package.py. Record real output and update CLAUDE.md step 1 status only after its checks pass. Apply the shared 0/1/2/3/4 exit contract throughout.

## Prompt 2: Stream parsing
> Execute step 2. Read architecture's input grammar and malformed rules first. Create reader.py and parser.py plus test_reader.py and test_parser.py. Handle escaped quoted fields, IPv4/IPv6, status boundaries, calendar-valid timestamps/offsets, final lines without newline, CRLF, invalid UTF-8 and oversized-line draining. Do not load all lines. Keep malformed outcomes distinct from I/O failures. Run python -m pytest tests/test_reader.py tests/test_parser.py and the existing suite. Apply the shared exit contract 0/1/2/3/4 and record evidence.

## Prompt 3: Metrics and exhaustion
> Execute step 3. Create aggregate.py and test_aggregate.py using exact dictionaries, a 24-entry hour list and an exact nonmissing-agent set. Canonicalize IPs, preserve URL queries, count combined 400–599 error requests, and use deterministic count-descending/key-ascending ranking. Implement the shared cardinality cap and whole-record preflight; test cap equality and overflow, including one record introducing keys to multiple collections. Preserve unique-cardinality exhaustion as exit 4 in the 0/1/2/3/4 contract. Test hand-calculated hourly and User-Agent percentages and missing-agent behavior. Add the small diagnostic benchmark driver, run the step's commands and the existing suite, and report measured results without extrapolating a 1 GB pass.

## Prompt 4: Pipeline exports
> Execute step 4. Implement JSON and normalized CSV in render.py exactly as architecture's CLI Interface specifies, including schema version, all fields, row ordering, empty/null handling, Unicode and quoting. Add independently computed expected.json/expected.csv and tests/test_exports.py; assert exports contain no ANSI and can be decoded by standard-library readers. Run python -m pytest tests/test_exports.py and the existing suite. Retain exit codes 0/1/2/3/4 and prevent warnings from contaminating stdout.

## Prompt 5: Terminal output
> Execute step 5. Add Rich tables for every required metric, count and percentage. Keep colors terminal-aware with NO_COLOR and explicit override semantics. Render untrusted strings without Rich markup evaluation and visibly escape terminal controls. Add tests/test_terminal.py for color, safe labels, empty input and N/A User-Agent share. Run python -m pytest tests/test_terminal.py and the existing suite. Preserve the shared 0/1/2/3/4 contract and machine-output behavior.

## Prompt 6: CLI integration
> Execute step 6. Complete cli.py and tests/test_cli.py: one optional input path, default stdin, mutually exclusive --json/--csv, positive --max-unique and --color choices. Test all exits 0/1/2/3/4, including unique-cardinality exhaustion at 4, mixed malformed success, all-malformed 3, missing/read-failing input 1, invalid usage 2, and empty/help/version 0. Map interruption and broken pipe to 1 without traceback. Emit no report before successful aggregation; describe that write failures may leave bytes on stdout. Run python -m pytest tests/test_cli.py, a JSON fixture smoke command and the existing suite.

## Prompt 7: Acceptance and throughput
> Execute step 7. Add tests/test_acceptance.py and benchmarks/generate.py; finish benchmarks/benchmark.py. Verify PRD P0 criteria independently of implementation details, all exits 0/1/2/3/4, exact counts and output schemas. Generate a labeled synthetic 1,000,000,000-byte combined-log corpus within the default unique-key budget; record hardware, Python, OS, cache conditions, corpus distributions, three end-to-end timings, median, and peak RSS in benchmarks/RESULTS.md. Separately test overflow and repeated-key memory stability. Run the coverage suite and the benchmark commands in the plan. If <30 seconds or resource targets fail, report the failure and optimize measured hotspots within scope; do not claim the target passed or change stacks silently.

## Prompt 8: Distribution and handoff
> Execute step 8. Run the full suite, build a wheel, install dist/*.whl into a new .venv-smoke and verify installed help and synthetic file/stdin/export flows. Recheck the complete 0/1/2/3/4 contract; code 4 remains unique-cardinality exhaustion. Update README.md, this guide and CLAUDE.md with only measured status and known limitations. Include license metadata and record future code-review evidence before release. Keep all artifacts local; publishing/pushing requires separate confirmation. Save context through /session-save with the exact next action.

## Recovery and completion
On a failing check, preserve the failure evidence and fix the active step before moving forward. If cardinality exhaustion occurs, explain the configured limit and suggest an explicit larger limit only when memory permits; never drop keys automatically. A green small fixture does not prove the 1 GB target. Step completion requires executed checks; release requires the full Definition of Done. The current status of all eight implementation steps is not started.
