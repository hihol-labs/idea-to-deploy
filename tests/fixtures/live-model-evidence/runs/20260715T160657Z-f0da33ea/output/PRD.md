# Product Requirements Document: Nginx Stream Analytics CLI

## 1. Product Summary

Nginx Stream Analytics CLI gives DevOps/SRE engineers four exact summaries from a local nginx combined access log without deploying or maintaining infrastructure. It consumes a file or stdin once, prints colored terminal text by default, and supports stable JSON and CSV for pipelines.

The MVP is a pip-installable Python 3.11 package delivered in one weekend at $0 infrastructure cost. Architecture and non-goals are defined in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md).

## 2. Problem and Goals

During an incident, engineers often have only an access log and a shell. Ad hoc commands become difficult to audit when quoted fields, multiple metrics, malformed lines, and machine-readable output are involved; full analytics stacks are disproportionate for a one-off local investigation.

Goals:

- Produce the top 10 client IPs by request count.
- Produce the top 10 request targets whose responses are 4xx or 5xx.
- Count successfully parsed requests in each logged local hour, `00` through `23`.
- Report distinct non-empty User-Agent count and its share of parsed requests.
- Work with files and stdin and keep stdout safe for pipelines.
- Process the defined 1 GB benchmark in under 30 seconds on a documented laptop.

## 3. Non-goals

- Authentication or multi-user access.
- Persistent storage, database, historical query, or incremental state.
- HTTP API, daemon, server, web UI, cloud service, containers, or Kubernetes.
- Arbitrary nginx formats in version 0.1.
- GeoIP, bandwidth reports, bots, referrers, live dashboards, or alerting.
- Guaranteed bounded memory under arbitrary key cardinality; the MVP is exact.

## 4. Users and Use Cases

Primary users are on-call SREs, platform/DevOps engineers, and service owners. Core uses are rapid post-incident inspection, piping structured metrics into automation, and validating traffic/error hypotheses without moving logs off the laptop.

## 5. Definitions

| Term | Definition |
|---|---|
| Parsed request | A line valid under the documented nginx combined-format contract |
| Client IP | Exact `$remote_addr` string, including IPv6 form as logged |
| Error URL | Exact request target, including query string, for status 400–599 |
| Hour | Two-digit hour in `$time_local`; no timezone conversion |
| Unique User-Agent | Distinct, non-empty `$http_user_agent` string among parsed requests |
| Unique User-Agent share | `unique User-Agent count / parsed request count × 100`, or `0.0` when no request parses |
| Deterministic tie | Equal counts order by key ascending |

## 6. User Stories

### US-1 — Stream a local log

As an on-call SRE, I want to process a file or stdin without loading the full log, so that I can inspect a large log locally.

**Priority:** P0

**Acceptance criteria:**

- [ ] Omitting `LOGFILE` and passing `-` both read stdin; a path reads that file.
- [ ] The implementation iterates line-by-line and does not retain parsed request records.
- [ ] A missing or unreadable file yields a concise stderr message, no report on stdout, and exit 1.
- [ ] The documented 1 GB fixture completes in under 30 seconds on the named reference laptop.
- [ ] The default 250,000 combined-unique-key guard fails before the next unique insertion with a concise stderr diagnostic and exit 1.

### US-2 — Identify top client IPs

As an SRE, I want the ten highest-volume client IPs, so that I can identify dominant traffic sources.

**Priority:** P0

**Acceptance criteria:**

- [ ] Every successfully parsed line increments its exact IP once.
- [ ] At most ten entries are returned by count descending, then IP ascending.
- [ ] IPv4 and IPv6 strings are supported without normalization.

### US-3 — Identify failing URLs

As a service owner, I want the ten request targets with the most 4xx/5xx responses, so that I can focus failure investigation.

**Priority:** P0

**Acceptance criteria:**

- [ ] Only statuses 400 through 599 contribute.
- [ ] The exact logged target, including query string, is the grouping key.
- [ ] At most ten entries are returned by count descending, then target ascending.

### US-4 — See hourly distribution

As an incident responder, I want request counts for each hour, so that I can see when load occurred.

**Priority:** P0

**Acceptance criteria:**

- [ ] The report always contains 24 ordered buckets `00`–`23`, including zeroes.
- [ ] Each parsed request increments the hour in its logged timestamp exactly once.
- [ ] Timestamps are not converted to the workstation timezone.

### US-5 — Measure User-Agent diversity

As a DevOps engineer, I want the exact number and share of unique User-Agent strings, so that I can estimate client diversity.

**Priority:** P0

**Acceptance criteria:**

- [ ] Duplicate non-empty values count once; empty values do not enter the distinct set.
- [ ] Share uses parsed request count as denominator and is zero for empty input.
- [ ] JSON exposes the unrounded numeric value; terminal formatting may round for display.

### US-6 — Consume reports in pipelines

