# Product Requirements Document: nginx-log-report

## 1. Purpose

Give DevOps/SRE engineers a trustworthy, zero-setup overview of a local nginx combined access log through one pip-installed command. The MVP produces top client IPs, top error URLs, hourly traffic distribution, and exact User-Agent diversity as colored text, JSON, or CSV.

## 2. Goals and Non-Goals

### Goals

- Analyze a file or stdin in one streaming pass.
- Produce the four specified reports with deterministic semantics.
- Support human terminals and stable automation formats.
- Process an exactly 1,000,000,000-byte reference log in under 30 seconds on a documented laptop.
- Remain local, stateless, open source, and free to operate.

### Non-Goals

- Authentication, authorization, accounts, or telemetry.
- Database, retained history, index, cache, or cross-run state.
- HTTP API, server, dashboard, cloud service, Docker, or Kubernetes.
- General-purpose nginx configuration parsing or arbitrary custom `log_format` in MVP.
- Live tail/follow output in MVP.

## 3. Users and Use Cases

Primary users are on-call SREs, platform engineers, and developer/operators. They use the tool during incident triage, post-event inspection, and shell automation where deploying a full log analytics stack is too slow or expensive.

## User Stories

### US-1: Identify dominant client IPs

As an on-call SRE, I want the ten client IPs with the most requests so that I can quickly spot dominant or suspicious traffic sources.

**Priority:** P0

**Acceptance criteria:**

- [ ] Every valid request increments its exact logged client IP.
- [ ] At most ten results are sorted by count descending, then IP ascending for ties.
- [ ] Text, JSON, and CSV express the same IP/count values.

### US-2: Find URLs producing errors

As a service owner, I want the ten URLs with the most 4xx/5xx responses so that I can focus investigation on failing routes.

**Priority:** P0

**Acceptance criteria:**

- [ ] Statuses 400–599 inclusive contribute; all others do not.
- [ ] The exact raw logged request-target bytes, including query string, are the ranking key.
- [ ] At most ten results sort by error count descending, then URL ascending.

### US-3: See hourly request distribution

As an SRE, I want request counts for each logged hour so that I can see traffic concentration and gaps.

**Priority:** P0

**Acceptance criteria:**

- [ ] The report always contains hours 00 through 23, including zero-count hours.
- [ ] Each valid request increments the hour encoded in its nginx timestamp and offset.
- [ ] Counts sum to the number of valid requests.

### US-4: Measure User-Agent diversity

As a platform engineer, I want the share of distinct non-empty User-Agent strings relative to valid requests so that I can gauge client diversity or automation patterns.

**Priority:** P0

**Acceptance criteria:**

- [ ] Exact, non-empty User-Agent byte sequences are counted distinctly; invalid UTF-8 bytes do not collapse.
- [ ] Share equals `unique User-Agents / valid requests × 100` and is rounded to two decimals only for display.
- [ ] The output labels this as a diversity ratio and reports both unique count and percentage.

### US-5: Use reports in pipelines

As a platform engineer, I want stable JSON and CSV modes so that I can feed results to `jq`, spreadsheets, or automation without scraping terminal tables.

**Priority:** P0

**Acceptance criteria:**

- [ ] `--json` emits one schema-version-1 JSON document and a trailing newline.
- [ ] `--csv` emits the documented five-column RFC 4180 schema.
- [ ] Modes are mutually exclusive, never contain ANSI, and keep diagnostics on stderr.

### US-6: Trust partial-input diagnostics

As an operator, I want malformed records disclosed without losing valid results so that I know whether a report is representative.

**Priority:** P0

**Acceptance criteria:**

- [ ] Malformed lines are skipped and counted without aborting otherwise valid input.
- [ ] Metadata contains total, valid, and malformed counts.
- [ ] Input with zero valid records exits 4 and does not present a successful report.

### US-7: Adjust ranking depth

As an investigator, I want to set the number of ranked results so that I can expand an investigation beyond ten entries.

**Priority:** P1

**Acceptance criteria:**

- [ ] `--top N` accepts 1–1000 and applies to both ranked reports.
- [ ] Omitting the option retains the required top-10 behavior.

