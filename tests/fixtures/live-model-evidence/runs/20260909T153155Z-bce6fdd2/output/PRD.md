# Product Requirements Document: nginx-insight

## 1. Overview

`nginx-insight` gives DevOps/SRE engineers a fast, local, reproducible summary of nginx combined access logs. It is a Python 3.11 CLI installed through pip, reads paths or stdin sequentially, and emits Rich terminal text by default or JSON/CSV for pipelines. It stores nothing and contacts nothing.

## 2. Goals

- Report the required four views exactly and deterministically.
- Process a representative 1 GB log in under 30 seconds on a documented laptop baseline.
- Behave safely in pipelines through stable schemas, stderr diagnostics, and exit codes `0/1/2/3/4`.
- Deliver an open-source MVP for $0 in one weekend.

## 3. Non-Goals

- Authentication, authorization, a database, retained history, an HTTP API, a server, dashboards, cloud services, containers, or Kubernetes.
- General web-log query language or parity with GoAccess/Elastic/AWStats.
- GeoIP, bot identification, sessionization, latency percentiles, live network ingestion, or approximate counts in MVP.
- Arbitrary nginx `log_format` configuration in MVP.

## User Stories

- As a DevOps engineer, I want to stream an nginx access log from a file or stdin so that I can inspect traffic without importing data into a service. **Priority: P0.** Acceptance: a regular file and `-`/implicit stdin produce identical schema-v1 results for identical bytes; multiple paths are processed in argument order; inputs are never modified.
- As an on-call SRE, I want the top 10 client IPs so that I can identify concentrated request sources quickly. **Priority: P0.** Acceptance: results use all valid records, contain at most 10 rows, and order by descending count then ascending IP text.
- As an on-call SRE, I want the top 10 URLs producing 4xx/5xx responses so that I can localize failing routes. **Priority: P0.** Acceptance: only status 400–599 is counted, raw query strings remain part of the target, and ties order by ascending target text.
- As a capacity engineer, I want hourly request distribution percentages so that I can see the traffic shape at a glance. **Priority: P0.** Acceptance: there are 24 local-log-hour buckets based only on valid records, each defined by `100 × hourly_request_count / total_valid_requests`, and the zero-valid-record case reports 0.0 for every hour.
- As an SRE, I want the share of unique User-Agents so that I can gauge client diversity without retaining log events. **Priority: P0.** Acceptance: the value is `100 × unique_non_missing_user_agents / valid_requests_with_non_missing_user_agent`; `"-"` is excluded from numerator and denominator; both counts are reported.
- As a terminal user, I want a colored readable default report so that the important values are scannable during triage. **Priority: P0.** Acceptance: four labeled views and summary counts render; color appears only on a TTY unless disabled; no ANSI escapes enter JSON/CSV.
- As an automation author, I want versioned JSON and CSV so that I can compose reports with pipelines. **Priority: P0.** Acceptance: the formats carry equivalent metrics, produce data only on stdout, remain deterministic, and escape untrusted values with standard serializers.
- As an automation author, I want distinct failure codes so that scripts can tell bad input from partial data and cardinality exhaustion. **Priority: P0.** Acceptance: observable integration tests cover every code in `0/1/2/3/4`; exhaustion is code 4 and emits no report.
- As an operator using rotated logs, I want gzip input so that I can avoid manual decompression. **Priority: P1.** Acceptance: deferred until every P0 gate passes; when added, decompressed data follows the same parser and schemas.
- As a user with a custom nginx format, I want declarative field mapping so that I can analyze non-combined logs. **Priority: P2.** Acceptance: excluded from MVP and requires a separately approved grammar/versioning design.

## 5. Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-001 | P0 | The `nginx-insight [OPTIONS] [INPUTS]...` command accepts ordered paths or stdin and never writes an input. |
| FR-002 | P0 | The parser accepts the exact combined grammar in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) and validates timestamp and status. |
| FR-003 | P0 | Top IPs count every valid record and return at most 10 deterministic rows. |
| FR-004 | P0 | Top error URLs count status codes 400–599 inclusive and return at most 10 deterministic rows. |
| FR-005 | P0 | Hourly distribution contains hours 00–23 and uses `100 × hourly_request_count / total_valid_requests`. |
| FR-006 | P0 | Unique-UA share excludes missing `"-"` values and exposes numerator, denominator, and percentage. |
| FR-007 | P0 | Exact IP, error-URL, and User-Agent cardinality is guarded independently by `--max-unique`. |
| FR-008 | P0 | Malformed records are skipped and counted; diagnostics omit raw full lines; a resulting partial report exits 3. |
| FR-009 | P0 | Default Rich output has four views, summary totals, empty states, and terminal-aware color. |
| FR-010 | P0 | JSON schema version 1 uses numeric counts/percentages and stable ordered arrays. |
| FR-011 | P0 | CSV schema version 1 uses `schema_version,metric,rank,key,count,total,percentage`. |
| FR-012 | P0 | CLI outcomes follow the exact `0/1/2/3/4` contract in the architecture. |
| FR-013 | P1 | `--no-color` overrides Rich styling. |
| FR-014 | P1 | Gzip paths may be accepted after MVP without changing metric semantics. |
| FR-015 | P2 | Additional log formats require explicit named format versions, not heuristic guessing. |

