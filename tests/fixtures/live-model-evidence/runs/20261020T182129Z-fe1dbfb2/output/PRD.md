# Product Requirements Document: nginx-log-report

## Product Summary

`nginx-log-report` gives DevOps and SRE engineers a fast, local, repeatable summary of nginx access logs. It is a Python 3.11 CLI installed with pip. It streams input without persistent storage and emits colored terminal output by default, or stable JSON/CSV for pipelines.

## Goals

- Produce the four required views correctly from supported nginx combined logs.
- Process a representative 1 GB uncompressed local log in under 30 seconds on a documented laptop.
- Remain stateless, local, installable through pip, and free to operate.
- Make malformed input, invalid invocation, internal failure, and cardinality exhaustion distinguishable to automation.

## Non-Goals

- Authentication, accounts, tenancy, or authorization.
- Database, retained history, HTTP API, daemon, web UI, or server.
- Cloud deployment, Docker requirement, or Kubernetes.
- Arbitrary nginx `log_format` autodetection in the MVP.
- Replacement for a full observability/search platform.

## User Stories

- As a on-call SRE, I want to see the top 10 client IPs so that I can identify traffic concentration during an incident. **Priority: P0.** Acceptance: counts combine all valid inputs; ties sort by IP ascending; no more than 10 rows are shown.
- As a DevOps engineer, I want to see the top 10 request URLs producing 4xx or 5xx responses so that I can identify failing routes quickly. **Priority: P0.** Acceptance: only statuses 400–599 count; ties sort by URL ascending; output includes counts and percentages.
- As a SRE, I want hourly request distribution so that I can spot traffic concentration by hour. **Priority: P0.** Acceptance: all 24 hours are present and each percentage is calculated as `100 × hourly_request_count / total_valid_requests`.
- As a platform engineer, I want the share of unique User-Agent values so that I can estimate client diversity. **Priority: P0.** Acceptance: exact nonempty strings are distinct; the numerator and percentage are emitted; denominator is all valid requests.
- As an automation owner, I want JSON and CSV output so that I can feed results into pipelines without scraping styled text. **Priority: P0.** Acceptance: modes are mutually exclusive, schemas are stable, stdout contains no ANSI escapes, and diagnostics remain on stderr.
- As an operator, I want malformed lines summarized or rejected in strict mode so that I know whether the report excluded input. **Priority: P0.** Acceptance: non-strict mode counts skips; strict mode exits 3 at the first malformed line; zero valid requests exits 3.
- As a pipeline author, I want stable exit codes including a distinct cardinality failure so that automation can take the correct recovery action. **Priority: P0.** Acceptance: integration tests cover `0/1/2/3/4`, with code 4 reserved for unique-cardinality exhaustion.
- As an operator with archived logs, I want to read gzip files directly so that I can avoid a separate decompression step. **Priority: P1.** Acceptance: enabled only after core performance passes and decompression limitations are documented.
- As a power user, I want configurable top-N output so that I can inspect more than ten entries. **Priority: P2.** Acceptance: deferred until the fixed top-10 schema has shipped.

## Functional Requirements

### P0 — Must Ship

#### FR-1: Inputs

- With no path, read UTF-8 input from stdin.
- Accept one or more file paths and combine them into one report.
- Permit `-` once as stdin among paths.
- Process records incrementally; do not load a whole input file.

#### FR-2: Supported parsing

- Parse the documented nginx combined-log format, including IPv4/IPv6, timestamp offset, request target, status, and quoted User-Agent.
- Count invalid lines without echoing their full content.
- In non-strict mode, continue if at least one valid request exists.
- In `--strict` mode, fail at the first invalid line with source and line number.

#### FR-3: Top client IPs

- Count client IP per valid request.
- Return at most 10 entries ordered by count descending and key ascending for ties.
- Include each count and its percentage of total valid requests.

#### FR-4: Top error URLs

- Count request targets only when status is 400–599 inclusive.
- Return at most 10 entries ordered by error count descending and key ascending for ties.
- Include each count and its percentage of all 4xx/5xx requests; if there are no error requests, emit an empty top list.

#### FR-5: Hourly distribution

