# Product Requirements Document: nginx-report

## 1. Product Summary

`nginx-report` gives DevOps and SRE engineers a fast, local summary of a
standard nginx combined access log. It processes finite files or stdin in a
single pass and reports traffic leaders, error hotspots, hourly traffic share,
and User-Agent diversity. The default is readable colored terminal text;
versioned JSON and normalized CSV make the same facts safe to automate.

## 2. Problem and Goals

During incident response, engineers often have only a shell and one or more
large log files. Ad hoc text pipelines are hard to review and comprehensive
analytics stacks are too heavy for immediate, local triage.

### Goals

- Produce the four required summaries with explicit, reproducible semantics.
- Process a representative 1 GB log in under 30 seconds on a documented laptop.
- Keep raw logs local and require no service, database, account, or network.
- Make terminal, JSON, and CSV outputs mutually consistent.
- Fail predictably through the complete `0/1/2/3/4` exit-code contract.

### Non-goals

- Historical storage, cross-run comparisons, dashboards, live tail/follow mode.
- Authentication, authorization, HTTP API, daemon, database, cloud, or Kubernetes.
- Arbitrary nginx `log_format` support in the MVP.
- GeoIP, bot classification, latency percentiles, or approximate analytics.

## 3. Users and Jobs to Be Done

| User | Job | Success signal |
|---|---|---|
| On-call SRE | Identify dominant callers and erroring endpoints during triage | One command yields a trustworthy summary in under 30 seconds for 1 GB |
| Platform engineer | Feed daily summaries into a pipeline | JSON/CSV schemas and exit codes stay stable and contain no ANSI escapes |
| DevOps engineer | Analyze logs without standing up infrastructure | pip install plus local file/stdin access is sufficient |

## User Stories

### US-1 — Analyze a finite log stream

As an on-call SRE, I want to analyze named logs or stdin incrementally so that
I can inspect large logs without loading the input into memory.

**Priority:** P0

**Acceptance criteria:**

- [ ] With no input paths, the command reads UTF-8 combined-log records from stdin.
- [ ] With multiple paths, it opens and processes each sequentially in argument order.
- [ ] The process does not retain raw input lines after aggregation.
- [ ] Valid and malformed line counts appear in every successful output mode.
- [ ] Zero valid lines produce no partial report and exit 3.

### US-2 — Find dominant traffic sources

As an SRE, I want the ten most active client IPs so that I can recognize hot
callers, scanners, or an uneven traffic source.

**Priority:** P0

**Acceptance criteria:**

- [ ] Counts include every valid request, regardless of status.
- [ ] At most ten rows are returned, ordered by count descending then IP ascending.
- [ ] IPv4 and IPv6 address tokens are preserved and counted distinctly.
- [ ] Terminal, JSON, and CSV produce the same keys and counts.

### US-3 — Find erroring URLs

As an on-call engineer, I want the top ten request targets producing 4xx or
5xx responses so that I can focus investigation on the largest error sources.

**Priority:** P0

**Acceptance criteria:**

- [ ] Only statuses 400–599 contribute to this metric.
- [ ] Each row includes total, 4xx, and 5xx counts.
- [ ] URL keys preserve the logged request-target, including query strings.
- [ ] Rows sort by total errors descending then URL ascending, capped at ten.

### US-4 — Understand hourly load shape

As a platform engineer, I want each hour's percentage of valid requests so
that I can see when traffic is concentrated.

**Priority:** P0

**Acceptance criteria:**

- [ ] Output always contains hours 00 through 23, including zero-count hours.
- [ ] Each value uses the literal formula `100 × hourly_request_count / total_valid_requests`.
- [ ] Bucketing uses the hour printed in nginx `$time_local`, without timezone conversion.
- [ ] Each row exposes the request count and percentage; terminal/CSV display two decimals.

### US-5 — Measure User-Agent diversity safely

As an SRE, I want the share of unique User-Agent values so that I can quickly
estimate client diversity without risking unbounded cardinality.

**Priority:** P0

**Acceptance criteria:**

- [ ] The unique share is `100 × unique_user_agent_count / total_valid_requests`.
- [ ] Distinctness uses the exact logged User-Agent string; `-` is a value.
- [ ] The default distinct-value cap is 1,000,000 and can be set to a positive integer.
- [ ] The first value that would exceed the cap stops processing, emits no partial report, and exits 4.

### US-6 — Use human and machine output

As a platform engineer, I want terminal, JSON, and CSV modes so that the same
tool works for interactive response and automation.

**Priority:** P0

**Acceptance criteria:**

- [ ] Default output is Rich terminal text; color appears only on a TTY unless disabled.
- [ ] `--json` emits the version-1 JSON schema defined in `PROJECT_ARCHITECTURE.md`.
- [ ] `--csv` emits the documented header and normalized section rows.
- [ ] `--json` and `--csv` together are rejected with exit 2.
- [ ] JSON and CSV never contain ANSI escape codes or diagnostics on stdout.

### US-7 — Read compressed operational archives

