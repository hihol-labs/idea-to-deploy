# PRD: Nginx Log Lens

## Product and scope
Local Python 3.11 CLI for DevOps/SRE incident summaries. The approved MVP processes nginx combined access logs from a file or stdin through EOF without persistence. [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) defines parsing, metrics, schemas and failures; [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) records priorities and business assumptions. [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) and [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md) translate these requirements into work. [CLAUDE.md](CLAUDE.md) holds agent rules.

## User Stories
- As a DevOps on-call engineer, I want to stream a file or stdin, so that I can inspect an incident without loading the full log into memory. Priority: P0, Must; first in RICE order.
  Acceptance: identical records from a file and stdin yield identical machine reports; valid combined records are counted; malformed records are skipped and counted; final unterminated lines work; oversized lines never accumulate unbounded memory.
- As a DevOps engineer, I want the top ten client IPs, so that I can identify traffic concentration. Priority: P0, Must; second in RICE order.
  Acceptance: all statuses contribute; IPv6 aliases canonicalize; at most ten rows; ties sort by canonical IP string; fixtures with eleven distinct IPs select the correct ten.
- As a service maintainer, I want the top ten URLs by 4xx/5xx errors, so that I can prioritize failing paths. Priority: P0, Must; third in RICE order.
  Acceptance: 399 and 600 are excluded (600 is malformed), 400 and 599 included; query strings are removed; each row shows combined count and separate 4xx/5xx counts; equal totals sort by URL ascending.
- As a SRE, I want hourly request percentages, so that I can compare traffic over the observed hours. Priority: P0, Must; fourth in RICE order.
  Acceptance: each percentage uses `100 × hourly_request_count / total_valid_requests`; two requests in one hour and one in another yield 66.666667 and 33.333333; offsets remain in distinct hour keys and sorting follows UTC instant.
- As a platform engineer, I want the share of unique User-Agents, so that I can inspect client diversity. Priority: P0, Must; fifth in RICE order.
  Acceptance: UAs A,A,B yield unique count 2 and 66.666667%; missing `-` and empty UA are excluded from the numerator but not the request denominator; exact distinct counting stops with exit 4 when its cap would be exceeded.
- As a pipeline author, I want deterministic JSON/CSV and explicit failures, so that automated jobs can trust completed reports. Priority: P0, Must; bounds precede exports by dependency.
  Acceptance: JSON/CSV obey architecture schemas, contain no ANSI output and keep diagnostics on stderr; exits are 0/1/2/3/4 with code 4 for unique-cardinality exhaustion; no report on pre-render failures.
- As a local tool user, I want pip installation and readable colored text, so that I can start with one command. Priority: P0, Must.
  Acceptance: clean Python 3.11 environment installs a local wheel; console entry point, help/version and all four report sections work; redirected text disables color.
- As a responder, I want gzip log input, so that archives need no manual decompression. Priority: P1, Should; deferred beyond weekend.
- As a maintainer, I want custom log-format configuration, so that nonstandard nginx logs can be analyzed. Priority: P2, Could; deferred.

## Functional requirements
| ID | Priority | Requirement |
|---|---|---|
| F1 | P0 / Must | Stream one file or stdin using bounded lines and strict combined-format parsing |
| F2 | P0 / Must | Exact top-10 IP ranking across valid requests |
| F3 | P0 / Must | Exact top-10 query-stripped error paths, combined 4xx/5xx ranking and split counts |
| F4 | P0 / Must | Observed hour counts and percentages using the literal formula above |
| F5 | P0 / Must | Exact UA unique count and percentage against all valid requests |
| F6 | P0 / Must | Default Rich text, mutually exclusive --json/--csv, stable schemas |
| F7 | P0 / Must | Per-dimension --max-unique cap; never silently approximate |
| F8 | P0 / Must | pip package, console entry point, help/version, full exit codes |
| F9 | P1 / Should | gzip support after MVP |
| F10 | P2 / Could | Custom formats after MVP |

## Nonfunctional requirements
- Target decimal 1 GB in <30 seconds on a recorded laptop within the architecture's cardinality and line-size envelope; <=512 MiB peak RSS on its baseline workload. These are release gates to measure, not current results.
- No authentication, database, HTTP API, server, cloud or Kubernetes. No outbound runtime requests, telemetry or persisted aggregates.
- Stable deterministic order, six-decimal percentage rounding, bounded line framing, and explicit error diagnostics without raw log records.
- Python 3.11 minimum; local paths/stdin; portable logic with performance measurements tied to the measured OS/hardware.

## Acceptance scenarios
Use hand-calculated fixtures covering IPv4/IPv6, ties, timezone rollover/DST, status boundaries, repeated/missing UAs, quoted escapes, non-ASCII fields, malformed dates/bytes, empty input and maximum line size. Set --max-unique=1 to test first-key acceptance, repeated-key acceptance and second-key failure independently for IP, error URL, hour and UA dimensions. Include non-error URLs that must not consume the error-URL cap.

Validate exports with a JSON parser and CSV reader, not snapshots alone. Verify exit 0 success/help; 1 unreadable input/write failure/broken pipe; 2 conflicting flags/invalid ranges; 3 empty/all-malformed input; 4 unique-cardinality exhaustion. No runtime tests were run during blueprint authoring because product code is intentionally absent.

## Kill criteria and scope controls
If the optimized Python baseline cannot meet 30 seconds in the weekend, do not advertise success: record measurements and defer release or explicitly renegotiate the target. If exact cardinality exceeds the cap, fail with 4 rather than publishing partial analytics. If combined-format parsing cannot be made trustworthy, block MVP rather than silently guessing custom formats.

Out of scope: remote ingestion, follow mode, historical storage, dashboards, custom format configuration in MVP, authentication, cloud deployment, paid services, public publishing during this session and approximate counting. P1/P2 work cannot delay the Must release gates. Spec changes precede implementation changes.
