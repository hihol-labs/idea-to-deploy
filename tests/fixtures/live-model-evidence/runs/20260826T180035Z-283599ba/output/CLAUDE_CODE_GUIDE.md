# Claude Code Implementation Guide

## Purpose and Operating Contract

Use this guide to execute `IMPLEMENTATION_PLAN.md` one step at a time. Before each step, read `PRD.md` and the relevant `PROJECT_ARCHITECTURE.md` sections. Change the specification first if behavior must change. Never add a database, HTTP API, authentication, server, cloud service, Docker/Kubernetes requirement, or persistent runtime state.

Every step must preserve and test the exit-code contract `0/1/2/3/4`:

- `0`: success
- `1`: input I/O failure
- `2`: CLI usage or option validation error
- `3`: no valid nginx records
- `4`: unique-cardinality exhaustion

Do not remap code 4 or silently approximate exact User-Agent cardinality.

## Step Prompts

### Prompt 1 — Package and CLI Contract

> Implement Step 1 from `IMPLEMENTATION_PLAN.md`. Create only the package skeleton, Click command/options, typed error placeholders, and contract tests. Use Python 3.11, Click, Rich, dataclasses, and a `src/` layout. Run the listed checks and report changed files plus evidence. Do not implement parsing or aggregation yet.

### Prompt 2 — Streaming Parser

> Implement Step 2. Parse supported nginx common/combined lines from an iterator without reading the full input. Produce small dataclasses containing only required fields. Add realistic fixtures and boundary tests for timestamp, status, quotes, LF/CRLF, and malformed lines. Run the specified parser tests.

### Prompt 3 — Ranked Aggregations

> Implement Step 3. Add one-pass client-IP and 400–599 request-target counters, then deterministic top-N finalization: count descending and key ascending. Do not render output. Prove boundary statuses and ties with tests.

### Prompt 4 — Hour and User-Agent Metrics

> Implement Step 4. Emit 24 hourly buckets using `100 × hourly_request_count / total_valid_requests`. Track exact nonempty User-Agents and valid records having a User-Agent. Enforce the configured cap before exceeding it and preserve exit code 4. Add focused tests and run them.

### Prompt 5 — Rich Terminal Output

> Implement Step 5. Render every report section with Rich. Color defaults to TTY detection and is controllable with `--color/--no-color`. Keep diagnostics on stderr and report data on stdout. Add renderer tests, including redirected ANSI-free output.

### Prompt 6 — JSON and CSV

> Implement Step 6. Add the exact JSON object and normalized CSV schemas from `PROJECT_ARCHITECTURE.md`. Make `--json` and `--csv` mutually exclusive. Ensure both formats are deterministic, parseable, and ANSI-free. Run renderer and CLI integration tests.

### Prompt 7 — Failure Contract

> Implement Step 7. Exercise all exit codes 0, 1, 2, 3, and 4 through the public command. Emit no partial report on failure. Sanitize terminal control characters and safely handle malformed or oversized input. Run the full failure-focused suite and show evidence for every code.

### Prompt 8 — Performance Gate

> Implement Step 8. Establish a reproducible, non-repository 1 GB benchmark fixture and record CPU, storage, Python version, input size/checksum, wall time, and peak RSS. Measure first, profile any miss, and optimize only demonstrated bottlenecks without changing semantics. The acceptance target is under 30 seconds on the reference laptop.

### Prompt 9 — Package Release

> Implement Step 9. Finalize user documentation and package metadata, build wheel and sdist, install the wheel in a clean Python 3.11 environment, run the full suite, and rerun the performance gate. Do not declare completion without evidence for every P0 acceptance criterion.

## Review Checklist for Every Step

- Scope is limited to the active implementation step.
- Input remains streaming and the process remains stateless.
- Renderer code does not parse or aggregate.
- Machine output is stable and contains no ANSI styling.
- Tests cover new success, boundary, and failure behavior.
- Verification commands actually ran; failures are reported rather than narrated away.
- Documentation and implementation agree before the step is accepted.

## Final Release Checklist

- [ ] All P0 criteria in `PRD.md` have automated evidence.
- [ ] Top defaults are 10 and tie ordering is deterministic.
- [ ] Hourly percentages use the specified percentage formula.
- [ ] The complete `0/1/2/3/4` contract is integration-tested.
- [ ] The 1 GB run is under 30 seconds on the documented laptop.
- [ ] Wheel installation and console invocation succeed on Python 3.11.

