# Product Requirements Document: Nginx Stream Analyzer

## Product Summary

Nginx Stream Analyzer gives DevOps/SRE users a fast, local, reproducible summary of a large nginx combined access log. It is a stateless Python 3.11 CLI with Rich text by default and stable JSON/CSV output for pipelines.

## Goals and Success Criteria

- Produce all four required metrics from one streaming pass.
- Process a representative 1 GB log in under 30 seconds on the documented reference laptop.
- Install through pip and run without a database, service, authentication, or network access.
- Keep human and machine outputs semantically equivalent and exit behavior stable.

## User Stories

### US-1 — Find dominant clients

As an on-call SRE, I want the top 10 client IP addresses by valid request count so that I can identify dominant or suspicious traffic sources.

Priority: P0

Acceptance criteria:

- [ ] The report contains at most 10 IP entries ordered by descending count, then ascending IP text for ties.
- [ ] Each valid request increments exactly one IP; malformed lines increment none.
- [ ] Text, JSON, and CSV expose the same ranks and counts.

### US-2 — Find error hotspots

As a service owner, I want the top 10 request URLs producing 4xx or 5xx responses so that I can prioritize broken routes and client failures.

Priority: P0

Acceptance criteria:

- [ ] Only statuses from 400 through 599 contribute.
- [ ] Entries are ordered by descending error count, then ascending URL for ties, and truncated to 10.
- [ ] Query strings remain part of the request target as logged.

### US-3 — Understand hourly traffic shape

As a capacity engineer, I want 24 hourly request percentages so that I can see when traffic is concentrated.

Priority: P0

Acceptance criteria:

- [ ] The report includes hours `00` through `23`, including zero-valued hours.
- [ ] Every value uses `100 × hourly_request_count / total_valid_requests` and is explicitly labeled as a percentage.
- [ ] With valid requests, the unrounded values sum to 100%; with none, all values are `0.0`.

### US-4 — Measure User-Agent diversity safely

As an incident responder, I want the share of unique User-Agents so that I can distinguish concentrated automation from diverse clients without risking uncontrolled aggregate memory use.

Priority: P0

Acceptance criteria:

- [ ] The report exposes exact unique count and `100 × unique_user_agent_count / total_valid_requests`.
- [ ] An empty valid set produces count `0` and share `0.0%`.
- [ ] Exceeding an exact IP, error-URL, or User-Agent cardinality limit emits a diagnostic and exits with code 4 without a misleading partial report.

### US-5 — Consume reports in automation

As a DevOps engineer, I want stable JSON or CSV on stdout so that I can feed reports to `jq`, spreadsheets, and CI jobs.

Priority: P0

Acceptance criteria:

- [ ] `--json` and `--csv` are mutually exclusive and invalid combinations exit 2.
- [ ] Machine output is UTF-8, contains no ANSI control sequences, and diagnostics use stderr.
- [ ] Golden fixtures validate schema, ordering, units, and parity with terminal output.

### US-6 — Stream from a pipeline

As a shell user, I want `-` to read stdin so that decompression or filtering can be composed without temporary files.

Priority: P1

Acceptance criteria:

- [ ] `INPUT=-` reads stdin incrementally and does not close a caller-owned stream.
- [ ] Output and exit contracts are identical to file input.

### US-7 — Read compressed logs

As an operator, I want transparent `.gz` input so that rotated nginx logs need not be expanded to disk.

Priority: P1

Acceptance criteria:

- [ ] `.gz` content is decompressed incrementally.
- [ ] Corrupt gzip input exits 3 and emits no successful report.

### US-8 — Choose arbitrary top-N

As an analyst, I want to adjust the number of ranked entries so that I can explore beyond the default summary.

Priority: P2

Acceptance criteria:

- [ ] A future positive `--top` option changes both ranked sections consistently.

## Functional Requirements

### P0 — Must ship

- Parse supported nginx combined-log lines incrementally and count malformed lines.
- Compute the four metrics and deterministic top-10 rankings defined above.
- Render Rich terminal text, JSON, or CSV through mutually exclusive modes.
- Enforce the full exit-code contract: `0` success, `1` unexpected runtime failure, `2` usage error, `3` input failure, `4` unique-cardinality exhaustion.
- Enforce exact IP, error-URL, and User-Agent cardinality limits without silent approximation.
- Read binary physical lines with strict UTF-8 decoding and a bounded line-length policy so malformed input can be skipped safely.
- Provide pip-installable Python 3.11 packaging.

### P1 — Should ship after MVP stability

- Accept stdin with `INPUT=-`.
- Stream gzip-compressed files.

### P2 — Could ship

- Configurable top-N while retaining 10 as the default.

## Non-Functional Requirements

- **Performance:** representative 1 GB input completes in under 30 seconds on the documented reference laptop.
- **Memory:** no raw-line or record accumulation; mandatory per-dimension cardinality and physical-line limits bound aggregate memory.
- **Determinism:** ties, schemas, percentage precision, and 24-hour ordering are stable.
- **Compatibility:** CPython 3.11; pip installation; Linux and macOS primary, Windows best effort.
- **Privacy:** no network access, telemetry, database, or retained report state.
- **Usability:** default text uses color only on a TTY; `--no-color` is available.

## Out of Scope

Authentication, a database, HTTP API, server/daemon mode, cloud services, Kubernetes, dashboards, historical storage, arbitrary nginx format configuration, geo-IP enrichment, bot detection, and approximate cardinality algorithms are excluded from the MVP.

## Dependencies and Assumptions

The input uses the documented nginx combined-log format. Click owns CLI parsing, Rich owns text presentation, standard-library CSV/JSON serializers own machine escaping, and dataclasses define domain/report records. Architecture details are authoritative in `PROJECT_ARCHITECTURE.md`.

## Release Acceptance

- All P0 story criteria pass in automated tests.
- A clean Python 3.11 environment installs and invokes the console script.
- The full `0/1/2/3/4` exit-code matrix is integration-tested, including code 4 for IP, error-URL, or User-Agent unique-cardinality exhaustion.
- The 1 GB benchmark and peak RSS are recorded; elapsed time is below 30 seconds.
- The required documentation matches the emitted schemas and options.

## Kill Criteria

Pause release if required metrics would need persistent state, if exact User-Agent handling cannot fail safely at a bounded limit, or if the reference benchmark remains at or above 30 seconds after profiling and one focused optimization iteration.
