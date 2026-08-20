# Product Requirements Document: Nginx Log Lens

## Product Summary

Nginx Log Lens is a local Python 3.11 CLI that gives DevOps/SRE engineers a
fast, one-pass operational summary of nginx access logs. It reads a path or
stdin, defaults to colored terminal output, and offers stable JSON and CSV for
pipelines. The MVP is open source, stateless, pip-installable, and deliverable
in one weekend at $0 infrastructure cost.

## Problem and Outcome

During triage, operators often need a small set of answers before a full log
platform can be queried or when no platform exists. Ad hoc shell pipelines are
easy to misparse and usually reread the file. The product succeeds when one
local command returns correct, deterministic answers for supported logs and
processes a representative 1 GB input in under 30 seconds on a documented laptop.

## Goals

- Stream supported nginx logs without loading the input into memory.
- Report top-10 client IPs and top-10 URLs for statuses 400–599.
- Report 24 hourly percentages using
  `100 × hourly_request_count / total_valid_requests`.
- Report exact unique User-Agent share with an explicit cardinality ceiling.
- Serve humans with Rich and automation with JSON/CSV plus stable exit codes.

## Non-Goals

Authentication, accounts, database/persistence, HTTP API, daemon/server mode,
cloud services, Kubernetes, dashboards, historical correlation, log tailing,
distributed processing, approximate cardinality, arbitrary nginx `log_format`,
and Windows-specific shell integration are outside the MVP.

## User Stories

### US-001 — Analyze a local access log

As an on-call SRE, I want to pass an nginx access-log path to one command so
that I can get an immediate traffic and error overview.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] A readable Common or Combined log is processed line-by-line and exits `0`.
- [ ] The default report contains all four sections in the documented order.
- [ ] The process does not retain raw lines after processing them.

### US-002 — Analyze a pipeline stream

As a DevOps engineer, I want to pipe log text through stdin so that the tool
composes with local shell workflows.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Omitting `INPUT` and using `INPUT=-` both read stdin.
- [ ] File and stdin forms produce identical machine output for identical bytes.
- [ ] The tool does not close caller-owned stdin.

### US-003 — Find noisy clients

As an incident responder, I want the ten busiest client IPs so that I can spot
traffic concentration quickly.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] All valid requests contribute once to their client IP count.
- [ ] At most ten entries are returned, sorted count-descending then IP ascending on ties.
- [ ] Fewer than ten distinct IPs produces only the observed entries.

### US-004 — Find failing URLs

As an incident responder, I want the ten URLs with the most 4xx/5xx responses
so that I can prioritize broken or abused routes.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Statuses 400 through 599 inclusive contribute to the URL ranking.
- [ ] Other statuses do not contribute; a missing URL is excluded without invalidating the record.
- [ ] Ranking and tie behavior match US-003.

### US-005 — Understand hourly traffic shape

As an SRE, I want requests distributed across local log hours as percentages so
that I can identify when traffic concentrates.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Output always includes ordered hours `00` through `23`.
- [ ] Each value is calculated as `100 × hourly_request_count / total_valid_requests`.
- [ ] Empty input yields zero count and `0.00%` for every hour.

### US-006 — Measure User-Agent diversity safely

As a platform engineer, I want exact unique User-Agent share with a hard limit
so that I get a trustworthy signal without unbounded cardinality risk.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Missing User-Agents are excluded from observations and unique count.
- [ ] Share equals `100 × unique_user_agent_count / total_user_agent_observations`,
  or zero with no observations.
- [ ] The first new value beyond the configured ceiling emits no report and exits `4`.

### US-007 — Consume stable machine output

As an automation author, I want JSON or CSV output so that downstream jobs do
not scrape terminal presentation.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] `--json` matches schema version 1 and contains 24 hour entries.
- [ ] `--csv` matches the documented long-form header and RFC 4180 quoting.
- [ ] Machine stdout has no ANSI escapes or diagnostics.
- [ ] Supplying both flags is a usage error with exit `2`.

### US-008 — Diagnose unsupported data

As an operator, I want safe, precise parse errors so that I can correct a format
mismatch without exposing log content.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] A malformed non-empty line reports the line number and a reason on stderr.
- [ ] The raw line is not printed by default, stdout remains empty, and exit is `3`.
- [ ] Unreadable/undecodable input exits `1`; help/option errors exit `2`.

### US-009 — Read compressed archives directly

As an operator, I want transparent `.gz` input so that archived logs need no
separate decompression command.

**Priority:** P1 (Should)

**Acceptance criteria:**

- [ ] Deferred until every P0 criterion and the performance target pass.
- [ ] A future implementation must preserve identical metric/output semantics.

### US-010 — Sample multiple malformed lines

As an operator, I want a bounded summary of malformed-line reasons so that I
can diagnose a format systematically.

**Priority:** P1 (Should)

**Acceptance criteria:**

- [ ] Deferred design must bound retained samples and never emit raw sensitive lines by default.

