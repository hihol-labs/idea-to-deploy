# Product Requirements Document: nginx-stream-stats

## 1. Product Summary

`nginx-stream-stats` lets DevOps/SRE practitioners locally stream a supported nginx combined access log and obtain four operational views: top client IPs, URLs with the most 4xx/5xx responses, hourly request distribution, and unique User-Agent share. Default output is colored terminal text; JSON and CSV enable pipelines. The MVP is stateless, local, open source, and pip-installable.

## 2. Problem and Outcome

During incidents and routine checks, operators often have a log file but not a configured analytics stack. Existing stacks are expensive to deploy for a one-off question, while shell pipelines are easy to get subtly wrong. The intended outcome is a trusted report within one local command and, for a 1 GB supported log, under 30 seconds on the documented reference laptop.

## 3. Personas

- On-call SRE: needs rapid error and traffic concentration signals.
- Platform/DevOps engineer: needs stable output for scripts and CI jobs.
- Small-estate systems administrator: needs useful analysis without services or persistent infrastructure.

## 4. Goals and Non-Goals

### Goals

- Correctly process nginx combined-format files and stdin in a single streaming pass.
- Implement the four metric definitions in this PRD exactly.
- Keep default output readable and machine output deterministic.
- Bound high-cardinality failure explicitly rather than crash or silently approximate.
- Package for Python 3.11 installation through pip.

### Non-goals

- Custom nginx `log_format` definitions in MVP.
- Historical retention, cross-file sessions, live dashboard refresh, or remote tailing.
- Authentication, database, HTTP API, server, cloud, Docker, or Kubernetes.
- GeoIP, bots, referrer analytics, bandwidth reports, latency analysis, or approximate cardinality.

## User Stories

### US-1 — Analyze a large local log

As an on-call SRE, I want to stream an nginx access-log file without loading it all into memory, so that I can investigate a large incident artifact on my laptop.  
**Priority:** P0

**Acceptance criteria:**

- [ ] A supported file is read incrementally and raw lines are not accumulated.
- [ ] A 1 GB benchmark completes in under 30 seconds on the documented reference laptop.
- [ ] The report includes valid and malformed line counts.

### US-2 — Find traffic concentration by IP

As an SRE, I want the ten most frequent client IP values, so that I can spot concentrated traffic.  
**Priority:** P0

**Acceptance criteria:**

- [ ] Counts include all valid requests, regardless of status.
- [ ] At most ten rows are returned, ordered by count descending and IP string ascending on ties.
- [ ] IPv4 and IPv6 tokens are preserved as logged.

### US-3 — Find URLs producing errors

As an on-call engineer, I want the ten URLs with the most 4xx/5xx responses, so that I can focus remediation on failing targets.  
**Priority:** P0

**Acceptance criteria:**

- [ ] Only status codes 400 through 599 contribute.
- [ ] 4xx and 5xx counts are combined per exact request-target, including its query string.
- [ ] At most ten rows are returned, ordered by count descending and URL ascending on ties.

### US-4 — Understand hourly request shape

As a capacity engineer, I want each logged hour’s share of valid requests, so that I can see when traffic clusters.  
**Priority:** P0

**Acceptance criteria:**

- [ ] Exactly 24 buckets from `00` through `23` are present.
- [ ] Each percentage uses `100 × hourly_request_count / total_valid_requests`.
- [ ] The hour is taken from the timestamp’s logged local offset; displayed values are rounded to two decimal places.

### US-5 — Gauge User-Agent diversity

As an incident responder, I want the share of unique User-Agent values, so that I can quickly gauge client diversity.  
**Priority:** P0

**Acceptance criteria:**

- [ ] The numerator is the count of distinct, non-missing User-Agent strings among valid requests.
- [ ] The denominator is `total_valid_requests`, so the percentage is `100 × unique_user_agents / total_valid_requests`.
- [ ] The nginx placeholder `-` is missing and does not enter the distinct set.

### US-6 — Use reports in pipelines

As a platform engineer, I want stable JSON and CSV output, so that I can consume results without scraping terminal tables.  
**Priority:** P0

**Acceptance criteria:**

- [ ] `--json` emits one valid versioned JSON object and no ANSI bytes.
- [ ] `--csv` emits the documented long-form header and deterministic rows with no ANSI bytes.
- [ ] Selecting both options is a usage error with exit `2`.

### US-7 — Pipe logs over stdin

As a systems administrator, I want `-` to read stdin, so that decompression and remote-copy tools can feed the analyzer.  
**Priority:** P1

**Acceptance criteria:**

- [ ] The same supported records produce semantically identical reports from a file and stdin.
- [ ] The program does not close a caller-owned stdin stream.

### US-8 — Diagnose imperfect data safely

As an operator, I want bounded malformed-record diagnostics, so that I understand exclusions without leaking log contents.  
**Priority:** P1

**Acceptance criteria:**

- [ ] Malformed lines are counted, and up to `--show-malformed N` line numbers/reason categories appear on stderr.
- [ ] Raw log text is never echoed in diagnostics.
- [ ] Zero valid records produces exit `3` and no success report.

### US-9 — Analyze gzip files directly

As an operator, I want direct `.gz` input, so that I can avoid a decompression pipe.  
**Priority:** P2

