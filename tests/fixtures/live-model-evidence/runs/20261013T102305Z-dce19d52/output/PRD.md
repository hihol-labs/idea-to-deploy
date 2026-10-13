# Product Requirements: Nginx Lens

## Product and Outcome

Enable a DevOps/SRE engineer to summarize a finite nginx combined access log locally, without an analytics server. Required reports are top-10 IPs, top-10 URLs by combined 4xx/5xx errors, hourly request percentages, and the share of unique User-Agents. Provide colored terminal output plus JSON and CSV for pipelines. This document defines future behavior; no product implementation is delivered by this blueprint.

Related: [strategy](STRATEGIC_PLAN.md), [architecture and CLI contract](PROJECT_ARCHITECTURE.md), [implementation plan](IMPLEMENTATION_PLAN.md), [developer guide](CLAUDE_CODE_GUIDE.md), [quick start](README.md), [project memory](CLAUDE.md).

## User Stories

Stories follow the strategy's RICE ordering by feature group: metrics, exports, parser workflow, then guardrails/delivery. Dependencies still determine implementation order. P0 = Must, P1 = Should, P2 = Could.

- As a responding SRE, I want the top ten client IPs so that I can identify dominant traffic sources. **S1 — P0.**
  - [ ] AC1: A hand-audited input with more than ten canonical IPs returns exactly ten in descending valid-request count, ties in ascending canonical IP text order.
  - [ ] AC2: Fewer than ten IPs returns only present entries, invalid lines are excluded, and equivalent IPv6 spellings group together.
- As a service owner, I want the top ten failing URLs so that I can prioritize broken resources. **S2 — P0.**
  - [ ] AC3: Rank request targets by combined 400–599 count with separate 4xx and 5xx counts; exclude all other statuses from this ranking.
  - [ ] AC4: A target with two 404s and one 503 has error_count=3, count_4xx=2, count_5xx=1; ties use ascending target text. Query strings remain part of the key.
- As a capacity engineer, I want hourly request percentages so that I can understand the daily traffic pattern. **S3 — P0.**
  - [ ] AC5: Emit 24 UTC hour-of-day buckets across all dates using `100 × hourly_request_count / total_valid_requests`.
  - [ ] AC6: Three requests in UTC hour 11 and one in hour 12 yield 75% and 25%; all other buckets yield 0%. Test timestamps with different offsets mapping into the same UTC hour and a UTC date crossing.
- As a DevOps engineer, I want the share of distinct User-Agents so that I can assess client diversity. **S4 — P0.**
  - [ ] AC7: For four valid records with agents `A`, `A`, `B`, `-`, report distinct known count 2 and share 50%, using all four valid requests in the denominator.
  - [ ] AC8: UA comparison is case-sensitive; empty/`-` agents are unknown. Zero valid requests yields 0 distinct agents and 0%, never NaN or division failure.
- As a pipeline maintainer, I want terminal, JSON, and CSV output so that humans and scripts consume the same metrics. **S5 — P0.**
  - [ ] AC9: Default TTY rendering is colored; `--no-color`, `NO_COLOR`, and redirected stdout remove ANSI escapes. Literal log fields cannot invoke Rich markup or terminal controls.
  - [ ] AC10: `--json` emits one version-1 object and `--csv` emits one table with the exact architecture schema; parse exports with standard JSON/CSV parsers and compare counts and percentages.
  - [ ] AC11: JSON/CSV contain no progress text or ANSI; diagnostics stay on stderr. CSV formula/control protection changes display keys only, and JSON preserves original decoded keys.
- As a responder, I want to read a file or stdin despite isolated bad records so that one malformed line does not hide otherwise useful traffic. **S6 — P0.**
  - [ ] AC12: A finite file, omitted input with piped stdin, and explicit `-` produce identical metrics. UTF-8 combined lines with LF/CRLF or no final newline are accepted.
  - [ ] AC13: Two valid records plus one invalid record produce total_lines=3, total_valid_requests=2, invalid_lines=1, a report with complete=true, and exit 3 by default. Strict mode exits 3 at the invalid record with no stdout report.
  - [ ] AC14: Invalid timestamps, invalid IPs, unsupported escapes, invalid UTF-8, unsupported formats, and overlong records are classified as invalid; no raw log data appears in diagnostics.
- As a platform engineer, I want explicit resource and failure behavior so that automation never mistakes incomplete results for a successful report. **S7 — P0.**
  - [ ] AC15: Exercise the full exit contract: 0 success/empty/help/version; 1 read/write/internal error; 2 usage error; 3 malformed records; 4 unique-cardinality exhaustion for either retained-key limit.
  - [ ] AC16: At either limit, existing keys still work; adding a key over a cap aborts with code 4 and no report. A multi-key record is preflighted atomically. No approximate or silently truncated results are produced.
  - [ ] AC17: A later fatal capacity or I/O failure overrides earlier nonfatal malformed records. A broken pipe returns 1 without a traceback; output already written cannot be retracted.
