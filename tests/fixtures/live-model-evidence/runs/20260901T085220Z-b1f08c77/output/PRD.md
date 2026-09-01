# Product Requirements Document: nginx-stream-insights

## Product Summary

`nginx-stream-insights` is a local Python 3.11 command-line tool for DevOps and SRE engineers. It streams an nginx combined access log from a path or stdin and reports traffic concentration, error hotspots, hourly distribution, and User-Agent diversity. It defaults to colored terminal text and supports stable JSON and CSV for pipelines.

## Problem Statement

During incidents and routine checks, operators frequently need a small set of answers from large nginx logs. Shell one-liners are quick but fragile and often scan the same data several times; full analytics stacks require deployment, storage, and ongoing operations. The product must provide the required answers in one local pass without retaining log data.

## Goals

- Produce all four required analyses from one pass over a file or stdin.
- Process a representative 1 GB log in under 30 seconds on a documented laptop.
- Provide readable terminal output and deterministic JSON/CSV contracts.
- Fail explicitly on input, usage, no-valid-data, and exact-cardinality conditions.
- Remain installable through pip with a $0 infrastructure budget.

## Non-Goals

- Authentication or authorization inside the tool.
- A database, retained history, indexing, dashboards, or scheduled reports.
- An HTTP API, server, daemon, cloud service, Docker requirement, or Kubernetes.
- Real-time tail-following, geo-IP lookup, bot detection, or configurable queries.
- Supporting every custom nginx `log_format` in the MVP.

## User Stories

- As a SRE, I want to stream a large nginx log from a file and see the top 10 client IPs so that I can identify concentrated traffic during an incident. **Priority: P0.**
  - [ ] A valid input produces no more than 10 IP rows ordered by count descending and IP ascending for ties.
  - [ ] Counts include every valid request and exclude malformed lines.
- As an on-call engineer, I want the top 10 request URLs associated with 4xx and 5xx responses so that I can locate error hotspots quickly. **Priority: P0.**
  - [ ] Only status codes 400–599 contribute to this ranking.
  - [ ] Each row reports the URL and error count with deterministic tie ordering.
- As a service owner, I want hourly request distribution expressed as a percentage so that I can see when traffic occurred without doing mental normalization. **Priority: P0.**
  - [ ] The output includes all 24 hours in ascending order.
  - [ ] Every bucket uses the literal formula `100 × hourly_request_count / total_valid_requests` and the successful result totals approximately 100% subject only to presentation rounding.
- As a platform engineer, I want the share of unique User-Agents so that I can estimate client diversity while retaining exact, bounded behavior. **Priority: P0.**
  - [ ] The tool reports exact unique count and `100 × unique_user_agents / total_valid_requests` when within the configured ceiling.
  - [ ] Exceeding the ceiling produces exit code 4 and no misleading partial report.
- As a pipeline author, I want JSON and CSV modes so that I can consume the same analysis without scraping colored text. **Priority: P0.**
  - [ ] `--json` emits one valid JSON object and `--csv` emits the documented normalized schema.
  - [ ] Machine-readable stdout contains no ANSI escapes or diagnostics.
- As an operator, I want stdin support so that I can compose decompression, remote-copy, and filtering commands. **Priority: P0.**
  - [ ] Omitting `INPUT` and passing `-` both read stdin.
  - [ ] A fixture produces equivalent metrics through stdin and a file path.
- As an operator, I want malformed records summarized so that I know whether the report is based on incomplete data. **Priority: P0.**
  - [ ] Malformed lines are counted and excluded from every metric denominator.
  - [ ] A mixed valid/malformed input completes with code 0 and reports both counts.
- As an operator, I want direct gzip input so that I can skip a decompression pipeline. **Priority: P1.**
  - [ ] A `.gz` file yields the same snapshot as its plain-text source.
- As a power user, I want a configurable top-N value so that I can widen a report when investigating. **Priority: P2.**
  - [ ] If implemented later, the default remains 10 and output schemas remain compatible.

## Functional Requirements

### P0 — Must ship

| ID | Requirement |
|---|---|
| FR-01 | Accept one optional file path; absent input or `-` reads stdin incrementally. |
| FR-02 | Parse UTF-8 nginx combined-log records and classify every physical line as valid or malformed. |
| FR-03 | Report at most 10 IPs by valid-request count, with deterministic ordering. |
| FR-04 | Report at most 10 request targets by count of status codes 400–599, with deterministic ordering. |
| FR-05 | Report 24 hourly percentage buckets using `100 × hourly_request_count / total_valid_requests`; values are percentages, not unscaled fractions. |
| FR-06 | Report exact unique User-Agent count and share, bounded by `--max-unique-user-agents`. |
| FR-07 | Default to Rich terminal output, color only when appropriate, and honor `--no-color`. |
| FR-08 | Support mutually exclusive `--json` and `--csv` modes with stable schemas. |
| FR-09 | Keep diagnostics on stderr and report data on stdout. |
| FR-10 | Implement the fixed exit codes `0/1/2/3/4` described below. |

