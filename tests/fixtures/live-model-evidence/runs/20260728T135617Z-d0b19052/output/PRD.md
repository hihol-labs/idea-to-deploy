# Product Requirements Document: nginx-log-top

## 1. Product Summary

`nginx-log-top` gives DevOps/SRE engineers a fast, local, reproducible summary of nginx combined access logs. It is a Python 3.11 CLI installed with pip, processes a file or stdin in one pass, and emits colored terminal text by default or pipeline-safe JSON/CSV.

Success means the four required views are correct and deterministic, a 1 GB file is processed in under 30 seconds on a recorded reference laptop, and no database, HTTP service, authentication system, cloud resource, or Kubernetes component is introduced.

## User Stories

### US-1: Stream local or piped logs

As an on-call SRE, I want to analyze a log file or stdin without loading it in full, so that I can inspect gigabyte-scale logs using ordinary shell workflows.

**Priority:** P0

**Acceptance criteria:**

- [ ] `nginx-log-top access.log` and `cat access.log | nginx-log-top -` produce equivalent report data.
- [ ] Empty valid input produces an empty report and exits `0`.
- [ ] A deterministic 1 GB fixture is processed in under 30 seconds on the documented reference laptop.
- [ ] Inspection or instrumentation confirms the implementation does not retain a list of raw log events.

### US-2: Identify busiest client IPs

As a DevOps engineer, I want the ten client IPs with the most requests, so that I can spot abusive or unexpectedly concentrated traffic.

**Priority:** P0

**Acceptance criteria:**

- [ ] The default report contains at most ten IP rows ordered by descending request count.
- [ ] Equal counts are ordered lexicographically by IP.
- [ ] IPv4 and IPv6 addresses present in valid combined-log input are counted as strings without DNS resolution.

### US-3: Identify failing URLs

As a platform developer, I want the ten URLs with the most 4xx/5xx responses, so that I can locate the endpoints driving an incident.

**Priority:** P0

**Acceptance criteria:**

- [ ] Only status codes 400 through 599 contribute to this ranking.
- [ ] The default report contains at most ten URL rows ordered by descending error count, then URL.
- [ ] Query strings remain part of the request target and therefore the URL key.

### US-4: See hourly demand

As an SRE, I want request counts grouped by logged hour, so that I can correlate traffic bursts with incident timing.

**Priority:** P0

**Acceptance criteria:**

- [ ] Every valid request contributes to exactly one hour bucket.
- [ ] Buckets retain the explicit offset from each parsed log timestamp and use `YYYY-MM-DDTHH:00:00±HH:MM`.
- [ ] Different local-hour/offset strings remain separate even when their bucket starts represent the same UTC instant.
- [ ] Output buckets are chronologically ordered.

### US-5: Measure User-Agent diversity

As an SRE, I want the share of unique User-Agents, so that I can quickly distinguish concentrated automated traffic from a diverse request population.

**Priority:** P0

**Acceptance criteria:**

- [ ] The report includes distinct User-Agent count and `distinct / parsed_requests`.
- [ ] The share is `0.0` when there are no parsed requests.
- [ ] Missing User-Agent values normalize to `"(missing)"`.
- [ ] Repeated identical strings count once, with exact case-sensitive comparison.

### US-6: Read an operator-friendly terminal report

As an on-call engineer, I want clear colored terminal tables, so that I can scan findings quickly during triage.

**Priority:** P0

**Acceptance criteria:**

- [ ] With no machine-output flag, stdout contains labeled sections for all four metrics and the summary.
- [ ] Color is enabled only on an appropriate TTY and is disabled by `--no-color` or `NO_COLOR`.
- [ ] Redirected output and stderr diagnostics never inject ANSI codes into JSON or CSV.

### US-7: Compose stable machine output

As an automation author, I want JSON or CSV output with stable schemas and exit codes, so that I can consume the report in pipelines.

**Priority:** P0

**Acceptance criteria:**

- [ ] `--json` emits exactly one valid JSON document matching the schema in `PROJECT_ARCHITECTURE.md`.
- [ ] `--csv` emits RFC 4180-compatible rows with the documented union schema and deterministic section order.
- [ ] `--json` and `--csv` together fail as a usage error with exit code `2`.
- [ ] Machine-readable stdout contains no progress, warnings, or ANSI escape sequences.

### US-8: Control ranking depth and parse strictness

As an advanced operator, I want to choose ranking depth and malformed-line policy, so that I can adapt analysis to an investigation.

**Priority:** P1

**Acceptance criteria:**

- [ ] `--top N` accepts 1–100 and applies to both IP and error-URL rankings.
- [ ] Default lenient mode counts and skips malformed non-empty lines.
- [ ] `--strict` stops on the first malformed line and exits `4`.

### US-9: Analyze compressed logs directly

As an operator, I want gzip auto-detection, so that I can avoid a separate decompression process.

**Priority:** P2

**Acceptance criteria:**

- [ ] Deferred from MVP; if promoted, file and piped gzip behavior must be specified separately.

