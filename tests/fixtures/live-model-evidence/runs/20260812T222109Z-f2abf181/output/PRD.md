# Product Requirements Document: nginx-log-report

## Product Summary

`nginx-log-report` lets DevOps/SRE engineers turn one finite nginx access-log stream into four incident-oriented summaries from a local shell. It is a pip-installable Python 3.11 CLI with Rich terminal output and deterministic JSON/CSV alternatives. Version 1 is stateless, single-process, and service-free.

## Problem and Outcome

During incident triage, engineers need quick answers from large nginx logs but often choose between fragile shell pipelines and operationally heavy analytics platforms. The product succeeds when an engineer can analyze a representative 1 GB log locally in under 30 seconds, trust the metric definitions, and compose the result in automation using explicit output and failure contracts.

## Goals

- Read a file or stdin exactly once without retaining raw records.
- Report top 10 client IPs and top 10 request targets producing 4xx/5xx.
- Report a 24-hour percentage distribution using `100 × hourly_request_count / total_valid_requests`.
- Report exact unique User-Agent share for Combined logs, protected by a cardinality cap.
- Support terminal, JSON, and CSV consumers with deterministic schemas.
- Finish as a $0 open-source, one-weekend, pip-installable MVP.

## Non-Goals

- Authentication, accounts, authorization, or credential management.
- Database, historical storage, cross-run comparisons, dashboards, or reports served over a network.
- HTTP API, daemon/server mode, cloud resources, Docker, or Kubernetes.
- Arbitrary nginx `log_format`, live file following, compressed input, or probabilistic metrics in MVP.
- GeoIP, bot classification, security blocking, alerting, or remediation actions.

## User Stories

### US-1 — Analyze a local stream

As an on-call SRE, I want to analyze either a log file or stdin in one command so that I can use the tool during an incident without preparing infrastructure.

**Priority:** P0

**Acceptance criteria:**

- [ ] `nginx-log-report access.log` and `cat access.log | nginx-log-report -` produce equivalent metric data.
- [ ] Input is processed once and raw records are not retained.
- [ ] A successful finite stream exits `0`; unreadable input exits `1`; invalid CLI usage exits `2`.

### US-2 — Find dominant clients

As an SRE investigating load or abuse, I want the top 10 client IPs so that I can identify dominant request sources.

**Priority:** P0

**Acceptance criteria:**

- [ ] Every valid request increments exactly one IP count.
- [ ] At most 10 rows are returned, ordered by count descending and IP string ascending on ties.
- [ ] Invalid lines never contribute to counts.

### US-3 — Find failing request targets

As a service owner, I want the top 10 URLs associated with 4xx/5xx responses so that I can prioritize broken or abused paths.

**Priority:** P0

**Acceptance criteria:**

- [ ] Statuses 400–599 contribute; statuses 100–399 do not.
- [ ] The request target is preserved without URL decoding.
- [ ] At most 10 rows are returned, ordered by count descending and target ascending on ties.

### US-4 — Understand hourly traffic shape

As a capacity engineer, I want request volume expressed as a percentage for every logged hour so that I can see when traffic concentrates.

**Priority:** P0

**Acceptance criteria:**

- [ ] All 24 buckets `00` through `23` are present, including zero buckets.
- [ ] Each percentage uses exactly `100 × hourly_request_count / total_valid_requests`; invalid lines are excluded from both numerator and denominator.
- [ ] Hours are bucketed as written in the nginx timestamp; timezone offsets are not normalized.

### US-5 — Measure User-Agent diversity safely

As an incident responder, I want the share of distinct User-Agent values so that I can distinguish concentrated clients from diverse traffic without risking uncontrolled memory use.

**Priority:** P0

**Acceptance criteria:**

- [ ] Combined logs calculate `100 × unique_normalized_user_agent_count / total_valid_requests` exactly.
- [ ] Leading/trailing whitespace is removed; case remains significant; `-` maps to one `<missing>` value.
- [ ] Common logs render this metric as `N/A`, JSON `null`, and empty CSV percentage—not zero.
- [ ] Exceeding `--max-unique-user-agents` emits no partial report and exits `4`.

### US-6 — Use reports in people and machine workflows

As a DevOps engineer, I want colored terminal output by default and stable JSON/CSV modes so that the same tool works interactively and in pipelines.

**Priority:** P0

**Acceptance criteria:**

- [ ] Default output uses Rich tables and does not interpret log values as markup.
- [ ] `--json` emits one schema-versioned object; `--csv` emits `section,rank,key,count,percentage` rows.
- [ ] JSON and CSV contain no ANSI codes or prose, use stdout only, and are mutually exclusive with exit `2` on conflict.
- [ ] Rankings and field order are deterministic for the same input and version.

### US-7 — Read compressed archives

As a platform engineer, I want transparent `.gz` input so that I can analyze rotated logs without a separate decompression pipeline.

