# Product Requirements Document: Nginx Stream Insights

## 1. Product Summary

Nginx Stream Insights is a pip-installable Python 3.11 CLI for DevOps/SRE engineers who need a fast local summary of nginx access logs. It streams one file or stdin and reports top client IPs, top error-producing URLs, hourly request percentages, and exact unique User-Agent share in terminal, JSON, or CSV form.

## 2. Goals and Success Measures

- Produce all four required metrics correctly from nginx combined/common logs.
- Process a fixed 1 GB representative log in under 30 seconds on a documented laptop.
- Preserve pipeline safety through stable JSON/CSV schemas, stdout/stderr separation, and exit codes `0/1/2/3/4`.
- Remain local and stateless, with no authentication, database, HTTP API, server, cloud, or Kubernetes.
- Install with pip and deliver within one weekend at $0 cash cost.

## 3. Non-Goals

- Retention, historical comparison, live dashboards, tail-follow mode, or interactive TUI.
- Custom nginx `log_format` language in the MVP.
- Authentication, multi-user access, a database, HTTP service, cloud storage, or cluster deployment.
- General log search, alerting, correlation, or replacement of Elastic/GoAccess.
- Approximate values presented as exact values.

## 4. Personas and Primary Use Cases

| Persona | Trigger | Desired outcome |
|---|---|---|
| On-call SRE | Elevated nginx errors | Identify noisy clients and failing URLs within seconds |
| DevOps engineer | Capacity or traffic review | See traffic shape by hour and automate extraction in shell pipelines |
| Systems engineer | Local/air-gapped diagnosis | Analyze sensitive logs without uploading or operating services |

## User Stories

### US-01 — Stream a local log (P0)

As an on-call SRE, I want to analyze a log file or stdin in one pass so that I can get a report without staging data in another system.

Priority: **P0**

Acceptance criteria:

- [ ] `nginx-stream-insights access.log` and `cat access.log | nginx-stream-insights -` produce equivalent report data.
- [ ] The implementation iterates over lines and does not retain individual parsed requests.
- [ ] A missing/unreadable file exits `1`; invalid option usage exits `2`.
- [ ] At least one valid request with a completed report exits `0`.

### US-02 — Identify top client IPs (P0)

As an SRE investigating load or abuse, I want the top 10 client IPs so that I can quickly identify dominant request sources.

Priority: **P0**

Acceptance criteria:

- [ ] Every valid request increments exactly one exact client-IP key.
- [ ] At most 10 rows are returned by default, ordered by count descending then key ascending.
- [ ] IPv4 and IPv6 text values supported by the input grammar are reported without truncation.

### US-03 — Identify error-producing URLs (P0)

As an on-call engineer, I want the top 10 URLs among 4xx and 5xx responses so that I can focus diagnosis on failing request targets.

Priority: **P0**

Acceptance criteria:

- [ ] Only status codes from 400 through 599 inclusive contribute.
- [ ] Exact request targets, including query strings, are grouped and ranked deterministically.
- [ ] At most 10 rows are returned by default; a log with no errors returns an empty ranked section, not a failure.

### US-04 — Understand hourly distribution (P0)

As a platform engineer, I want the percentage of valid requests in every hour of day so that I can recognize traffic concentration.

Priority: **P0**

Acceptance criteria:

- [ ] The report contains hours `00` through `23`, including zero-count hours.
- [ ] Each hour uses the timestamp offset/hour encoded in the log record.
- [ ] The percentage uses exactly `100 × hourly_request_count / total_valid_requests`; it is not an unscaled fraction.
- [ ] Rendering rounds to two decimals while internal calculation retains full precision.

### US-05 — Measure unique User-Agent share safely (P0)

As an SRE assessing client diversity, I want the percentage of distinct User-Agent values among valid requests so that I can spot highly repetitive or unusually diverse traffic.

Priority: **P0**

Acceptance criteria:

- [ ] The exact distinct count is case-sensitive and includes `-` as a value for common-format lines.
- [ ] Share is `100 × unique_user_agents / total_valid_requests`.
- [ ] If another distinct User-Agent would exceed the configured limit, processing stops with exit `4` and no partial value is presented as exact.

### US-06 — Consume machine-readable output (P0)

As a DevOps engineer, I want JSON or CSV output so that I can feed report data into scripts and CI jobs.

Priority: **P0**

Acceptance criteria:

- [ ] `--json` emits one schema-versioned JSON document; `--csv` emits the documented normalized table.
- [ ] `--json` and `--csv` are mutually exclusive and invalid combination exits `2`.
- [ ] Machine-readable stdout contains no ANSI codes or prose diagnostics.
- [ ] Counts and percentages match the default terminal report for the same input.

### US-07 — Read human-friendly output (P0)

As an on-call engineer, I want a colored terminal report by default so that I can scan results quickly.

Priority: **P0**

Acceptance criteria:

- [ ] Rich renders labeled sections for all required metrics and input quality totals.
- [ ] Color is enabled automatically only for a TTY and can be forced or disabled.
- [ ] Redirected default output contains no ANSI codes.

### US-08 — Tune bounded defaults (P1)

