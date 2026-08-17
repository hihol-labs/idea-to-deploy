# Product Requirements Document: nginx-stream-stats

## Product Summary

`nginx-stream-stats` is a local Python 3.11 command-line tool that converts an
nginx combined access-log stream into a concise operational report. It targets
DevOps and SRE users who need immediate traffic and error signals without
deploying or maintaining a log platform.

## Problem Statement

During incident triage, operators often have an nginx log but no prepared
dashboard. Shell pipelines are quick but fragile, and full analytics platforms
are costly to deploy for a one-off local question. The product must produce the
same exact four metric families from files and stdin, remain pipeline-safe, and
process a representative 1 GB log in under 30 seconds on a documented laptop.

## Goals

- Analyze combined-format logs in one pass without retaining raw records.
- Report top 10 IPs, top 10 error URLs, 24 hourly percentages, and unique
  User-Agent share with deterministic semantics.
- Serve humans through colored Rich text and automation through JSON and CSV.
- Install through pip and behave predictably through exit codes `0/1/2/3/4`.
- Remain local, stateless, open source, and free to operate.

## Non-Goals

- Authentication, accounts, database storage, HTTP API, server mode, cloud
  deployment, Docker, Kubernetes, or remote log collection.
- Dashboards, HTML reports, queries across runs, live screen refresh, or tailing
  file rotation directly.
- Arbitrary nginx `log_format` support in the MVP.
- GeoIP, bot detection, latency percentiles, bandwidth accounting, or alerting.
- Silent approximate cardinality when exact aggregation exhausts its bound.

## User Stories

### US-1: Stream local logs

As an on-call SRE, I want to analyze a file or piped nginx combined log so that
I can obtain a report wherever the log already resides.

**Priority:** P0

**Acceptance criteria:**

- [ ] `nginx-stream-stats access.log` and `cat access.log | nginx-stream-stats`
  produce semantically identical reports.
- [ ] Input is consumed incrementally and no raw-record collection grows with
  the number of lines.
- [ ] A missing/unreadable input or a stream with zero valid requests exits 3,
  writes a concise diagnostic to stderr, and leaves stdout empty.
- [ ] A representative 1 GB fixture completes in under 30 seconds on the
  documented laptop baseline.

### US-2: Identify dominant client IPs

As an incident responder, I want the top 10 client IPs so that I can spot
traffic concentration or abusive sources.

**Priority:** P0

**Acceptance criteria:**

- [ ] Counts include every valid request and use `remote_addr` exactly as logged.
- [ ] At most 10 rows are returned, ordered by count descending and IP string
  ascending for equal counts.
- [ ] IPv4 and IPv6 fixtures are accepted and counted independently.

### US-3: Identify failing URLs

As a service operator, I want the top 10 URL paths producing 4xx/5xx responses
so that I can prioritize broken or abused routes.

**Priority:** P0

**Acceptance criteria:**

- [ ] Only status codes 400 through 599 contribute to the metric.
- [ ] Query strings are removed; percent encoding and trailing slashes are
  preserved.
- [ ] 4xx and 5xx counts are combined per path, with at most 10 deterministic
  results ordered by count descending then path ascending.

### US-4: Understand hourly traffic

As an SRE, I want request distribution by hour so that I can identify time
concentration in the log's own recorded timezone.

**Priority:** P0

**Acceptance criteria:**

- [ ] Output always contains buckets `00` through `23` in ascending order.
- [ ] Every percentage uses the literal formula
  `100 × hourly_request_count / total_valid_requests`, not an unscaled fraction.
- [ ] Percentages are serialized to six decimal places and their unrounded sum
  is 100% within floating-point tolerance.
- [ ] The hour is taken from each timestamp as logged; records are not converted
  to the machine's timezone.

### US-5: Measure User-Agent diversity safely

As a DevOps engineer, I want the share of unique User-Agent values so that I
can quickly estimate client diversity without risking unbounded memory.

**Priority:** P0

**Acceptance criteria:**

- [ ] The tool reports exact distinct User-Agent count and
  `100 × unique_user_agent_count / total_valid_requests`.
- [ ] The nginx placeholder `-` is one literal distinct value.
- [ ] If any exact aggregation would exceed `--max-cardinality`, processing
  stops with exit code 4, a stderr diagnostic, and empty stdout.
- [ ] The tool never substitutes an approximate result without explicit future
  product approval.

### US-6: Use human-readable terminal output

As an on-call engineer, I want concise colored tables so that I can scan a
report quickly during an incident.

**Priority:** P0

**Acceptance criteria:**

- [ ] Default output presents totals, top IPs, top error URLs, all hours, and
  User-Agent metrics using Rich.
- [ ] Color is automatic for TTY stdout, absent when redirected, and controllable
  with `--color/--no-color`.
- [ ] Log-derived strings are rendered as data, not Rich markup or terminal
  control instructions.

### US-7: Integrate with pipelines

As a platform engineer, I want stable JSON and CSV so that scripts can consume
the same metrics without scraping terminal output.

**Priority:** P0

**Acceptance criteria:**

- [ ] `--json` emits one schema-versioned JSON object and `--csv` emits one
  RFC 4180 long-form table matching `PROJECT_ARCHITECTURE.md`.
- [ ] `--json` and `--csv` are mutually exclusive and invalid use exits 2.
- [ ] Machine formats contain no ANSI sequences or diagnostic text on stdout.
- [ ] Deterministic input produces byte-stable JSON and CSV apart from the
  platform-standard final newline defined by golden tests.

### US-8: Detect malformed input

As an automation owner, I want a lenient default and strict opt-in so that I can
choose between best-effort incident analysis and validation gates.