As a platform engineer, I want stable JSON and CSV modes, so that automation does not scrape terminal tables.

**Priority:** P0

**Acceptance criteria:**

- [ ] `--json` returns one schema-versioned JSON document matching Architecture section 9.
- [ ] `--csv` returns normalized rows with columns `schema_version,metric,rank,key,count,value`.
- [ ] `--json` and `--csv` together fail as a usage error with exit 2.
- [ ] Structured stdout contains no color or diagnostics; warnings go to stderr or structured summary fields.

### US-7 — Understand malformed input

As an SRE, I want corrupt lines counted and an optional strict failure, so that I can judge report completeness.

**Priority:** P1

**Acceptance criteria:**

- [ ] Default mode skips malformed lines and reports total, parsed, and skipped counts.
- [ ] `--strict` stops at the first malformed line, identifies its line number on stderr, and exits 2.
- [ ] Log content is not dumped in error messages.

### US-8 — Support custom log formats

As a platform engineer, I want a configurable field template, so that I can analyze non-combined nginx logs.

**Priority:** P2

**Acceptance criteria:**

- [ ] A future format option validates that every metric-required field is present.
- [ ] Invalid templates fail before reading input.

### US-9 — Bound extreme-cardinality memory

As an SRE analyzing adversarial traffic, I want an explicitly approximate mode, so that I can trade accuracy for bounded memory.

**Priority:** P2

**Acceptance criteria:**

- [ ] Approximation is opt-in and output declares algorithm/error bounds.
- [ ] Exact mode remains the default and never silently degrades.

## 7. Functional Requirements

### P0 — Must ship

| ID | Requirement |
|---|---|
| FR-01 | Accept a combined-format file, `-`, or omitted path for stdin |
| FR-02 | Parse valid lines and aggregate without retaining all requests |
| FR-03 | Compute exact top IP, top 4xx/5xx target, hourly, and User-Agent metrics |
| FR-04 | Render safe Rich terminal text by default with TTY-aware color |
| FR-05 | Render deterministic schema-versioned JSON |
| FR-06 | Render deterministic normalized CSV |
| FR-07 | Keep diagnostics off structured stdout and implement documented EPIPE/non-EPIPE exit codes |
| FR-08 | Install on Python 3.11 through pip with `nginx-stats` console script |
| FR-09 | Enforce a configurable default 250,000 combined-unique-key safety guard without approximation |

### P1 — Should ship after P0

| ID | Requirement |
|---|---|
| FR-10 | Count malformed lines in default mode and expose `--strict` |
| FR-11 | Honor `NO_COLOR` and `--no-color` |
| FR-12 | Publish recorded warm/cold benchmark and peak-memory evidence |

### P2 — Could follow

| ID | Requirement |
|---|---|
| FR-13 | Configurable nginx log format |
| FR-14 | Optional path-only URL grouping |
| FR-15 | Explicit approximate bounded-memory mode |

## 8. Non-functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-01 | 1 GB fixture completes in <30 seconds on recorded laptop | `/usr/bin/time -v` benchmark |
| NFR-02 | Peak RSS remains <250 MB on the reference corpus | Same benchmark output |
| NFR-03 | Parser/aggregator/renderers have >=90% branch coverage | pytest coverage gate |
| NFR-04 | Results and row ordering are deterministic | Golden output tests repeated twice |
| NFR-05 | Log-derived text cannot become Rich markup or executable behavior | Adversarial renderer tests |
| NFR-06 | Python 3.11 is the supported runtime floor | Clean environment install/test |
| NFR-07 | The runtime requires no network and creates no persistent state | Integration test plus architecture review |

## 9. CLI and Output Acceptance

The CLI syntax, schemas, and exit codes in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) are normative. Backward-incompatible JSON/CSV changes require a new `schema_version`. Human terminal layout may evolve if all data remains present and no-color output remains readable.

## 10. Success Metrics

Release success requires all P0 criteria, the performance and memory gates, installability from a wheel, no high-severity review findings, and zero known structured-output regressions. Longer-term adoption KPIs are in [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md).

## 11. Kill Criteria

Pause release and revise the spec if correctness-preserving profiling cannot meet the 1 GB/30 s gate, reference peak RSS exceeds 250 MB because realistic key cardinality is too high, or JSON/CSV cannot pass golden compatibility tests. Do not solve a failure by adding a hidden database/service or silently returning approximate results.

## 12. Release Scope Traceability

| Story | Requirements | Implementation steps |
|---|---|---|
| US-1 | FR-01, FR-02, FR-08, FR-09 | 1, 3, 8, 9 |
| US-2–US-5 | FR-03 | 2, 4, 8 |
| US-6 | FR-05–FR-07 | 5, 6, 9 |
| US-7 | FR-10 | 3, 7 |
| US-8–US-9 | FR-13, FR-15 | Deferred P2 |
