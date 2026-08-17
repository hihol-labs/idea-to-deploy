# Product Requirements Document: Nginx Stream Analyzer

## Product Summary

Nginx Stream Analyzer gives DevOps/SRE users a fast, local summary of nginx
access logs. It reads one or more files or stdin in a single pass and reports
the ten busiest IPs, ten URLs with the most 4xx/5xx responses, distribution of
valid requests across the 24 hours of day, and distinct User-Agent share. Its
default is colored terminal output; JSON and CSV are stable pipeline formats.

## Goals

1. Produce the four specified metrics correctly and deterministically.
2. Process a supported 1 GB log in under 30 seconds on a documented laptop.
3. Work locally after pip installation with no account or running service.
4. Be safe in shell pipelines through stable schemas, stdout/stderr separation,
   and the complete `0/1/2/3/4` exit-code contract.

## Non-Goals

- Persistent history, database storage, dashboards, alerting, or log search.
- HTTP API, server mode, authentication, multi-user access, or remote upload.
- Cloud deployment, Docker as a requirement, or Kubernetes.
- Arbitrary nginx `log_format` support in the MVP.
- Correlating sessions, geolocating IPs, bot classification, or anomaly detection.
- Approximate results when exact-cardinality capacity is exhausted.

## Personas and Primary Jobs

- **On-call SRE:** “Summarize this incident log before I choose a deeper tool.”
- **DevOps engineer:** “Compare traffic/error shape after a proxy rollout.”
- **Platform engineer:** “Put deterministic nginx summary data into a script.”

## User Stories

### US-01 — Stream local input

As an on-call SRE, I want to pipe a log or name files so that I can analyze
data without copying it into a service.

**Priority:** P0

**Acceptance criteria:**

- [ ] With no file argument, the command lazily reads stdin.
- [ ] One or more regular files are read lazily in command-line order into one report.
- [ ] A literal `-` selects stdin and is accepted at most once.
- [ ] No implementation retains all raw lines in memory or writes input to disk.
- [ ] Unreadable input returns 1; invalid source usage returns 2.

### US-02 — Parse supported nginx records safely

As a DevOps engineer, I want combined/common nginx records parsed consistently
so that malformed data cannot silently become plausible metrics.

**Priority:** P0

**Acceptance criteria:**

- [ ] Combined and common fixtures parse remote address, timestamp, request, status, and bytes; combined also parses User-Agent.
- [ ] IPv4, IPv6, escaped quoted content, `-` body bytes, and numeric timezone offsets are covered.
- [ ] Non-strict mode skips and counts malformed lines while keeping stdout machine-readable.
- [ ] Strict mode stops on the first malformed record and exits 3 without a partial report.
- [ ] Zero valid records exits 3.

### US-03 — See the busiest client IPs

As an on-call SRE, I want the ten client IPs with the most requests so that I
can identify concentrated traffic quickly.

**Priority:** P0

**Acceptance criteria:**

- [ ] Every valid request increments its raw remote-address count once.
- [ ] At most ten rows are ordered by count descending, then IP ascending.
- [ ] Counts are identical in terminal, JSON, and CSV output.

### US-04 — Find URLs producing client/server errors

As a DevOps engineer, I want the ten URLs with the most 4xx/5xx responses so
that I can focus remediation on the largest error sources.

**Priority:** P0

**Acceptance criteria:**

- [ ] Only statuses 400 through 599 inclusive increment this metric.
- [ ] The request target remains raw; query strings and percent escapes are not normalized.
- [ ] At most ten rows are ordered by error count descending, then URL ascending.
- [ ] A log with no 4xx/5xx requests returns an empty top-error list, not an error.

### US-05 — Understand hourly traffic distribution

As a platform engineer, I want a percentage for every hour of day so that I
can spot when traffic is concentrated.

**Priority:** P0

**Acceptance criteria:**

- [ ] Output contains all 24 local log hours `00`–`23`, including zero-count hours.
- [ ] Each percentage uses exactly `100 × hourly_request_count / total_valid_requests`.
- [ ] The hour is taken as written in the offset-aware nginx timestamp; records are not timezone-normalized.
- [ ] Display values use two-decimal round-half-even; counts remain available in JSON/CSV.

### US-06 — Measure User-Agent diversity

As an SRE, I want the share of distinct User-Agent strings so that I have a
simple indicator of client diversity.

**Priority:** P0

**Acceptance criteria:**

- [ ] For combined logs the share is `100 × distinct_nonempty_user_agent_count / total_valid_requests`.
- [ ] Literal `-` is missing and does not add a distinct User-Agent.
- [ ] Common format returns zero distinct/observed counts and a null share.
- [ ] Exceeding the configured exact cardinality ceiling exits 4 without a partial or approximate report.

### US-07 — Read a useful terminal report

As an interactive user, I want concise colored tables so that the result is
easy to scan during an incident.

**Priority:** P0

**Acceptance criteria:**

- [ ] Default output includes summary, both top-ten sections, 24-hour distribution, and User-Agent summary.
- [ ] `--color auto` emits ANSI styling only to a TTY; `always` and `never` override it in terminal mode.
- [ ] Untrusted control characters in displayed keys cannot alter terminal structure.
- [ ] Diagnostics are written to stderr, never mixed into the report.

### US-08 — Consume JSON or CSV in a pipeline

As a platform engineer, I want versioned JSON and regular CSV so that scripts
can consume results without scraping terminal text.

**Priority:** P0

**Acceptance criteria:**

- [ ] `--json` emits one schema-version-1 JSON document and `--csv` emits the documented RFC 4180 table.
- [ ] The two options are mutually exclusive and invalid combinations exit 2.
- [ ] Machine output contains no ANSI sequences or prose diagnostics.
- [ ] Golden tests prove all metric values match terminal mode and ordering is deterministic.

