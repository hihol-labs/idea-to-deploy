# Product Requirements: Nginx Lens

## Product and scope
A local, pip-installable Python 3.11 CLI helps DevOps/SRE engineers summarize nginx combined access logs during incident response. It reads a file or stdin through EOF and emits colored terminal text by default, JSON with `--json`, or CSV with `--csv`. See [strategy](STRATEGIC_PLAN.md) for personas and prioritization and [architecture](PROJECT_ARCHITECTURE.md) for the binding schemas and CLI contract.

P0 = MoSCoW Must; P1 = Should; P2 = Could. Story order follows RICE, with prerequisites respected. All following acceptance checks describe future tests; none have been executed against a product in this planning session.

## User Stories
- As a DevOps engineer, I want to stream a combined access log from a file or stdin so that I can inspect incidents without importing data. (US-1, P0)
  - [ ] The same bytes from a path and stdin produce identical metric payloads in JSON.
  - [ ] A valid line is counted once; malformed/invalid UTF-8/oversized lines are counted once as malformed and excluded from metrics.
  - [ ] Mixed valid/malformed input returns 0 with a warning; nonempty input with no valid records returns 3 without a report; empty input returns 0 with an empty report.
  - [ ] Input is read incrementally and no runtime network/service dependency exists.
- As an on-call SRE, I want top-10 client IPs and top-10 error URLs so that I can identify traffic sources and failing request targets. (US-2, P0)
  - [ ] IP ranks count all valid requests; error URL ranks count only 400–599 statuses with combined 4xx/5xx totals.
  - [ ] Up to ten entries appear per list, ordered by count descending and key ascending on ties.
  - [ ] Query strings remain part of the target; `/a?x=1` and `/a?x=2` remain distinct.
  - [ ] A fixture covering 399, 400, 499, 500, and 599 proves error boundaries.
- As an SRE investigating a traffic spike, I want hourly request percentages so that I can compare traffic distribution by logged hour. (US-3, P0)
  - [ ] The report contains hours 00–23, counts, and percentages calculated as `100 × hourly_request_count / total_valid_requests`.
  - [ ] With four valid requests, three at hour 10 and one at hour 11, those buckets are 75.00% and 25.00%; malformed records do not alter the denominator.
  - [ ] Bucket by each record's logged hour-of-day across dates and offsets; perform no UTC conversion.
  - [ ] Empty input produces 0.0 for each hourly percentage; rounding is to two decimal places.
- As a service maintainer, I want the share of unique User-Agent strings so that I can assess client-string diversity. (US-4, P0)
  - [ ] The numerator counts exact distinct nonmissing strings and the denominator counts valid requests with a nonmissing User-Agent.
  - [ ] For agents A, A, B, and `-`, unique count is 2, observed-agent requests is 3, and share is 66.67%.
  - [ ] Empty strings and `-` are missing; case variants remain distinct; no observed agents yields null JSON share, empty CSV share cell, and text N/A.
  - [ ] Labels explain that strings do not identify unique people.
- As a platform engineer, I want stable JSON and CSV output so that I can compose shell pipelines reliably. (US-5, P0)
  - [ ] JSON schema version 1 and the normalized CSV header/sections match architecture's CLI Interface exactly.
  - [ ] stdout contains only the selected report; errors/warnings go to stderr; no ANSI codes appear in exports.
  - [ ] CSV round-trips commas, quotes, Unicode and newline escapes using a standard CSV reader; JSON parses with a standard JSON decoder.
  - [ ] Combining `--json` and `--csv` returns 2.
- As an on-call engineer, I want readable default terminal tables so that I can scan all four metrics quickly. (US-6, P0)
  - [ ] Default output includes both top lists, 24 hourly counts/percentages, User-Agent statistics, valid count and malformed count.
  - [ ] Color follows TTY detection and NO_COLOR in auto mode; explicit always/never is honored.
  - [ ] Untrusted labels cannot inject Rich markup or terminal control sequences.
- As an operator of untrusted logs, I want a deterministic unique-key limit so that excessive cardinality cannot silently distort the answer. (US-7, P0; cross-cutting safety prerequisite for US-2–US-4)
  - [ ] Shared default cap is 250000 keys across IP, error URL, and User-Agent collections, with a positive `--max-unique` override.
  - [ ] At the cap aggregation succeeds; insertion of a new record that would exceed it aborts atomically with code 4 and a stderr diagnostic, without a partial report.
  - [ ] No sampling, eviction, approximation, or disk spill substitutes for exact results.
- As a new user, I want actionable custom-format diagnostics so that I can correct unsupported nginx log configuration. (US-8, P1)
  - Guidance names supported combined format without echoing full potentially sensitive records; defer enhanced detection beyond MVP.
- As a frequent CLI user, I want shell completion so that I can discover options faster. (US-9, P2)
  - Add completion only after the P0 release criteria are satisfied.

## Functional requirements
P0 includes US-1–US-7, local pip installation, help/version, deterministic ties, all five exit codes, bounded line reads, and warning accounting. P1 includes enhanced format diagnostics. P2 includes completion. The shared cardinality guard is implemented with metrics even though its user story is cross-cutting.

The complete exit contract is **0/1/2/3/4**: 0 success/empty/help/version; 1 I/O, interruption, or internal failure; 2 invalid CLI usage; 3 nonempty input with no valid records; 4 unique-cardinality exhaustion. Architecture specifies precedence and the limits of stdout atomicity for write failures.

## Nonfunctional requirements
- Performance target: 1,000,000,000 bytes in <30 seconds on a documented laptop; three-run median and peak RSS evidence required. No claim that this target has been met yet.
- Resource target: ≤512 MiB peak RSS on the declared representative corpus, with exact counts and default shared key cap. Worst-case long keys can consume more memory; the cap is not a universal byte-memory guarantee.
- Compatibility: Python 3.11 on local Linux/macOS; terminal output respects redirected stdout. Windows compatibility is deferred until tested.
- Privacy/security: no network calls or telemetry, read-only source access, bounded lines, safe terminal labels, and no log contents in default diagnostics.
- Correctness: independently calculated synthetic golden fixtures, all P0 acceptance cases passing, and core parser/aggregator branch coverage target ≥90%.

## Out of scope
Authentication, database, HTTP API, server, cloud, Kubernetes, persistent history, live tail, custom nginx formats, compressed-file decoding, dashboards, approximate metrics, bot classification, remote fetching, and multiple path arguments. External tools may concatenate/decompress into stdin. No product code is delivered by this blueprint.

## Release and kill criteria
Release only when P0 acceptance checks, package smoke tests, documented performance checks, and future code review satisfy [Definition of Done](STRATEGIC_PLAN.md). Stop release if metrics are silently wrong, code 4 is missing, exports are unstable, or private records leave the machine. If <30 seconds remains unattainable after a measured optimization pass within the weekend, record the miss and revisit the delivery promise; do not declare success, silently approximate, or substitute Go for the approved Python stack.

See [implementation plan](IMPLEMENTATION_PLAN.md), [developer prompts](CLAUDE_CODE_GUIDE.md), [quick start](README.md), and [agent rules](CLAUDE.md).
