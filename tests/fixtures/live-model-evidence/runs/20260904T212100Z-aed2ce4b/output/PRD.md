# Product Requirements Document: nginx-log-report

## 1. Summary

`nginx-log-report` gives DevOps/SRE users a fast, deterministic summary of conventional nginx combined access logs through a local Python 3.11 CLI. The release is successful when the four required metrics are correct across terminal, JSON, and CSV output, the process streams rather than buffers the log, and a representative 1 GB input completes in under 30 seconds on recorded reference hardware.

## 2. Problem and Goals

During incident triage, raw access logs are available before or instead of an observability platform. Shell pipelines can answer individual questions but are difficult to reuse safely across malformed lines and output formats. The MVP provides one stable contract.

Goals:

- Compute the four required summaries in one pass.
- Work equally from stdin, plain files, and gzip files.
- Be readable interactively and dependable in pipelines.
- Fail explicitly for usage, I/O, unusable data, internal errors, and cardinality exhaustion.
- Meet the 1 GB performance target without a service or persistent store.

Non-goals include historical trends across runs, arbitrary query exploration, dashboards, authentication, databases, APIs, servers, cloud deployment, or Kubernetes.

## User Stories

- As a member of the on-call SRE rotation, I want the top 10 client IPs so that I can identify dominant traffic sources during an incident. **Priority: P0.**
- As a DevOps engineer, I want the top 10 request targets returning 4xx or 5xx so that I can focus error remediation. **Priority: P0.**
- As a SRE, I want each hour’s request percentage so that I can see when traffic was concentrated. **Priority: P0.**
- As a platform engineer, I want the unique User-Agent share so that I can estimate client diversity. **Priority: P0.**
- As a shell user, I want colored terminal tables by default so that I can scan results quickly. **Priority: P0.**
- As an automation author, I want JSON and CSV output with stable schemas so that I can feed results into pipelines. **Priority: P0.**
- As an operator, I want malformed records counted and resource-limit failures distinguished so that incomplete results are never mistaken for success. **Priority: P0.**
- As an operator with rotated logs, I want transparent gzip input so that I do not need a decompression intermediate. **Priority: P1.**
- As a maintainer, I want configurable cardinality ceilings so that memory behavior is testable on different laptops. **Priority: P1.**
- As a user with a custom nginx format, I want a format description option so that I can analyze non-combined logs. **Priority: P2.**

## 4. P0 Functional Requirements and Acceptance Criteria

### FR-1: Streaming ingestion

- [ ] With no path or input `-`, bytes are consumed from stdin exactly once.
- [ ] Plain files and multiple paths are read line by line in argument order.
- [ ] The implementation does not call an unbounded `read()` or retain raw lines.
- [ ] `.gz` input is supported at P1 without changing aggregation semantics.

### FR-2: Parsing and accounting

- [ ] Supported combined-log records produce the domain fields defined in `PROJECT_ARCHITECTURE.md`.
- [ ] Malformed lines increment `invalid_lines` and default processing continues when another line is valid.
- [ ] `total_lines = total_valid_requests + invalid_lines` for every completed report.
- [ ] With no valid records the process emits no partial report and exits 3.

### FR-3: Top client IPs

- [ ] Every valid request increments its exact client IP count.
- [ ] At most 10 entries are returned, ordered by descending count then ascending value.
- [ ] A hand-counted fixture matches expected counts and tie order.

### FR-4: Top error URLs

- [ ] Only statuses 400–599 contribute.
- [ ] Request targets preserve query strings and receive no normalization.
- [ ] At most 10 entries are returned, ordered by descending count then ascending value.

### FR-5: Hourly request distribution

- [ ] Exactly 24 buckets (00 through 23) are emitted.
- [ ] Each percentage uses `100 × hourly_request_count / total_valid_requests`.
- [ ] Percentages derive from the hour and offset written in the log, not the workstation timezone.
- [ ] Unrounded percentages sum to 100 within floating-point tolerance; renderers may round display values only.

### FR-6: Unique User-Agent share

- [ ] Exact distinct User-Agent strings are counted across valid requests.
- [ ] The percentage equals `100 × unique_user_agents / total_valid_requests`.
- [ ] Repeated identical strings count once; `(missing)` is one normalized distinct value.

### FR-7: Output modes

- [ ] Default output presents totals and all four metrics as Rich terminal sections.
- [ ] `--json` emits one parseable object using documented snake_case fields.
- [ ] `--csv` emits the documented normalized header and section rows.
- [ ] JSON/CSV stdout contains no ANSI escapes or diagnostics.
- [ ] Ties and rows are deterministic across repeated runs.

### FR-8: Failure contract

- [ ] The CLI implements all exit codes `0/1/2/3/4` exactly as defined in `PROJECT_ARCHITECTURE.md`.
- [ ] Exceeding a cardinality ceiling emits no partial report and exits 4.
- [ ] Usage and input I/O errors exit 2; strict/no-valid data errors exit 3; unexpected failures exit 1.
- [ ] Diagnostics do not echo complete raw log lines by default.

### FR-9: Packaging and performance

- [ ] A wheel installs under Python 3.11 and exposes `nginx-log-report`.
- [ ] A representative generated 1 GB input completes under 30 seconds on the recorded reference laptop.
- [ ] Peak RSS is recorded and stays inside the project’s stated laptop memory budget for the benchmark corpus.

## 5. P1 Requirements

- Transparently decompress `.gz` file paths while retaining streaming behavior.
- Expose a positive `--max-cardinality` option with a documented default of 1,000,000 per distinct-key collection.
- Preserve the same report and error contracts for multiple input files.

## 6. P2 Requirements

- Allow a constrained custom `log_format` description only after a grammar and security design is approved.
- Consider live-follow output only as a separate command with explicit snapshot and signal semantics.
- Consider approximate cardinality only as an opt-in, visibly labeled metric with separate schema fields; never silently replace exact P0 behavior.

## 7. Output Schema Summary

The terminal, JSON, and CSV modes are projections of the same immutable report. JSON keys and CSV columns are specified in `PROJECT_ARCHITECTURE.md`; changes to them are compatibility changes. Percentages are percentages on a 0–100 scale, never fractions on a 0–1 scale.

## 8. Quality Attributes

| Attribute | Requirement | Evidence |
|---|---|---|
| Performance | 1 GB in <30 s on recorded laptop | Repeatable benchmark command, elapsed time, peak RSS |
| Correctness | Exact counts and formulas | Hand-audited fixtures and property checks |
| Memory safety | Bounded distinct-key state | Boundary tests and exit 4 scenario |
| Composability | Clean stdout, deterministic schemas | CLI golden tests |
| Privacy | Local-only, no telemetry, redacted diagnostics | Static inspection and error-path tests |
| Portability | Python 3.11 pip install | Clean-environment wheel test |

## 9. Release and Kill Criteria

Release requires every P0 criterion, the Definition of Done in `STRATEGIC_PLAN.md`, and recorded benchmark evidence. Stop or rescope if the target cannot be met without native extensions or silently approximate metrics, if real combined logs cannot be parsed reliably within the weekend, or if exact high-cardinality behavior cannot be bounded with an explicit failure contract.

## 10. Dependencies

Architecture and precise CLI/schema contracts live in `PROJECT_ARCHITECTURE.md`. Work sequencing and verification commands live in `IMPLEMENTATION_PLAN.md`. Agent prompts must follow `CLAUDE_CODE_GUIDE.md`, and persistent repository rules live in `CLAUDE.md`.
