# Product Requirements Document: Nginx Insights CLI

## 1. Summary

Nginx Insights CLI gives DevOps/SRE users a fast, local summary of standard nginx combined access logs. It streams a file or stdin, computes four exact metric families, and emits colored terminal text, JSON, or CSV. It is pip-installable on Python 3.11 and does not run a service or retain data.

## 2. Problem and Outcome

During incident response, engineers need answers from large access logs without first deploying an analytics stack or assembling fragile pipelines. Success means a user can run one command against a 1 GB log, receive a correct report in under 30 seconds on the reference laptop, and feed the same metrics to automation through stable machine formats.

## 3. Scope

### P0 — Must ship

- Read standard nginx combined logs from a file or stdin in one pass.
- Report top 10 IPs by all valid requests.
- Report top 10 request targets by combined 4xx/5xx count.
- Report all 24 hourly request percentages using `100 × hourly_request_count / total_valid_requests`.
- Report unique User-Agent share using distinct nonempty User-Agents divided by total valid requests.
- Support Rich terminal, JSON, and CSV output.
- Enforce the `0/1/2/3/4` exit-code and cardinality-safety contracts.

### P1 — Should follow MVP

- Accept a user-supplied nginx `log_format` grammar while preserving the metric schema.

### P2 — Could add

- Transparently read gzip-compressed inputs.

### Out of scope / Won't

- Authentication, database, persistent history, HTTP API, server, cloud, or Kubernetes.
- Dashboards, tail-follow mode, multi-file joins, bot detection, geo-IP, and approximate cardinality.

## User Stories

### US-1: Analyze a local incident log

As an on-call SRE, I want to pass a log path and see a readable terminal report so that I can identify heavy clients and failing URLs quickly.

**Priority:** P0

**Acceptance criteria:**

- [ ] `nginx-insights access.log` produces sections for top IPs, error URLs, 24 hourly buckets, and User-Agent share.
- [ ] Rankings contain no more than 10 entries and ties use ascending key order.
- [ ] Terminal color appears only on a compatible TTY and never corrupts redirected output.

### US-2: Analyze a live pipeline snapshot

As a platform engineer, I want to pipe combined-log text through stdin so that I can analyze remote or decompressed logs without a temporary file.

**Priority:** P0

**Acceptance criteria:**

- [ ] Omitted `INPUT` and `INPUT=-` both read until stdin EOF.
- [ ] The reader never seeks and performs one sequential pass.
- [ ] File and stdin inputs with identical bytes produce identical machine reports.

### US-3: Consume results as JSON

As an automation author, I want stable JSON output so that a script can inspect metrics without scraping terminal text.

**Priority:** P0

**Acceptance criteria:**

- [ ] `--json` emits one valid UTF-8 JSON object matching architecture schema version 1.
- [ ] The object includes totals, malformed count, ranked metrics, 24 hourly entries, and User-Agent counts and percentage.
- [ ] stdout contains no ANSI escapes or diagnostics.

### US-4: Export results as CSV

As a DevOps engineer, I want normalized CSV output so that I can import results into spreadsheets and Unix pipelines.

**Priority:** P0

**Acceptance criteria:**

- [ ] `--csv` emits the header `metric,rank,key,count,percentage` and valid RFC 4180-compatible rows.
- [ ] Values containing commas, quotes, or newlines are safely quoted by the CSV writer.
- [ ] `--csv --json` is rejected with exit code 2.

### US-5: Trust percentage definitions

As an incident commander, I want precise denominator rules so that I do not make decisions from ambiguous charts.

**Priority:** P0

**Acceptance criteria:**

- [ ] Each hourly percentage is computed with `100 × hourly_request_count / total_valid_requests` and is presented as a percentage, not an unscaled fraction.
- [ ] Unique User-Agent share equals `100 × distinct_nonempty_user_agents / total_valid_requests`.
- [ ] All 24 hours appear, including zero-count hours.

### US-6: Fail safely on hostile cardinality