- Emit exactly 24 ordered hour buckets, including zeros.
- Use the hour and UTC offset as represented in each record; do not normalize timezones.
- Define every hourly percentage as `100 × hourly_request_count / total_valid_requests`, not as an unscaled fraction.

#### FR-6: Unique User-Agent share

- Count exact, case-sensitive, nonempty/non-`-` User-Agent strings once each.
- Emit distinct count and `100 × unique_nonempty_user_agent_count / total_valid_requests`.
- Do not claim that the value represents unique people or devices.

#### FR-7: Output modes

- Default to readable Rich terminal tables with color auto-detection.
- `--json` emits the schema in `PROJECT_ARCHITECTURE.md`.
- `--csv` emits `section,rank,key,count,percent` long-form rows.
- `--json` and `--csv` together are a usage error.
- Machine modes never include Rich markup or ANSI control sequences.

#### FR-8: Cardinality and failure behavior

- Enforce a positive `--max-unique` per tracked dimension before inserting a new key.
- On unique-cardinality exhaustion, emit no partial report and exit 4.
- Preserve this complete contract: `0` success, `1` internal/runtime failure, `2` usage/configuration error, `3` input/read/decode/parse failure or no valid requests, `4` unique-cardinality exhaustion.

### P1 — Should Ship After MVP

- Transparently read `.gz` files while documenting that decompression is excluded from the 1 GB/30 s uncompressed target.
- Add macOS/Windows CI after the Linux Python 3.11 release path is stable.

### P2 — Could Ship Later

- Add `--top N` while retaining 10 as the default and versioning any schema impact.
- Support explicitly configured custom nginx formats; never guess field layouts.

## Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-1 | Representative 1 GB uncompressed local input completes in <30 seconds | Documented benchmark command and result on reference laptop |
| NFR-2 | Streaming memory excludes raw-line accumulation and stays <512 MiB within default cardinality limits | Peak-RSS benchmark plus code review |
| NFR-3 | Python 3.11 package installs through pip and exposes `nginx-log-report` | Build wheel in a clean venv and run `--version` |
| NFR-4 | JSON and CSV are deterministic and undecorated | Golden tests and ANSI scan |
| NFR-5 | Log contents never leave the machine and no cache is written | Static inspection and integration test in a temporary directory |
| NFR-6 | Core parser/aggregation modules maintain >=90% branch coverage | Coverage gate |

## Acceptance Scenarios

1. A mixed valid fixture produces deterministic top-IP/error-URL order, 24 hourly buckets whose counts sum to total valid requests, and the expected exact UA distinct count.
2. JSON parses with a standard decoder; CSV parses with Python's `csv` module; neither contains ANSI escapes.
3. A file with some malformed lines succeeds in non-strict mode, reports skip totals on stderr, and bases all percentages only on valid requests.
4. The same malformed file with `--strict` emits no report and exits 3.
5. Conflicting `--json --csv` exits 2; a deliberately injected internal failure maps to 1 in a controlled test.
6. A fixture exceeding `--max-unique` exits 4 and leaves stdout empty.
7. The benchmark fixture meets the target under the documented environment and command.

## Analytics and Observability

The CLI performs no telemetry and sends no network requests. Operational observability consists of elapsed time measured by the caller, stable exit codes, stderr diagnostics, and the valid/rejected totals in successful output.

## Dependencies and Assumptions

- Python 3.11, Click, Rich, and standard-library dataclasses are available through a pip installation.
- Input uses the documented nginx combined-log format and UTF-8 encoding.
- The performance target applies to a local SSD, uncompressed input, and cardinality within the default limit.

## Release Criteria

- All P0 acceptance scenarios and the full `0/1/2/3/4` contract pass on Python 3.11.
- The 1 GB benchmark target is met and recorded with machine details.
- Wheel and source distribution build, install, and expose the console entry point in a clean environment.
- `README.md`, `PROJECT_ARCHITECTURE.md`, and CLI help agree on input, output, and failure contracts.

## Kill Criteria

Stop release and revise the design if the exact reports cannot meet the benchmark within the resource envelope, or if malformed input/cardinality conditions can produce a plausible but incomplete success result. Do not solve either problem by adding a database, service, or silent approximation without a new product decision.
