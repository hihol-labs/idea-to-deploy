# Product Requirements Document: nginx Log Top

## 1. Product Summary

nginx Log Top is a pip-installable Python 3.11 CLI for DevOps and SRE engineers who need a fast, private summary of nginx access logs. It streams a local file or stdin and emits four reports: top 10 client IPs, top 10 URLs with 4xx/5xx responses, request counts by hour, and the share of unique User-Agents.

Default output is colored terminal text. JSON and CSV are stable alternatives for pipelines. The product is local and stateless: no authentication, database, HTTP API, server, cloud, or Kubernetes.

## 2. Problem and Goals

During incidents, operators often have a large nginx log but not an already deployed analytics stack. General platforms are costly to provision, historical report tools are too heavy for an immediate answer, and ad hoc shell pipelines are easy to get wrong.

Goals:

- Produce the four approved summaries from a supported log in one command.
- Stream a 1 GB file in under 30 seconds on the documented reference laptop.
- Keep log data local and retain no state after the command exits.
- Provide deterministic, pipeline-safe JSON and CSV.
- Be installable with pip on Python 3.11.

Non-goals:

- Searching individual requests or retaining historical data.
- Arbitrary nginx `log_format` support in the MVP.
- Authentication, accounts, database, API, web UI, daemon, cloud, or Kubernetes.
- Distributed or multi-process processing.
- Replacing a full observability platform.

## 3. Personas

- **On-call SRE:** needs trustworthy incident signals in seconds.
- **DevOps automation author:** needs schemas and exit codes that do not change with terminal presentation.
- **Platform engineer in a restricted environment:** needs local-only processing with no network dependency.

## User Stories

### US-01 — Stream a log safely

As an on-call SRE, I want to analyze a log path or stdin in one pass so that I can inspect a large file without loading it into memory or deploying infrastructure.

Priority: **P0**

Acceptance criteria:

- [ ] `nginx-log-top access.log` and `cat access.log | nginx-log-top -` analyze equivalent bytes and produce equivalent metrics.
- [ ] A generated 1 GiB supported-format fixture completes in under 30 seconds on the documented reference laptop.
- [ ] The tool never creates a database, cache file, report file, or network connection.
- [ ] Malformed lines are skipped and counted without per-line warning output; retained samples contain no full raw line.

### US-02 — Identify dominant clients

As an SRE, I want the top 10 client IPs by request count so that I can spot concentrated traffic or abuse.

Priority: **P0**

Acceptance criteria:

- [ ] Results contain no more than 10 IPs and show exact counts.
- [ ] Results sort by descending count and then ascending IP string for ties.
- [ ] IPv4 and IPv6 address strings accepted by the supported log grammar are preserved.

### US-03 — Find failing URLs

As a DevOps engineer, I want the top 10 request targets returning 4xx/5xx statuses so that I can prioritize broken or attacked routes.

Priority: **P0**

Acceptance criteria:

- [ ] Only status codes 400–599 contribute to this ranking.
- [ ] Request targets, including query strings, are counted exactly as logged.
- [ ] Results sort by descending count and then ascending URL string for ties.

### US-04 — See traffic by hour

As an SRE, I want a 24-bucket request distribution so that I can see when traffic is concentrated.

Priority: **P0**

Acceptance criteria:

- [ ] The report always contains hours 00 through 23, including zero-count hours.
- [ ] Each request uses the hour encoded in its nginx timestamp before timezone conversion.
- [ ] The sum of hourly counts equals the total valid request count.

### US-05 — Measure User-Agent diversity

As a platform engineer, I want the share of unique User-Agents so that I can quickly estimate client diversity or automation.

Priority: **P0**

Acceptance criteria:

- [ ] `unique_share` equals distinct parsed User-Agent strings divided by valid request count.
- [ ] Empty input returns a zero share without division errors.
- [ ] The literal unknown marker `"-"` counts as one distinct value when present.

### US-06 — Read a clear terminal report

As an on-call SRE, I want colored, labeled terminal tables so that I can scan results quickly.

Priority: **P0**

Acceptance criteria:

- [ ] Default TTY output visibly separates the four reports and diagnostics.
- [ ] Logged values are rendered as data and cannot inject Rich markup.
- [ ] Color is disabled automatically outside a TTY and explicitly by `--no-color`.

### US-07 — Consume JSON in automation

As a DevOps automation author, I want a versioned JSON document so that I can reliably extract every metric with standard tools.

Priority: **P0**

Acceptance criteria:

- [ ] `--json` emits exactly one valid JSON document to stdout with `schema_version: 1`.
- [ ] stdout contains no ANSI codes, progress text, or diagnostics.
- [ ] The schema matches `PROJECT_ARCHITECTURE.md` and has contract tests.

### US-08 — Consume CSV in a pipeline

