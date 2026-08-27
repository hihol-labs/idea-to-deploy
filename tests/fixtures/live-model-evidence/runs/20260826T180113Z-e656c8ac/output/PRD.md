# Product Requirements Document: Nginx Log Insights CLI

## Product Summary

Nginx Log Insights CLI lets DevOps and SRE engineers turn an nginx combined access log into four immediate summaries: top-10 client IPs, top-10 URLs by 4xx/5xx responses, hourly request distribution, and unique User-Agent share. It is a local, stateless Python 3.11 program with colored terminal output plus JSON and CSV pipeline formats.

## Goals

- Provide actionable incident-triage summaries with one local command.
- Stream logs without retaining raw records or requiring a service.
- Define stable machine-output and exit-code contracts.
- Process a representative 1 GB log in under 30 seconds on a documented laptop.
- Ship a useful open-source MVP within one weekend and a $0 budget.

## Non-Goals

- Authentication, accounts, authorization, or multi-tenancy.
- A database, stored history, search interface, HTTP API, daemon, or web UI.
- Cloud or Kubernetes deployment.
- Arbitrary nginx log-format configuration in the MVP.
- Replacing a general-purpose observability or SIEM platform.

## User Stories

- As a SRE, I want to see the top 10 client IPs so that I can identify traffic concentration during an incident.
- As a service owner, I want to rank URLs by 4xx/5xx response count so that I can find failing routes quickly.
- As an on-call engineer, I want hourly request distribution percentages so that I can recognize traffic spikes and quiet periods.
- As a platform engineer, I want the share of unique User-Agents so that I can estimate client diversity or suspicious churn.
- As a DevOps engineer, I want JSON output so that I can pass deterministic results into automation.
- As a shell user, I want CSV output so that I can inspect or transform report rows with standard tools.
- As a maintainer, I want explicit failures for malformed data and cardinality exhaustion so that pipelines never mistake incomplete analysis for success.

## Functional Requirements

### P0 — Must ship

#### FR-1: Stream input

The command accepts one path or stdin, processes UTF-8 nginx combined-log lines sequentially, and never loads the entire source into memory.

Acceptance criteria:

- [ ] A file path and piped stdin yield identical reports for identical bytes.
- [ ] A test double that forbids whole-file `read()` still completes successfully.
- [ ] Unreadable input exits 1 and emits no report to stdout.

#### FR-2: Rank client IPs

Count valid requests per client IP and return at most ten entries sorted by count descending and IP string ascending on ties.

Acceptance criteria:

- [ ] A golden fixture produces the exact expected counts and deterministic tie order.
- [ ] Fewer than ten distinct IPs produces only the available entries.

#### FR-3: Rank error URLs

Count a URL only when its response status is in 400–599 inclusive and return at most ten URLs using deterministic ranking.

Acceptance criteria:

- [ ] 399 and 600 do not contribute; 400, 499, 500, and 599 do.
- [ ] Repeated errors for the same URL aggregate into one ranked entry.
- [ ] Valid input containing no errors succeeds with an empty ranked list.

#### FR-4: Calculate hourly request distribution

Provide 24 local-log-time buckets. Hourly request distribution is a percentage calculated with the literal formula `100 × hourly_request_count / total_valid_requests`.

Acceptance criteria:

- [ ] Counts across all 24 buckets sum to `total_valid_requests`.
- [ ] Unrounded percentages sum to 100, within floating-point tolerance.
- [ ] Serialized percentages are rounded to two decimal places while counts remain present.

#### FR-5: Calculate exact unique User-Agent share

Count exact distinct User-Agent field values and report their share as `100 × unique_user_agents / total_valid_requests`.

Acceptance criteria:

- [ ] Repeated identical values count once, including the literal `-` value.
- [ ] The reported count and percentage match a golden fixture.
- [ ] Attempting to exceed `--max-unique-user-agents` emits no report and exits 4.

#### FR-6: Render terminal output

