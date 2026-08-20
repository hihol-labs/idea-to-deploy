# Product Requirements Document: Nginx Stream Insights

## 1. Summary

Nginx Stream Insights is a local Python 3.11 CLI that streams standard nginx
combined access logs and reports top client IPs, error-producing URLs, hourly
request distribution, and exact User-Agent diversity. It serves fast incident
triage and shell automation without persistent or networked infrastructure.

## 2. Problem and Goals

Operators often have a large access log but no ready analytics stack. Repeated
grep/awk pipelines are hard to validate and machine-consume, while hosted or
service-based tools are too heavy for an immediate local question.

Goals:

- Process a 1 GB supported log in under 30 seconds on the documented laptop.
- Read incrementally and remain stateless across runs.
- Produce all four required summaries from one pass.
- Offer readable Rich text and stable JSON/CSV pipeline formats.
- Fail explicitly when input has no valid records or exact UA cardinality can
  no longer be guaranteed.

## 3. Non-Goals

- Authentication, accounts, database storage, history, or dashboards.
- HTTP API, daemon, server, cloud service, Docker, or Kubernetes.
- Arbitrary nginx `log_format` support in the MVP.
- GeoIP, bot classification, latency percentiles, live tail-follow mode, or
  approximate cardinality in the MVP.
- Replacing GoAccess or an observability platform for long-term analytics.

## User Stories

### US-01: Analyze a local incident log

As an on-call SRE, I want to analyze one or more local nginx access-log files
with one command so that I can identify dominant clients and traffic shape
during an incident.

**Priority:** P0

**Acceptance criteria:**

- [ ] The command accepts regular files and combines multiple files in argument order.
- [ ] It reads input incrementally rather than loading the complete file.
- [ ] A successful text report contains all four required sections and record totals.
- [ ] Top IPs contain at most 10 entries ordered by count descending, then IP ascending.

### US-02: Find error hot spots

As a platform engineer, I want the URLs responsible for the most 4xx and 5xx
responses so that I can prioritize routing, application, or client failures.

**Priority:** P0

**Acceptance criteria:**

- [ ] Only statuses 400–599 increment the error-URL metric.
- [ ] Query strings and fragments do not split one request path into multiple keys.
- [ ] The report contains at most 10 URLs ordered by count descending, then URL ascending.
- [ ] 2xx/3xx requests still contribute to valid totals and hourly distribution.

### US-03: Understand hourly traffic distribution

As an SRE, I want every hour’s request share as a percentage so that I can see
when traffic was concentrated.

**Priority:** P0

**Acceptance criteria:**

- [ ] The report contains buckets `00` through `23`, including empty hours.
- [ ] Each bucket uses the timestamp/offset in the original line.
- [ ] Each percentage uses exactly `100 × hourly_request_count / total_valid_requests`.
- [ ] The counts across all 24 buckets equal `total_valid_requests`.

### US-04: Measure User-Agent diversity honestly

As a DevOps engineer, I want the exact share of unique User-Agents so that I
can gauge client diversity without receiving a mislabeled approximation.

**Priority:** P0

**Acceptance criteria:**

- [ ] The successful report includes exact unique count and percentage `100 × unique_user_agent_count / total_valid_requests`.
- [ ] The configured positive cardinality ceiling is enforced before adding an excess distinct value.
- [ ] Exhaustion exits 4, writes an actionable error to stderr, and emits no partial report to stdout.

### US-05: Feed results into automation

As a platform engineer, I want JSON or CSV output so that a script can consume
the same report without scraping terminal formatting.

**Priority:** P0

**Acceptance criteria:**

- [ ] `--json` emits the documented versioned JSON schema and valid UTF-8 JSON.
- [ ] `--csv` emits the documented six-column normalized schema with correct quoting.
- [ ] The flags are mutually exclusive, structured stdout contains no ANSI sequences, and invalid combinations exit 2.
- [ ] Text, JSON, and CSV derive from the same immutable report and agree on values.

### US-06: Diagnose imperfect logs

As an on-call SRE, I want malformed records summarized without losing useful
valid data so that a few damaged lines do not block incident triage.

**Priority:** P1

**Acceptance criteria:**

- [ ] Malformed records are skipped, counted, and represented in diagnostics.
- [ ] Diagnostic samples are bounded, escaped, and length-limited.
- [ ] At least one valid record permits success code 0; zero valid records exits 3 with no report.

### US-07: Read rotated gzip logs directly

