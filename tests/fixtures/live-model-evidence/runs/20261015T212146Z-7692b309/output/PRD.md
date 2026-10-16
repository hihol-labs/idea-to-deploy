# Product Requirements: nginx-stream-report

## 1. Product Summary

`nginx-stream-report` gives DevOps/SRE users a fast local summary of nginx combined access logs without uploading logs or operating a service. The MVP is a pip-installable Python 3.11 CLI with colored terminal output and stable JSON/CSV modes.

## 2. Goals and Non-goals

### Goals

- Process a 1 GB reference log in under 30 seconds on a documented laptop.
- Compute all required metrics in one streaming pass.
- Work naturally with files, stdin, terminals, and Unix pipelines.
- Keep output deterministic, safe for untrusted log text, and testable.
- Fail explicitly on input, parse, usage, or unique-cardinality errors.

### Non-goals

- Authentication, user accounts, database storage, historical queries, or saved dashboards.
- HTTP API, server/daemon mode, log shipping, cloud deployment, or Kubernetes.
- Arbitrary nginx formats, Apache logs, live follow/`tail -f`, correlation, alerting, or visualization beyond the four reports.
- Replacing a full observability platform.

## User Stories

- As a DevOps engineer, I want the ten most frequent client IPs so that I can spot abusive or dominant sources during an incident. **Priority: P0.**
- As an on-call SRE, I want the ten URLs with the most 4xx/5xx responses so that I can find failing endpoints quickly. **Priority: P0.**
- As an SRE, I want hourly request percentages so that I can see when traffic was concentrated. **Priority: P0.**
- As a platform engineer, I want the unique User-Agent share so that I can estimate client diversity while receiving an explicit failure if the safe cardinality limit is exceeded. **Priority: P0.**
- As a terminal user, I want a readable colored report so that I can understand results without post-processing. **Priority: P0.**
- As an automation author, I want JSON, CSV, stderr separation, and stable exit codes so that scripts can consume results reliably. **Priority: P0.**
- As an operator, I want malformed-line counts and an optional strict mode so that I can choose tolerant triage or fail-fast validation. **Priority: P0.**
- As an operator with archived logs, I want gzip input so that I can avoid manual decompression. **Priority: P1.**
- As a power user, I want a configurable ranking size so that I can explore beyond ten results. **Priority: P2.**

## 4. P0 Functional Requirements and Acceptance Criteria

### FR-1: Streaming input and parsing

- The command accepts one or more file paths, or stdin when no path/a single `-` is supplied.
- It accepts nginx combined-format records and does not retain raw lines after aggregation.
- Non-strict mode skips and counts malformed lines; `--strict` stops at the first malformed line.

Acceptance criteria:

- [ ] A fixture split across two files produces the same snapshot as their concatenation in the same order.
- [ ] Piped stdin produces the same snapshot as file input.
- [ ] A malformed line increments `malformed_lines` and does not increment `total_valid_requests` in tolerant mode.
- [ ] The same malformed line yields exit `3` and no report under `--strict`.

### FR-2: Top-ten client IPs

- Count the client IP from every valid request.
- Return at most ten entries ordered by count descending, then value ascending.

Acceptance criteria:

- [ ] A golden fixture containing more than ten IPs returns exactly the expected first ten.
- [ ] Equal counts use ascending address text as the deterministic tie-break.

### FR-3: Top-ten error URLs

- Count request targets only for status codes `400..599` inclusive.
- Return at most ten entries with the same deterministic ordering as IPs.

Acceptance criteria:

- [ ] Status `399` and `600` do not contribute; `400`, `499`, `500`, and `599` do.
- [ ] Successful requests never appear in this ranking unless the same target also has qualifying errors.

### FR-4: Hourly request distribution

- Produce all 24 hour buckets based on the hour encoded in each parsed timestamp.
- The percentage definition is exactly `100 × hourly_request_count / total_valid_requests`.
- Zero valid requests produce zero counts and `0.0` for every percentage.

Acceptance criteria:

