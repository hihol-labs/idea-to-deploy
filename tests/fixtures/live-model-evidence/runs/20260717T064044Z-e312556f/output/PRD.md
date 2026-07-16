# Product Requirements Document: Nginx Stream Report

## 1. Product summary

Nginx Stream Report is a local Python 3.11 command-line utility for fast, one-pass analysis of standard nginx combined access logs. It produces four operational views: top client IPs, top error-producing URLs, hourly request distribution, and unique User-Agent share. It is stateless and emits Rich terminal, JSON, or CSV output.

## 2. Problem and outcome

During incident triage, engineers often have an exported log but not a working observability stack. Repeated `grep`/`awk` pipelines are difficult to verify and inconsistent across people. The desired outcome is a trustworthy report from a 1 GB log in under 30 seconds with no infrastructure or persistent state.

## 3. Scope

### In scope

- Python 3.11/pip-installed local CLI.
- file path and stdin input.
- standard nginx combined-log parsing with malformed-line accounting.
- exact top 10 IPs and exact top 10 URLs for statuses 400–599.
- 24 hourly buckets and exact unique User-Agent count/share.
- default Rich terminal, `--json`, and `--csv` outputs.
- deterministic results, documented exit codes, and the performance benchmark.

### Out of scope

- authentication, database, persistence, HTTP API, server, cloud, containers, and Kubernetes;
- live web dashboard, multi-user access, historical trends, or scheduled ingestion;
- access to remote hosts or automatic log discovery;
- arbitrary nginx `log_format` configuration in P0;
- URL normalization, bot classification, geo-IP, alerts, and traffic blocking.

## 4. User stories

### US-001 — Rapid IP concentration triage

As an on-call SRE, I want the ten most active client IPs so that I can identify concentrated traffic during an incident.

**Priority:** P0

**Acceptance criteria:**

- [ ] every valid request increments exactly one IP count;
- [ ] at most ten entries are returned in descending count order;
- [ ] equal counts are ordered by ascending IP text;
- [ ] file and stdin inputs yield identical rankings.

### US-002 — Find error-producing URLs

As a DevOps engineer, I want the ten URLs with the most 4xx/5xx responses so that I can focus investigation on failing routes.

**Priority:** P0

**Acceptance criteria:**

- [ ] only status codes 400 through 599 contribute;
- [ ] 2xx and 3xx requests never appear in the metric;
- [ ] request targets retain their parsed path/query text;
- [ ] ordering is descending count then ascending URL, limited to ten.

### US-003 — See the hourly traffic shape

As an SRE, I want requests grouped by hour so that I can see when load or incidents peaked.

**Priority:** P0

**Acceptance criteria:**

- [ ] the report always contains buckets `00` through `23`;
- [ ] the hour is derived from each valid record's timezone-aware nginx timestamp;
- [ ] bucket counts sum to the valid request total;
- [ ] empty hours have count zero.

### US-004 — Measure User-Agent diversity

As a platform engineer, I want the unique User-Agent count and its share of valid requests so that I can estimate client diversity or automation concentration.

**Priority:** P0

**Acceptance criteria:**

- [ ] uniqueness uses exact User-Agent string equality;
- [ ] share equals `unique count / valid request count * 100`;
- [ ] empty input reports count `0` and share `0.0`;
- [ ] malformed lines do not affect the numerator or denominator.

### US-005 — Automate analysis

As a DevOps engineer, I want JSON and CSV output so that I can feed the metrics into scripts without scraping terminal text.

**Priority:** P0

**Acceptance criteria:**

- [ ] `--json` produces one valid JSON document with a schema version;
- [ ] `--csv` produces one header and valid normalized CSV rows;
- [ ] both modes contain the same metric values as terminal mode;
- [ ] neither mode emits ANSI sequences or progress messages to stdout;
- [ ] `--json` and `--csv` together fail as invalid usage.

### US-006 — Use common compressed logs directly

As an operator, I want gzip input so that I do not need a separate decompression pipeline.

**Priority:** P1

Acceptance can be defined when promoted. MVP users can run `gzip -dc access.log.gz | nginx-stream-report --json -`.