As a DevOps automation author, I want normalized CSV so that I can feed results to spreadsheets and command-line processors.

Priority: **P0**

Acceptance criteria:

- [ ] `--csv` emits the header `report,key,count,value` and correctly quoted rows.
- [ ] All four metrics and diagnostics are representable using the documented report discriminators.
- [ ] stdout contains no ANSI codes or non-CSV commentary.

### US-09 — Diagnose input failures

As an operator, I want stable exit codes and concise stderr messages so that failures are actionable and scripts can branch safely.

Priority: **P1**

Acceptance criteria:

- [ ] Usage, input, no-valid-record, internal, interrupt, and broken-pipe behaviors match the architecture exit-code table.
- [ ] A non-empty input with zero valid records exits 4 and emits no structured stdout payload.

### US-10 — Read compressed logs directly

As an operator, I want optional gzip input so that I can avoid a separate decompression pipeline.

Priority: **P2**

Acceptance criteria:

- [ ] Deferred from the MVP; design must not make a later decompression input adapter require parser changes.

## 5. Functional Requirements

### P0 — Must ship

| ID | Requirement |
|---|---|
| FR-01 | Accept one optional input path; omission or `-` reads stdin |
| FR-02 | Parse documented nginx combined format and compatible common-format lines |
| FR-03 | Maintain exact streaming aggregates without retaining parsed requests |
| FR-04 | Produce deterministic top 10 IP and error-URL rankings |
| FR-05 | Produce all 24 hourly buckets |
| FR-06 | Produce unique User-Agent count and share |
| FR-07 | Render safe Rich terminal output by default |
| FR-08 | Render schema-versioned JSON with `--json` |
| FR-09 | Render normalized RFC 4180-compatible CSV with `--csv` |
| FR-10 | Keep stdout clean and send errors/diagnostics to stderr |

### P1 — Should ship if P0 is stable

| ID | Requirement |
|---|---|
| FR-11 | Count malformed lines, retain at most three diagnostic samples, and avoid per-line output |
| FR-12 | Implement the documented exit codes and quiet broken-pipe handling |
| FR-13 | Honor non-TTY color detection, `--no-color`, and optional `NO_COLOR` |

### P2 — Could follow later

| ID | Requirement |
|---|---|
| FR-14 | Read `.gz` input through an input adapter |
| FR-15 | Accept a bounded custom nginx log-format description |
| FR-16 | Offer an explicitly approximate bounded-memory mode for extreme cardinality |

## 6. Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-01 | Python 3.11; pip-installable wheel and sdist | Clean-environment install smoke test |
| NFR-02 | The representative 1 GiB profile is processed in <30 s and <512 MiB RSS on the documented 16 GiB reference laptop | Recorded benchmark excluding fixture generation |
| NFR-03 | Exact one-pass metrics for supported input | Fixture and property tests |
| NFR-04 | No network or persistent state | Static review plus isolated runtime test |
| NFR-05 | Deterministic output for identical input/options | Golden output hashes |
| NFR-06 | Parser/aggregator/renderer line coverage >=90% | Coverage report |
| NFR-07 | Untrusted log fields cannot inject terminal controls/formatting or CSV spreadsheet formulas | Adversarial fixture tests |

## 7. Input, Output, and Error Contracts

`PROJECT_ARCHITECTURE.md` under `## CLI Interface` is authoritative for command syntax, options, supported line interpretation, JSON and CSV schemas, and exit codes. Any behavior change updates the architecture and this PRD before code.

## 8. Dependencies and Assumptions

- Python 3.11 is available to the installer.
- Click and Rich can be installed from the package index or an approved offline mirror.
- The performance target applies to a documented reference laptop and supported line shape; fixture composition and command must be recorded.
- Exact aggregate memory depends on distinct IP, error URL, and User-Agent cardinality.

## 9. Release Acceptance

Release is accepted only when all P0 acceptance criteria pass, package installation works in a clean environment, JSON/CSV golden tests pass, the 1 GiB benchmark meets target, documentation matches `--help`, and the exact candidate has the required current Verification Loop adjudication receipt.

## 10. Kill Criteria

- Stop or renegotiate exactness if realistic high-cardinality input exceeds the agreed laptop memory envelope.
- Re-scope parser compatibility if the supported grammar fails representative standard combined/common logs.
- Reconsider Python or the target if measured profiling plus one optimization cycle cannot reach 1 GiB in 30 seconds.
- Do not add a database, HTTP service, or distributed platform to rescue the MVP; that would constitute a new product.

## 11. Traceability

Feature priority derives from `STRATEGIC_PLAN.md`. Component and interface contracts derive from `PROJECT_ARCHITECTURE.md`. Delivery steps and test commands are in `IMPLEMENTATION_PLAN.md`.