As a DevOps engineer, I want to read gzip logs so that I do not need a separate
decompression step.

**Priority:** P1

**Acceptance criteria:**

- [ ] `.gz` named files auto-detect gzip and explicit `--gzip` works for stdin.
- [ ] Truncated/invalid gzip data exits 1 without a partial report.

### US-8 — Change the top-N limit

As an analyst, I want to request a result limit other than ten so that the tool
can support deeper exploration.

**Priority:** P2

**Acceptance criteria:**

- [ ] A future option applies consistently to both ranked metrics.
- [ ] The default and current MVP contract remain ten.

## 5. Functional Requirements

### P0 — Must ship

| ID | Requirement |
|---|---|
| FR-1 | Expose `nginx-report [OPTIONS] [INPUT]...` as a pip-installed console script. |
| FR-2 | Parse the exact standard combined-log grammar in `PROJECT_ARCHITECTURE.md`; skip and count malformed lines. |
| FR-3 | Aggregate exact top IP, top error URL, hourly, and unique-UA metrics in one pass. |
| FR-4 | Produce deterministic terminal, JSON, and CSV output contracts. |
| FR-5 | Enforce the User-Agent cap before adding a cap-plus-one value. |
| FR-6 | Send report data only to stdout and diagnostics only to stderr. |
| FR-7 | Implement codes 0 success, 1 operational failure, 2 usage error, 3 no valid records, and 4 unique-cardinality exhaustion. |

### P1 — Should ship

| ID | Requirement |
|---|---|
| FR-8 | Read gzip named files by suffix and stdin when explicitly selected. |
| FR-9 | Report malformed-line totals without printing every malformed record. |

### P2 — Could ship later

| ID | Requirement |
|---|---|
| FR-10 | Allow a shared configurable top-N limit while retaining ten as default. |
| FR-11 | Support explicitly configured alternate nginx log formats. |

## 6. Non-functional Requirements

| Area | Requirement | Verification |
|---|---|---|
| Performance | Representative 1 GB input completes in < 30 s | Recorded benchmark on reference laptop |
| Memory | No whole-file buffering; target ≤ 512 MiB RSS under fixture assumptions | Peak-RSS benchmark and high-cardinality tests |
| Compatibility | CPython 3.11 on current Linux and macOS | CI matrix plus clean-venv smoke install |
| Correctness | Golden metrics and schemas match exact expected values | Unit/integration/golden tests |
| Accessibility | Meaning is not conveyed by color alone | `--no-color` and non-TTY snapshots |
| Privacy | No network access, telemetry, or retained log copy | Dependency/code inspection and network-isolated test |
| Maintainability | Typed modules, ≥90% line coverage, Ruff/mypy clean | Quality commands in `IMPLEMENTATION_PLAN.md` |

## 7. Output and Error Contract

The JSON object, CSV columns/row order, terminal behavior, input grammar,
metric tie-breaking, and complete exit-code table are normative in
`PROJECT_ARCHITECTURE.md` under `## CLI Interface`. Schema changes require a
PRD and architecture update before implementation.

The exit codes are fixed across all implementation work:

- `0`: successful report, help, or version.
- `1`: input/output/decode/gzip/unexpected operational error.
- `2`: Click argument or option usage error.
- `3`: no valid records after complete finite input.
- `4`: unique-cardinality exhaustion.

No failure returns a partial report.

## 8. Dependencies and Constraints

- Python 3.11, Click, Rich, dataclasses, standard-library parsing/aggregation.
- pip-installable; $0 cash budget; open source; one-weekend target.
- No authentication, database, HTTP API, server, cloud, or Kubernetes.
- Single process and finite input streams; no live follow mode.

## 9. Analytics and Telemetry

The product collects no telemetry. Adoption is assessed from voluntary
repository/package signals and user reports. Runtime reports never leave the
machine unless the user deliberately redirects stdout.

## 10. Release Criteria

- All P0 acceptance criteria and the Definition of Done in `STRATEGIC_PLAN.md` pass.
- All golden fixtures return exact metrics and exit codes `0/1/2/3/4` as applicable.
- Clean pip installation on Python 3.11 succeeds.
- The documented representative 1 GB benchmark is below 30 seconds.
- CLI help, README, architecture, and schemas agree.

## 11. Kill Criteria

Pause release and rescope if, after measurement and profiling, the 1 GB target
cannot be met on the documented reference laptop, exact metrics exceed the
documented memory envelope for representative cardinalities, or the combined
format cannot be parsed deterministically. Do not replace exact results with
approximations or partial reports without first revising this PRD.

## 12. Traceability

| Requirement group | Architecture | Implementation |
|---|---|---|
| Input/parsing | Sections 3–5 | Steps 1–2, 6–7 |
| Metrics | Section 6 | Step 3 |
| CLI/output/exits | `## CLI Interface`, Sections 13–14 | Steps 4–6 |
| Performance | Section 12 | Steps 3 and 7 |
| Packaging/release | Section 11 | Steps 1 and 8 |
