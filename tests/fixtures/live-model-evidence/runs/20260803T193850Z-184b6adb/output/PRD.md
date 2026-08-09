# Product Requirements Document: nginx-log-top

## Product Goal

Give DevOps/SRE engineers a fast, trustworthy, local summary of a supported nginx access log without building or operating a logging platform.

## Scope and Priorities

P0 maps to Must, P1 to Should, and P2 to Could from [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md). MVP includes streaming file/stdin ingestion, all four metrics, terminal/JSON/CSV output, and the documented failure contract.

## User Stories

### US-1: Analyze a log locally

As an on-call SRE, I want to stream an nginx access-log file or stdin so that I can investigate without uploading operational data.

Priority: **P0**

Acceptance criteria:

- [ ] `nginx-log-top access.log` and `cat access.log | nginx-log-top` produce equivalent metrics.
- [ ] A 1 GB content-hashed fixture completes in under 30 seconds on the recorded reference laptop.
- [ ] Input is iterated and is not read wholly into memory.
- [ ] Missing/unreadable/invalidly encoded input exits 3 with a concise stderr message.
- [ ] The declared 1 GB cardinality envelope stays below 512 MiB peak RSS; the benchmark manifest records machine, Python, fixture, command, three measured runs, and hash.

### US-2: Find dominant client IPs

As an SRE, I want the ten most frequent client IPs so that I can spot dominant or suspicious sources.

Priority: **P0**

Acceptance criteria:

- [ ] At most ten IP/count pairs are returned from valid records.
- [ ] Results sort by count descending and IP ascending for ties.
- [ ] IPv4 and IPv6 strings supported by the log format are counted without DNS resolution.

### US-3: Find error hotspots

As a service owner, I want the ten request targets with the most 4xx/5xx responses so that I can prioritize broken routes and dependencies.

Priority: **P0**

Acceptance criteria:

- [ ] Only statuses 400 through 599 inclusive contribute.
- [ ] Request targets remain exactly as logged, including query strings.
- [ ] Results sort by count descending and URL ascending for ties and contain at most ten entries.

### US-4: See hourly request distribution

As an incident responder, I want requests grouped by logged local hour so that I can correlate traffic changes with an event window.

Priority: **P0**

Acceptance criteria:

- [ ] Output contains all 24 buckets `00`–`23` in ascending order, including zeros.
- [ ] Each record uses its parsed nginx timestamp offset rather than the workstation timezone.
- [ ] Bucket counts sum to the valid-request count.

### US-5: Measure User-Agent diversity

As a platform engineer, I want the share of distinct User-Agent values so that I can gauge client diversity or automation concentration.

Priority: **P0**

Acceptance criteria:

- [ ] The percentage equals `distinct nonempty User-Agents / valid requests × 100`.
- [ ] Output includes the distinct count, valid-request denominator, and percentage.
- [ ] Repeated identical strings count once in the numerator and once per request in the denominator.
- [ ] Missing or empty User-Agent values do not enter the numerator but their valid records remain in the denominator.

### US-6: Read an incident summary in the terminal

As a human operator, I want colored labeled output by default so that I can scan results quickly.

Priority: **P0**

Acceptance criteria:

- [ ] A TTY shows four labeled report sections using Rich.
- [ ] Redirected output, `NO_COLOR`, and `--no-color` contain no ANSI escapes.
- [ ] Untrusted log strings cannot be interpreted as Rich markup.
- [ ] ESC, C0/C1, DEL, and Unicode bidi/format controls are visibly escaped and cannot control the terminal.

### US-7: Use results in pipelines

As a DevOps engineer, I want JSON or CSV output so that scripts can consume results reliably.

Priority: **P0**

Acceptance criteria:

- [ ] `--json` emits one valid object matching schema version 1.
- [ ] `--csv` emits the documented `report,key,count,value` header and normalized rows.
- [ ] Both formats are deterministic, UTF-8, ANSI-free, and mutually exclusive.
- [ ] Known input failures do not emit partial JSON or CSV.
- [ ] JSON types/order/rounding and every CSV row/empty/newline rule match the architecture's normative schema and golden fixtures.

### US-8: Understand imperfect input

As an operator, I want malformed records counted and expected failures classified so that I do not mistake partial analysis for complete data.

Priority: **P1**

Acceptance criteria:

- [ ] Mixed valid/malformed input succeeds, reports both counts, and bases metrics only on valid lines.
- [ ] Input with no valid records exits 4 and emits no success report.
- [ ] Usage errors exit 2; unexpected internal failures exit 1; broken pipes terminate quietly.

### US-9: Choose another top-N size

As a power user, I want to override the top-list size so that I can broaden an investigation.

Priority: **P2**

Acceptance criteria:

- [ ] A future bounded positive option changes both rankings consistently without changing schemas.

### US-10: Parse configured nginx formats

As a platform owner, I want to describe a custom nginx log format so that the tool can cover non-combined deployments.

Priority: **P2**

Acceptance criteria:

- [ ] A future format mechanism fails fast when required fields are absent and preserves MVP combined-format behavior.

## Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-1 | P0 | Read one UTF-8 file path, `-`, or stdin through buffered iteration |
| FR-2 | P0 | Parse the supported combined-log contract into typed records |
| FR-3 | P0 | Produce the four exact metrics with deterministic ordering |
| FR-4 | P0 | Render terminal, JSON schema v1, or normalized CSV |
| FR-5 | P0 | Keep stdout data separate from stderr warnings/errors |
| FR-6 | P1 | Count malformed lines and implement exit codes 0/1/2/3/4 |
| FR-7 | P2 | Allow a bounded top-N override after MVP |
| FR-8 | P2 | Add explicit custom-format support after MVP |

## Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-1 | Python 3.11; installable with pip | Build wheel/sdist and install wheel in clean venv |
| NFR-2 | Process 1 GB in <30 s on declared laptop | `/usr/bin/time` against hashed fixture and exact candidate |
| NFR-3 | Single pass and no whole-file materialization | Instrumented iterator test and code review |
| NFR-4 | No network, auth, database, server, cloud, or Kubernetes | Dependency/config inspection and architecture review |
| NFR-5 | Deterministic machine output | Repeated golden tests across hash seeds/locales |
| NFR-6 | Safe handling of untrusted text | Markup, JSON, CSV, control-character test corpus |
| NFR-7 | Exact metric resource envelope is explicit | High-cardinality fixture stays below 512 MiB RSS; beyond-envelope behavior is documented |

## Out of Scope

- Authentication, users, permissions, database, caching service, HTTP API, daemon/server mode.
- Cloud service, Kubernetes, Docker requirement, centralized ingestion, dashboards, alerting.
- Tail/follow, multiple inputs, compressed input, remote URLs, geo-IP/DNS enrichment.
- Arbitrary nginx formats in P0/P1.

## Release and Kill Criteria

Release when every P0 criterion passes, installation succeeds from a built wheel, and the exact 1 GB benchmark passes with recorded environment/hash/RSS. Stop or re-scope if Python 3.11 cannot meet the performance target after profile-driven optimization within the weekend, or if the supported grammar cannot be made reliable without expanding configuration scope.

## Traceability

Architecture is defined in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md); implementation order and commands are in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Behavior changes must begin here before code changes.
