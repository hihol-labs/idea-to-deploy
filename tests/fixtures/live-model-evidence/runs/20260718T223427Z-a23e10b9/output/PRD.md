# Product Requirements Document: nginx-log-report

## 1. Product summary

`nginx-log-report` gives DevOps/SRE engineers a fast, local summary of nginx access logs without deploying or maintaining a service. It reads a file or stdin as a stream and emits top client IPs, URLs producing 4xx/5xx errors, hourly request distribution, and User-Agent uniqueness share. The default is colored terminal text; JSON and CSV are stable pipeline formats.

## 2. Problem statement

During incident triage and capacity investigation, engineers often have a large access-log file but no configured analytics stack. Handwritten shell pipelines are error-prone, and full observability products impose setup and persistence costs. The product must turn a 1 GB log into a trustworthy fixed report in under 30 seconds on a documented laptop, entirely offline.

## 3. Goals and success measures

- Produce all four required reports exactly from documented nginx common/combined input.
- Keep processing stateless and streaming; never retain raw log history.
- Provide text, JSON, and CSV without mixing diagnostics into stdout.
- Install through pip and run on Python 3.11.
- Prove a real 1 GB run under 30 seconds with peak RSS recorded.

## 4. Non-goals

- Authentication, accounts, authorization, or multi-tenancy.
- Database, retained history, indexing, search, or cross-run comparison.
- HTTP API, server, daemon, browser UI, or live dashboard.
- Cloud deployment, Kubernetes, Docker runtime, or managed infrastructure.
- Arbitrary nginx `log_format` configuration in v0.1.
- GeoIP, bot classification, latency percentiles, bandwidth reports, or alerting.

## 5. Personas

The primary persona is an on-call SRE analyzing an incident artifact in a terminal. Secondary personas are a DevOps engineer embedding a stable report in a pipeline and a platform engineer standardizing a lightweight local tool. Their pains and alternatives are detailed in [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md).

## 6. User stories

### US-1 — Stream local or piped input

As an SRE, I want to read a log path or stdin one line at a time so that I can analyze large files and shell pipelines without loading the entire file.

**Priority:** P0  
**Acceptance criteria:**

- [ ] Omitting `INPUT` or using `-` consumes stdin; a path consumes that file.
- [ ] A valid input is traversed once and no raw-record collection grows with total line count.
- [ ] Unreadable input exits 3 and produces no report payload on stdout.
- [ ] Zero valid records exits 4.
- [ ] A late input error discards accumulated state and emits no stdout report.

### US-2 — Identify top client IPs

As an on-call SRE, I want the ten most frequent client IPs so that I can detect dominant or suspicious sources.

**Priority:** P0  
**Acceptance criteria:**

- [ ] Every valid record increments exactly one IP count.
- [ ] At most ten rows are returned in descending count order.
- [ ] Equal counts are ordered lexically by IP string for deterministic output.

### US-3 — Identify error-producing URLs

As an SRE, I want the ten request targets with the most 4xx/5xx responses so that I can focus remediation on failing routes.

**Priority:** P0  
**Acceptance criteria:**

- [ ] Statuses 400 through 599 inclusive contribute; all other statuses do not.
- [ ] Counts combine 4xx and 5xx records by the exact parsed request target.
- [ ] At most ten rows are emitted with deterministic count/key ordering.

### US-4 — See hourly traffic distribution

As a DevOps engineer, I want request counts by log-record hour so that I can spot traffic concentration and quiet periods.

**Priority:** P0  
**Acceptance criteria:**

- [ ] Output always represents all 24 buckets from `00` through `23`.
- [ ] Each valid record increments the hour present in its timestamp without host-timezone conversion.
- [ ] Bucket counts sum to the number of valid records.

### US-5 — Measure User-Agent uniqueness share

As an SRE, I want the share of distinct User-Agent values so that I can gauge client diversity or possible automated traffic.

**Priority:** P0  
**Acceptance criteria:**

- [ ] Blank/missing User-Agent values are excluded from numerator and denominator.
- [ ] Share equals distinct non-empty values divided by valid requests with non-empty User-Agent, multiplied by 100.
- [ ] A zero denominator yields `0.00`, never division failure or `NaN`.
- [ ] Equality is defined after supported nginx escape decoding and UTF-8 replacement, including documented invalid-byte collision behavior.

### US-6 — Understand malformed input

As an operator, I want malformed records counted with bounded stderr examples so that data quality issues are visible without corrupting the report.

**Priority:** P1  
**Acceptance criteria:**

- [ ] Mixed input yields a successful report from valid records and states malformed count on stderr and in metadata.
- [ ] At most `--max-diagnostic-lines` reason entries are emitted, containing line numbers and reason codes but no raw log excerpts.
- [ ] Structured stdout contains no diagnostic prose or raw invalid lines.

### US-7 — Use structured pipeline output

As a DevOps engineer, I want versioned JSON or normalized CSV so that automation can consume every report section reliably.

**Priority:** P0  
**Acceptance criteria:**

