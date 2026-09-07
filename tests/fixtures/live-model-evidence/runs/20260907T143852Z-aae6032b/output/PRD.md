# Product Requirements Document: nginx-stream-report

## 1. Product Summary

`nginx-stream-report` is a local Python 3.11 CLI for DevOps/SRE users who need a fast, repeatable summary of nginx access logs. It streams files or stdin and emits four metric families: top client IPs, top URLs returning 4xx/5xx, hourly request distribution, and the share of unique User-Agent values. Default output is colored terminal text; JSON and CSV are stable pipeline formats.

## 2. Goals

- Produce the required report in one pass without persisting raw or derived data.
- Process a deterministic 1 GiB combined-format fixture in under 30 seconds on a declared laptop benchmark.
- Be installable through pip and usable within 30 seconds of installation.
- Keep human output legible and machine output deterministic.
- Fail explicitly before exact User-Agent cardinality can grow beyond its configured guard.

## 3. Non-Goals

- Authentication, users, permissions beyond OS file access, or secrets management.
- Database, cache, retained history, indexing, or cross-run comparison.
- HTTP API, server, daemon, web UI, dashboard, cloud, Docker, or Kubernetes.
- Tail-follow mode, log rotation coordination, remote URLs, or direct compressed-file input in MVP.
- Arbitrary custom nginx `log_format` parsing, geolocation, bot detection, sessionization, or approximate cardinality.

## 4. Personas

1. **On-call SRE:** wants rapid concentration signals during an incident.
2. **DevOps engineer:** wants a stable machine-readable step in a deployment or audit pipeline.
3. **Platform engineer:** wants local processing that does not upload or retain potentially sensitive logs.

## User Stories

- As a on-call SRE, I want to stream a large nginx access log once, so that I can begin incident triage without provisioning an analytics stack. **Priority: P0.**
- As a on-call SRE, I want the ten most active client IPs, so that I can identify traffic concentration or abusive sources. **Priority: P0.**
- As a DevOps engineer, I want the ten URLs with the most 4xx/5xx responses, so that I can focus remediation on the highest-error routes. **Priority: P0.**
- As a platform engineer, I want each hour’s share of valid requests as a percentage, so that I can see daily traffic shape consistently across differently sized logs. **Priority: P0.**
- As a security-minded operator, I want the exact share of unique User-Agent values with a hard cardinality limit, so that I get a useful diversity signal without silent approximation or unbounded memory growth. **Priority: P0.**
- As a terminal user, I want colored, readable default output, so that I can scan the report quickly. **Priority: P0.**
- As an automation author, I want versioned JSON and deterministic CSV, so that scripts can consume results without scraping terminal text. **Priority: P0.**
- As an operator validating log quality, I want strict and permissive malformed-line modes, so that I can choose between best-effort triage and fail-fast auditing. **Priority: P1.**
- As an operator, I want to adjust top-N and color behavior, so that the same command fits interactive and redirected use. **Priority: P1.**
- As an operator with archived logs, I want direct gzip input, so that I can avoid a decompression pipe. **Priority: P2.**

### P0 Acceptance Criteria

#### Streaming input

- [ ] With a regular file, memory does not grow with raw line count except for documented distinct-key aggregates.
- [ ] With no paths or input `-`, the command consumes stdin.
- [ ] Multiple paths are processed in argument order as one report.
- [ ] No database, temp file, network call, or retained state is created.

#### Top client IPs

- [ ] The report contains at most 10 IP rows by default.
- [ ] Counts include every valid record.
- [ ] Ordering is count descending, then IP text ascending for ties.

#### Top error URLs

- [ ] Only status codes 400–599 inclusive contribute.
- [ ] The report contains at most 10 URL rows by default.
- [ ] Query strings remain part of the URL key and ties use lexical ascending order.

#### Hourly request distribution

- [ ] The output includes all 24 logged wall-clock hours, including zero-count hours.
- [ ] Each percentage uses exactly `100 × hourly_request_count / total_valid_requests`.
- [ ] For zero valid requests in permissive mode, all hourly percentages are `0.0`.
- [ ] No documentation or output labels the metric as an unscaled fraction.

#### Unique User-Agent share

- [ ] The share is `100 × unique_user_agent_count / total_valid_requests` and is labeled as a percentage.
- [ ] Common-format records use one documented `<missing>` sentinel value.
- [ ] A new distinct UA beyond `--max-unique-user-agents` produces exit code 4 and no partial report on stdout.
- [ ] At or below the limit, the reported distinct count is exact.

#### Output modes

- [ ] With no output flag, all four metric sections appear in Rich terminal text; color is automatic and can be forced or disabled.
- [ ] `--json` emits one valid object with `schema_version: 1` and the architecture-defined keys.
- [ ] `--csv` emits the documented `metric,rank,key,count,percentage` header and deterministic rows.
- [ ] `--json` and `--csv` together produce a Click usage error with exit code 2.
- [ ] Diagnostics use stderr and never corrupt JSON or CSV stdout.

