# Product Requirements Document: Nginx Stream Analyzer

## Product Summary

Nginx Stream Analyzer is a local Python 3.11 command-line utility that incrementally reads nginx combined access logs and reports high-signal operational summaries. It targets engineers who need fast incident triage or pipeline-ready aggregates without deploying a service or retaining log data.

## Goals

- Produce the four required metric families correctly in one input pass.
- Process a 1 GB supported-format log in under 30 seconds on a documented laptop.
- Work equally from a path and stdin.
- Provide readable colored terminal output and stable JSON/CSV schemas.
- Remain local, stateless, installable by pip, and explicit about resource exhaustion.

## Non-Goals

- Authentication, accounts, database storage, historical queries, HTTP API, daemon, web UI, server, cloud, Docker, or Kubernetes.
- Real-time file following or log rotation handling.
- Arbitrary nginx `log_format` parsing in the MVP.
- GeoIP, bot classification, dashboards, alerting, or approximate analytics.

## User Stories

- As a DevOps engineer, I want to stream a local nginx access log and see the top 10 client IPs so that I can identify dominant callers without loading the full file into memory.
- As an on-call SRE, I want the top 10 URLs with 4xx/5xx responses so that I can focus incident investigation on failing routes.
- As a service owner, I want hourly request percentages so that I can see when traffic is concentrated across the day.
- As a reliability engineer, I want the share of unique User-Agents so that I can quickly estimate client diversity.
- As an automation engineer, I want JSON output with a versioned schema so that I can consume the report safely in a pipeline.
- As an automation engineer, I want normalized CSV output so that I can load metrics into standard tabular tools.
- As an operator, I want explicit exit codes and stderr diagnostics so that failures cannot be mistaken for complete results.
- As a laptop user, I want cardinality limits to fail explicitly so that hostile logs do not silently consume all memory.

## Functional Requirements

### P0 — Must

#### FR-P0-1: Supported input and parsing

The command accepts one optional path; omission or `-` reads stdin. It supports the documented nginx combined log format, reads incrementally, and counts malformed lines without retaining raw records.

**Acceptance criteria:**

- [ ] A regular file and the same bytes through stdin yield semantically identical reports.
- [ ] IPv4, IPv6, timezone offsets, quoted requests, query strings, and empty User-Agent fields match fixture expectations.
- [ ] The process does not read the entire input into one bytes or string object.
- [ ] A mixed valid/malformed file succeeds, reports the malformed count, and warns on stderr.
- [ ] Input containing malformed lines and no valid record exits 3 without normal output.

#### FR-P0-2: Top client IPs

Count requests by source IP and emit at most 10 entries ordered by count descending, then IP string ascending.

**Acceptance criteria:**

- [ ] Hand-calculated fixtures match every emitted key and count.
- [ ] Ties use deterministic lexical ordering.
- [ ] Fewer than 10 distinct IPs emit only observed IPs.

#### FR-P0-3: Top error URLs

Count request targets only for response statuses 400 through 599 inclusive and emit at most 10 entries ordered by count descending, then URL ascending.

**Acceptance criteria:**

- [ ] Statuses 399 and 600 are excluded; 400, 499, 500, and 599 are included.
- [ ] Query strings remain part of the URL key.
- [ ] Ties are deterministic and no successful-only URL appears.

#### FR-P0-4: Hourly request distribution

Emit all 24 hour buckets using the hour in each record’s logged timestamp. Each percentage is defined by the literal formula `100 × hourly_request_count / total_valid_requests`.

**Acceptance criteria:**

- [ ] Hours `00` through `23` appear in order with counts and percentages.
- [ ] Percentages use total valid requests as the denominator and sum to approximately 100% subject only to display rounding when at least one record is valid.
- [ ] With zero valid requests, all percentages are defined as 0.0 and the run follows the no-valid-input failure contract.

#### FR-P0-5: Unique User-Agent share

Emit the exact distinct User-Agent count and its percentage of total valid requests, calculated as `100 × unique_user_agent_count / total_valid_requests`.

**Acceptance criteria:**

- [ ] Repeated identical User-Agent values count once in the numerator.
- [ ] An empty User-Agent field on an otherwise valid record is one observed value.
- [ ] The denominator is the number of valid requests, not the number of non-empty User-Agent fields.

#### FR-P0-6: Cardinality safety

Limit exact distinct values for guarded aggregation dimensions. If the next new value would exceed the configured cap, stop and report unique-cardinality exhaustion.

**Acceptance criteria:**

- [ ] A run at the cap can succeed.
- [ ] The first distinct value beyond the cap exits 4.
- [ ] Exit 4 emits a concise diagnostic to stderr and no normal report to stdout.
- [ ] No approximate or partial result is labeled complete.

