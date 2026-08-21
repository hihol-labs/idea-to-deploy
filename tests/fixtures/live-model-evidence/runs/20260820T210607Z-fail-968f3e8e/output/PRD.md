# Product Requirements Document: nginx-stream-report

## Product Summary

`nginx-stream-report` gives DevOps/SRE users a fast local summary of nginx combined access logs. It is a Python 3.11 CLI installed through pip and designed for regular files and stdin. It is stateless, local, and intentionally has no authentication, database, HTTP service, cloud component, or Kubernetes deployment.

## Goals

- Produce the four required analytics in one streaming pass.
- Process a representative 1 GB log in under 30 seconds on a documented laptop baseline.
- Provide a readable colored terminal report and stable JSON/CSV pipeline formats.
- Make invalid input, operational failures, usage mistakes, and cardinality exhaustion distinguishable through exit codes.
- Deliver an open-source, `$0`, one-weekend MVP.

## Non-Goals

- Persistent history, indexing, dashboards, alerts, or arbitrary queries.
- HTTP API, authentication, accounts, server mode, cloud, Docker, or Kubernetes.
- Custom nginx `log_format` parsing in MVP.
- GeoIP, referrer analysis, bot classification, live tail/follow mode, or approximate metrics.
- Replacement of GoAccess or an observability stack for long-term analytics.

## Personas and Use Cases

1. An on-call SRE pipes a current log into the tool during an error spike and sees which request targets dominate 4xx/5xx responses.
2. A DevOps engineer analyzes rotated files as one dataset to identify high-volume client IPs and daily traffic shape.
3. An analyst writes the JSON or CSV result into a repeatable incident pipeline and branches on the exit code.

## User Stories

### US-1: Analyze a local stream

As an on-call SRE, I want to read a file or stdin in one pass so that I can obtain a report without importing data into another system.

**Priority:** P0

**Acceptance criteria:**

- [ ] With no input path, the command reads nginx combined-format lines from stdin.
- [ ] One or more path arguments are read sequentially as one logical dataset.
- [ ] The process does not load the full file or retain individual parsed entries.
- [ ] A representative 1 GB file completes in under 30 seconds on the documented laptop benchmark.

### US-2: Find highest-volume clients

As an SRE, I want the top 10 IP addresses by valid request count so that I can identify dominant traffic sources.

**Priority:** P0

**Acceptance criteria:**

- [ ] Only successfully parsed requests contribute.
- [ ] At most 10 IPs are emitted with exact counts.
- [ ] Results sort by descending count and ascending value for ties.

### US-3: Find error hotspots

As a DevOps engineer, I want the top 10 request targets producing 4xx or 5xx statuses so that I can focus remediation on the largest error sources.

**Priority:** P0

**Acceptance criteria:**

- [ ] Statuses 400 through 599 inclusive contribute; other statuses do not.
- [ ] The request target includes its query string exactly as parsed.
- [ ] At most 10 targets are emitted with exact counts and deterministic tie ordering.
- [ ] A log with no errors emits an empty top-error list rather than failing.

### US-4: Understand hourly traffic shape

As an operations engineer, I want the percentage of valid requests in each hour so that I can see traffic concentration across a day.

**Priority:** P0

**Acceptance criteria:**

- [ ] All 24 hour buckets from `00` through `23` are emitted, including zero-count hours.
- [ ] For each bucket, the percentage uses the literal formula `100 × hourly_request_count / total_valid_requests`.
- [ ] The hour encoded in the nginx timestamp is used without timezone conversion.
- [ ] Percentages are numeric and rounded consistently to two decimal places.

### US-5: Measure User-Agent diversity safely

As an analyst, I want the share of distinct User-Agent values so that I can quickly assess client diversity without risking uncontrolled memory growth.

**Priority:** P0

**Acceptance criteria:**

- [ ] The report includes the exact distinct User-Agent count.
- [ ] Share equals `100 × unique_user_agents / total_valid_requests`, is numeric, and is rounded to two decimals.
- [ ] The literal `-` User-Agent is treated as an observed value.
- [ ] Inserting a value beyond the configured unique limit emits no partial report and exits 4.

### US-6: Read a terminal-first report

As an interactive user, I want concise colored tables so that the result is easy to scan during an incident.

**Priority:** P0

**Acceptance criteria:**

- [ ] Default output includes summary, IP, error-target, hourly, and User-Agent sections.
- [ ] ANSI color is used only when stdout is a TTY, `NO_COLOR` is absent, and `--no-color` is not set.
- [ ] Untrusted log values are not interpreted as Rich markup or terminal control sequences.