## 6. Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-1 | P0 | Accept zero or more file paths, with stdin represented by no path or one `-`, and stream all inputs once |
| FR-2 | P0 | Parse standard nginx combined format and extract client IP, logged hour, request target, status, and User-Agent |
| FR-3 | P0 | Parse standard common format; skip-and-count malformed lines by default and fail with code 3 under `--strict` |
| FR-4 | P0 | Count all valid requests by client IP and return deterministic top 10 |
| FR-5 | P0 | Count request targets for 400–599 responses and return deterministic top 10 |
| FR-6 | P0 | Return count and percentage for each of 24 logged wall-clock hours |
| FR-7 | P0 | Return exact distinct UA count/share or fail before exceeding the configured cardinality limit |
| FR-8 | P0 | Render a safe Rich terminal report by default |
| FR-9 | P0 | Render the documented JSON v1 and long-form CSV schemas |
| FR-10 | P0 | Keep reports on stdout and diagnostics on stderr; emit no partial report on failure |
| FR-11 | P1 | Allow `--top` from 1 to 1000 and explicit color behavior |
| FR-12 | P1 | Report total, valid, and malformed line counts in all output modes |
| FR-13 | P2 | Add direct `.gz` input only after MVP acceptance and benchmark validation |

## 7. CLI and Exit-Code Contract

Canonical invocation:

```text
nginx-stream-report [--json | --csv] [--format combined|common]
                    [--top 10] [--strict] [--max-unique-user-agents 1000000]
                    [--color | --no-color] [INPUTS]...
```

| Code | Contract |
|---:|---|
| `0` | Report, help, or version completed successfully |
| `1` | Runtime input/output failure |
| `2` | Usage or option-validation failure |
| `3` | Strict parse/validation failure |
| `4` | Unique-cardinality exhaustion |

## 8. Non-Functional Requirements

| ID | Requirement | Acceptance evidence |
|---|---|---|
| NFR-1 Performance | Process deterministic 1 GiB fixture in <30.0 s on declared laptop | Timed exact-candidate benchmark with correct golden summary |
| NFR-2 Streaming | Do not retain raw records or read an entire input | Review plus input test that rejects whole-file reads |
| NFR-3 Memory safety | Enforce configurable exact-UA distinct limit before insertion | Boundary tests and peak-RSS benchmark |
| NFR-4 Compatibility | Run on CPython 3.11 and install from wheel with pip | Clean-environment smoke test |
| NFR-5 Determinism | Stable tie-breaks, schemas, precision, and all 24 hours | Golden outputs and repeated-run comparison |
| NFR-6 Security | Treat logs as untrusted data; neutralize terminal/CSV injection; do not echo full lines | Adversarial fixtures and output tests |
| NFR-7 Privacy | Make no network calls or telemetry and persist nothing | Dependency/config review and runtime observation |
| NFR-8 Quality | At least 90% line coverage for product package with focused boundary tests | Coverage report plus current verification receipt |

## 9. Output Definitions

- **Top IPs:** valid-request count grouped by literal client IP token.
- **Top error URLs:** count grouped by literal request target, limited to HTTP statuses 400–599.
- **Hourly distribution:** valid-request count and percentage for the wall-clock hour encoded in each nginx timestamp; no timezone normalization.
- **Unique User-Agent share:** exact number of distinct UA strings divided by total valid requests and multiplied by 100. It measures value diversity, not human uniqueness.
- **Parse summary:** physical input lines, valid requests, and malformed lines.

## 10. Release Acceptance Matrix

| Flow | Expected result |
|---|---|
| Combined fixture → terminal | Four sections, top 10 defaults, 24 hourly rows, code 0 |
| Common fixture → JSON | Valid v1 object, `<missing>` UA semantics, code 0 |
| Multiple files → CSV | One header, one combined report, deterministic rows, code 0 |
| Missing input path | Concise stderr diagnostic, empty stdout, code 1 |
| Conflicting `--json --csv` | Click usage diagnostic, empty report stdout, code 2 |
| Malformed line under `--strict` | Source/line diagnostic without full raw line, code 3 |
| UA distinct limit exceeded | Cardinality diagnostic, empty stdout, code 4 |
| 1 GiB benchmark | Correct golden summary and wall time <30.0 s |

## 11. Kill Criteria

- The parser cannot meet the performance target after measurement, profiling, and one bounded optimization pass within the selected architecture.
- Exact metrics cannot be produced within a documented, operator-controlled memory guard.
- JSON/CSV stability would require retaining all raw records.
- The product requires a database, server, remote ingestion, authentication, or historical search to deliver value; that is a different product and requires a new PRD.

## 12. Dependencies and Open Assumptions

The approved runtime dependencies are Click and Rich; dataclasses come from Python 3.11. Development tooling may include pytest, Ruff, mypy, build, twine, and coverage. The only performance assumption is that a single-process Python implementation may meet the target; this must be confirmed by the Step 9 benchmark and is not considered proven by this document.