As an SRE analyzing an untrusted log, I want a memory-safety limit and distinct failure status so that the tool does not consume unbounded memory or masquerade as success.

**Priority:** P0

**Acceptance criteria:**

- [ ] `--max-unique` applies independently to IP, error-URL, and User-Agent collections.
- [ ] The first attempted insertion beyond a cap stops processing, produces no report, writes a concise diagnostic to stderr, and exits 4.
- [ ] Exit 4 is not used for input I/O, usage, or malformed-data failures.

### US-7: Extend format coverage later

As an nginx operator with a custom `log_format`, I want to map my fields after MVP so that I can use the same reports without reformatting logs.

**Priority:** P1

### US-8: Read compressed logs later

As an operator with rotated logs, I want gzip input after MVP so that I can avoid an explicit decompression pipe.

**Priority:** P2

## 5. Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-1 | P0 | Accept one optional path positional argument; absent or `-` means stdin |
| FR-2 | P0 | Parse the combined format and retain valid/malformed counts |
| FR-3 | P0 | Count all valid records by IP and return exactly `min(10, unique_ips)` |
| FR-4 | P0 | Count targets only when status is 400–599 and return at most 10 |
| FR-5 | P0 | Return ordered hour buckets `00` through `23` with counts and percentages |
| FR-6 | P0 | Count distinct nonempty, non-`-` User-Agent strings and calculate their share over total valid requests |
| FR-7 | P0 | Default to terminal output; provide mutually exclusive `--json` and `--csv` |
| FR-8 | P0 | Provide `--strict`, `--max-unique`, `--no-color`, `--help`, and `--version` |
| FR-9 | P0 | Map outcomes to the complete `0/1/2/3/4` exit contract in `PROJECT_ARCHITECTURE.md` |
| FR-10 | P1 | Add custom format mapping without changing default combined behavior |
| FR-11 | P2 | Add direct gzip reads while preserving stdin and plain-file behavior |

## 6. Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-1 Performance | Representative 1 GB input completes in <30 seconds on documented reference laptop | Reproducible benchmark command and recorded environment |
| NFR-2 Memory | State grows only with guarded unique keys, never with line count | High-cardinality test plus peak-RSS observation |
| NFR-3 Determinism | Identical records produce identical JSON/CSV byte output | Golden tests, including tie cases |
| NFR-4 Privacy | No logs retained and no network access; diagnostics omit raw lines | Static review and integration test |
| NFR-5 Portability | Wheel installs and runs on supported Python 3.11 environments | Clean virtual-environment smoke test |
| NFR-6 Testability | Core parser and aggregate logic is independent of Click/Rich | Unit tests against pure module APIs |

## 7. Exit and Error Requirements

The public exit codes are fixed: 0 success; 1 input I/O/decoding failure; 2 CLI usage or option conflict; 3 log-data failure (strict malformed input, empty input, or zero valid records); 4 unique-cardinality exhaustion. No partial report is written after a nonzero failure. Diagnostics go to stderr and do not include raw log lines.

## 8. Release Acceptance

- All P0 acceptance criteria and golden-output tests pass.
- A wheel and sdist build; the wheel installs in a clean Python 3.11 virtual environment.
- `--help` documents inputs, metric definitions, cardinality behavior, and exit codes.
- The representative 1 GB benchmark meets NFR-1 without exceeding the default cardinality cap.
- The repository contains no service, database, HTTP, cloud, Docker, or Kubernetes implementation.

## 9. Kill Criteria

Stop the weekend release and revisit the premise if a correct, profiled Python implementation remains above 30 seconds for the agreed benchmark; if common real inputs cannot be parsed without implementing a general nginx configuration language; or if exact aggregation cannot remain within a practical documented memory bound. Do not respond by silently adding a server, database, or approximate results.

## 10. Dependencies and Source of Truth

`PROJECT_ARCHITECTURE.md` defines the CLI schemas and module boundaries. `IMPLEMENTATION_PLAN.md` sequences delivery. If implementation behavior changes, update this PRD and its acceptance criteria first.