Deferred: shell decompression to stdin covers MVP.

### US-10 — Supply a custom log format

As an nginx administrator, I want to define field mapping for a custom `log_format`, so that non-combined logs can be analyzed.  
**Priority:** P2

Deferred: grammar design and ambiguity handling exceed the weekend MVP.

## 6. Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-1 | P0 | Parse UTF-8 nginx combined-format records from one path or stdin incrementally |
| FR-2 | P0 | Count valid requests by exact IP and return deterministic top 10 |
| FR-3 | P0 | Count exact URL targets for statuses 400–599 and return deterministic top 10 |
| FR-4 | P0 | Return 24 hourly percentage buckets using `100 × hourly_request_count / total_valid_requests` |
| FR-5 | P0 | Return distinct non-missing User-Agent count and `100 × unique_user_agents / total_valid_requests` |
| FR-6 | P0 | Track valid/malformed counts and enforce shared unique-key ceiling before insertion |
| FR-7 | P0 | Provide `nginx-stream-stats analyze [OPTIONS] INPUT` and pip console script |
| FR-8 | P0 | Emit versioned JSON contract under `--json` |
| FR-9 | P0 | Emit long-form CSV contract under `--csv` |
| FR-10 | P0 | Emit colored Rich terminal text by default on TTY and clean text otherwise |
| FR-11 | P0 | Implement complete exit codes `0/1/2/3/4`; `4` exclusively means unique-cardinality exhaustion |
| FR-12 | P1 | Provide bounded safe malformed-line diagnostics |
| FR-13 | P2 | Read `.gz` directly |
| FR-14 | P2 | Support user-defined log-field mapping |

## 7. CLI and Output Acceptance Contract

The canonical commands, options, schemas, and exit details live under `## CLI Interface` in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md). This PRD requires the complete exit-code contract everywhere it is documented:

| Code | Contract |
|---:|---|
| `0` | Successful analysis/help/version |
| `1` | Input or runtime failure |
| `2` | CLI usage error |
| `3` | No valid supported records |
| `4` | Unique-cardinality exhaustion |

Success output is stdout-only. Warnings and errors are stderr-only. JSON/CSV output contains no styling or human commentary.

## 8. Non-Functional Requirements

| ID | Requirement | Evidence |
|---|---|---|
| NFR-1 Performance | Process exactly 1 GB of supported benchmark input in under 30 seconds on documented laptop hardware | `/usr/bin/time -v` record in `docs/PERFORMANCE.md` |
| NFR-2 Streaming | Do not retain raw lines; memory depends on unique tracked keys, capped by `--max-unique` | Lazy-iterator test, peak RSS record, exhaustion test |
| NFR-3 Determinism | Identical valid records and options yield identical semantic report; ties have key-ascending rule | Golden/snapshot tests |
| NFR-4 Compatibility | Install and run on CPython 3.11 via pip | Clean-venv wheel smoke test |
| NFR-5 Privacy | No network/telemetry/persistence; no raw malformed lines in errors | Network-free design review and diagnostics tests |
| NFR-6 Quality | At least 90% line coverage for package code and all acceptance cases pass | pytest coverage report |
| NFR-7 Usability | Fresh-venv Quick Start takes under 30 seconds excluding package download/network time | Timed local smoke procedure |

## 9. Release Acceptance Matrix

| Outcome | Required proof |
|---|---|
| Metrics correct | Golden fixture proves all four metrics, ties, status boundaries, and missing User-Agent behavior |
| Formats stable | Text, JSON, and CSV contract tests pass without cross-stream or ANSI contamination |
| Failure semantics correct | Integration cases exercise exit `0`, `1`, `2`, `3`, and `4` independently |
| Scale target met | Documented exact-candidate 1 GB run is below 30 seconds |
| Package usable | Wheel/sdist metadata checks and clean Python 3.11 install smoke pass |

## 10. Dependencies and Assumptions

- Source timestamps contain numeric offsets and are bucketed by their logged local hour; no timezone conversion is performed.
- Supported input is nginx combined format; custom formats are rejected/count as malformed rather than guessed.
- Query strings remain in URL keys. IPs and User-Agents are exact string matches with no normalization.
- Click and Rich versions are constrained in `pyproject.toml`; everything else in the runtime pipeline uses Python’s standard library.
- Benchmark hardware and input-generation method are recorded so “under 30 seconds” is reproducible rather than universal.

## 11. Kill Criteria

Stop or explicitly re-scope the MVP rather than ship misleading behavior if any condition holds at the end of the weekend:

1. The supported 1 GB fixture still takes 30 seconds or more after profile-guided single-process optimization.
2. The implementation cannot stop predictably with exit `4` before its configured unique-cardinality ceiling is crossed.
3. Any renderer produces a different metric definition or JSON/CSV cannot remain ANSI-free and parseable.
4. Combined-format parsing cannot distinguish malformed data from valid records with the golden fixture.
5. Meeting the target would require a database, server, cloud service, or silent approximation contrary to the approved scope.

The fallback is to publish benchmark findings and revise the specification, not weaken acceptance claims.

## 12. Traceability

- Strategy, MoSCoW, RICE, budget, and risks: [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md)
- Architecture and exact interface: [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md)
- Implementation and verification sequence: [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)
- Step prompts and handoff rules: [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md)
