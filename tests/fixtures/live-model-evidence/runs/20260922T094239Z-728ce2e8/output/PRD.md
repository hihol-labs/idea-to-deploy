# Product Requirements Document: nginx-stream-report

## 1. Product Summary

`nginx-stream-report` lets DevOps and SRE users obtain a fixed, trustworthy diagnostic summary from local nginx access logs without operating a service. The MVP is a pip-installable Python 3.11 CLI using Click, Rich, and dataclasses. The architecture and exact interface are defined in `PROJECT_ARCHITECTURE.md`.

## 2. Goals and Success Criteria

- Report the top 10 client IPs across valid requests.
- Report the top 10 request targets whose responses are 4xx or 5xx.
- Report 24 hourly request percentages using `100 × hourly_request_count / total_valid_requests`.
- Report exact distinct non-missing User-Agent count as a share of valid requests that contain a User-Agent.
- Support readable colored text and deterministic `--json`/`--csv` pipeline output.
- Process a representative 1 GB log in under 30 seconds on a documented laptop.
- Remain stateless, local, and bounded by an explicit distinct-cardinality safety limit.

## 3. Non-Goals

- Authentication, users, permissions, or multi-tenancy.
- A database, retained history, search index, or cache.
- An HTTP API, daemon, server, web UI, cloud service, Docker, or Kubernetes.
- Log tailing, live refresh, alerts, dashboards, or scheduled jobs.
- Arbitrary custom nginx `log_format` parsing in the MVP.
- Approximate cardinality results or silent sampling.

## User Stories

- As a site reliability engineer on call, I want the top client IPs from a local nginx log so that I can identify concentrated traffic during an incident.
- As a DevOps engineer, I want the top URLs returning 4xx/5xx responses so that I can focus remediation on the most frequent failing routes.
- As a platform engineer, I want every hour's share computed as `100 × hourly_request_count / total_valid_requests` so that I can recognize traffic concentration over the day.
- As a privacy-conscious operator, I want the share of exact unique non-missing User-Agents so that I can estimate client diversity without uploading logs.
- As an automation author, I want stable JSON and CSV schemas and exit codes `0/1/2/3/4` so that a pipeline can distinguish success, usage, data, I/O, and cardinality failures.
- As a laptop user, I want line-by-line processing with bounded distinct-key state so that a 1 GB file does not need to fit in memory.

### P0 Acceptance Criteria

#### US-1: Stream supported nginx logs

- **Priority:** P0
- **Given** a readable common- or combined-format file, **when** the CLI runs, **then** it reads the file line by line and never loads the full file.
- **Given** `INPUT` is omitted or `-`, **when** bytes arrive on stdin, **then** the same parser and metrics are used.
- **Given** a mix of valid and malformed lines with at least one valid line, **then** the report includes only valid lines, records the malformed count, warns on stderr, and exits 0.
- **Given** no valid records, **then** stdout is empty and the process exits 3.

#### US-2: Produce top client and error URL rankings

- **Priority:** P0
- Rankings contain at most 10 entries.
- Client IP counts include every valid request.
- Error URL counts include statuses 400–599 and no other status.
- URL keys preserve the logged request target, including query strings.
- Ties use ascending UTF-8 key ordering after descending count.

#### US-3: Produce hourly distribution

- **Priority:** P0
- Exactly 24 hour buckets are represented, including zero-count hours.
- Each percentage uses `100 × hourly_request_count / total_valid_requests` and is presented to two decimal places.
- The sum of raw bucket counts equals total valid requests.
- Rounding may make displayed percentages differ slightly from exactly 100.00; raw counts remain authoritative.

#### US-4: Produce User-Agent share

- **Priority:** P0
- `"-"` or absent User-Agent values do not enter the numerator or denominator.
- The numerator is the count of exact distinct non-missing User-Agent strings.
- The denominator is the count of valid requests with a non-missing User-Agent.
- The percentage is `100 × distinct_non_missing_user_agent_count / valid_requests_with_non_missing_user_agent`.
- A zero denominator appears as `null` in JSON, an empty CSV percentage, and `N/A` in text.