Default output presents the four report sections with Rich and uses color only when enabled or auto-detected on a capable terminal.

Acceptance criteria:

- [ ] Redirected default output contains no ANSI control sequences.
- [ ] Log-derived strings are escaped and cannot inject Rich markup or terminal controls.
- [ ] Section order matches the CLI contract in `PROJECT_ARCHITECTURE.md`.

#### FR-7: Render JSON and CSV

`--json` emits one schema-versioned JSON document; `--csv` emits RFC 4180 long-form rows. The flags are mutually exclusive.

Acceptance criteria:

- [ ] Both outputs parse with Python standard-library parsers.
- [ ] Machine formats contain all four metrics plus processing metadata.
- [ ] Machine formats contain no ANSI escapes.
- [ ] Supplying both flags exits 2.

#### FR-8: Handle malformed records and failures

Non-strict mode skips malformed records and exposes their count; strict mode exits 3 on the first malformed record. Zero-valid-record input exits 3.

Acceptance criteria:

- [ ] Diagnostics identify the 1-based line number and a concise reason without echoing the full raw line.
- [ ] Exit behavior follows the complete 0/1/2/3/4 contract in `PROJECT_ARCHITECTURE.md`.
- [ ] No failure path writes a partial JSON or CSV report.

### P1 — Should ship next

- Transparently read a single gzip-compressed combined log while preserving the same report and failure contracts.
- Add benchmark tooling that can generate a deterministic large fixture without checking that fixture into source control.
- Publish signed or provenance-attested distributions after the MVP release process is stable.

### P2 — Could ship later

- Support user-defined nginx log formats through an explicit grammar.
- Offer an approximate distinct User-Agent algorithm as an opt-in mode with clearly separate output metadata.
- Allow multiple input files with documented ordering and aggregate semantics.

## Output Requirements

Terminal, JSON, and CSV report the same numeric result. JSON fields and CSV columns are specified in `PROJECT_ARCHITECTURE.md`; changing them requires a schema-version decision. stdout is reserved for the selected report. stderr carries diagnostics. Ordering is deterministic for reproducible pipelines and snapshots.

## Performance Requirements

- Representative workload: 1 GB UTF-8 nginx combined log with realistic IP, URL, status, and User-Agent distributions.
- Target: median of three warm-cache runs below 30 seconds on the declared reference laptop.
- Peak resident memory target: below 512 MB while distinct User-Agent count remains under the default cap.
- Benchmark reporting must name the Python version, CPU, storage type, input hash, command, wall time, and peak RSS.
- A failed cardinality guard is a supported explicit outcome, not a successful performance result.

## Quality and Compatibility Requirements

- Support CPython 3.11 on current Linux and macOS environments; Windows compatibility is desirable but not a release gate unless verified.
- pip installation into a clean virtual environment exposes `nginx-insights`.
- Product-module test coverage is at least 90%, with golden fixtures for parsing and all renderers.
- No production network access, telemetry, raw-log persistence, or secret configuration.

## Dependencies and Assumptions

- Input uses nginx combined log format and UTF-8 encoding.
- The logged timestamp's hour is used as-is; the program does not convert time zones.
- Exact User-Agent distinctness is case-sensitive and byte-decoded-string exact.
- Click and Rich versions are constrained in `pyproject.toml` to tested compatible ranges.
- The single-process design in `PROJECT_ARCHITECTURE.md` is approved.

## Release Acceptance

The MVP is releasable when every P0 acceptance criterion passes, pip installation works in a clean Python 3.11 environment, output schemas match golden tests, the 1 GB performance gate passes, and all five exit failures/success outcomes have subprocess tests.

## Kill Criteria

Pause or re-scope release if the fixed combined-format parser cannot reliably distinguish valid and malformed lines, if the 1 GB target remains above 30 seconds after measured optimization, or if the default exact-cardinality boundary routinely rejects representative logs. Persistence or a server is not an acceptable unreviewed workaround.
