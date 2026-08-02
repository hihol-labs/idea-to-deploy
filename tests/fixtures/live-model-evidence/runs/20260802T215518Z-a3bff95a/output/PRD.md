# Product Requirements Document: nginx-streamtop

## 1. Product Summary

`nginx-streamtop` is a pip-installable Python 3.11 CLI that streams a supported
nginx combined access log and reports top client IPs, URLs producing client or
server errors, hourly traffic, and User-Agent diversity. It serves local
incident investigation and shell automation without a service or persistent
data store.

## 2. Problem and Outcome

Operators frequently need an immediate summary from a large nginx log but do
not want to provision or maintain an analytics stack. Success means the user
can run one local command against a file or stdin, understand the four required
metrics, and safely consume the same result as terminal text, JSON, or CSV.

## 3. Personas

- **On-call SRE:** prioritizes speed, trustworthy error hotspots, and visible
  data-quality warnings.
- **DevOps engineer:** prioritizes zero-service installation and large-file
  behavior.
- **Automation author:** prioritizes stable schemas, exit codes, stderr/stdout
  separation, and absence of ANSI bytes.

## User Stories

### US-01 — Stream local and piped logs

As a DevOps engineer, I want to analyze either a path or stdin so that I can use
the same command for stored logs and live shell pipelines.

Priority: **P0**

Acceptance criteria:

- [ ] A readable path, `-`, and omitted input have the behavior defined in
  `PROJECT_ARCHITECTURE.md` under `## CLI Interface`.
- [ ] A valid report is produced without loading all raw lines into memory.
- [ ] Missing/unreadable input exits 3 with a concise stderr diagnostic.

### US-02 — Find busiest client IPs

As an on-call SRE, I want the ten IP addresses with the most requests so that I
can identify traffic concentration or abusive clients.

Priority: **P0**

Acceptance criteria:

- [ ] At most ten IPs are ordered by request count descending.
- [ ] Equal counts are ordered lexicographically by IP for deterministic output.
- [ ] IPv4 and IPv6 values supported by the combined log fixture are counted.

### US-03 — Find URLs producing errors

As an on-call SRE, I want the ten request targets with the most 4xx/5xx
responses so that I can focus diagnosis on failing routes.

Priority: **P0**

Acceptance criteria:

- [ ] Only status codes 400–599 contribute to this metric.
- [ ] Query strings are retained in the request target.
- [ ] At most ten targets use the documented deterministic ranking.

### US-04 — See hourly request distribution

As an SRE, I want request counts by log-local hour so that I can correlate
traffic shape with an incident timeline.

Priority: **P0**

Acceptance criteria:

- [ ] Every valid request contributes to exactly one hour bucket.
- [ ] Buckets retain the timestamp's source UTC offset and are chronological.
- [ ] Multiple dates do not collapse into a single hour-of-day value.

### US-05 — Measure User-Agent diversity

As a DevOps engineer, I want the share of unique User-Agent values so that I can
quickly gauge client diversity or automation-heavy traffic.

Priority: **P0**

Acceptance criteria:

- [ ] The report contains exact unique count, total valid requests, and
  `unique / total * 100` percentage.
- [ ] Repeated values count once; a literal `-` is treated consistently as a
  value.
- [ ] Zero valid records produce a 0.0% share without division failure.

### US-06 — Understand malformed input

As an on-call SRE, I want malformed lines surfaced without dumping sensitive
log content so that I can judge whether the report is trustworthy.

Priority: **P0**

Acceptance criteria:

- [ ] Default mode skips malformed non-empty lines, counts them, and exits 0
  after producing the report.
- [ ] `--strict` stops on the first malformed line and exits 2.
- [ ] Diagnostics identify line number/reason but do not echo the full line.

### US-07 — Read a colored terminal report

As an interactive operator, I want a clear colored report so that I can scan
the result quickly during an incident.

Priority: **P0**

Acceptance criteria:

- [ ] Four labeled metric sections and processing counts are present.
- [ ] Color is automatic for a TTY, disabled for redirection, and suppressible
  through `--no-color`.
- [ ] Log-derived values cannot inject Rich markup or terminal escape behavior.

### US-08 — Feed pipelines with JSON or CSV

As an automation author, I want stable JSON and CSV modes so that I can process
the report without scraping terminal text.

Priority: **P0**

Acceptance criteria:

- [ ] `--json` matches the architecture schema and parses as one JSON object.
- [ ] `--csv` begins with exactly `section,key,count,value` and represents all
  report sections.
- [ ] The flags are mutually exclusive; neither format includes ANSI bytes or
  stderr diagnostics on stdout.

### US-09 — Choose strict validation

As an automation author, I want explicit strict parsing so that a damaged input
can fail my pipeline instead of yielding a partial report.

Priority: **P1**

Acceptance criteria:

- [ ] Strict failure is deterministic and documented as exit 2.
- [ ] No final machine report is emitted after the strict failure.

### US-10 — Bound hostile high-cardinality memory

As an operator, I want a deterministic exact-cardinality safety guard so that
adversarial unique values do not degrade my laptop until the process is killed.

Priority: **P1**

Acceptance criteria:

- [ ] `--max-distinct` defaults to 2,000,000 combined distinct aggregate keys;
  `0` explicitly disables the guard.