### US-011 — Choose ranking size

As a power user, I want to choose N so that I can explore beyond the default ten.

**Priority:** P2 (Could)

**Acceptance criteria:**

- [ ] The MVP remains fixed at top 10; any later option defaults to 10 and keeps deterministic ties.

## Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-001 | P0 | Accept one path, omitted input, or `-`; omitted/`-` means stdin |
| FR-002 | P0 | Support nginx Common and Combined formats with `auto`, `common`, and `combined` selection |
| FR-003 | P0 | Process incrementally with strict UTF-8 and a bounded current line |
| FR-004 | P0 | Ignore blank lines; fail atomically on malformed non-empty data |
| FR-005 | P0 | Count and deterministically return at most 10 client IPs |
| FR-006 | P0 | Count and deterministically return at most 10 URLs for status 400–599 |
| FR-007 | P0 | Return 24 hourly buckets using the literal approved percentage formula |
| FR-008 | P0 | Calculate exact UA observations, unique count, and share |
| FR-009 | P0 | Enforce a positive configurable exact-UA ceiling; exhaustion maps to `4` |
| FR-010 | P0 | Default to Rich terminal output with auto color and safe untrusted text |
| FR-011 | P0 | `--json` emits the version 1 schema and a trailing newline |
| FR-012 | P0 | `--csv` emits `section,rank,key,count,percentage` with RFC 4180 quoting |
| FR-013 | P0 | Round displayed percentages to two decimals, half-up |
| FR-014 | P0 | Preserve the full exit contract `0/1/2/3/4` and stderr/stdout separation |
| FR-015 | P0 | Never emit a partial report after a failure |
| FR-016 | P0 | Provide `--help`, `--version`, `--color/--no-color`, and `NO_COLOR` behavior |
| FR-017 | P1 | Add gzip input only after P0 acceptance |
| FR-018 | P1 | Add bounded malformed-reason sampling only after P0 acceptance |
| FR-019 | P2 | Consider configurable top N without changing default output |

## Output and Exit-Code Contract

The normative CLI schema and examples are under the exact `CLI Interface`
heading in `PROJECT_ARCHITECTURE.md`. The exit meanings are:

- `0`: success, including an empty-input report.
- `1`: runtime or input/output failure.
- `2`: Click usage error.
- `3`: malformed non-empty log data; no report.
- `4`: unique-cardinality exhaustion; no report.

## Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-001 | Process a representative 1 GB fixture in <30 s on the documented reference laptop | Installed-command wall-clock benchmark |
| NFR-002 | Do not materialize the input; aggregate memory is cardinality-dependent and UA-bounded | Code review plus peak-RSS benchmark |
| NFR-003 | Support Python 3.11 and pip installation | Clean-environment wheel install |
| NFR-004 | No network egress, persistence, auth, server, cloud, or Kubernetes | Dependency/config inspection |
| NFR-005 | Deterministic results independent of locale and TTY | Golden tests across output modes |
| NFR-006 | At least 90% line coverage with all P0 branches tested | Coverage gate |
| NFR-007 | Log-derived values are safely escaped/quoted and raw malformed lines are not diagnosed | Adversarial fixture tests |

## Analytics Definitions

- `total_valid_requests`: parsed non-empty records.
- IP count: valid requests grouped by parsed client IP string.
- Error URL count: valid records with status 400–599 and a present URL.
- Hourly request distribution: for each parsed timestamp's written local hour,
  `100 × hourly_request_count / total_valid_requests`.
- UA observations: valid Combined records with a non-`-` User-Agent.
- Unique UA share: `100 × unique_user_agent_count / total_user_agent_observations`.

Percentages are display-rounded, but rankings always use integer counts.

## Release Acceptance

- Every P0 story criterion passes against the installed wheel.
- The entire test suite, lint, type check, output goldens, and coverage gate pass.
- The documented reference-laptop 1 GB benchmark is under 30 seconds.
- All five exit paths are exercised end-to-end with empty stdout on failures.
- Package metadata and help match architecture and README.
- The exact staged candidate has a current accepted ITD verification receipt.

## Kill Criteria

Pause release and reduce scope or redesign when any of these is true:

- Representative 1 GB processing remains at or above 30 seconds after profiling
  and one weekend cannot produce a measured remedy.
- Exact successful UA results cannot be bounded with the specified code `4` behavior.
- Parser correctness on the supported golden corpus is below 100%.
- A P0 output schema cannot remain consistent across terminal, JSON, and CSV.
- The MVP requires a database, HTTP service, paid dependency, or ongoing infrastructure.

## Traceability

`STRATEGIC_PLAN.md` owns priorities and success framing;
`PROJECT_ARCHITECTURE.md` owns technical and CLI contracts;
`IMPLEMENTATION_PLAN.md` maps FRs to eight dependency-ordered steps; and
`CLAUDE_CODE_GUIDE.md` supplies bounded implementation prompts. When behavior
changes, update this PRD first, then reconcile the other documents before code.