### US-8: Tail a growing log

As an on-call engineer, I want a follow mode with periodic snapshots so that I can watch an active incident.

**Priority:** P2

**Acceptance criteria:** Deferred until the final-snapshot and structured-output behavior is separately specified.

## 5. Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-1 | P0 | Accept one optional `PATH`; omitted or `-` reads stdin lazily |
| FR-2 | P0 | Parse the documented nginx combined format and count skipped malformed lines |
| FR-3 | P0 | Compute deterministic top-10 IP request counts |
| FR-4 | P0 | Compute deterministic top-10 URL counts for statuses 400–599 |
| FR-5 | P0 | Compute all 24 logged-hour request buckets |
| FR-6 | P0 | Compute exact unique non-empty UA count and diversity ratio |
| FR-7 | P0 | Render colored Rich text by default, with auto/no/forced color behavior |
| FR-8 | P0 | Emit the versioned JSON contract defined in architecture |
| FR-9 | P0 | Emit the long-form CSV contract defined in architecture |
| FR-10 | P0 | Enforce stdout/stderr and exit-code contracts |
| FR-11 | P1 | Support configurable top N from 1 to 1000 |
| FR-12 | P2 | Add live follow only after a separate output lifecycle design |

## 6. Non-Functional Requirements

| ID | Requirement | Acceptance measure |
|---|---|---|
| NFR-1 Performance | Process exactly 1,000,000,000 bytes under 30 seconds and <=2.0 GiB RSS | Median of three runs on the frozen representative corpus and documented laptop |
| NFR-2 Streaming | Never read the entire input into memory | IO instrumentation/test and code review show incremental iteration |
| NFR-3 Reliability | Expected failures have deterministic codes and no traceback | CLI integration tests cover codes 0, 2, 3, 4, and 130 |
| NFR-4 Security | Treat every log field as untrusted display data | Control/markup tests; no shell, eval, network, or Rich markup interpretation |
| NFR-5 Portability | Install and run on supported Python 3.11 environments | Clean wheel-install smoke test on Linux; other OS support documented from evidence |
| NFR-6 Determinism | Same records and options yield equivalent values in all formats | Golden and cross-renderer tests |
| NFR-7 Quality | Maintain useful automated coverage | Overall line coverage >=85%, higher on parser/aggregator hot core |

## 7. Input, Output, and Error Rules

The exact command, options, JSON/CSV schemas, and exit codes are normative in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md#cli-interface). If this PRD and architecture diverge technically, architecture wins and this PRD must be reconciled before implementation.

Malformed lines are recoverable when at least one valid record exists. Structured output metadata discloses their count; bounded examples are stderr-only. Unreadable input, no valid records, interruption, and internal failure follow the architecture exit table.

## 8. Scope Priorities

P0 maps to Must, P1 to Should, and P2 to Could in [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md). The P0 release boundary includes all four reports, all three output modes, streaming input, diagnostics, and deterministic CLI behavior. No Won't item may be pulled into the MVP without updating the scope lock and all four planning documents.

## 9. Analytics and Privacy

The CLI sends no analytics and makes no network calls. Logs may contain personal or sensitive operational data; all processing remains local and results go only to user-selected stdout/stderr destinations. The tool retains nothing after process exit.

## 10. Release Acceptance

Release requires all P0 story criteria, packaging smoke tests, coverage/static checks, security/robustness tests, and the reference performance gate. Completion additionally requires the repository's current exact-candidate Verification Loop adjudication receipt, not a standalone passing command or narrative claim.

## 11. Kill Criteria

Pause or re-scope the MVP if any of these occurs:

- The Python 3.11 single-process implementation remains at or above 30 seconds after profiling and one bounded optimization pass on the fixed decimal 1 GB corpus.
- Exact required aggregates exceed practical laptop memory on the representative corpus and no scope-compatible mitigation preserves correctness.
- Reliable combined-format parsing cannot be delivered and tested within the one-weekend budget.
- Delivery requires a database, HTTP service, cloud resource, or recurring spend, contradicting the approved product premise.
