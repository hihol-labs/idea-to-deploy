# Product Requirements Document: Nginx Stream Report

## 1. Summary

Nginx Stream Report is a local Python 3.11 CLI that turns an nginx combined access-log stream into four exact operational summaries: top client IPs, top 4xx/5xx URLs, hourly request percentages, and unique User-Agent share. It is intended for DevOps/SRE incident triage and automation, works on a file or stdin, and emits colored text by default with JSON and CSV alternatives.

The MVP is open source, costs $0, and is delivered in one weekend. `PROJECT_ARCHITECTURE.md` is authoritative for component and interface design; this PRD is authoritative for user-visible behavior and acceptance criteria.

## 2. Problem and Goals

Engineers often receive a large nginx log before a dashboard exists, while a dashboard is unavailable, or in an environment where uploading logs is inappropriate. Existing platforms are too operationally heavy for a one-off analysis, and ad-hoc shell pipelines are easy to get subtly wrong.

Goals:

- Produce all four required summaries in one local streaming pass.
- Make default output useful to a human and structured modes reliable for pipelines.
- Process a representative 1 GB log in under 30 seconds on the recorded laptop benchmark.
- Fail explicitly on invalid input or unsafe unique cardinality.
- Require no service, credentials, persistence, or network access.

Non-goals include arbitrary nginx formats, live dashboards, historical storage, enrichment, authentication, databases, HTTP APIs, servers, cloud resources, and Kubernetes.

## User Stories

### US-01: Analyze a local incident log

As an on-call SRE, I want to run one command on a local nginx log so that I can see the most active IPs and error-prone URLs during triage.

**Priority:** P0

**Acceptance criteria:**

- [ ] With a readable file containing valid combined-log records, the command exits 0 and shows both top lists.
- [ ] Each list defaults to at most 10 rows, sorted by count descending and key ascending on ties.
- [ ] Error URLs include statuses 400–599 and exclude all other statuses.
- [ ] The input is iterated rather than loaded wholesale.

### US-02: Understand traffic by hour

As a platform engineer, I want a 24-hour request distribution so that I can identify traffic concentration by clock hour.

**Priority:** P0

**Acceptance criteria:**

- [ ] The report contains all hours `00` through `23`, including zero-count hours.
- [ ] Each percentage uses the exact formula `100 × hourly_request_count / total_valid_requests`.
- [ ] Malformed lines are absent from the numerator and denominator.
- [ ] The hour comes from the offset-bearing timestamp as recorded and is not timezone-normalized.

### US-03: Measure User-Agent diversity

As an SRE, I want the number and share of distinct User-Agent strings so that I can quickly spot unusually concentrated or diverse clients.

**Priority:** P0

**Acceptance criteria:**

- [ ] Literal User-Agent strings on valid records are counted exactly and case-sensitively.
- [ ] Share percentage equals `100 × unique_user_agent_count / total_valid_requests`.
- [ ] Exceeding the configured User-Agent cardinality ceiling exits 4 and emits no partial report.

### US-04: Use results in a pipeline

As a DevOps engineer, I want stable JSON and CSV output so that scripts can consume the same metrics without scraping terminal tables.

**Priority:** P0

**Acceptance criteria:**

- [ ] `--json` emits one valid schema-versioned JSON document to stdout with numeric counts and percentages.
- [ ] `--csv` emits the header `section,rank,key,count,percentage` and parseable normalized rows.
- [ ] Structured output has no ANSI control bytes, while warnings remain on stderr.
- [ ] `--json` and `--csv` together are rejected with exit 2.

### US-05: Stream through stdin

As a command-line user, I want to pipe logs into the analyzer so that decompression, remote retrieval, and filtering can remain separate Unix tools.

**Priority:** P0

**Acceptance criteria:**

- [ ] Omitted `INPUT` and `INPUT` equal to `-` both read stdin.
- [ ] The same records produce semantically identical results from stdin and a regular file.
- [ ] The tool does not close a stdin stream it does not own.

### US-06: Trust automation failure signals

As an automation author, I want distinct stable exit codes so that a job can distinguish usage, input, internal, and memory-safety failures.

**Priority:** P0

**Acceptance criteria:**

- [ ] Tests demonstrate all codes: 0 success, 1 internal/output failure, 2 usage error, 3 input/read/parse failure, and 4 unique-cardinality exhaustion.
- [ ] Empty or all-invalid input exits 3.
- [ ] A mixture with at least one valid line exits 0, reports the malformed count to stderr, and excludes malformed lines from metrics.
- [ ] Fatal outcomes emit no partial report.

### US-07: Analyze compressed logs directly

As an operator, I want optional gzip input so that I can avoid a separate decompression process.

**Priority:** P1

**Acceptance criteria:**

- [ ] A future `--gzip` or detected `.gz` input produces the same result as its decompressed bytes.
- [ ] Until implemented, piping `gzip -dc` into stdin is documented as the supported workaround.

### US-08: Adjust ranking depth

As an investigator, I want `--top N` so that I can expand or narrow rankings without changing the metrics.

**Priority:** P1

**Acceptance criteria:**

- [ ] Values from 1 through 1000 are accepted and applied to both rankings.
- [ ] Invalid values exit 2.
- [ ] Default behavior remains top 10.

### US-09: Disable color explicitly