### US-09 — Branch reliably on failures

As a script author, I want stable exit codes so that automation can distinguish
operator mistakes, bad input, and capacity failure.

**Priority:** P0

**Acceptance criteria:**

- [ ] Code 0 means a complete report; code 1 means operational/I/O failure.
- [ ] Code 2 means a CLI usage error; code 3 means log data/strict parse failure.
- [ ] Code 4 means unique-cardinality exhaustion and is never remapped.
- [ ] Exits 1–4 do not emit partial report data on stdout.

### US-10 — Read rotated gzip logs directly

As an operator, I want to pass `.gz` files so that I can avoid an explicit
decompression pipeline.

**Priority:** P2

**Acceptance criteria:** Deferred until after the MVP performance and schema
contracts are stable.

### US-11 — Supply a custom nginx format

As a platform owner, I want to describe my custom `log_format` so that the tool
can analyze nonstandard logs.

**Priority:** P2

**Acceptance criteria:** Deferred; requires a separately designed safe grammar
and compatibility contract.

## Functional Requirements

### P0 — Must ship

| ID | Requirement |
|---|---|
| FR-01 | Install with pip on Python 3.11 and expose `nginx-stream-analyzer` |
| FR-02 | Lazily consume stdin and one or more uncompressed UTF-8 files |
| FR-03 | Parse documented nginx combined and common formats |
| FR-04 | Report deterministic top-10 IP and 4xx/5xx URL counts |
| FR-05 | Report 24 hourly counts and percentages |
| FR-06 | Report exact distinct User-Agent share or a documented null for common logs |
| FR-07 | Emit Rich terminal text, schema-v1 JSON, and long-form CSV |
| FR-08 | Support strict/non-strict parsing and privacy-safe diagnostics |
| FR-09 | Enforce configurable exact cardinality and exit 4 on exhaustion |
| FR-10 | Honor exit codes 0/1/2/3/4 and no partial output on failure |

### P1 — Should ship if the time box allows

| ID | Requirement |
|---|---|
| FR-11 | Aggregate multiple files and stdin in one invocation under the ordering rules |
| FR-12 | Include package/version metadata in help and reports where schema permits |

### P2 — Could follow after MVP

| ID | Requirement |
|---|---|
| FR-13 | Transparently read gzip-compressed rotated logs |
| FR-14 | Safely map user-defined nginx log formats |

## Non-Functional Requirements

| Area | Requirement | Evidence |
|---|---|---|
| Performance | 1 GB supported corpus in under 30 seconds on a documented laptop | Timed installed-wheel benchmark, corpus generation excluded |
| Memory | Peak RSS <= 512 MiB at default cardinality on reference corpus | Recorded peak-RSS benchmark |
| Determinism | Equal-count keys use lexical tie-break; JSON/CSV ordering is stable | Golden and repeated-run tests |
| Correctness | P0 conformance and boundary fixtures pass | pytest suite and coverage >= 90% |
| Portability | Python 3.11 on Linux/macOS; no GNU shell tools at runtime | Clean virtual-environment smoke tests |
| Privacy | No network/write behavior; diagnostics omit raw sensitive records | Source review and subprocess tests |
| Usability | Quick Start produces a report in under 30 seconds after installation | Manual clean-environment check |

## Output and Exit Contracts

`PROJECT_ARCHITECTURE.md` section `CLI Interface` is authoritative for exact
options and schemas. The exit contract is complete: `0` success, `1`
operational/I/O failure, `2` usage error, `3` log-data/strict-parse failure,
and `4` unique-cardinality exhaustion.

Changing JSON keys, CSV columns/order, metric denominators, tie-breaking,
status range, rounding, or exit meanings requires a PRD and schema-version
decision before implementation.

## Dependencies and Assumptions

- Users have Python 3.11 and permission to read the selected logs.
- Supported inputs conform to nginx combined/common grammar, not arbitrary
  custom formats.
- The 1 GB target is measured on local storage; network filesystem performance
  is outside the release gate.
- Exact results are required within the configured key ceiling. Capacity
  exhaustion is explicit rather than silently approximate.

## Release Criteria

- All P0 acceptance criteria and golden outputs pass.
- The built wheel installs in a clean Python 3.11 virtual environment.
- The slowest of terminal-no-color, JSON, and CSV 1 GB benchmark modes is under
  30 seconds on the recorded reference laptop.
- Peak RSS stays within the documented budget on the reference corpus.
- Exit codes 0, 1, 2, 3, and 4 are each demonstrated by subprocess tests.
- No known critical/high security defect remains and user documentation is current.

## Kill Criteria

Stop or explicitly re-scope the MVP rather than shipping if any is true:

- After measurement and profiling, the chosen Python 3.11 single-process
  design cannot analyze the 1 GB reference corpus in under 30 seconds.
- Exact required metrics cannot remain within 512 MiB on representative logs
  at the default key ceiling.
- Combined/common compatibility needs a database, server, network dependency,
  or custom-format engine to be useful.
- Machine-format or exit contracts remain nondeterministic at the end of the
  one-weekend time box.
- Critical/high security or privacy findings cannot be mitigated locally.

## Traceability

| Requirement group | Architecture | Implementation |
|---|---|---|
| FR-01, FR-10 | CLI Interface; Packaging and Runtime | Steps 1, 6, 8 |
| FR-02, FR-03, FR-08 | Inputs; Error/Privacy Boundaries | Step 3 |
| FR-04–FR-06, FR-09 | Metric Definitions; Streaming Algorithm | Step 4 |
| FR-07 | Outputs; ADR-003 | Step 5 |
| Performance and memory | Performance Verification; ADR-001/002 | Step 7 |
