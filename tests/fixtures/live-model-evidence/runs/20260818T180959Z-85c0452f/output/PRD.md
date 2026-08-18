# Product Requirements Document: nginx-logtop

## Product Summary

`nginx-logtop` gives DevOps and SRE engineers a fast, local summary of nginx combined access logs. The Python 3.11 CLI streams files or stdin without retaining requests, defaults to colored terminal output, and offers stable JSON and CSV for automation. The MVP is open source, costs $0 to operate, and is deliverable in one weekend.

## Problem Statement

During incident response and routine checks, engineers often need four answers before a full observability stack is available: which client IPs dominate traffic, which URLs dominate 4xx/5xx failures, how requests are distributed by hour, and how diverse User-Agents are. Existing dashboard stacks require deployment and persistence, while ad hoc shell pipelines are multi-pass and contract-poor. The product must answer these questions locally and deterministically for a 1 GB log in under 30 seconds on the reference laptop.

## Goals

- Parse conventional nginx combined logs from files or stdin in one pass.
- Produce correct, deterministic top-10 IP and error-URL summaries.
- Produce all 24 hourly buckets with `100 × hourly_request_count / total_valid_requests`.
- Produce the exact share of distinct nonempty User-Agents over total valid requests, or fail explicitly when the configured cardinality ceiling is exhausted.
- Support human-friendly terminal output and pipeline-safe JSON/CSV.
- Remain installable by pip on Python 3.11 with no service or persistent storage.

## Non-Goals

- Authentication, accounts, authorization, or multi-tenancy.
- Database, retained history, dashboards, HTTP API, server, cloud runtime, or Kubernetes.
- Live `tail -f` session management; continuous input can be piped, but the report is emitted at EOF.
- Arbitrary nginx `log_format` parsing in MVP.
- Approximate User-Agent cardinality.
- URL normalization, query-string stripping, geolocation, bot classification, or log enrichment.

## User Stories

### US-1: Summarize active clients

As an on-call SRE, I want the ten most active client IPs so that I can quickly identify traffic concentration.

Priority: **P0**

Acceptance criteria:

- [ ] Counts include every valid request across every input in argument order.
- [ ] At most 10 rows are returned, sorted by count descending and IP string ascending on ties.
- [ ] The same IPs and counts appear in terminal, JSON, and CSV outputs.

### US-2: Locate error-heavy URLs

As a service owner, I want the ten URLs with the most 4xx/5xx responses so that I can focus diagnosis on the routes causing client or server failures.

Priority: **P0**

Acceptance criteria:

- [ ] Only statuses 400–599 contribute.
- [ ] Each row contains combined error count and separate 4xx and 5xx counts.
- [ ] Rows sort by combined error count descending and exact request target ascending on ties.
- [ ] Request targets retain query strings and receive no decoding or normalization.

### US-3: Understand hourly traffic shape

As a platform engineer, I want request distribution by logged hour so that I can see when traffic is concentrated.

Priority: **P0**

Acceptance criteria:

- [ ] Output always includes hours `00` through `23` in ascending order.
- [ ] Each bucket uses the nginx timestamp's validated wall-clock hour without timezone conversion.
- [ ] Each percentage uses the literal formula `100 × hourly_request_count / total_valid_requests` and is displayed to two decimal places.
- [ ] Percentages are 0–100 values, not unscaled fractions.

### US-4: Measure User-Agent diversity safely

As an SRE, I want the share of unique User-Agents so that I can estimate client diversity without receiving an approximate result disguised as exact.

Priority: **P0**

Acceptance criteria:

- [ ] The numerator is the number of distinct User-Agent strings other than `-` among valid requests.
- [ ] The percentage is `100 × unique_nonempty_user_agent_count / total_valid_requests`.
- [ ] A new distinct User-Agent beyond the configured ceiling stops processing, emits no normal report, and exits with code `4`.

### US-5: Use the result in a pipeline

As a DevOps engineer, I want JSON or CSV output so that I can feed results to `jq`, spreadsheets, and scheduled checks.

Priority: **P0**

Acceptance criteria:

- [ ] `--json` emits exactly one valid JSON document and a trailing newline on stdout.
- [ ] `--csv` emits one documented header and valid long-form CSV rows on stdout.
- [ ] `--json` and `--csv` are mutually exclusive and conflicts exit `2`.
- [ ] Machine output never includes Rich markup, ANSI escapes, or stderr diagnostics.

### US-6: Detect bad input deliberately

As an engineer validating a log export, I want explicit malformed-line behavior so that I can choose between best-effort triage and data-quality enforcement.

Priority: **P1**

Acceptance criteria:

- [ ] Default mode skips malformed lines and reports their count.
- [ ] `--strict` exits `3` on the first malformed line and identifies the source and line number without echoing the raw line.
- [ ] An unreadable/undecodable input or a run with zero valid lines exits `3` and emits no normal report.

### US-7: Read clear local output

As an on-call engineer, I want colored terminal tables by default so that I can scan results quickly during an incident.

Priority: **P0**

Acceptance criteria:

- [ ] Default output presents all four required metrics plus valid/invalid totals.
- [ ] Color is automatically enabled for a TTY and disabled for a non-TTY unless explicitly controlled.
- [ ] `--no-color` removes ANSI styling without changing data or order.

### US-8: Extend top-N and formats later

As a power user, I want configurable rankings and additional nginx formats so that the tool can cover more environments.

Priority: **P2**

Acceptance criteria:

- [ ] These capabilities remain outside the MVP CLI and do not weaken the combined-format contract.
- [ ] Any later addition receives new parser fixtures and preserves schema-version rules.

## Functional Requirements

### P0 — Must

| ID | Requirement |
|---|---|
| FR-01 | Accept zero or more file paths, with zero meaning stdin; explicit `-` must be the only input. |
| FR-02 | Parse UTF-8 nginx combined-format lines and count invalid lines in lenient mode. |
| FR-03 | Count all valid requests per exact client IP and return deterministic top 10. |
| FR-04 | Count statuses 400–599 per exact request target, split 4xx/5xx, and return deterministic top 10. |
| FR-05 | Count all valid requests in 24 logged-hour buckets and compute percentages with `100 × hourly_request_count / total_valid_requests`. |
| FR-06 | Track exact distinct nonempty User-Agents up to a configurable positive ceiling. |
| FR-07 | Render colored Rich terminal output by default with automatic TTY behavior. |
| FR-08 | Render schema-versioned JSON and documented long-form CSV. |
| FR-09 | Use the complete exit-code contract `0/1/2/3/4`, with `4` reserved for unique-cardinality exhaustion. |
| FR-10 | Keep stdout data separate from stderr diagnostics and suppress normal reports on data/cardinality failure. |

### P1 — Should

| ID | Requirement |
|---|---|
| FR-11 | `--strict` fails on the first malformed line with source and line number. |
| FR-12 | Successful metadata includes source count, valid-line count, and invalid-line count. |
| FR-13 | Build wheel and source distribution and expose a `nginx-logtop` console script. |

### P2 — Could

| ID | Requirement |
|---|---|
| FR-14 | Allow configurable top-N after the fixed top-10 contract is stable. |
| FR-15 | Add explicit parsers for named nginx formats without format guessing. |

## Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-01 | Process the fixed 1 GB representative log in under 30 seconds on the named reference laptop. | Versioned benchmark records wall time, peak RSS, CPU, Python, and package versions. |
| NFR-02 | Request memory is streaming: no parsed request collection grows with line count. | Code review plus peak-RSS comparison across repeated copies with fixed cardinality. |
| NFR-03 | Results are deterministic across runs and output formats. | Golden and cross-renderer semantic tests. |
| NFR-04 | Run on CPython 3.11 and install through pip. | Clean virtualenv build/install smoke test. |
| NFR-05 | Perform no network access, telemetry, persistent writes, or source modification. | Static review and isolated end-to-end test. |
| NFR-06 | Treat Rich markup and CSV/JSON metacharacters in log-derived values as data. | Injection-focused renderer fixtures. |
| NFR-07 | Parser, aggregation, and renderer code reaches at least 90% test coverage. | Coverage command from `IMPLEMENTATION_PLAN.md`. |

## CLI and Exit Contract

The canonical interface and output schemas are specified in `PROJECT_ARCHITECTURE.md` under `## CLI Interface`. Exit codes are immutable for schema version 1:

| Code | Contract |
|---:|---|
| `0` | Successful report or successful help/version action |
| `1` | Unexpected internal error |
| `2` | CLI usage error |
| `3` | Input or data error |
| `4` | Unique-cardinality exhaustion |

## Dependencies and Assumptions

- CPython 3.11 is installed locally.
- Runtime dependencies are Click and Rich; standard-library `dataclasses`, `json`, `csv`, `collections`, `datetime`, and file I/O provide the rest.
- The performance fixture represents conventional combined logs and is generated or sourced without including secrets in the repository.
- The 1 GB target applies to processing and rendering to a controlled sink, not pip installation time or decompression performed by an upstream command.

## Release Acceptance

The MVP is releasable only when all P0 acceptance criteria pass, all exit codes `0/1/2/3/4` have end-to-end coverage, the package installs in clean Python 3.11, the machine-output schema fixtures match, and the named 1 GB benchmark finishes under 30 seconds. P1 strict mode is planned for the same weekend but cannot delay an otherwise complete P0 release unless malformed input could produce silent misreporting.

## Kill Criteria

- Stop and revisit the Python parsing approach if profiler-guided optimization cannot meet the fixed 1 GB target under 30 seconds.
- Do not release exact unique-UA reporting if exhaustion can yield a partial success or any exit code other than `4`.
- Do not release pipeline formats if semantically equivalent terminal/JSON/CSV fixtures disagree.
- Reduce scope rather than adding a database, server, cloud service, or Kubernetes to meet the weekend deadline.

## Traceability

`STRATEGIC_PLAN.md` defines priority and success; `PROJECT_ARCHITECTURE.md` defines exact calculations, module boundaries, CLI, and schemas; `IMPLEMENTATION_PLAN.md` sequences delivery; `CLAUDE_CODE_GUIDE.md` provides step prompts that must preserve this PRD.
