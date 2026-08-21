# Product Requirements Document: nginx-stream-stats

## 1. Summary

`nginx-stream-stats` is a local Python 3.11 CLI that converts one nginx access-log stream into four operational reports: top 10 client IPs, top 10 URLs by combined 4xx/5xx count, hourly request percentages, and unique User-Agent share. It is pip-installable, stateless, and produces colored terminal text by default plus JSON or CSV for pipelines.

## 2. Problem and Outcome

DevOps and SRE engineers can build these views with shell pipelines or deploy full analytics stacks, but the former are fragile and the latter are disproportionate for quick local diagnosis. The desired outcome is a reproducible one-command report that runs locally on a representative 1 GB log in under 30 seconds without a database or service.

## 3. Goals

- Parse documented nginx common and combined access-log lines from a file or stdin in one pass.
- Calculate all four required metrics correctly and deterministically.
- Give people readable colored terminal tables and automation stable JSON/CSV schemas.
- Be pip-installable on Python 3.11 with only Click and Rich as runtime dependencies.
- Fail predictably through the complete `0/1/2/3/4` exit-code contract.
- Retain no data and make no network calls.

## 4. Non-goals

- Authentication, authorization, accounts, or multi-tenancy.
- Database, retained history, incremental state, cache, or resume support.
- HTTP API, web UI, server, daemon, cloud deployment, or Kubernetes.
- Real-time tail-follow mode in the MVP; stdin can be a live producer, but the report is emitted at EOF.
- Native compressed-file handling, custom nginx format expressions, geolocation, bots, dashboards, alerting, or approximate cardinality.
- Replacing GoAccess, Elastic/Kibana, or AWStats for their broader use cases.

## 5. Personas and Primary Use Cases

1. An on-call SRE runs the command against a rotated log to identify noisy clients and failing routes.
2. A DevOps engineer pipes a log from another local command and archives JSON as an incident artifact.
3. A platform engineer consumes CSV in a shell or spreadsheet workflow and uses exit codes for branching.

## User Stories

### US-1 — Analyze a local log once

As an on-call SRE, I want to analyze a local nginx log in one command so that I can get incident signals without deploying infrastructure.

Priority: **P0**

Acceptance criteria:

- [ ] A valid path is read to EOF using the selected common or combined format.
- [ ] Omitting the path or passing `-` reads stdin.
- [ ] Input records are processed incrementally and are not retained as a list.
- [ ] A successful run reports total, valid, and skipped physical-line counts.

### US-2 — Find top traffic sources

As an SRE, I want the top 10 client IPs so that I can spot dominant or abusive sources.

Priority: **P0**

Acceptance criteria:

- [ ] Each valid request increments exactly one client-IP counter.
- [ ] At most 10 entries are returned in descending count order.
- [ ] Equal counts are ordered by ascending IP string for deterministic output.
- [ ] Counts are identical in terminal, JSON, and CSV output.

### US-3 — Find error-heavy URLs

As a DevOps engineer, I want the top 10 request targets producing 4xx/5xx statuses so that I can prioritize broken routes and client failures.

Priority: **P0**

Acceptance criteria:

- [ ] Only statuses from 400 through 599 increment the error-URL counter.
- [ ] 4xx and 5xx counts are combined per exact request target.
- [ ] At most 10 entries are sorted by descending error count, then ascending URL.
- [ ] Method and protocol do not create separate URL keys.

### US-4 — Understand hourly traffic shape

As an SRE, I want request distribution by log-entry hour so that I can see when traffic is concentrated.

Priority: **P0**

Acceptance criteria:

- [ ] The report always includes buckets `00` through `23` when a report is emitted.
- [ ] Each valid request increments the hour expressed by its nginx timestamp and numeric offset.
- [ ] Each hourly percentage uses exactly `100 × hourly_request_count / total_valid_requests`.
- [ ] Counts remain authoritative when independently rounded percentages do not display as exactly 100.00 in total.

### US-5 — Measure User-Agent diversity safely

As a platform engineer, I want the share of unique User-Agents so that I can estimate client diversity while retaining no raw records.

Priority: **P0**

Acceptance criteria:

- [ ] The unique count is exact among valid requests with a present User-Agent.
- [ ] The percentage is `100 × unique_user_agent_count / requests_with_user_agent` and is 0.0 when that denominator is zero.
- [ ] `-`, empty, or unavailable common-format User-Agent values are not inserted into the set.
- [ ] Inserting beyond the configured distinct-value ceiling emits no partial report and exits 4.

### US-6 — Use results in automation

As a platform engineer, I want stable JSON and CSV output so that downstream tools can parse results without terminal decoration.

Priority: **P0**

Acceptance criteria:

- [ ] `--json` emits one valid UTF-8 JSON object with `schema_version: 1`.
- [ ] `--csv` emits the documented header and RFC 4180-compatible rows with a final newline.
- [ ] `--json` and `--csv` are mutually exclusive and invalid use exits 2.
- [ ] stdout contains only the requested report; diagnostics are written to stderr.
- [ ] JSON and CSV never contain ANSI escape sequences.

### US-7 — Read an accessible default report

As an operator at a terminal, I want concise colored tables so that I can scan results quickly.

Priority: **P0**

Acceptance criteria:

- [ ] With no format flag, the CLI renders all four metrics and line-accounting summary through Rich.
- [ ] Untrusted log values are rendered as text, never interpreted as Rich markup.
- [ ] Color is automatic by terminal capability and can be forced with `--color` or disabled with `--no-color`.
- [ ] Redirected auto-mode output contains no ANSI escape sequences.