- [ ] Counts across the 24 buckets sum to `total_valid_requests`.
- [ ] For non-empty input, unrounded percentages sum to 100 within floating-point tolerance.
- [ ] A known multi-timezone fixture uses the local hour in each record’s explicit offset.

### FR-5: Unique User-Agent share and safety

- Normalize a missing nginx User-Agent field to `"-"` and count it as a distinct observed value.
- Compute `100 × unique_user_agent_count / total_valid_requests`, or `0.0` when there are no valid requests.
- Stop before inserting a distinct UA beyond `--max-unique-user-agents`.

Acceptance criteria:

- [ ] Repeated UAs affect the denominator but do not increase the unique count.
- [ ] At the configured ceiling, existing UAs continue to process successfully.
- [ ] The first additional distinct UA produces exit `4`, a stderr diagnostic, and no partial stdout report.

### FR-6: Output formats

- Default output uses Rich sections for summary, top IPs, error URLs, hourly distribution, and unique UA share.
- `--json` emits the versioned schema in `PROJECT_ARCHITECTURE.md`.
- `--csv` emits the normalized `section,key,count,percentage` schema.
- Machine output contains no ANSI escape sequences.

Acceptance criteria:

- [ ] Terminal snapshots are readable with color enabled and disabled.
- [ ] JSON parses with the standard library and contains all required keys and 24 hourly entries.
- [ ] CSV parses with `csv.DictReader` and contains the exact documented header.
- [ ] Log-derived Rich markup/control characters are rendered as data, not interpreted.

### FR-7: CLI and failure contract

The complete exit-code contract is `0/1/2/3/4`:

| Code | Required behavior |
|---:|---|
| `0` | Successful complete report |
| `1` | Input/I/O/decoding or unexpected runtime failure |
| `2` | Invalid CLI usage/options |
| `3` | Strict parse failure |
| `4` | unique-cardinality exhaustion |

Acceptance criteria:

- [ ] Contract tests exercise all five codes.
- [ ] Report data is stdout-only and diagnostics are stderr-only.
- [ ] Exit `1`, `3`, or `4` never leaves a partial JSON, CSV, or terminal report on stdout.

## 5. P1 and P2 Requirements

### P1: Gzip input

Detect `.gz` by explicit path suffix and stream-decompress it without staging the full file. This feature ships only after the uncompressed performance target and core contracts pass.

### P2: Configurable ranking size

Add `--top N` while retaining `10` as default and enforcing a reasonable positive maximum. This is deferred to avoid widening the MVP schema and help surface.

## 6. Non-functional Requirements

| Area | Requirement |
|---|---|
| Performance | A 1 GB reference combined-format log completes in under 30 seconds on the recorded laptop configuration |
| Memory | No raw-record retention; resource tests document scaling and UA cap behavior |
| Compatibility | Python 3.11; pip-installable console entry point on common POSIX environments |
| Privacy | No network access, telemetry, persistence, or log upload |
| Determinism | Stable tie-breaks, section order, schemas, percentage rounding, and exit mapping |
| Accessibility | `--no-color` and automatic non-TTY no-color behavior |
| Security | Escape log-derived terminal data and bound diagnostics |

## 7. Analytics and Telemetry

There is no product telemetry. Success measurement is performed locally through test/benchmark outputs and voluntary user feedback; logs and reports are not transmitted.

## 8. Release Acceptance

- All P0 acceptance criteria pass on Python 3.11.
- `pip install .` exposes `nginx-stream-report` and help/version work without input.
- The documented benchmark satisfies 1 GB under 30 seconds.
- The complete `0/1/2/3/4` exit contract and three output formats have automated coverage.
- Documentation contains no claims of database, API, auth, cloud, or server capabilities.

## 9. Kill Criteria

Pause release and revise scope if the benchmark cannot meet 1 GB under 30 seconds after evidence-based profiling, if exact output cannot remain within a safe resource envelope, or if malformed/untrusted log content cannot be handled without corrupting output. Do not ship a silently approximate report under the current contract.