### US-007 — Support custom log formats

As a platform engineer, I want a configurable field format so that the utility works with our nonstandard nginx configuration.

**Priority:** P1

Acceptance can be defined only after representative format samples are collected.

### US-008 — Bound extreme cardinality memory

As an operator processing adversarial traffic, I want optional approximate unique counting so that memory remains bounded.

**Priority:** P2

This feature is promoted only if benchmark evidence shows exact cardinality is unsafe for target laptops.

## 5. Functional requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-001 | P0 | accept one optional input path; omitted or `-` reads stdin incrementally |
| FR-002 | P0 | parse standard nginx combined logs; skip/count malformed lines without aborting |
| FR-003 | P0 | report deterministic top-10 client IP request counts |
| FR-004 | P0 | report deterministic top-10 request targets for 4xx/5xx counts |
| FR-005 | P0 | report all 24 hourly request buckets |
| FR-006 | P0 | report exact unique User-Agent count and percentage of valid requests |
| FR-007 | P0 | use Rich terminal output by default with color only when appropriate |
| FR-008 | P0 | provide mutually exclusive `--json` and `--csv` stable outputs |
| FR-009 | P0 | send reports to stdout, diagnostics to stderr, and follow documented exit codes |
| FR-010 | P1 | accept gzip-compressed input directly |
| FR-011 | P1 | support user-specified log field formats |
| FR-012 | P2 | offer measured-need options such as approximate cardinality or custom top N |

## 6. Non-functional requirements

### Performance

- **AC-PERF-001:** a representative 1 GiB combined log completes in less than `30.0` seconds on a documented reference laptop and Python 3.11 version.
- The implementation reads incrementally and never loads the raw log into memory.
- Peak memory is reported; with constant cardinality, it must not scale with line count.

### Correctness and resilience

- All output modes use one report model.
- Malformed input is counted, not silently treated as valid.
- Results are deterministic across repeated runs.
- Exact counts use unrounded values; percentages may be rounded only in serialization/display.

### Usability

- `nginx-stream-report --help` documents inputs, formats, exit codes, and the supported log format.
- A successful file or stdin example can be copied from the README.
- Empty valid input produces a valid empty report rather than an exception.

### Security and privacy

- The utility makes no network requests and collects no telemetry.
- It never executes or interpolates log data as code or terminal markup.
- Fatal errors do not echo complete sensitive log lines.
- Documentation warns that reports can contain IP addresses, URLs, and User-Agents.

### Compatibility

- Support CPython 3.11 at minimum.
- Install from a wheel or source distribution with pip.
- Machine-readable output is UTF-8 and pipeline-safe.

## 7. Output acceptance examples

Given a fixture with three valid requests from IP A, two from IP B, one 404 and one 500 for `/failed`, two distinct User-Agents, and one malformed line:

- `total_requests` is 5 and `malformed_lines` is 1;
- A ranks before B with counts 3 and 2;
- `/failed` has error count 2;
- 24 hour buckets sum to 5;
- unique User-Agent count is 2 and share is 40%;
- terminal, JSON, and CSV expose these same values.

## 8. Release criteria

- [ ] every P0 acceptance criterion passes in Python 3.11;
- [ ] overall automated test coverage is at least 90%;
- [ ] 1 GiB benchmark evidence meets AC-PERF-001;
- [ ] clean wheel build/install/smoke test passes;
- [ ] no Critical/High security finding is open;
- [ ] README describes format limitations, privacy, exit codes, and all output modes.

## 9. Kill criteria

- Do not publish if AC-PERF-001 is unmet after profiling and bounded hot-path optimization.
- Do not publish if parser ambiguity can silently misattribute IP, URL, status, timestamp, or User-Agent.
- Do not add services or persistence to rescue the MVP; select an existing analytics stack if those become requirements.

## 10. Dependencies and traceability

The selected architecture is `PROJECT_ARCHITECTURE.md` Variant A. Delivery steps and test commands are in `IMPLEMENTATION_PLAN.md`. MoSCoW/RICE reasoning, budget, and Definition of Done are in `STRATEGIC_PLAN.md`.