## 6. Output Data Contract

### JSON schema version 1

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | integer, always `1` | Compatibility discriminator |
| `summary.total_lines` | integer | All input lines encountered |
| `summary.total_valid_requests` | integer | Successfully parsed request records |
| `summary.invalid_lines` | integer | Skipped malformed records |
| `top_ips[]` | `{rank, ip, request_count}` | Up to 10 deterministic rows |
| `top_error_urls[]` | `{rank, url, error_count}` | Up to 10 deterministic 4xx/5xx rows |
| `hourly_distribution[]` | `{hour, request_count, percentage}` | Exactly 24 rows in hour order |
| `unique_user_agents` | `{unique_count, observed_count, percentage}` | Exact non-missing UA metric |

### CSV schema version 1

One header is followed by normalized rows using `schema_version,metric,rank,key,count,total,percentage`. `metric` is one of `top_ip`, `top_error_url`, `hourly_request_distribution`, `unique_user_agent_share`, or `summary`. Values that do not apply are empty, not invented zeroes.

## 7. Exit-Code Contract

| Code | Required behavior |
|---:|---|
| `0` | Complete report and no malformed input records |
| `1` | Input/output operational failure |
| `2` | Usage or configuration failure |
| `3` | Report emitted after one or more malformed records were skipped |
| `4` | Unique-cardinality exhaustion; abort and emit no report |

Diagnostics go to stderr. JSON/CSV stdout must remain parseable whenever a report is emitted.

## 8. Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-001 Performance | Representative 1 GB input completes in <30 s | Median of three installed-CLI runs on recorded laptop baseline |
| NFR-002 Memory | No raw record accumulation; cardinality cap stops adversarial growth | Peak RSS record plus cap-plus-one test exiting 4 |
| NFR-003 Correctness | Every output matches an independent golden oracle | Unit, property/boundary, and end-to-end tests |
| NFR-004 Determinism | Equal input/options yield byte-stable JSON and CSV | Repeated-run byte comparison |
| NFR-005 Privacy | No persistence, telemetry, or network access | Static inspection and isolated runtime test |
| NFR-006 Compatibility | Installs and runs on CPython 3.11 via pip | Clean virtual-environment wheel install |
| NFR-007 Quality | Parser/aggregate/renderers maintain ≥90% line coverage | Coverage gate |
| NFR-008 Safety | Untrusted log fields cannot inject terminal formatting or break serializers | Hostile-value fixtures |

## 9. UX Requirements

- Help includes input grammar, examples for file/stdin/JSON/CSV, and all exit codes.
- Empty valid input is a successful empty report (code 0), not a crash.
- Partial-data diagnostics identify source and line number without echoing the entire log record.
- Ranked results use stable tie-breaking so diffs and automation are reliable.
- Percentages are labeled as percentages and never presented as unscaled fractions.

## 10. Dependencies and Assumptions

- Python 3.11, Click, Rich, and standard-library dataclasses are fixed choices.
- Input timestamps contain nginx combined-format numeric offsets; hour grouping uses the hour as represented in each log record.
- Exact unique counting is required up to the operator-selected cap.
- Performance approval is conditional on measured benchmark evidence, not an estimate.

## 11. Release Acceptance

The MVP may release only when all P0 stories and NFR gates pass, the wheel installs cleanly, and the repository’s current exact-candidate verification receipt is accepted. P1/P2 items cannot delay release.

## 12. Kill Criteria

- Kill or re-scope if the representative 1 GB oracle-correct run cannot meet 30 seconds after profiling within the weekend.
- Kill the combined-format claim if common representative records require heuristic parsing; replace it with a narrower explicit grammar.
- Do not release if malformed input can yield a code-0 report, JSON/CSV can be contaminated by diagnostics, or cap exhaustion can emit partial metrics.
- Do not add infrastructure outside the local CLI constraints to meet a requirement.
