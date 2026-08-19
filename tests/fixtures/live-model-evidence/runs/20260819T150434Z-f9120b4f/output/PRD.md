# Product Requirements Document: nginx-log-insights

## Product Summary

`nginx-log-insights` lets a DevOps/SRE engineer stream a local nginx combined
access log from a file or stdin and receive four exact operational summaries:
top 10 client IPs, top 10 URLs by combined 4xx/5xx count, hourly request
distribution, and unique User-Agent share. Default output is colored terminal
text; JSON and CSV are stable pipeline interfaces.

The MVP is a Python 3.11 pip package using Click, Rich, and dataclasses. It is
stateless, local, and single-process. It has no authentication, database, HTTP
API, server, cloud service, or Kubernetes component.

## Goals

- Produce an incident-oriented report with one command and no infrastructure.
- Process a representative 1 GB log in under 30 seconds on a documented laptop.
- Preserve constant input-buffer memory and fail predictably when exact unique
  aggregation reaches its configured cardinality ceiling.
- Make terminal, JSON, and CSV results semantically consistent and deterministic.

## Non-Goals

- Historical storage, dashboards, alerting, or continuous file following.
- Authentication, multi-user access, database persistence, or an HTTP API.
- Cloud/Kubernetes deployment or any network communication.
- Parsing arbitrary custom nginx `log_format` strings in the MVP.
- Approximate cardinality, sampled rankings, URL normalization, or geolocation.

## User Stories

### US-1: Stream a local log

As an on-call SRE, I want to pass a log path or pipe a log to stdin so that I
can analyze evidence without deploying a service.

Priority: **P0**

Acceptance criteria:

- [ ] `nginx-log-insights access.log` reads incrementally and produces a report.
- [ ] `cat access.log | nginx-log-insights -` produces the same semantic report.
- [ ] The process does not read the complete file into a string/list.
- [ ] An unreadable path emits a diagnostic on stderr and exits 1.
- [ ] An input with no valid records emits no report and exits 3.

### US-2: Identify the busiest client IPs

As an SRE investigating abnormal traffic, I want the ten highest-frequency
client IPs so that I can identify dominant or abusive clients.

Priority: **P0**

Acceptance criteria:

- [ ] At most ten entries are ordered by descending request count.
- [ ] Equal counts are ordered by ascending IP string for reproducibility.
- [ ] All valid statuses contribute to IP counts.

### US-3: Identify failing URLs

As a service owner, I want the ten URLs with the most 4xx/5xx responses so that
I can focus remediation on the most frequent failing routes.

Priority: **P0**

Acceptance criteria:

- [ ] Only status codes 400–599 contribute to error-URL counts.
- [ ] 4xx and 5xx counts are combined per exact logged request target.
- [ ] Query strings remain part of the target.
- [ ] At most ten entries use descending count and ascending URL tie-breaking.

### US-4: See hourly traffic distribution

As an on-call engineer, I want each hour's percentage of valid traffic so that
I can spot time-localized spikes.

Priority: **P0**

Acceptance criteria:

- [ ] Output contains ordered buckets 00–23 using each record's logged offset.
- [ ] Each percentage uses the literal formula `100 × hourly_request_count / total_valid_requests`.
- [ ] Empty hours have count 0 and percentage 0.0.
- [ ] Display rounding is two decimals; aggregation retains unrounded values.
- [ ] Displayed percentages sum to approximately 100%, allowing rounding error.

### US-5: Measure User-Agent diversity

As a platform engineer, I want the share of distinct User-Agents among valid
requests so that I can estimate client diversity or automation concentration.

Priority: **P0**

Acceptance criteria:

- [ ] The distinct count includes the literal `-` value when present as a parsed User-Agent.
- [ ] Share is `100 × unique_user_agents / total_valid_requests` and is labeled as a percentage.
- [ ] A new unique key beyond `--max-unique-keys` produces no partial report and exits 4.

### US-6: Use human-readable terminal output

As an on-call engineer, I want concise colored tables so that I can scan results
quickly in a terminal.

Priority: **P0**

Acceptance criteria:

- [ ] Terminal mode is the default and contains all four metrics plus valid/invalid totals.
- [ ] ANSI color is used only for a TTY unless explicitly disabled.
- [ ] Untrusted log values render literally; Rich markup is not interpreted.

### US-7: Integrate with pipelines

As a platform engineer, I want JSON or CSV output so that I can feed results to
`jq`, spreadsheets, and automation.

Priority: **P0**

Acceptance criteria:

- [ ] `--json` emits exactly one valid UTF-8 JSON document to stdout.
- [ ] `--csv` emits the documented `section,rank,key,count,percentage` schema.
- [ ] Both formats contain all four metrics and no ANSI escape sequences.
- [ ] `--json --csv` is rejected on stderr with exit 2.

### US-8: Diagnose imperfect logs

As an operator, I want malformed records counted and optionally treated as
fatal so that I can choose tolerant triage or strict validation.

Priority: **P1**

Acceptance criteria:

- [ ] Default mode skips malformed lines, reports their count, and succeeds if at least one valid record exists.
- [ ] `--strict` stops at the first malformed line and exits 3.
- [ ] Diagnostics may include line number but never echo the full access-log line.

### US-9: Choose the top-N size

As a repeat operator, I want configurable ranking size so that I can perform
deeper analysis without a second tool.

Priority: **P2**

Acceptance criteria:

- [ ] A future `--top N` positive integer changes both ranking lengths.
- [ ] Omitting it retains the stable top-10 default.

## Functional Requirements

### P0 — Must ship

| ID | Requirement |
|---|---|
| FR-01 | Accept one optional input path, with omitted input or `-` meaning stdin. |
| FR-02 | Parse standard nginx combined-log records incrementally. |
| FR-03 | Count valid and malformed lines without retaining source lines. |
| FR-04 | Compute exact top-10 IPs and exact top-10 4xx/5xx URLs with deterministic ties. |
| FR-05 | Compute 24 hourly count/percentage buckets using `100 × hourly_request_count / total_valid_requests`. |
| FR-06 | Compute exact distinct User-Agent count and percentage share. |
| FR-07 | Render default Rich terminal, JSON, or normalized CSV output. |
| FR-08 | Enforce a positive unique-key ceiling and use the complete `0/1/2/3/4` exit-code contract in `PROJECT_ARCHITECTURE.md`. |
| FR-09 | Install with pip and expose the `nginx-log-insights` console command. |

### P1 — Should ship

| ID | Requirement |
|---|---|
| FR-10 | Support strict parsing with line-number diagnostics. |
| FR-11 | Record a reproducible 1 GB wall-time and peak-RSS benchmark. |
| FR-12 | Publish wheel and source distribution validation instructions. |

### P2 — Could ship after MVP

| ID | Requirement |
|---|---|
| FR-13 | Add configurable top-N while preserving top 10 by default. |
| FR-14 | Add explicit common/custom format definitions without heuristic guessing. |

## Output Requirements

The three renderers consume the same immutable report model. The JSON top-level
fields and normalized CSV schema are defined in `PROJECT_ARCHITECTURE.md` and
are compatibility contracts. Counts are integers; percentages are numbers on a
0–100 scale rounded to two decimals only at serialization. stdout contains only
the requested report; diagnostics go to stderr.

## Exit-Code Requirements

| Code | Required meaning |
|---:|---|
| `0` | Success/help/version |
| `1` | Input/output failure |
| `2` | CLI usage or option/configuration error |
| `3` | Parse/validation failure or zero valid requests |
| `4` | Unique-cardinality exhaustion; no partial report |

No implementation may omit, reuse, or remap code 4.

## Non-Functional Requirements

| Category | Requirement |
|---|---|
| Performance | Representative 1 GB fixture processes in <30 seconds on the recorded reference laptop. |
| Memory | Input buffering is O(1); aggregation memory is O(distinct IPs + distinct error URLs + distinct User-Agents), bounded by `--max-unique-keys`. |
| Compatibility | Runtime and tests support Python 3.11; package installs with pip. |
| Determinism | Same records and options produce byte-stable JSON/CSV ordering. |
| Privacy | No network access, telemetry, persistence, or full-line error echo. |
| Security | Treat all parsed fields as data; never evaluate shell/markup content. |
| Accessibility | Terminal meaning does not depend on color alone; `--no-color` is available. |

## Performance Acceptance Method

Create a deterministic 1 GB fixture of valid nginx combined records outside the
timed interval. From an installed wheel, run terminal output redirected to a
file and separately run JSON output. Record OS, CPU, RAM, Python version,
fixture checksum in the benchmark artifact (not chat), elapsed wall time, and
peak RSS. Both runs must produce valid reports; the slower run must be under 30
seconds. A failed or unrecorded benchmark blocks the performance claim.

## Dependencies and Assumptions

- The input uses nginx combined-log field ordering and a numeric timezone offset.
- Hour buckets use the offset in each record; no timezone conversion is performed.
- Exact request targets are meaningful to the operator even when query strings increase cardinality.
- Python 3.11, Click, and Rich are available through pip.
- `STRATEGIC_PLAN.md` governs scope; `PROJECT_ARCHITECTURE.md` governs technical contracts.

## Kill Criteria

Stop or re-scope the MVP if any is true after the weekend timebox:

- The reproducible 1 GB benchmark remains at or above 30 seconds after profiling
  and one focused optimization pass.
- Exact aggregation exceeds the documented memory budget on the representative
  fixture before the configured unique-key ceiling.
- Combined-log parsing cannot reach 100% correctness on the golden valid/invalid fixtures.
- The solution requires a database, daemon, cloud service, or paid dependency.

## Release Acceptance

All P0 stories, package checks, unit/CLI/output tests, and the measured
performance gate must pass. The exact candidate must satisfy the repository's
active Verification Loop contract. P1 items may be deferred only when they do
not invalidate a P0 acceptance criterion; P2 items are explicitly non-blocking.