### US-10: Parse custom nginx formats

As a platform owner, I want a configurable `log_format`, so that non-combined logs can be analyzed.

**Priority:** P2

**Acceptance criteria:**

- [ ] Deferred from MVP; promotion requires an explicit grammar and compatibility plan.

## 3. Functional Requirements

### P0 — Must

| ID | Requirement |
|---|---|
| FR-01 | Accept one optional input path; omitted input or `-` reads stdin |
| FR-02 | Lazily parse nginx combined-format lines into timezone-aware events |
| FR-03 | Skip and count malformed non-empty lines in default mode |
| FR-04 | Compute default top-10 IPs |
| FR-05 | Compute default top-10 request targets for statuses 400–599 |
| FR-06 | Count all valid requests by logged hour |
| FR-07 | Compute exact distinct User-Agent count and share |
| FR-08 | Render colored Rich terminal output by default |
| FR-09 | Render the documented stable JSON object with `--json` |
| FR-10 | Render the documented stable CSV stream with `--csv` |
| FR-11 | Follow the exit-code and stdout/stderr contract in `PROJECT_ARCHITECTURE.md` |
| FR-12 | Install on Python 3.11 through pip with `nginx-log-top` entry point |

### P1 — Should

| ID | Requirement |
|---|---|
| FR-13 | `--top` selects 1–100 ranking rows |
| FR-14 | `--strict` turns malformed input into exit code `4` |
| FR-15 | `--no-color`, `NO_COLOR`, `--version`, and `--help` behave as documented |

### P2 — Could

| ID | Requirement |
|---|---|
| FR-16 | Auto-detect and stream gzip files |
| FR-17 | Support an explicitly designed subset of custom nginx log formats |

## 4. Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-01 | Python 3.11, Click, Rich, dataclasses; pip-installable | wheel install smoke test |
| NFR-02 | 1 GB under 30 seconds on a documented reference laptop | isolated benchmark report |
| NFR-03 | One-pass processing; no raw-event collection | code review plus memory instrumentation |
| NFR-04 | Deterministic ordering and serialization | golden tests repeated across runs |
| NFR-05 | At least 90% package coverage | coverage command |
| NFR-06 | No database, HTTP listener/API, auth, server, cloud, or Kubernetes | dependency/config/static review |
| NFR-07 | No log content execution or network access | security review |
| NFR-08 | Peak memory recorded for the 1 GB benchmark | benchmark report |
| NFR-09 | Normal-profile 1 GiB fixture uses no more than 1.5 GiB peak RSS on BR-1 | benchmark manifest and `/usr/bin/time -v` |
| NFR-10 | Terminal values cannot inject controls or Rich markup | hostile-field golden tests |

## 5. Input and Parsing Contract

The MVP supports nginx combined access-log format only. Required parsed fields are remote address, timestamp with numeric offset, request target, status, and User-Agent. Empty lines are ignored. Invalid UTF-8/read errors are input failures; malformed decoded records follow lenient or strict mode.

A physical line is limited to 1 MiB including its terminator. Oversized records are discarded with bounded reads and follow the malformed-line policy.

The tool does not infer hostnames, geo-locations, sessions, bots, or clients. It treats extracted strings as untrusted data and performs no network requests.

## 6. Output and Compatibility Contract

`PROJECT_ARCHITECTURE.md` under `## CLI Interface` is normative for commands, options, input semantics, output schemas, ordering, stderr use, and exit codes. JSON keys and CSV columns are public interfaces. Additive schema changes require a documented compatibility decision; renaming/removing fields requires a major version.

## 7. Out of Scope

- authentication, accounts, permissions, database, retained history;
- HTTP API, web UI, server mode, dashboards, cloud, containers, Kubernetes;
- log shipping, alerting, tail-follow, and distributed processing;
- access-log mutation, redaction pipeline, geo-IP, bot classification;
- arbitrary nginx formats in MVP;
- Windows-specific shell integration guarantees.

## 8. Analytics and Telemetry

The CLI collects and transmits no telemetry. Product evaluation uses opt-in repository signals and local benchmark/test evidence only. Log content never leaves the caller’s machine through product behavior.

## 9. Release Acceptance

Release is accepted only when:

1. every P0 story and NFR has current recorded evidence;
2. file/stdin, terminal/JSON/CSV, malformed input, and exit codes pass integration tests;
3. the 1 GB benchmark is under 30 seconds on the documented reference laptop;
4. wheel installation and console invocation pass in a clean Python 3.11 environment;
5. architecture, CLI help, README, and schemas agree.

## 10. Kill Criteria

Stop or revise the MVP if the performance target remains unmet after profiling, if correct results require forbidden persistent/service architecture, or if the supported combined format cannot be specified and tested deterministically.

Priorities derive from `STRATEGIC_PLAN.md`; technical decisions derive from `PROJECT_ARCHITECTURE.md`; delivery evidence is assigned in `IMPLEMENTATION_PLAN.md`.