As a user of an unusual terminal, I want `--no-color` so that I can guarantee plain text.

**Priority:** P2

**Acceptance criteria:**

- [ ] No ANSI styling is emitted when `--no-color` is set.

## 4. Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-01 | P0 | Accept exactly one optional file path or stdin and process it with buffered line iteration |
| FR-02 | P0 | Parse the documented nginx combined-log grammar and count malformed lines |
| FR-03 | P0 | Count exact requests by client IP and return deterministic top 10 by default |
| FR-04 | P0 | Count exact request targets for statuses 400–599 and return deterministic top 10 by default |
| FR-05 | P0 | Emit 24 clock-hour buckets with `100 × hourly_request_count / total_valid_requests` |
| FR-06 | P0 | Emit exact distinct User-Agent count and its percentage of valid requests |
| FR-07 | P0 | Default to a colored Rich terminal report with safe untrusted-text rendering |
| FR-08 | P0 | Support mutually exclusive `--json` and `--csv` schemas defined in the architecture |
| FR-09 | P0 | Enforce independent per-dimension unique-key ceilings and exit 4 on exhaustion |
| FR-10 | P0 | Implement the complete exit contract 0/1/2/3/4 and stdout/stderr separation |
| FR-11 | P1 | Support gzip input without changing metric semantics |
| FR-12 | P1 | Support `--top N` in range 1–1000 |
| FR-13 | P2 | Support `--no-color` for text mode |

### Exit-code contract

| Code | Meaning |
|---:|---|
| 0 | Successful report, even when malformed lines were skipped |
| 1 | Unexpected internal failure or output I/O failure |
| 2 | CLI usage error |
| 3 | Input/read/parse failure, including empty or zero-valid-record input |
| 4 | Unique-cardinality exhaustion |

## 5. Non-Functional Requirements

| ID | Requirement | Acceptance measure |
|---|---|---|
| NFR-01 Performance | Process a representative 1 GB log in under 30 seconds | Recorded elapsed wall time on the documented laptop profile |
| NFR-02 Memory | Never retain the complete input; fail before exceeding configured unique-key counts | Streaming test plus boundary tests for every tracked dimension |
| NFR-03 Determinism | Same accepted records/options produce byte-stable JSON/CSV and stable text ordering | Repeat-run golden tests |
| NFR-04 Correctness | Exact counts and formula results; no sampling | Fixture oracle and unit/integration suite |
| NFR-05 Portability | Install and run on supported Python 3.11 environments via pip | Clean-environment wheel smoke test |
| NFR-06 Safety | Log content cannot become Rich markup, a shell command, or evaluated data | Adversarial renderer fixtures and no shell/network calls |
| NFR-07 Maintainability | Typed modules with >=90% core line coverage | mypy, Ruff, pytest coverage gates |

## 6. Output Contract

The default text report presents the total valid and malformed counts, Top IPs, Top Error URLs, all hourly buckets, and User-Agent diversity. JSON and CSV carry the same data and schema described in `PROJECT_ARCHITECTURE.md` under `## CLI Interface`. Percentages in structured output are numbers, not strings with percent signs. Ties are stable. Query strings remain part of URL keys.

Diagnostics never contaminate stdout. Expected diagnostics name the failure category and remediation without printing entire sensitive log lines.

## 7. Scope by Release

### MVP / P0

Streaming file/stdin parser, all four exact metrics, default top 10, colored text, JSON, CSV, malformed-line warning behavior, cardinality guard, full exit codes, package, tests, and benchmark evidence.

### Next / P1

Gzip input and configurable ranking depth, only after the MVP Definition of Done remains satisfied.

### Optional / P2

Explicit no-color override if not already inexpensive within the MVP renderer work.

### Explicitly out of scope

Custom `log_format`, approximate analytics, live tail/follow mode, dashboards, persistence/history, authentication, database, HTTP API, server, cloud, Kubernetes, GeoIP/enrichment, alerting, and telemetry.

## 8. Dependencies and Assumptions

- Python 3.11 is installed on the operator machine.
- The input follows the documented combined-log grammar.
- Click and Rich can be installed from the chosen package source; all other runtime facilities are standard library.
- The 1 GB target is measured against the benchmark profile, not claimed for every storage device or CPU.
- Exact metrics are preferred over silently degraded results; cardinality exhaustion is an explicit failure.

## 9. Release Criteria

- Every P0 story and requirement has passing automated acceptance evidence.
- File and stdin results match across text, JSON, and CSV semantics.
- All five exit codes are exercised by integration tests.
- Core coverage is at least 90%, and Ruff/mypy/package checks pass.
- A clean environment installs the built wheel and runs `nginx-report`.
- The recorded representative 1 GB benchmark completes in under 30 seconds and matches the oracle.
- The exact staged candidate has a current, revalidated Idea to Deploy adjudication receipt.

## 10. Kill and Reconsideration Criteria

Pause release and revisit architecture if either condition holds after targeted profiling:

1. Exact single-process Python 3.11 processing cannot complete the agreed 1 GB fixture in under 30 seconds on the reference laptop.
2. A normal-cardinality 1 GB fixture requires more than 512 MiB peak RSS.

Do not silently sample, merge URLs, approximate User-Agent cardinality, add a database, or introduce a server to evade a criterion. Any such change requires an explicit PRD and architecture decision update first.