- As a DevOps engineer, I want a pip-installable local tool so that I can inspect large files without provisioning infrastructure. **S8 — P0.**
  - [ ] AC18: Build a wheel, install it in a clean Python 3.11 venv, and exercise help/version and all report modes without a database, credentials, or network service.
  - [ ] AC19: The defined 1,000,000,000-byte reference fixture completes in under 30 seconds and at most 512 MiB peak RSS for every measured warm-cache repetition; publish environment metadata and real results.
- As a SRE, I want gzip input so that rotated logs need no separate decompression command. **S9 — P1, deferred.** Acceptance for a future iteration: decompressed content gives the same report and invalid-line policy; include decompression cost in a separately defined performance profile.
- As a service owner, I want optional date and status filters so that I can inspect a narrower incident window. **S10 — P2, deferred.** Future acceptance must explicitly define filtered denominators before implementation.

## Functional Requirements

| Priority | Requirement | Stories |
|---|---|---|
| P0 | Exact IP and combined-error URL top-ten rankings with deterministic ties | S1, S2 |
| P0 | UTC 24-hour distribution and exact known-UA diversity percentage | S3, S4 |
| P0 | Terminal, JSON, CSV and documented escaping/schema | S5 |
| P0 | Finite file/stdin combined parser, skipped counts and strict option | S6 |
| P0 | Bounded lines and key state; complete exit contract 0/1/2/3/4 | S7 |
| P0 | Python 3.11 pip package and measured performance release gate | S8 |
| P1 | gzip input | S9 |
| P2 | Date/status filtering | S10 |

## Semantic Contract

A valid request is one complete supported combined record, even when its status is a 4xx or 5xx. Malformed records affect invalid totals only. Both percentages use total valid requests as denominator: hourly `100 × hourly_request_count / total_valid_requests`; unique UA `100 × unique_user_agent_count / total_valid_requests`. Empty denominators produce 0%. Round to six decimal places; percentages are scaled values, not fractions. Hourly buckets combine dates after timezone normalization. Unique share is a distinct-count ratio, not bot detection or frequency analysis.

Raw request targets, including query strings, are grouped as URLs after log escaping is decoded; no percent decoding, normalization, or query removal occurs. This can create high cardinality and expose sensitive fields in local exports. Users control where they store/share those exports. Complete=true means EOF reached, not that every line was valid; consult invalid_lines and exit status.

## Nonfunctional Requirements

- Process input once with bounded physical-line buffering and limited exact key state; never read a gigabyte file into memory as a whole.
- Default caps: 250,000 retained keys combined and 67,108,864 UTF-8 key bytes; line limit 65,536 bytes excluding newline. Exceeding either key cap returns 4; a line-size violation is malformed input, code 3.
- Target the architecture's recorded laptop/reference workload at under 30 seconds and at most 512 MiB RSS, including process startup through final output. This is a release target, not a measured claim.
- Keep runtime local, offline, and stateless between runs. Use Python 3.11, Click, Rich, and dataclasses; no authentication, persistence service, HTTP API, or telemetry.
- Maintain JSON/CSV schema version 1, deterministic ranking, locale-independent timestamps, and stable exit semantics across supported environments.
- Open-source MIT distribution, $0 incremental infrastructure cost, and one-weekend implementation budget.

## Out of Scope

Authentication, database, HTTP API, server, hosted dashboards, cloud, Kubernetes, live follow/rotation tracking, custom nginx formats, historical persistence, GeoIP, user tracking, bot classification, approximate sketches, compressed input in MVP, and filters in MVP. No graphical UI is needed for terminal/pipeline workflows.

## Kill and Release-Hold Criteria

Hold MVP release if any P0 correctness or exit-code criterion fails, exact results silently degrade, raw input can execute/control output, clean wheel installation fails, or the defined benchmark misses its target after the tuning allowance. Preserve failing evidence; do not relabel a smaller file or weaker machine workload as the target.

Stop expanding the utility if three initial target engineers cannot identify a recurring need beyond their existing alternatives; gather voluntary feedback first. Adoption targets are hypotheses and do not block technical completion. If required exact cardinality routinely exceeds the safe defaults, revisit scope openly rather than adding a database or approximation without a new decision.

## Acceptance and Handoff

Trace AC1–AC8 to parser/aggregator tests, AC9–AC11 to render/schema tests, AC12–AC17 to reader/CLI/limit tests, AC18 to wheel installation, and AC19 to benchmark evidence. Product acceptance requires the strategy's Definition of Done. Blueprint static validation does not satisfy runtime criteria. Independent architecture review remains owned by the external harness; current product step statuses remain unstarted.