#### FR-P0-7: Terminal output

Default output uses Rich to present labeled metric sections, totals, and warnings. Color is automatic for a TTY and absent when redirected or disabled.

**Acceptance criteria:**

- [ ] All four metrics and valid/invalid counts are visible.
- [ ] `--no-color` emits no ANSI escapes.
- [ ] Redirected terminal output emits no ANSI escapes.
- [ ] Log-derived strings cannot inject Rich markup or terminal control formatting.

#### FR-P0-8: JSON output

`--json` emits one valid UTF-8 JSON document with `schema_version: 1`, totals, and all metric families.

**Acceptance criteria:**

- [ ] Standard JSON parsers accept stdout without preprocessing.
- [ ] stdout contains no prose, warnings, or ANSI sequences.
- [ ] Counts are integers; percentages are numbers; rankings retain deterministic order.

#### FR-P0-9: CSV output

`--csv` emits a long-form UTF-8 CSV with columns `schema_version,metric,rank,key,count,percentage`.

**Acceptance criteria:**

- [ ] Python’s standard CSV reader parses every row.
- [ ] Commas, quotes, Unicode, and embedded special characters are correctly escaped.
- [ ] stdout contains no prose or ANSI sequences.

#### FR-P0-10: CLI and process contract

The options and outputs match `PROJECT_ARCHITECTURE.md` under `## CLI Interface`. `--json` and `--csv` are mutually exclusive. Diagnostics use stderr.

**Acceptance criteria:**

- [ ] The complete exit contract is `0/1/2/3/4`: success/internal error/input error/usage-or-no-valid-input/unique-cardinality exhaustion.
- [ ] Expected operational failures show no traceback.
- [ ] Help documents every option, input convention, and exit code.
- [ ] JSON and CSV never contain terminal styling.

### P1 — Should

#### FR-P1-1: gzip files

Recognize a `.gz` path or an explicit future option and incrementally decompress it without changing metric semantics. Shell decompression into stdin is the supported MVP workaround.

### P2 — Could

#### FR-P2-1: Custom log formats

Accept a constrained format description and compile a parser with equivalent field guarantees.

#### FR-P2-2: Approximate cardinality mode

Offer an explicitly labeled approximate distinct-count algorithm for inputs that exceed exact-memory limits. It must never be enabled implicitly.

## Quality Attributes

| Attribute | Requirement | Evidence |
|---|---|---|
| Performance | 1 GB in < 30 seconds on named reference laptop | Reproducible end-to-end benchmark report |
| Memory | Streaming reads and configured distinct-key caps | Peak RSS measurement and exhaustion tests |
| Correctness | Exact fixture aggregates across all formats | Unit and end-to-end tests |
| Determinism | Stable tie breaks and schema ordering | Repeated-run byte comparison for JSON/CSV where applicable |
| Privacy | No network, persistence, telemetry, or raw-line diagnostics | Static inspection and integration tests |
| Portability | Python 3.11 and pip install | Clean-environment wheel test |

## Acceptance Matrix

| Scenario | Expected stdout | Expected stderr | Exit |
|---|---|---|---:|
| Valid file, default mode | Complete terminal report | Empty | 0 |
| Mixed valid and malformed | Complete report with invalid count | Warning | 0 |
| Valid stdin with `--json` | One JSON document | Empty | 0 |
| Valid file with `--csv` | CSV header and rows | Empty | 0 |
| Missing/unreadable/undecodable input | Empty | Input diagnostic | 2 |
| Invalid options or no valid records | Help/error or empty | Usage/parse diagnostic | 3 |
| Cardinality cap exceeded | Empty | Exhaustion diagnostic | 4 |
| Unexpected internal failure | Empty | Internal diagnostic | 1 |

## Dependencies and Assumptions

- Python 3.11 is present; Click and Rich can be installed from the chosen package source.
- The user can read the input log.
- The reference laptop and benchmark corpus will be named before performance acceptance.
- The conventional combined log format is the only guaranteed MVP grammar.

## Release Criteria

- Every P0 acceptance criterion passes in the automated suite.
- The full exit contract is tested through subprocess execution.
- The 1 GB benchmark meets the time target and records peak memory.
- A clean Python 3.11 environment installs the built wheel and runs all documented examples.
- No product code is released until an independent implementation review occurs in its appropriate workflow.

## Kill Criteria

- The fixed 1 GB benchmark cannot meet 30 seconds after evidence-led profiling and reasonable single-process optimization.
- Parser ambiguity causes supported valid records to be silently misclassified.
- Exact cardinality cannot be bounded without presenting partial data as complete.
- The weekend scope would require adding a database, HTTP API, server, cloud service, or Kubernetes.

