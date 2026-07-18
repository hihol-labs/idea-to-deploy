# Product Requirements: Nginx Log Lens

## 1. Product summary

Nginx Log Lens gives DevOps/SRE engineers a fast local summary of nginx access
logs without a service or datastore. It streams a file or stdin and emits
colored terminal text by default, or stable JSON/CSV for pipelines.

## 2. Goals and non-goals

### Goals

- Compute the required four views correctly in a single streaming pass.
- Process a reproducible 1 GB log in under 30 seconds on the reference laptop.
- Provide predictable human and machine-readable interfaces.
- Install through pip on Python 3.11 with no operated dependency.

### Non-goals

- Authentication, accounts, a database, an HTTP API, a server, cloud services,
  Docker as a runtime requirement, or Kubernetes.
- Live network tailing, retained history, dashboards, alerting, or arbitrary
  exploratory queries.
- Full compatibility with every custom nginx `log_format` in the MVP.

## 3. Users and primary flow

The primary user is an on-call engineer with a local or piped access log:

1. Run `nginx-log-lens access.log` or pipe lines to `nginx-log-lens`.
2. Inspect the four default terminal sections and malformed-line summary.
3. Repeat with `--json` or `--csv` when composing an automated pipeline.

## 4. User stories

### US-01 — Stream local and piped logs

As an on-call SRE, I want to read an nginx log from a path or stdin so that I
can use the same command with saved and live shell data.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] A path argument reads that file lazily and produces a report.
- [ ] Omitting the path reads stdin without seeking or loading all input.
- [ ] File/read/strict UTF-8 decode failures produce an actionable stderr message and exit code 3.
- [ ] A malformed line is skipped and counted rather than aborting the run.

### US-02 — Find dominant client IPs

As a DevOps engineer, I want the ten most frequent client IPs so that I can
spot concentration, crawlers, or abusive clients quickly.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] At most ten IP/count pairs are returned, ordered by count descending.
- [ ] Equal counts are ordered by IP string ascending for deterministic output.
- [ ] Counts include every successfully parsed request regardless of status.

### US-03 — Find failing URLs

As an incident responder, I want the ten request targets with the most 4xx/5xx
responses so that I can focus diagnosis on failing routes.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Only statuses 400 through 599 contribute.
- [ ] At most ten URL/count pairs are returned with deterministic tie ordering.
- [ ] The key is the exact logged request target, including query text.

### US-04 — See time and client diversity

As an SRE, I want hourly request counts and unique User-Agent share so that I
can recognize traffic timing and client diversity.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Output contains all 24 hour buckets, including zero-count hours.
- [ ] Buckets use the hour and offset represented in each log record without timezone conversion.
- [ ] Missing User-Agent values do not count as unique.
- [ ] Share equals unique non-missing User-Agents divided by valid requests, or 0.0 when there are none.

### US-05 — Read a clear terminal report

As an engineer working interactively, I want a colored terminal report by
default so that the important rankings and totals are easy to scan.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Default output labels all four required report sections.
- [ ] Color is enabled only according to terminal/explicit option behavior.
- [ ] `--no-color` output contains no ANSI escape bytes.

### US-06 — Consume stable JSON and CSV

As a platform engineer, I want JSON and CSV output so that I can feed the
analysis into scripts and reporting systems.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] `--json` emits exactly one valid JSON document matching the versioned schema.
- [ ] `--csv` emits a single header and normalized report rows matching the versioned schema.
- [ ] The two flags are mutually exclusive and invalid use exits 2.
- [ ] Neither machine format contains ANSI escapes or human diagnostics on stdout.
- [ ] A downstream broken pipe closes quietly without diagnostics and exits 0.

### US-07 — Understand imperfect input

As an operator, I want a malformed-line count and concise diagnostics so that I
know whether the report is complete without losing usable results.

**Priority:** P1 (Should)

**Acceptance criteria:**

- [ ] All formats expose total, parsed, and malformed line counts.
- [ ] Individual malformed lines do not flood stderr in the default mode.
- [ ] Zero valid lines still produce a structurally valid empty report.

### US-08 — Change ranking depth

As a repeat user, I want to change top-N so that I can inspect beyond ten
entries when needed.

**Priority:** P2 (Could)

**Acceptance criteria:**

- [ ] A later `--top N` option validates a positive bounded integer.
- [ ] Default behavior remains top 10 and existing schemas remain compatible.

## 5. Functional requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-01 | Accept one optional log path; otherwise consume stdin | P0 |
| FR-02 | Parse nginx common and combined access-log lines | P0 |
| FR-03 | Report deterministic top-10 client IP counts | P0 |
| FR-04 | Report deterministic top-10 request targets for status 400–599 | P0 |
| FR-05 | Report 24 hourly request buckets | P0 |
| FR-06 | Report exact unique User-Agent count and share | P0 |
| FR-07 | Render Rich terminal text by default | P0 |
| FR-08 | Render versioned, ANSI-free JSON and CSV | P0 |
| FR-09 | Report parsed/malformed totals and stable fatal exit codes | P1 |
| FR-10 | Support configurable top-N | P2 |

## 6. Nonfunctional requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-01 | Python 3.11; pip-installable wheel and sdist | Clean environment build/install test |
| NFR-02 | The architecture-defined 1 GiB representative fixture is processed in <30 seconds on a documented reference laptop | Reproducible benchmark with wall-time evidence |
| NFR-03 | Peak RSS <=250 MiB on that fixture and its fixed cardinalities | Benchmark peak-memory evidence |
| NFR-04 | Raw input is consumed once and never retained as a collection | Streaming integration test and review |
| NFR-05 | Deterministic results for identical bytes/options | Repeat-run byte comparison for JSON/CSV |
| NFR-06 | No network calls, persistence, secrets, or telemetry | Static review and isolated runtime test |
| NFR-07 | Core parser/aggregator line coverage >=90% | Coverage gate |

Performance claims are valid only with the fixture recipe and cardinalities
from Architecture section 5, generator seed and SHA-256, hardware, OS, Python
version, input format, wall-time method, and peak-RSS method recorded. They do
not claim bounded memory for adversarially unique IP/URL/User-Agent values.

## 7. Output contract

Text output is presentation-oriented. JSON keys and CSV columns are the public
pipeline interface defined in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md).
Both machine formats carry `schema_version: 1` (or its CSV column), expose all
four reports and processing totals, use UTF-8, and write diagnostics only to
stderr. Rankings are count descending then key ascending.

## 8. Release acceptance

- Every P0 acceptance criterion passes in Python 3.11.
- File and stdin golden flows produce equivalent reports.
- Text, JSON, and CSV outputs satisfy their format contracts.
- Package build, isolated install, static checks, and test suite pass.
- The documented 1 GB benchmark is under 30 seconds and 250 MiB peak RSS.
- No database, network listener, authentication, cloud, or Kubernetes artifact
  enters the runtime design.

## 9. Kill and re-scope criteria

Pause release and re-scope if representative common/combined logs cannot be
parsed at >=99%, if machine output cannot be versioned without ambiguity, or
if the performance target remains over 45 seconds after profiling and one
focused optimization pass. If exact User-Agent cardinality alone exceeds the
memory gate on the representative fixture, record the dataset and decide in
the specification whether to raise the documented ceiling or introduce an
explicit approximate mode; do not silently change semantics.

## 10. Dependencies

The architecture in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) is the
technical source of truth, priorities come from
[STRATEGIC_PLAN.md](STRATEGIC_PLAN.md), and delivery evidence follows
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).