### P1 — Should ship after MVP

| ID | Requirement |
|---|---|
| FR-11 | Transparently read gzip-compressed files without changing metric semantics. |

### P2 — Could ship

| ID | Requirement |
|---|---|
| FR-12 | Allow a top-N override while preserving 10 as the default. |
| FR-13 | Add explicitly configured nginx log-format templates after the combined-format parser is stable. |

## Input Contract

- Default accepted format is nginx combined log with one record per physical line.
- Timestamp parsing preserves the logged timezone and assigns the record to its logged local hour.
- Status codes outside 100–599, missing required fields, invalid request fields, invalid UTF-8, and overlong lines follow the architecture error rules.
- `-` as User-Agent is a legitimate exact value, not a missing record.
- The tool never reads the complete input into memory.

## Metric Definitions

| Metric | Numerator | Denominator/filter | Presentation |
|---|---|---|---|
| Top IPs | Valid requests for each remote address | All valid requests | Count, top 10 |
| Top error URLs | Requests for each target | Only valid records with status 400–599 | Error count, top 10 |
| Hourly distribution | Valid requests in hour | `total_valid_requests` | `100 × hourly_request_count / total_valid_requests`, 24 buckets |
| Unique User-Agent share | Number of exact distinct User-Agent strings | `total_valid_requests` | `100 × unique_user_agents / total_valid_requests` |

Division-by-zero values are `0.0`; the command returns code 3 when no valid requests exist. Percentages round to two decimals only in output.

## Output Requirements

### Terminal

Rich tables show source summary, ranked IPs, ranked error URLs, 24 hourly percentages, and unique User-Agent count/share. The output is colored for an interactive TTY unless `--no-color` is passed; redirected output remains readable without ANSI codes.

### JSON

The top-level keys are `total_lines`, `total_valid_requests`, `malformed_lines`, `top_ips`, `top_error_urls`, `hourly_request_distribution`, `unique_user_agents`, and `unique_user_agent_share_percent`. Ranked lists contain objects with `key` and `count`; hourly keys are `00` through `23`. No log lines or run timestamps make otherwise-identical results differ.

### CSV

The header is `metric,rank,key,count,percentage`. `metric` values distinguish summary, top IP, top error URL, hour, and unique User-Agent rows. Inapplicable cells are empty; output follows Python's `csv` quoting rules and mitigates spreadsheet formula injection for untrusted key fields.

## Exit Codes

| Code | Contract |
|---:|---|
| `0` | Complete report from at least one valid request; malformed lines may also be present |
| `1` | Input/read/runtime failure |
| `2` | Invalid CLI usage or option combination |
| `3` | Input was readable but contained no valid requests; emit a complete zero-valued report |
| `4` | Unique-cardinality exhaustion; stop without a partial report |

## Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-01 | A representative 1 GB fixture completes in under 30 seconds on the documented laptop. | Three-run benchmark; slowest run passes |
| NFR-02 | Input processing is stateless and single-pass. | Architecture review and iterator-based integration test |
| NFR-03 | Memory does not grow with total line count; exact distinct-value state is documented and the User-Agent state is hard-bounded. | Peak-RSS benchmark and exhaustion test |
| NFR-04 | Product supports Python 3.11 and installs through pip. | Clean-environment wheel smoke test |
| NFR-05 | Output is deterministic for identical input and options. | Repeat-run byte comparison for JSON/CSV |
| NFR-06 | Product performs no network calls and persists no input or results. | Dependency/code audit and isolated integration test |
| NFR-07 | Product-module statement coverage is at least 90%. | `pytest --cov` gate |

## Release Acceptance

The MVP is accepted when every P0 story passes, all exit codes have integration coverage, JSON/CSV golden fixtures are stable, clean pip installation works under Python 3.11, and the documented 1 GB benchmark meets the target. P1/P2 items do not block release.

## Kill Criteria

- Stop the weekend release if the 1 GB target remains above 30 seconds after measurement-guided optimization.
- Stop rather than ship if malformed input can corrupt denominators or produce a success report with wrong counts.
- Remove or defer exact User-Agent share if it cannot fail safely at a documented cardinality ceiling.
- Reject any proposal that requires authentication, a database, an HTTP API, a server, cloud resources, or Kubernetes for MVP.

`PROJECT_ARCHITECTURE.md` owns technical boundaries; `IMPLEMENTATION_PLAN.md` owns sequencing; behavior changes begin here before code changes.
