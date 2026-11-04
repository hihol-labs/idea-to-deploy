# Product Requirements: Nginx Lens

## Problem and Outcome

An on-call engineer needs trustworthy summaries from a local nginx log without configuring a log platform. Deliver a Python 3.11 CLI with exact aggregates and three interchangeable output formats. The approved one-weekend, $0 scope and priority rationale are in [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md); [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) defines parsing and the public interface.

## User Stories

Stories follow descending RICE order, with prerequisites implemented first. P0=Must, P1=Should, P2=Could.

- As a DevOps engineer, I want to stream a combined-format file or stdin so that I can analyze a large log without loading it into memory. **P0, US-1.**
  Acceptance: omitted INPUT and `-` read stdin; explicit paths read once; valid LF/CRLF and unterminated final records work; malformed/oversized/invalid UTF-8 records are counted and skipped once; quoted escapes and timezone offsets match the architecture. Fixtures must demonstrate incremental bounded reads rather than whole-file loading.
- As a SRE, I want exact top-ten IP and error-URL rankings, hourly percentages, and unique User-Agent share so that I can investigate traffic patterns. **P0, US-2.**
  Acceptance: canonical IPs count all valid requests; paths merge queries but preserve case; error paths rank by 4xx+5xx with separate breakdowns; ties sort lexically; all 24 UTC hours appear; unique agents exclude missing values and retain exact decoded identity. A small hand-computed fixture must match every count. At the unique-entry limit repeated keys succeed, the next new key exits 4 with no report.
- As an on-call engineer, I want readable colored terminal tables so that I can triage quickly. **P0, US-3.**
  Acceptance: default output includes totals and all four metrics; a TTY uses color; redirected output, `NO_COLOR`, and `--no-color` contain no ANSI escapes; untrusted markup and control characters render as literal escaped text.
- As a platform engineer, I want a JSON report so that a pipeline can consume stable typed fields. **P0, US-4.**
  Acceptance: stdout parses as exactly one object with schema_version=1, all architecture keys, numeric counts/percentages, and sorted arrays; no status prose or ANSI appears on stdout; JSON counts equal terminal counts.
- As an automation engineer, I want a CSV report so that existing tools can ingest the same metrics. **P0, US-5.**
  Acceptance: one fixed six-column header, deterministic row order, standard quoting for commas/quotes/newlines, empty irrelevant cells, numeric count values, and two-decimal percentages; CSV round trips through the standard library and agrees with JSON.
- As a pipeline owner, I want stable diagnostics and exit codes so that invalid input cannot look like a complete successful analysis. **P0, US-6.**
  Acceptance: the complete 0/1/2/3/4 matrix below passes subprocess tests, including all-malformed and empty input; diagnostics stay on stderr and omit raw records; input failures and cardinality exhaustion emit no report; output failure is nonzero even if stdout is partial.
- As a SRE, I want gzip files accepted directly so that I can inspect rotated logs without a decompression pipe. **P1, US-7.** Deferred; when added, the decompressed stream must retain the existing parser, outputs, caps, and error contract.
- As a service owner, I want configurable top-N so that I can explore beyond ten entries. **P2, US-8.** Deferred; if added, require a positive bound and deterministic ties.

## Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-1 | P0 | One input stream in nginx combined format; no persistent state |
| FR-2 | P0 | Top ten IPs by valid request count |
| FR-3 | P0 | Top ten URL paths by combined 4xx/5xx error count with breakdown |
| FR-4 | P0 | Hour-of-day distribution in UTC across dates |
| FR-5 | P0 | Exact nonmissing unique User-Agent count and share |
| FR-6 | P0 | Rich default plus mutually exclusive `--json` and `--csv` |
| FR-7 | P0 | Malformed-line accounting, bounded reads, explicit unique cap |
| FR-8 | P1 | gzip, deferred |
| FR-9 | P2 | Configurable top-N, deferred |

Hourly request distribution is `100 × hourly_request_count / total_valid_requests`. Unique-UA share is `100 × distinct_nonmissing_user_agents / total_valid_requests`. When valid requests are zero, both percentages are zero. Use integer totals for computation and round half-even to two decimal places at rendering; rounded hourly percentages need not sum to precisely 100.00.

Hand-check acceptance fixture: four valid requests with IP counts A=3, B=1, two error requests to `/bad?q=1` and `/bad?q=2` (404 and 500), two successes to `/ok`, UTC hours 00=3 and 01=1, and agents `agent-a`, `agent-a`, `agent-b`, `-`. Expect `/bad` total_errors=2, errors_4xx=1, errors_5xx=1; hour percentages 75.00 and 25.00; all other hours zero; unique-UA count=2 and share=50.00. Adding one malformed line changes total_lines to 5 and exit to 3, without changing metric denominators.

## Error and Exit Contract

| Code | Required behavior |
|---|---|
| 0 | Complete clean report, including empty input; help/version succeed |
| 1 | I/O, encoding/output, interruption, broken pipe, or unexpected operational failure |
| 2 | Invalid options/usage; includes conflicting formats and nonpositive cap |
| 3 | Complete report after skipping malformed records; all-malformed also uses 3 |
| 4 | unique-cardinality exhaustion; exact aggregate cannot continue within cap |

Codes 1/4 encountered before rendering leave stdout empty; write errors can leave partial stdout. Usage validation precedes input access; the first fatal runtime error overrides malformed status. See the architecture for detailed lifecycle rules.

## Nonfunctional Requirements

- Process 1,000,000,000 bytes in under 30 seconds on a documented laptop using the architecture benchmark; target peak RSS at most 512 MiB on that bounded-cardinality dataset.
- Exact aggregation uses O(distinct IPs + distinct error paths + distinct nonmissing agents) memory with a configurable combined key cap; no constant-memory claim.
- Runtime is Python 3.11, Click, Rich, dataclasses and standard library; pip-installable and offline after installation.
- Deterministic outputs independent of record order, locale, or terminal width for structured formats.
- No data egress, raw-record diagnostics, or telemetry. Exports are deliberate local stdout results.

## Out of Scope

Authentication, database, HTTP API, server, cloud, Kubernetes, Docker deployment, log collection, dashboards, watch mode, approximate sketches, multiple input files, custom nginx formats, and automatic publication. P1/P2 are not weekend release gates.

## Release and Kill Criteria

Ship only after P0 acceptance and the local install/benchmark gates pass. If profiling within the weekend cannot meet throughput or bounded-fixture RSS, stop the release and record measurements; do not quietly relax the target or claim success. If exact high-cardinality input exceeds the budget, exit 4 by design; it is not successful completion. Reassess product scope if custom formats or ongoing cross-run analytics become essential instead of adding a database implicitly.

This document is a replayable spec, not evidence that product tests have run. [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) maps it to files/checks; [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md) provides prompts, [README.md](README.md) describes use, and [CLAUDE.md](CLAUDE.md) maintains implementation status.