- [ ] `--json` matches Architecture JSON schema version 1 and parses as one JSON document.
- [ ] `--csv` uses exactly `schema_version,section,rank,key,value,count,share_percent` and the complete row mapping in Architecture Section 9.
- [ ] The flags are mutually exclusive and structured output contains no ANSI sequences.
- [ ] Repeating a run on identical input produces identical bytes except the input label when that label differs.

### US-8 — Read a useful terminal report

As an on-call SRE, I want a colored, labeled default report so that I can understand the result without post-processing.

**Priority:** P0  
**Acceptance criteria:**

- [ ] Interactive text labels all four metric sections and report metadata.
- [ ] `--no-color` and non-interactive redirection produce no ANSI control sequences.
- [ ] Log-derived values cannot be interpreted as Rich markup.
- [ ] Control/ANSI/OSC/bidi characters are visibly neutralized and displayed cells are safely truncated without changing metric grouping.

### US-9 — Analyze rotated gzip logs

As an operator, I want transparent `.gz` input so that I do not need a separate decompression command.

**Priority:** P2  
**Acceptance criteria:**

- [ ] If implemented after P0/P1, gzip input streams without full decompression to disk or memory.
- [ ] Corrupt gzip data produces an input error and no structured payload.

### US-10 — Tune report scope

As a platform engineer, I want configurable top-N and explicit timezone conversion so that teams can adapt the report beyond the fixed MVP.

**Priority:** P2  
**Acceptance criteria:**

- [ ] If implemented, defaults preserve top 10 and source-timestamp hour semantics.
- [ ] Any schema effect requires a deliberate schema-version decision.

## 7. Functional requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-1 | P0 | Accept a readable path or stdin and process records incrementally |
| FR-2 | P0 | Parse documented nginx common and combined records |
| FR-3 | P0 | Emit exact deterministic top-10 IP and 4xx/5xx URL rankings |
| FR-4 | P0 | Emit 24 source-timestamp hourly counts |
| FR-5 | P0 | Emit unique User-Agent count, denominator, and percent share |
| FR-6 | P0 | Support default Rich text, `--json`, and `--csv` |
| FR-7 | P0 | Keep stdout payload pure and route diagnostics to stderr |
| FR-8 | P1 | Count malformed lines and bound diagnostic examples |
| FR-9 | P1 | Publish stable exit codes and schema version 1 |
| FR-10 | P1 | Abort before mutation when the configured summed distinct-value limit would be exceeded |
| FR-11 | P2 | Optionally stream `.gz` files after MVP gates pass |
| FR-12 | P2 | Optionally configure top-N/timezone after schema review |

P0 corresponds to Must, P1 to Should, and P2 to Could in [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md). Within dependency constraints, implementation follows the RICE ordering there.

## 8. Non-functional requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-1 | A deterministic 1 GB fixture has a five-run warm-cache median under 30.0 seconds and no run above 33.0 seconds on the documented reference laptop | `/usr/bin/time -v` runs recorded in `BENCHMARK.md` |
| NFR-2 | Peak RSS remains below 512 MiB on that reference fixture | Maximum RSS from the same run |
| NFR-3 | Runs offline with no outbound or listening sockets | Dependency/code review and offline smoke test |
| NFR-4 | Python support is exactly the documented 3.11 release line for v0.1 | Package metadata and clean-environment test |
| NFR-5 | Parser, aggregation, and renderer modules maintain at least 90% line coverage | pytest-cov report |
| NFR-6 | JSON/CSV strings are correctly escaped and never contain ANSI control sequences | Golden and hostile-value tests |
| NFR-7 | Runtime memory is independent of total line count except distinct key cardinality | Design review plus scaling/RSS test |

## 9. Output and metric definitions

The version 1 JSON/CSV contracts, tie-breaking rules, exit codes, malformed-input semantics, and exact User-Agent denominator are normative in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), Sections 7–9. A behavioral change must update this PRD and architecture before implementation.

## 10. Release acceptance

- [ ] All P0 stories pass their acceptance checks.
- [ ] P1 malformed-record and exit-code behaviors are tested.
- [ ] The real 1 GB performance/RSS evidence meets NFR-1 and NFR-2.
- [ ] Wheel and sdist build; the wheel installs and runs in a clean Python 3.11 environment.
- [ ] Text, JSON, and CSV smoke tests all use the same canonical report.
- [ ] No database, HTTP server, authentication, cloud, or Kubernetes artifact exists.

## 11. Kill criteria

Do not release v0.1 if any required metric is inaccurate on golden fixtures, structured schemas cannot remain deterministic, the real 1 GB run is 30 seconds or slower after profiling, peak RSS exceeds 512 MiB on the reference input, or installation requires a service/persistent store. If Python cannot satisfy the measured performance gate, evaluate a compiled parser or Go rewrite as a new product decision; do not hide the miss with a smaller benchmark.

## 12. Dependencies and delivery

The planned implementation sequence and verification commands are in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). The product stack and boundaries are fixed by [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md). Strategy, competitors, budget, and risks are in [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md).
