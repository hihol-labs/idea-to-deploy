# Product Requirements Document: nginx-log-top

## Product Summary

`nginx-log-top` gives DevOps/SRE users a fast local summary of nginx access logs without deploying or operating a service. It reads stdin or files incrementally and emits terminal, JSON, or CSV reports.

## Goals and Success Criteria

- Produce correct top IP, error URL, hourly, and User-Agent metrics for supported logs.
- Process a representative 1 GB log in under 30 seconds on the documented reference laptop.
- Keep stdout safe for pipelines and make all expected failure classes distinguishable with `0/1/2/3/4` exit codes.
- Install cleanly into Python 3.11 with pip.

## Non-Goals

Authentication, persistence, HTTP APIs, servers, dashboards, cloud resources, Kubernetes, arbitrary query languages, and full custom `log_format` support are excluded from the MVP.

## User Stories

- As a DevOps engineer, I want to stream a local nginx log and see the top ten client IPs so that I can identify dominant traffic sources.
- As an on-call SRE, I want the top ten URLs with 4xx/5xx responses so that I can focus incident investigation on failing routes.
- As a capacity engineer, I want each hour's request percentage so that I can see daily traffic concentration independent of log size.
- As a security-minded operator, I want the share of unique User-Agents so that I can spot unusually diverse or automated traffic.
- As an automation author, I want stable JSON output so that scripts can consume the same metrics without scraping terminal text.
- As a shell user, I want rectangular CSV output so that I can feed the results into standard tabular tools.
- As an operator analyzing a growing log, I want optional follow mode so that I can refresh the final report when I stop the stream.

## Prioritized Requirements

### P0 — Must ship

#### P0-1 Streaming inputs

The command reads stdin when no path is supplied and reads one or more files sequentially otherwise.

Acceptance criteria:

- [ ] Memory use does not grow with total line count because raw records are not retained.
- [ ] `-` can represent stdin at most once.
- [ ] A missing or unreadable path emits a concise stderr message and exits 2.
- [ ] Empty input or input with no valid records exits 3 and emits no partial machine report.

#### P0-2 Supported parsing and error tolerance

The parser accepts nginx combined records and their common-log subset.

Acceptance criteria:

- [ ] A valid line yields remote address, timestamp hour, request target, status, and User-Agent.
- [ ] A malformed line is counted and skipped when at least one valid line exists.
- [ ] Status outside 100–599 is malformed.
- [ ] Verbose malformed diagnostics are bounded and written only to stderr.

#### P0-3 Top-ten client IPs

Acceptance criteria:

- [ ] The result contains at most ten IPs ordered by descending request count.
- [ ] Equal counts are ordered by ascending IP string.
- [ ] Counts include every valid record, regardless of status.

#### P0-4 Top-ten error URLs

Acceptance criteria:

- [ ] Only valid records with status 400–599 contribute.
- [ ] The request target includes the logged query string but excludes method and protocol.
- [ ] Results contain at most ten entries with deterministic tie ordering.

#### P0-5 Hourly request distribution

Acceptance criteria:

- [ ] Output contains all 24 hours from `00` through `23`, including zero-count buckets.
- [ ] The logged timestamp hour determines the bucket.
- [ ] Each percentage uses `100 × hourly_request_count / total_valid_requests`.
- [ ] Percentages sum to 100 within documented floating-point/rounding tolerance when valid requests exist.

#### P0-6 Unique User-Agent share

Acceptance criteria:

- [ ] The numerator is the count of distinct nonempty User-Agent strings; `-` is empty.
- [ ] Share is `100 × distinct_nonempty_user_agents / total_valid_requests`.
- [ ] Exceeding `--max-unique-user-agents` emits a concise stderr diagnostic, emits no report, and exits 4.
- [ ] No approximate value is substituted after unique-cardinality exhaustion.

#### P0-7 Output modes

Acceptance criteria:

- [ ] Default output is a readable Rich terminal report with color controlled by `--color`.
- [ ] `--json` emits valid UTF-8 JSON with `schema_version: 1` and no ANSI escapes.
- [ ] `--csv` emits the documented header and no ANSI escapes.
- [ ] `--json` and `--csv` together are rejected as a usage error with exit 2.
- [ ] Diagnostics never appear on stdout.

#### P0-8 Performance and packaging

Acceptance criteria:

- [ ] A clean Python 3.11 virtual environment can install the project with pip and invoke `nginx-log-top --help`.
- [ ] The documented 1 GB fixture completes in less than 30 seconds on the recorded reference laptop.
- [ ] Benchmark evidence includes wall-clock duration, peak RSS, fixture description, Python version, and hardware summary.

### P1 — Should ship after MVP stability

- Follow exactly one growing regular file with `--follow`; incompatible inputs are usage errors.
- Publish a reproducible wheel and source distribution.

### P2 — Could ship later

- Read gzip-compressed archives.
- Accept a constrained custom nginx log-format mapping.
- Add opt-in approximate unique cardinality as a visibly different metric and mode; exact remains the default contract.

## Output Contract

The canonical shapes, option rules, and field semantics are defined in `PROJECT_ARCHITECTURE.md` under `## CLI Interface`. Machine outputs use deterministic ordering. Percentages are numeric values in JSON, decimal text in CSV, and formatted percentages in terminal output.

## Exit-Code Contract

- `0`: success or normal downstream broken pipe.
- `1`: unexpected internal error.
- `2`: usage, path, permission, or input I/O error.
- `3`: no valid records.
- `4`: unique-cardinality exhaustion.

## Quality Attributes

| Attribute | Requirement |
|---|---|
| Correctness | Golden fixtures cover valid, malformed, tied, empty, and high-cardinality inputs |
| Performance | Representative 1 GB input in <30 seconds on reference laptop |
| Memory | Streaming raw records; explicit cardinality cap; peak RSS recorded |
| Determinism | Stable tie-breaking and serialized field order |
| Privacy | No telemetry/network/persistence; bounded diagnostics do not echo whole lines |
| Portability | Python 3.11 on current Linux/macOS; Windows is best-effort for MVP |

## Kill Criteria

Pause release if correctness differs between renderers, the supported syntax cannot be specified without ambiguity, the performance target remains unmet after one profiling/optimization cycle, or the design grows a service/database dependency. Re-scope custom formats or follow mode before weakening core correctness.

## Dependencies

This PRD relies on the decisions in `PROJECT_ARCHITECTURE.md`; delivery order and verification commands are in `IMPLEMENTATION_PLAN.md`.