**Priority:** P0

**Acceptance criteria:**

- [ ] Lenient mode skips malformed lines, reports their count, and succeeds if
  at least one valid request exists.
- [ ] `--strict` stops on the first malformed line with exit code 3.
- [ ] Diagnostics identify the line number and reason but never echo the raw log
  line or sensitive query data.
- [ ] All exit codes `0/1/2/3/4` match the architecture contract.

### US-9: Analyze compressed archives

As an SRE, I want `.gz` input detection so that I can analyze rotated logs
without a separate decompression command.

**Priority:** P1

**Acceptance criteria:**

- [ ] A `.gz` path streams through the same parser without extracting to disk.
- [ ] Corrupt gzip content exits 3 with empty stdout.
- [ ] File/stdin semantics remain unchanged; compressed stdin can still be
  composed through `gzip -dc`.

### US-10: Choose the ranking length

As an analyst, I want a bounded `--top N` option so that I can inspect more or
fewer ranked items while keeping the default at 10.

**Priority:** P2

**Acceptance criteria:**

- [ ] Default output remains top 10 and schemas remain backward compatible.
- [ ] Invalid or unsafe values exit 2.

### US-11: Parse custom log formats

As an nginx administrator, I want a declarative format option so that I can
analyze installations that do not use combined format.

**Priority:** P2

**Acceptance criteria:**

- [ ] Any future format language is specified and security-reviewed before
  implementation.
- [ ] Combined format remains the default and all P0 fixtures remain compatible.

## Functional Requirements

### P0 — Must ship

| ID | Requirement |
|---|---|
| FR-01 | Accept one path, omitted input, or `-`; omitted/`-` reads stdin incrementally |
| FR-02 | Parse nginx combined format and distinguish malformed from valid lines |
| FR-03 | Count all valid requests per exact client IP and return deterministic top 10 |
| FR-04 | Count statuses 400–599 by normalized URL path and return deterministic top 10 |
| FR-05 | Return 24 hour buckets using `100 × hourly_request_count / total_valid_requests` |
| FR-06 | Return exact unique User-Agent count and percentage share |
| FR-07 | Enforce a positive per-domain cardinality bound and exit 4 on exhaustion |
| FR-08 | Render Rich text by default and stable schema-versioned JSON/CSV on request |
| FR-09 | Support lenient and `--strict` malformed-line behavior |
| FR-10 | Implement the complete `0/1/2/3/4` exit-code contract without remapping |
| FR-11 | Install on Python 3.11 through pip with a console entry point |

### P1 — Should ship after MVP

| ID | Requirement |
|---|---|
| FR-12 | Transparently stream gzip file-path input without temporary extraction |

### P2 — Could ship

| ID | Requirement |
|---|---|
| FR-13 | Allow a safely bounded ranking length while preserving default top 10 |
| FR-14 | Support explicitly specified additional nginx log formats |
| FR-15 | Add property-based parser tests if they materially improve defect discovery |

## Non-Functional Requirements

| Area | Requirement |
|---|---|
| Performance | Representative 1 GB input completes in <30 seconds on a documented laptop baseline |
| Memory | Raw-line memory is O(1); aggregate cardinality is bounded and exhaustion is explicit |
| Correctness | Exact counts, deterministic ties, 24 buckets, and shared metrics across all renderers |
| Compatibility | Python 3.11; Linux/macOS supported; pure-Python wheel installable via pip |
| Security | No network, persistence, shell execution, unsafe Rich markup, or raw malformed-line echo |
| Accessibility | Text remains comprehensible without color; `NO_COLOR` and `--no-color` work |
| Maintainability | Parser, aggregator, report model, and renderers have one-way dependencies and tests |
| Observability | Concise stderr diagnostics and malformed totals; no progress noise in pipeline stdout |

## Output and Exit Contract

The authoritative commands, fields, ordering, schemas, and errors live under
`PROJECT_ARCHITECTURE.md` → `## CLI Interface`. Every delivery step must
preserve codes: `0` success; `1` unexpected runtime/output failure; `2` CLI
usage/configuration error; `3` input/log-data error; `4` unique-cardinality
exhaustion. No guide or implementation may omit or remap code 4.

## Dependencies and Assumptions

- Python 3.11 and pip are present on the operator's machine.
- Input uses nginx combined format and is readable by the invoking OS user.
- The <30-second goal is evaluated on a named, representative laptop and local
  storage; network filesystem behavior is not a release target.
- Product decisions and priorities in `STRATEGIC_PLAN.md` are approved for this
  one-weekend scope.

## Release Criteria

- Every P0 story passes its acceptance criteria.
- Unit/integration tests cover parser, aggregate formulas, schemas, all output
  modes, and exit codes `0/1/2/3/4`.
- The 1 GB release benchmark completes under 30 seconds and records environment,
  fixture, wall time, and peak RSS.
- A clean Python 3.11 virtual environment can build, install, execute help, and
  analyze a fixture without accessing the network after dependencies install.
- README and CLI help agree with this PRD and `PROJECT_ARCHITECTURE.md`.

## Kill Criteria

Pause or re-scope release if any of these remains true at the end of the planned
weekend:

- Representative 1 GB performance is 30 seconds or slower after one measured,
  profiled optimization pass.
- Exact User-Agent tracking cannot stay within the documented cardinality
  boundary and exit safely with code 4.
- Combined-format parsing produces known silent miscounts on the acceptance
  corpus.
- JSON/CSV require a server, database, or stateful staging layer to remain
  usable; that would invalidate the product premise.
- Completing P0 requires paid infrastructure or expands beyond the $0 budget.

P1/P2 items are dropped before any P0 acceptance criterion is weakened.