#### US-5: Support three output modes

- **Priority:** P0
- Default output is Rich text and uses color only for a TTY unless disabled.
- `--json` emits the complete schema-version-1 object from `PROJECT_ARCHITECTURE.md` and no ANSI escapes.
- `--csv` emits the documented long-form schema and no ANSI escapes.
- `--json` and `--csv` together are rejected as a usage error with exit code 2.
- Diagnostics go to stderr and never corrupt structured stdout.

#### US-6: Fail safely on cardinality growth

- **Priority:** P0
- A new distinct IP, error URL, or User-Agent beyond `--max-unique-values` stops analysis before partially updating that record.
- The process emits no report, names the exhausted dimension and limit on stderr, and exits 4.
- Existing keys may continue to increment when a dimension is exactly at its limit.

#### US-7: Meet the performance target

- **Priority:** P0
- A documented reference laptop processes a generated 1 GB representative fixture in under 30 seconds.
- The benchmark records Python version, hardware, input bytes, valid records, malformed records, and cardinalities.
- Peak memory is measured and remains below 256 MiB for the agreed bounded-cardinality fixture.

### P1 Requirements

- **US-8 (`--no-color`):** explicit suppression of ANSI styling in text mode, even on a TTY.
- Helpful concise error messages for unreadable input, broken output, no valid data, and cardinality exhaustion.

### P2 Requirements

- Configurable top-N while retaining 10 as default.
- Direct gzip-file input. Until then, decompression through stdin is documented.

## 5. Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-01 | P0 | Accept one optional path or stdin and process a single byte stream |
| FR-02 | P0 | Parse the supported common and combined shapes defined by architecture |
| FR-03 | P0 | Count valid and malformed lines separately |
| FR-04 | P0 | Calculate exact deterministic top-10 client IP and error URL rankings |
| FR-05 | P0 | Calculate all 24 hourly buckets and percentages |
| FR-06 | P0 | Calculate exact User-Agent numerator, denominator, and percentage |
| FR-07 | P0 | Render text, JSON, or CSV without mixing diagnostics into stdout |
| FR-08 | P0 | Enforce per-dimension distinct-key limit and exit 4 on exhaustion |
| FR-09 | P0 | Implement the complete exit-code contract `0/1/2/3/4` |
| FR-10 | P1 | Disable color automatically for non-TTY stdout and explicitly with `--no-color` |

## 6. Non-Functional Requirements

| Area | Requirement |
|---|---|
| Performance | 1 GB in under 30 seconds on the documented reference laptop |
| Memory | O(distinct keys), never O(input bytes); <256 MiB on the benchmark profile |
| Compatibility | CPython 3.11 on Linux and macOS; pip-installable wheel and sdist |
| Determinism | Same valid input and options produce byte-identical JSON/CSV |
| Testability | >=90% branch coverage plus golden CLI tests |
| Privacy | No network calls, telemetry, persistence, or entire malformed-line echoing |
| Accessibility | Text output has labels and values independent of color |

## 7. Exit-Code Contract

| Code | Meaning |
|---:|---|
| `0` | Complete successful report from at least one valid request |
| `1` | Input/output runtime failure |
| `2` | Invalid CLI usage or option value |
| `3` | Empty input or no valid nginx records |
| `4` | Unique-cardinality exhaustion |

## 8. Release Acceptance

The MVP is releasable only when all P0 criteria pass, the documented benchmark meets the target, packaging installs in a fresh Python 3.11 virtual environment, and the Definition of Done in `STRATEGIC_PLAN.md` is satisfied. P1 may follow only if it does not jeopardize P0; P2 is explicitly optional.

## 9. Kill Criteria

- Kill the weekend release if the required report cannot be correct for the published grammar.
- Kill or rescope if measured single-process performance remains above 30 seconds after profiling and one bounded optimization iteration.
- Reject any proposed shortcut that silently approximates distinct User-Agent results or remaps exit code 4.
