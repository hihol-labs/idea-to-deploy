# Product Requirements Document: nginx Stream Analytics CLI

## 1. Product Summary

The product is a local Python 3.11 CLI that converts an nginx access-log stream
into four exact operational summaries: top client IPs, top error URLs, hourly
request distribution, and unique User-Agent share. It targets DevOps and SRE
engineers who need quick, reproducible analysis without operating or sending
data to a service.

The MVP is pip-installable, open source, stateless between invocations, and
delivered within one weekend at $0 cost. `PROJECT_ARCHITECTURE.md` is the
technical source of truth for parsing, output schemas, and failure behavior.

## 2. Goals and Success Measures

### Goals

- Analyze a file or stdin in one pass without buffering raw input.
- Make the four required metrics exact and deterministic.
- Serve humans through colored terminal output and pipelines through stable
  JSON and CSV.
- Complete the documented representative 1 GB benchmark in under 30 seconds
  on the reference laptop.
- Fail explicitly when input or exact-cardinality limits prevent a trustworthy
  report.

### Non-goals

- Authentication or multi-user access.
- A database, retained history, dashboards, or alerting.
- An HTTP API, daemon, server, cloud deployment, Docker, or Kubernetes.
- Arbitrary custom nginx `log_format` definitions in the MVP.
- Replacing full observability or SIEM systems.

## User Stories

- As a on-call SRE, I want to stream an nginx access-log file through one local command so that I can triage traffic without deploying a service.
- As a DevOps engineer, I want the ten most frequent client IPs so that I can spot dominant or suspicious sources quickly.
- As a incident responder, I want the ten URLs with the most 4xx and 5xx responses so that I can focus on failing routes.
- As a capacity engineer, I want each hour's request percentage so that I can understand daily traffic shape without manual arithmetic.
- As a platform engineer, I want the share of unique User-Agents so that I can estimate client diversity and detect extreme cardinality.
- As a pipeline author, I want stable JSON and CSV reports and explicit exit codes so that automation can consume results safely.
- As a security-conscious operator, I want all processing to stay local and ephemeral so that access logs are not retained or uploaded.

### Story Acceptance Criteria

#### US-1 — Stream local input (P0)

- [ ] A readable file path and `-` stdin produce the same report for identical
  bytes.
- [ ] The implementation iterates lines and does not retain raw input or all
  parsed records.
- [ ] A missing or unreadable input exits 3 and writes no partial report.

#### US-2 — Top client IPs (P0)

- [ ] At most ten IPs are emitted, sorted by request count descending and then
  IP string ascending for ties.
- [ ] IPv4 and IPv6 strings from valid supported lines are counted.
- [ ] Counts are identical in text, JSON, and CSV.

#### US-3 — Top error URLs (P0)

- [ ] Only valid requests with status 400 through 599 inclusive contribute.
- [ ] The raw request target (path plus query string) is the grouping key.
- [ ] At most ten targets are emitted, sorted by error count descending and
  then target ascending for ties.

#### US-4 — Hourly distribution (P0)

- [ ] All 24 buckets from `00` through `23` are emitted in ascending order.
- [ ] Each bucket is a percentage calculated using the literal formula
  `100 × hourly_request_count / total_valid_requests`.
- [ ] With zero valid requests, all bucket counts and percentages are zero.
- [ ] Counts sum to `total_valid_requests`; unrounded percentages sum to 100
  when at least one valid request exists.

#### US-5 — Unique User-Agent share (P0)

- [ ] Exact distinct normalized non-missing User-Agent values are counted.
- [ ] Share percent is
  `100 × unique_normalized_user_agent_count / total_valid_requests`, or zero
  when there are no valid requests.
- [ ] Missing and `-` User-Agents do not increase the unique count.
- [ ] Exceeding the configured distinct User-Agent cap emits no partial report
  and exits 4.

#### US-6 — Output and automation contract (P0)

- [ ] Default output contains all metrics as readable Rich terminal tables.
- [ ] `--json` emits one valid JSON object with the architecture-defined shape.
- [ ] `--csv` emits the architecture-defined header and long-form rows.
- [ ] `--json` and `--csv` together are rejected as usage error code 2.
- [ ] Machine output contains no ANSI escapes and diagnostics use stderr.

#### US-7 — Local and ephemeral execution (P0)

- [ ] A run creates no database, cache, report file, network request, or
  telemetry event.
- [ ] Source logs are opened read-only and never modified.
- [ ] Aggregate state is released on process exit.

## 4. Functional Requirements

### P0 — Must ship

| ID | Requirement |
|---|---|
| FR-001 | Accept exactly one input path or `-` for stdin and process it line by line. |
| FR-002 | Parse conventional nginx common and combined access-log lines into the architecture-defined record fields. |
| FR-003 | In default non-strict mode, skip malformed lines, count them, and report the count without contaminating stdout machine output. |
| FR-004 | Count all valid requests by client IP and emit a deterministic top 10. |
| FR-005 | Count request targets for statuses 400–599 and emit a deterministic top 10. |
| FR-006 | Count valid requests in 24 local timestamp-hour buckets and calculate the required percentages. |
| FR-007 | Calculate exact unique User-Agent count and share with a configurable hard cap. |
| FR-008 | Render the same immutable report as Rich text, JSON, or CSV. |
| FR-009 | Implement the complete exit-code contract `0/1/2/3/4`. |
| FR-010 | Provide `--help`, `--version`, deterministic ordering, and a final output newline. |

