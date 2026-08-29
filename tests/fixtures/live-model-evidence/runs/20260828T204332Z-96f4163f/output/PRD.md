# Product Requirements Document: nginx-insight

## 1. Problem and Goal

DevOps and SRE engineers often receive an nginx access-log file during triage but do not have a log platform available or justified. The MVP must turn that local stream into a consistent report of traffic sources, error-producing URLs, hourly traffic distribution, and User-Agent diversity in one command.

Success means a clean Python 3.11 installation can analyze the representative 1 GB log in under 30 seconds on the documented laptop, while producing correct, deterministic terminal, JSON, and CSV reports.

## 2. Scope

### P0 — Must ship

- Sequential streaming from one or more files or stdin.
- Standard nginx combined-log parsing with malformed-line accounting.
- Top-10 IPs across all valid requests.
- Top-10 request targets among 4xx/5xx responses.
- Twenty-four hourly percentage buckets using `100 × hourly_request_count / total_valid_requests`.
- Unique User-Agent count and percentage share.
- Colored terminal output plus `--json` and `--csv`.
- Deterministic ordering, complete `0/1/2/3/4` exit codes, and unique-key ceiling.

### P1 — Should ship

- Multiple input paths combined into one report.
- Strict parse mode and bounded malformed-line diagnostics.
- `--no-color` and automatic non-TTY color suppression.

### P2 — Could follow

- Gzip input.
- Continuous `--follow` mode.
- User-supplied nginx log-format mapping.

### Out of scope

Authentication, database, HTTP API, server mode, cloud integration, Kubernetes, dashboards, retained history, bot detection, geo-IP enrichment, and approximate aggregates.

## User Stories

- As a DevOps engineer, I want the top ten client IPs from a log stream so that I can identify dominant traffic sources.
  - Priority: P0
  - Acceptance criteria:
    - [ ] Counts include every valid request across all inputs.
    - [ ] Results sort by count descending, then IP ascending, and contain at most ten entries.

- As an on-call SRE, I want the top ten URLs returning 4xx or 5xx status codes so that I can focus incident investigation on failing routes.
  - Priority: P0
  - Acceptance criteria:
    - [ ] Only status codes 400 through 599 contribute.
    - [ ] The parsed request target is the key and ties use ascending key order.

- As a capacity engineer, I want hourly request distribution percentages so that I can see when traffic concentrates during the day.
  - Priority: P0
  - Acceptance criteria:
    - [ ] Output always contains buckets `00` through `23` in order.
    - [ ] Each bucket uses `100 × hourly_request_count / total_valid_requests` and is based on the timestamp offset in each record.

- As a security-minded operator, I want the share of unique User-Agents so that I can quickly judge client diversity.
  - Priority: P0
  - Acceptance criteria:
    - [ ] The output reports both distinct User-Agent count and `100 × unique_user_agent_count / total_valid_requests`.
    - [ ] Cardinality above the configured ceiling produces no partial report and exits 4.

- As an automation engineer, I want JSON and CSV modes so that I can consume the report without parsing terminal decoration.
  - Priority: P0
  - Acceptance criteria:
    - [ ] `--json` emits one valid document matching the documented schema.
    - [ ] `--csv` emits RFC 4180-compatible normalized rows.
    - [ ] The modes are mutually exclusive and never include ANSI styling.

- As an operator handling imperfect exports, I want malformed lines counted and optionally rejected so that I can choose resilient or strict processing.
  - Priority: P1
  - Acceptance criteria:
    - [ ] Default mode skips malformed lines and reports their count.
    - [ ] `--strict` stops at the first malformed line with exit code 3.

## 4. Functional Requirements

### FR-1: Input

The command accepts zero or more paths. Zero paths or `-` selects stdin. Multiple inputs form one aggregate and are read in order. An unreadable path or UTF-8 decoding failure exits 1.

### FR-2: Parsing

The MVP recognizes standard nginx combined format. Each valid record yields a remote address, offset-aware timestamp, request target, numeric HTTP status, and User-Agent. By default malformed lines are skipped and counted; if all lines are malformed or the input has no valid requests, exit 3.

### FR-3: Aggregation

Aggregation is exact and one-pass. Top IPs include all statuses. Top error URLs include statuses 400–599. Hourly distribution contains all 24 hours and uses the record's own timezone offset. User-Agent share is a percentage of valid requests, not a fraction. Distinct aggregate keys are subject to `--max-unique`.

### FR-4: Presentation

Default output uses Rich tables when appropriate. JSON and CSV follow the schemas in `PROJECT_ARCHITECTURE.md`. All formats represent the same values, aside from serialization rounding and structural differences.

### FR-5: Process contract

The process uses exit codes `0/1/2/3/4`: success, input/I/O failure, usage failure, log-data failure, and unique-cardinality exhaustion respectively. Report data is stdout-only; diagnostics are stderr-only.

## 5. Non-Functional Requirements

- NFR-1: Process 1 GB under 30 seconds on the documented reference laptop.
- NFR-2: Never load the complete input into memory.
- NFR-3: Produce deterministic top-list ordering and stable versioned machine schemas.
- NFR-4: Install from a wheel with pip under Python 3.11.
- NFR-5: Make no network requests and persist no input or report data.
- NFR-6: Escape untrusted terminal values and use standard JSON/CSV encoding.
- NFR-7: Test parser, aggregates, renderers, exit mapping, and cardinality exhaustion.

## 6. Acceptance Scenarios

1. A mixed valid fixture produces known IP and error-URL rankings, 24 correct hourly percentages, and the known User-Agent share in all three formats.
2. A tie fixture proves lexicographic secondary ordering.
3. A malformed fixture is counted in default mode and exits 3 in strict mode.
4. Empty or entirely invalid input exits 3 without a partial report.
5. Unreadable input exits 1; conflicting output flags exit 2.
6. A fixture exceeding a small `--max-unique` exits 4 without a partial report.
7. A benchmark run of the installed artifact satisfies the named 1 GB target.

## 7. Release and Kill Criteria

Release requires all P0 criteria, clean-install smoke tests, documented benchmark evidence, and consistent schemas. Stop or redesign if the performance target cannot be met after profiling, exact results cannot be bounded safely, or real standard combined logs routinely fail parsing. Do not expand into a service or database to rescue the MVP.