As an SRE, I want `.gz` inputs read incrementally so that I can avoid a manual
decompression step.

**Priority:** P1

**Acceptance criteria:**

- [ ] Gzip support, when implemented after MVP, preserves all parser, output,
  resource, and exit-code contracts.

### US-08: Analyze custom nginx formats

As a platform owner, I want to configure field extraction for a custom nginx
format so that the tool can work outside standard combined logs.

**Priority:** P2

**Acceptance criteria:**

- [ ] A future design preserves explicit validation and cannot execute log
  content or configuration as code.

## 5. Functional Requirements

### P0 — Must ship

| ID | Requirement |
|---|---|
| FR-01 | Accept one or more local files and stdin as a single incremental stream |
| FR-02 | Parse the documented standard nginx combined format with IPv4/IPv6 and timezone offsets |
| FR-03 | Report top 10 IPs over all valid requests |
| FR-04 | Report top 10 normalized paths over status 400–599 |
| FR-05 | Report 24 hourly count/percentage buckets using `100 × hourly_request_count / total_valid_requests` |
| FR-06 | Report exact unique User-Agent count and percentage with a hard cardinality ceiling |
| FR-07 | Render Rich terminal text by default, versioned JSON with `--json`, or normalized CSV with `--csv` |
| FR-08 | Apply deterministic tie sorting and stable output schemas |
| FR-09 | Preserve the public exit contract: 0 success, 1 I/O/runtime, 2 usage, 3 zero valid records, 4 unique-cardinality exhaustion |
| FR-10 | Count and safely summarize malformed lines while allowing success when at least one line is valid |

### P1 — Should ship after MVP stability

- Incremental gzip input inferred from `.gz`.
- Explicit `--color auto|always|never`, with safe `auto` as the default.
- Additional benchmark fixtures representing realistic cardinality mixes.

### P2 — Could ship later

- Declarative custom `log_format` mappings.
- An explicitly labeled approximate User-Agent cardinality mode.
- Additional report metrics only after schema/versioning review.

## 6. CLI and Output Requirements

The normative command, option, input, output, and exit semantics are in
`PROJECT_ARCHITECTURE.md` under `## CLI Interface`. Product tests must treat
that section and this PRD as one contract. stdout is exclusively report data;
stderr is diagnostics. Broken-pipe termination is quiet. Structured modes are
never colored.

## 7. Non-Functional Requirements

| ID | Requirement | Acceptance evidence |
|---|---|---|
| NFR-01 | Process 1 GB in under 30 seconds | Median of three documented warm-cache benchmark runs on the reference laptop |
| NFR-02 | Stateless, single-process, one-pass processing | Architecture check plus I/O/aggregation tests; no persistent product writes |
| NFR-03 | Bounded unsafe output and honest resource failure | Escaping/length tests and code-4 integration test |
| NFR-04 | Python 3.11 pip installation | Clean-venv wheel smoke test |
| NFR-05 | Core parser/aggregator test coverage at least 90% | Coverage report plus golden fixtures |
| NFR-06 | Deterministic output | Repeated-run golden JSON/CSV/text assertions |
| NFR-07 | No data egress or telemetry | Dependency/source audit and zero network components |

## 8. Assumptions and Dependencies

- Input follows the documented combined format and fits local filesystem or
  stdin workflows.
- The reference laptop and benchmark methodology are recorded with results.
- Exact User-Agent cardinality may consume significant memory; the user can
  raise the ceiling only when the host has capacity.
- Click and Rich versions are constrained by compatible release ranges in the
  package metadata; Python standard-library modules handle CSV, JSON, datetime,
  gzip extension, and counters.

## 9. Release Criteria

- All P0 acceptance criteria pass against the exact candidate.
- The `0/1/2/3/4` exit-code integration matrix passes in all applicable modes.
- Text/JSON/CSV agree on a shared golden fixture.
- A clean Python 3.11 environment installs the wheel and runs the command.
- The documented 1 GB benchmark meets the under-30-second target.
- No critical/high security issue or unresolved data-corruption defect remains.

## 10. Kill and Reassessment Criteria

Pause release and reassess scope if measured Python performance still exceeds
30 seconds after profiling-directed optimizations, if correctness requires
loading complete input, or if exact User-Agent diversity cannot be bounded with
the code-4 contract. Do not add a server, database, cloud service,
multiprocessing architecture, or silent approximation to rescue the deadline;
each would require a new product and architecture decision.