The exit-code contract is: `0` success; `1` unexpected/runtime processing
failure; `2` CLI usage error; `3` input, decoding, or strict malformed-line
failure; `4` unique-cardinality exhaustion. No error path may emit a report
that appears complete.

### P1 — Should ship if P0 remains green

| ID | Requirement |
|---|---|
| FR-101 | `--strict` stops at the first malformed non-empty line and identifies its line number without echoing the entire line. |
| FR-102 | `--encoding` selects input decoding and rejects unknown codec names as usage errors. |
| FR-103 | `--color/--no-color` overrides terminal color detection for text only. |
| FR-104 | The User-Agent cap can be lowered with `--max-unique-user-agents` for constrained environments. |

### P2 — Could follow after MVP

| ID | Requirement |
|---|---|
| FR-201 | Read gzip files directly while preserving stdin composition. |
| FR-202 | Accept a documented custom field mapping for selected nginx `log_format` variants. |
| FR-203 | Add an opt-in verbose progress indicator that never contaminates JSON/CSV stdout. |

## 5. Parsing Rules

- Valid records contain an address, bracketed nginx timestamp with numeric
  offset, quoted request, integer status, and the fields required by common or
  combined format.
- The request field must yield method, target, and protocol; the target is the
  URL aggregation key.
- Timestamps determine the `00`–`23` bucket from the hour written in the log;
  no timezone conversion is performed.
- Lines with impossible timestamps, invalid status syntax, or malformed
  quoting are invalid.
- A blank line is invalid and follows the selected strictness behavior.
- Valid lines with request `"-"` are counted as requests but have no URL key;
  this exceptional case is represented explicitly in tests.

## 6. Output Requirements

All formats present the same values and deterministic ordering. Text labels may
be descriptive; JSON property names and CSV columns are versioned public
contracts. Percentages are finite numbers, never strings with `%` in machine
formats. A documented stable rounding policy applies only at serialization;
counts remain the source of truth.

Terminal color is automatic only for an interactive TTY. `NO_COLOR` should be
honored as a conventional environment signal, but it is not required for
correct machine output because JSON and CSV never use color.

## 7. Non-functional Requirements

| ID | Requirement | Evidence |
|---|---|---|
| NFR-001 | Representative 1 GB input completes in < 30 seconds on the documented reference laptop. | Repeatable benchmark record with fixture profile and machine details |
| NFR-002 | Raw input and parsed records are not accumulated. | Code review plus peak-RSS benchmark |
| NFR-003 | Runs on supported CPython 3.11 installations. | Clean-environment install and test matrix |
| NFR-004 | No network access or persistent data is required. | Integration check in isolated environment and filesystem-diff check |
| NFR-005 | Crafted fields cannot inject terminal control sequences or formulas into an operator workflow without safe encoding. | Security-focused renderer fixtures |
| NFR-006 | Repeated runs over identical bytes and options are byte-stable for JSON and CSV. | Golden-output repeatability test |

## 8. Edge Cases

- Empty file or no valid lines: successful zero report, unless strict mode
  encounters a malformed line.
- Fewer than ten distinct keys: emit only the available keys.
- Equal counts: use lexical secondary ordering.
- Status boundaries: 400 and 599 are errors; 399 and 600 are not.
- Input decoding error: fail with code 3 and no partial stdout report.
- Broken pipe from a downstream consumer: terminate quietly according to
  conventional CLI behavior without a traceback.
- User-Agent cardinality reaches the cap: the value at the cap is permitted;
  the next new value fails with code 4.
- Repeated User-Agent values beyond the cap do not fail because they do not
  increase cardinality.

## 9. Release Acceptance

Release requires all P0 acceptance criteria, a clean Python 3.11 install, all
unit/integration/golden tests passing, and a recorded representative 1 GB run
below 30 seconds. Any performance claim names the machine and fixture. P1 items
may ship only if they do not delay or destabilize P0.

## 10. Kill Criteria

Do not release if any of these remains true at the end of the weekend:

- Supported input produces nondeterministic or renderer-dependent metrics.
- The exact User-Agent share can silently become approximate.
- The 1 GB benchmark exceeds 30 seconds after evidence-driven optimization.
- Processing requires a database, network service, or input-sized raw buffer.
- The CLI cannot distinguish usage, input, runtime, and cardinality failures
  with the specified exit codes.

The response to a kill criterion is to narrow or defer the release, not to add
prohibited infrastructure.

## 11. Traceability

| Requirement group | Architecture source | Delivery source |
|---|---|---|
| Input and parsing | Data Model; CLI Interface | Implementation steps 2–3 |
| Metrics | Data Model and Metric Semantics | Implementation steps 4–5 |
| Renderers | CLI Interface / Outputs | Implementation step 6 |
| Failure contract | CLI Interface / Exit Codes | Implementation step 7 |
| Performance and release | Performance and Resource Design | Implementation steps 8–9 |