As an experienced operator, I want to adjust top-N and the unique User-Agent limit so that I can trade detail against resources explicitly.

Priority: **P1**

Acceptance criteria:

- [ ] `--top` accepts 1–100 and defaults to 10.
- [ ] `--max-unique-user-agents` accepts a positive integer and defaults to 1,000,000.
- [ ] Invalid values exit `2` before input processing begins.

### US-09 — Analyze compressed input directly (P2)

As an engineer working with rotated logs, I want gzip input so that I can avoid a separate decompression step.

Priority: **P2**; deferred from MVP.

### US-10 — Select additional named formats (P2)

As an nginx operator with a known format variant, I want named parsers so that I can analyze more logs without a custom service.

Priority: **P2**; deferred pending format evidence.

## 6. Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-01 | P0 | Accept one path, `-`, or omitted input for stdin |
| FR-02 | P0 | Parse nginx combined/common lines and reject malformed timestamp/status/quoting |
| FR-03 | P0 | Count valid and malformed lines separately |
| FR-04 | P0 | Compute deterministic default top-10 IP and 4xx/5xx URL rankings |
| FR-05 | P0 | Produce all 24 hourly counts and percentages with the valid-request denominator |
| FR-06 | P0 | Compute exact distinct User-Agent count/share up to a hard cap |
| FR-07 | P0 | Render semantically equivalent terminal, JSON, and CSV reports |
| FR-08 | P0 | Implement complete exit codes `0/1/2/3/4` as defined in architecture |
| FR-09 | P0 | Keep diagnostics on stderr and data on stdout |
| FR-10 | P1 | Allow explicit top-N, cardinality, encoding, and color controls |
| FR-11 | P2 | Add gzip input only after MVP criteria pass |
| FR-12 | P2 | Add named format variants only from validated user examples |

## 7. Non-Functional Requirements

| ID | Attribute | Requirement and measurement |
|---|---|---|
| NFR-01 | Performance | Median of three warm-cache 1 GB runs is under 30 seconds on the documented reference laptop |
| NFR-02 | Memory | Peak RSS target under 256 MiB on the same corpus; any miss is documented and blocks release review |
| NFR-03 | Compatibility | Runtime and tests use Python 3.11; wheel installs in a clean virtual environment |
| NFR-04 | Correctness | Golden fixtures cover grammar edges and all metric boundaries; core branch coverage ≥90% |
| NFR-05 | Determinism | Equal counts are ordered by key ascending; JSON/CSV schemas are stable for schema version 1 |
| NFR-06 | Privacy | No network access or persistence; raw rejected lines are not printed by default |
| NFR-07 | Usability | `--help` documents input, formats, defaults, and all exit codes |

## 8. Input and Parsing Contract

Input is decoded using UTF-8 by default and processed line by line. Supported records follow nginx combined or common access-log grammar. The parser extracts client IP, offset-aware timestamp, request target, numeric status, and User-Agent (or `-` for common format). Empty lines and syntactically/semantically invalid records are malformed. Malformed records are excluded from every metric. If the stream contains no valid request, the command exits `3` and emits no successful JSON/CSV report.

## 9. Output Contract

Default output is a Rich terminal report. `--json` and `--csv` select pipeline formats. All formats represent the same immutable report and include input-quality totals. JSON uses `schema_version: 1`; CSV uses `section,key,count,percentage`. Percentage fields are numeric, expressed on a 0–100 scale, and rounded to two decimals only for output.

Exit codes are: `0` success; `1` operational I/O failure; `2` invalid command usage/options; `3` input-data failure/no valid requests; `4` unique-cardinality exhaustion. This mapping is normative and may not be omitted or remapped by implementation work.

## 10. Analytics Examples

For 20 total valid requests with five requests in hour `13`, that hour is `25.00%` because `100 × 5 / 20 = 25`. If those requests contain four distinct exact User-Agent strings, the share is `20.00%` because `100 × 4 / 20 = 20`. Malformed lines do not change either denominator.

## 11. Release Acceptance

- All P0 story criteria pass against the exact release candidate.
- The test suite covers exit `0/1/2/3/4`, renderer equivalence, deterministic ties, parser edge cases, and pipe behavior.
- The benchmark protocol and reference environment are recorded, and the 1 GB median is under 30 seconds.
- A clean Python 3.11 environment can build a wheel, install it, and run the console entry point.
- Documentation contains no unsupported service/database/auth claims and no placeholder text.

## 12. Kill Criteria and Guardrails

Pause the release if the agreed Python parser cannot meet the benchmark after profiling; if memory grows beyond the KPI on representative input without an honest explicit failure; if common real logs cannot be parsed reliably by the declared grammar; or if output formats cannot maintain the same semantics. Do not resolve these issues by silently sampling, dropping valid records, changing denominators, or emitting approximate values as exact.

## 13. Dependencies and Traceability

The business case and MoSCoW/RICE rationale are in `STRATEGIC_PLAN.md`. The normative component, CLI, metric, schema, and error design is in `PROJECT_ARCHITECTURE.md`. Work packages and verification commands are in `IMPLEMENTATION_PLAN.md`.