**Priority:** P1

**Acceptance criteria:**

- [ ] Deferred until every P0 acceptance criterion and performance gate passes.
- [ ] When implemented, decompression errors preserve the input-data/I/O distinction and never emit partial output.

### US-8 — Support custom nginx formats

As an nginx operator, I want to map a custom `log_format` so that the tool works beyond Common/Combined logs.

**Priority:** P1

**Acceptance criteria:**

- [ ] Deferred; any design must keep metric field requirements explicit and retain deterministic parsing failures.

### US-9 — Follow a live log

As an on-call engineer, I want optional live-follow output so that I can observe a developing incident.

**Priority:** P2

**Acceptance criteria:**

- [ ] Deferred; it requires a separate snapshot/refresh contract and is not implied by MVP “streaming.”

## Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-1 | P0 | Accept one path, `-`, or omitted input (stdin), and consume until EOF |
| FR-2 | P0 | Parse explicitly selected nginx Combined or Common grammar; strict mode fails first malformed line, lenient mode counts/skips it |
| FR-3 | P0 | Count all valid requests by client IP and return deterministic top 10 |
| FR-4 | P0 | Count request targets only for 400–599 and return deterministic top 10 |
| FR-5 | P0 | Return all 24 hour buckets using `100 × hourly_request_count / total_valid_requests` |
| FR-6 | P0 | Return exact unique-UA share for Combined and unavailable semantics for Common |
| FR-7 | P0 | Render safe Rich terminal tables, honoring `--no-color` and `NO_COLOR` |
| FR-8 | P0 | Render versioned JSON or long-form RFC 4180 CSV with no ANSI and strict stdout/stderr separation |
| FR-9 | P0 | Enforce the UA cap before insertion and exit `4` without partial report on exhaustion |
| FR-10 | P0 | Implement the complete `0/1/2/3/4` exit contract from `PROJECT_ARCHITECTURE.md` |
| FR-11 | P1 | Add `.gz` input after MVP gates pass |
| FR-12 | P1 | Add a separately specified custom-format mapping after MVP |
| FR-13 | P2 | Explore live follow only with bounded refresh semantics |

## Output and Metric Contracts

- Valid request: a line that matches the selected grammar and passes timestamp, request-target, and status validation.
- Error URL: the raw request target from a valid 400–599 record.
- Hourly request distribution: percentage, never an unscaled fraction, calculated as `100 × hourly_request_count / total_valid_requests`.
- Unique-UA share: for Combined only, `100 × unique_normalized_user_agent_count / total_valid_requests`.
- Ranking ties: key ascending after count descending.
- Precision: terminal/CSV percentages show two decimal places; JSON percentages are numbers rounded to six decimal places.
- Zero valid requests: input-data failure, exit `3`, no report.

The canonical commands, options, schemas, and exit details are in `PROJECT_ARCHITECTURE.md` under `## CLI Interface`.

## Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-1 Performance | Representative 1 GB fixture completes in < 30 s on the documented laptop | `/usr/bin/time -v` against exact wheel candidate |
| NFR-2 Memory | No raw-line/record retention; exact UA set stops at configured cap | Unit cap boundary plus peak-RSS benchmark |
| NFR-3 Compatibility | Python 3.11 on Linux/macOS; terminal degrades without color | Clean-environment install and CLI smoke tests |
| NFR-4 Determinism | Same input/config/version yields identical JSON/CSV bytes | Repeat-run golden comparison |
| NFR-5 Security | No network, shell execution, markup interpretation, telemetry, or raw-line errors | Static review plus adversarial fixtures |
| NFR-6 Quality | ≥90% package line coverage and all black-box contract tests pass | pytest coverage gate |
| NFR-7 Packaging | PEP 517 wheel installs via pip/pipx and exposes console entry point | clean venv wheel install |

## Release Acceptance

MVP acceptance requires every P0 story, all NFRs, a clean wheel installation, and the complete exit-code contract:

- `0`: success;
- `1`: I/O/unexpected runtime failure;
- `2`: CLI usage error;
- `3`: input-data failure;
- `4`: unique-cardinality exhaustion.

P1/P2 features do not block MVP and must not be pulled into the weekend scope.

## Kill Criteria

Pause release and revise the specification if any of these remain after the weekend timebox:

- The exact release wheel cannot process the representative 1 GB fixture under 30 seconds on the documented laptop.
- Peak memory is unsafe before the declared UA cap, or exact IP/error rankings require unacceptable memory on representative/adversarial data.
- Combined/Common parsing cannot achieve 100% correctness on the maintained fixture corpus.
- JSON/CSV schemas or `0/1/2/3/4` failures cannot be made deterministic.

Do not respond to a kill criterion by adding a database, HTTP service, cloud system, or Kubernetes; those require a new product decision and PRD revision.