### US-7: Integrate with pipelines

As an automation engineer, I want JSON and CSV modes so that I can pass results to other tools reliably.

**Priority:** P0

**Acceptance criteria:**

- [ ] `--json` emits one valid JSON object and no ANSI sequences.
- [ ] `--csv` emits the documented fixed header and ordered metric rows with standards-compliant quoting.
- [ ] The two options are mutually exclusive and their conflict exits 2.
- [ ] Diagnostics use stderr and the complete report uses stdout.

### US-8: Enforce input quality when required

As an operator validating an export, I want strict malformed-line handling so that silent data loss can fail my pipeline.

**Priority:** P1

**Acceptance criteria:**

- [ ] Default mode counts malformed lines, reports a warning, and succeeds if at least one valid request exists.
- [ ] `--strict` stops on the first malformed line, emits no report, and exits 3.
- [ ] Zero valid requests emits no report and exits 3 in either mode.

### US-9: Read compressed rotations directly

As a DevOps engineer, I want direct gzip input so that I do not need a decompression process in the pipeline.

**Priority:** P1 (post-MVP)

**Acceptance criteria:**

- [ ] A future explicit option reads gzip streams without extracting them to disk.
- [ ] Decompression failures map to operational exit 1.

### US-10: Choose a different ranking length

As an exploratory user, I want a configurable top-N so that I can inspect beyond ten items.

**Priority:** P2

This is intentionally deferred; MVP always uses 10.

## Functional Requirements

### P0 — Must ship

- FR-1: Parse the conventional nginx combined access-log grammar, including quoted request, referrer, and User-Agent fields.
- FR-2: Count total, valid, and invalid physical lines.
- FR-3: Compute exact top-10 IP and 4xx/5xx request-target rankings with deterministic ties.
- FR-4: Emit 24 hourly counts and percentages, where each percentage is `100 × hourly_request_count / total_valid_requests`.
- FR-5: Compute exact distinct User-Agent count/share up to the configured limit and exit 4 on exhaustion.
- FR-6: Render default Rich terminal text, JSON, or CSV from one report model.
- FR-7: Support file paths, multiple files, and stdin.
- FR-8: Implement the `0/1/2/3/4` exit contract from the architecture.
- FR-9: Never emit a partial JSON/CSV report after a processing failure.

### P1 — Should follow MVP

- FR-10: Strict malformed-line mode.
- FR-11: Direct gzip input.

Strict mode is planned in the initial architecture because it is small and improves validation, but it may be cut before the P0 release without changing default behavior.

### P2 — Could add

- FR-12: Configurable ranking length with a safe positive maximum.

## CLI and Output Contract

The authoritative interface, schemas, stderr rules, and option definitions are in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md#cli-interface). The complete exit contract is:

| Exit | Contract |
|---:|---|
| `0` | Successful complete report |
| `1` | Operational I/O/output failure |
| `2` | Usage or option error |
| `3` | Data-quality failure or zero valid requests |
| `4` | Unique-cardinality exhaustion |

## Data Quality Requirements

- Invalid lines never contribute partially to metrics.
- Replacement decoding keeps line boundaries stable; parsing determines validity.
- Default permissive behavior reports invalid-line count and warns on stderr.
- Diagnostics identify source and line number but do not echo raw log content.
- No valid input is a failure rather than an all-zero success report.

## Performance and Quality Requirements

- NFR-1: Under 30 seconds for the representative 1 GB benchmark on a documented laptop using Python 3.11.
- NFR-2: Input is processed in one pass; individual entries are not accumulated.
- NFR-3: User-Agent cardinality is checked before growth beyond its configured limit.
- NFR-4: Parser/aggregator branch coverage is at least 90%; all public CLI exits have end-to-end tests.
- NFR-5: Ranking and serialization are deterministic for identical logical input.
- NFR-6: No network access, telemetry, persistent product data, or secret configuration.
- NFR-7: Wheel installation and execution succeed in a clean Python 3.11 virtual environment.

## Release Acceptance

The P0 release is acceptable only when all P0 stories pass, the exact CLI contract is snapshot-tested, the clean-wheel golden flow passes, and the 1 GB benchmark meets target. The implementation evidence and commands are defined in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## Kill Criteria

Stop or explicitly re-scope if profiling cannot achieve the 1 GB target on the agreed baseline, exact User-Agent share cannot be protected by the exit-4 cardinality boundary, or a database/service becomes necessary to satisfy P0. Do not silently relax the metric, performance target, or architecture.