- [ ] Exceeding the limit emits no partial report, exits 5, and gives a concise
  stderr diagnostic.
- [ ] An approximate mode remains deferred; future approximation must be
  visibly labeled and must not silently change exact default results.

### US-11 — Read gzip logs directly

As a DevOps engineer, I want to read `.gz` logs without a decompression command
so that archived-log analysis is more convenient.

Priority: **P2**

Acceptance criteria:

- [ ] Deferred from the weekend MVP; a future design must preserve stdin and
  error semantics.

## 5. Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-01 | P0 | Expose the single Click command, arguments, options, and exit codes defined in the architecture |
| FR-02 | P0 | Parse documented nginx combined-format records into typed fields |
| FR-03 | P0 | Update all four metrics during one traversal of valid records |
| FR-04 | P0 | Limit ranked lists to 10 with deterministic tie-breaking |
| FR-05 | P0 | Render the same semantic report as terminal, JSON, or CSV |
| FR-06 | P0 | Count valid, malformed, and empty lines and implement tolerant/strict behavior |
| FR-07 | P0 | Keep stdout reports separate from stderr diagnostics |
| FR-08 | P1 | Provide clear examples and output schema documentation |
| FR-09 | P1 | Enforce the configurable distinct-key guard and stable exit 5 behavior |
| FR-10 | P2 | Consider direct gzip input after MVP evidence |
| FR-11 | P2 | Consider explicit approximate aggregation after cardinality evidence |

P0 corresponds to Must, P1 to Should, and P2 to Could in
`STRATEGIC_PLAN.md`. Explicit Won't items are out of scope rather than a backlog
priority.

## 6. Data Definitions

- **Valid request:** a non-empty line fully parsed under the documented
  combined-format grammar.
- **Top IPs:** request count grouped by the parsed client address.
- **Error URL:** parsed request target for a record whose status is 400–599.
- **Hour:** timestamp truncated to the hour while retaining date and source UTC
  offset.
- **Unique User-Agent share:** distinct parsed User-Agent strings divided by
  valid request count, multiplied by 100.
- **Malformed line:** a non-empty line that does not satisfy the parser grammar
  or typed field invariants.

## 7. Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-01 | Analyze a declared 1 GB fixture in under 30 seconds on a documented laptop | `/usr/bin/time -v` record in `docs/PERFORMANCE.md` |
| NFR-02 | Never retain the complete raw input; memory scales with exact unique aggregates | code review plus high-cardinality benchmark |
| NFR-03 | Support Python 3.11 and installation from a built wheel with pip | clean-environment install smoke test |
| NFR-04 | Make terminal and machine output deterministic for identical input/options | golden CLI tests |
| NFR-05 | Make no network calls, telemetry writes, caches, or persistent report storage | dependency/code review and offline test |
| NFR-06 | Avoid disclosure of full malformed lines in diagnostics | negative tests with sensitive fixture values |
| NFR-07 | Maintain at least 90% product-module test coverage at release | coverage gate |

## 8. Scope

### MVP included

- Supported nginx combined-format input from a path/stdin.
- Exact versions of all four requested metrics.
- Rich terminal output, JSON, CSV, malformed-line accounting, and strict mode.
- Pip packaging, tests, documentation, and reproducible performance evidence.

### Explicitly out of scope

- Authentication, database, HTTP API, server, daemon, web UI, cloud services,
  Docker requirement, and Kubernetes.
- Persisting or joining reports across runs.
- Arbitrary custom nginx `log_format` parsing in the MVP.
- Live file-follow (`tail -f`) semantics, geo-IP enrichment, bot detection, and
  raw-log search.
- Direct gzip and approximate aggregation until P2 is promoted through spec
  change; the exact `--max-distinct` guard remains in MVP scope.

## 9. Dependencies and Assumptions

- Python 3.11 is available locally.
- Click and Rich can be installed from the configured package source.
- The user has permission to read the input and understands logs may contain
  personal or sensitive data.
- The 30-second target is meaningful only with the benchmark profile and
  hardware captured by the architecture.

## 10. Release Acceptance

The MVP is releasable only when all P0 story criteria pass, the wheel installs
cleanly, all three output modes satisfy golden tests, no Critical/High review
finding remains, and the current exact candidate has valid Idea to Deploy
verification/adjudication evidence.

## 11. Kill Criteria

Stop or re-scope the MVP if any of the following remains true after measured
optimization within the weekend:

- The representative 1 GB fixture takes 30 seconds or more on the documented
  target laptop.
- Correct combined-format parsing cannot be achieved without unsafe ambiguity.
- Exact aggregation exhausts the agreed laptop memory on the representative
  fixture (adversarial cardinality may instead trigger a documented P2 design).
- JSON/CSV cannot maintain a shared, deterministic semantic report.
- Completing P0 requires adding a database, HTTP service, cloud resource, or
  paid dependency.

## 12. Traceability

Architecture decisions and the CLI contract live in
`PROJECT_ARCHITECTURE.md`; sequencing and verification commands live in
`IMPLEMENTATION_PLAN.md`; priorities, budget, risks, and success measures live
in `STRATEGIC_PLAN.md`. Behavioral changes start by updating this PRD and its
acceptance criteria before code is changed.