### US-8 — Add native compressed input later

As an operator, I want to pass a `.gz` file directly so that I can avoid a shell decompression stage.

Priority: **P2**

Acceptance criteria:

- [ ] This is not implemented in the MVP; `gzip -cd access.log.gz | nginx-stream-stats` is the documented workaround.

## 7. Functional Requirements

### P0 — Must ship

| ID | Requirement |
|---|---|
| FR-1 | Provide `nginx-stream-stats [OPTIONS] [INPUT]` with file and stdin input semantics from `PROJECT_ARCHITECTURE.md`. |
| FR-2 | Support documented nginx `combined` and `common` grammars selected by `--log-format`. |
| FR-3 | Skip malformed physical lines, account for them, and succeed if at least one valid request exists. |
| FR-4 | Emit deterministic top-10 IPs and combined 4xx/5xx URL rankings. |
| FR-5 | Emit 24 hourly count/percentage buckets using `100 × hourly_request_count / total_valid_requests`. |
| FR-6 | Emit exact unique User-Agent count and share with a configurable positive cardinality ceiling. |
| FR-7 | Default to Rich terminal output and support mutually exclusive `--json` and `--csv`. |
| FR-8 | Serialize all formats from one immutable report contract. |
| FR-9 | Implement and test exit codes `0/1/2/3/4` exactly: success; no valid requests; usage; I/O/internal/resource failure; unique-cardinality exhaustion. |
| FR-10 | Package for pip on Python 3.11 with a console entry point. |

### P1 — Should ship if the Must set is safe

| ID | Requirement |
|---|---|
| FR-11 | Auto-detect terminal color capability and support explicit `--color/--no-color`. |
| FR-12 | Handle downstream broken pipes without a traceback or corrupt diagnostic output. |

### P2 — Could follow the MVP

| ID | Requirement |
|---|---|
| FR-13 | Read gzip files natively. |
| FR-14 | Support explicitly configured additional nginx format grammars. |

## 8. CLI and Output Contract

The authoritative command, options, inputs, output schemas, percentage definitions, malformed-line policy, ordering, and exit codes are in `PROJECT_ARCHITECTURE.md` under `## CLI Interface`. The implementation must not create a second, divergent schema.

The complete exit-code contract is:

| Code | Meaning |
|---:|---|
| `0` | Complete report, help, or version succeeded |
| `1` | EOF reached with zero valid requests |
| `2` | Invalid usage or configuration option |
| `3` | Input I/O, unexpected internal/runtime, or non-UA resource failure |
| `4` | Unique-cardinality exhaustion |

## 9. Non-functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-1 | Representative 1 GB input completes in under 30 seconds on a declared laptop | Recorded wall-clock performance test against a known expected report |
| NFR-2 | Processing is stateless and one-pass | Design review plus tests using non-seekable stdin |
| NFR-3 | No parsed-line collection or raw-log output is retained | Code review and memory profiling |
| NFR-4 | No database, HTTP listener, server, cloud, Kubernetes, authentication, or telemetry | Dependency/configuration and network-behavior review |
| NFR-5 | Output is deterministic for the same bytes/options/version | Repeated golden-output test |
| NFR-6 | Log values cannot inject terminal markup or output structure | Adversarial renderer fixtures |
| NFR-7 | Installable and runnable in a clean Python 3.11 environment | Build/wheel-install smoke test |
| NFR-8 | Runtime dependencies are only Click and Rich plus their transitive requirements | Packaging inspection |

## 10. Analytics Semantics and Edge Cases

- Empty and all-invalid inputs exit 1 without a report.
- A mix of valid and malformed lines exits 0 and exposes skipped count.
- Common-format input has no User-Agent values, so unique count and share are both zero.
- URL identity is exact parser output; no query stripping, percent decoding, host resolution, or normalization occurs.
- IPv4 and IPv6 remote-address tokens are treated as opaque non-empty strings.
- Multiple dates map into the same 24 hour-of-day buckets.
- A valid run with no 4xx/5xx responses emits an empty top-error list/table, not a synthetic row.
- Cardinality failure occurs before adding the over-limit User-Agent and never emits a partial report.

## 11. Release Acceptance

- All P0 user-story criteria pass.
- Golden fixtures prove the four metrics and cross-format equivalence.
- Subprocess integration tests cover file/stdin and exact exit codes `0/1/2/3/4`.
- The clean-wheel smoke test succeeds on Python 3.11.
- The benchmark meets 1 GB under 30 seconds on the declared reference laptop with correctness checked, not timing alone.
- Documentation and `--help` agree with the architecture contract.

## 12. Kill Criteria

- Do not release if any aggregate is not exact on the regression corpus.
- Re-scope implementation if the approved Python design cannot meet the measured performance target after hot-path optimization.
- Do not silently substitute approximate User-Agent cardinality; require a new PRD decision.
- Drop all P2 and then P1 work if one-weekend delivery of P0 is at risk.
- Do not introduce a database or service to meet performance; such a change requires a new architecture and product approval.

## 13. Dependencies and Document Links

Architecture and schemas: `PROJECT_ARCHITECTURE.md`. Sequence and verification: `IMPLEMENTATION_PLAN.md`. Agent-ready step prompts: `CLAUDE_CODE_GUIDE.md`. Repository execution rules: `CLAUDE.md`. Strategy and prioritization: `STRATEGIC_PLAN.md`.
