# PRD: Nginx Lens

## Problem and Product Goal

DevOps/SRE engineers need a reproducible local snapshot of nginx traffic without operating a reporting service. Deliver an open-source Python 3.11 CLI installable through pip in one weekend at $0 cash cost. The four reports, colored terminal default, JSON, and CSV are all MVP requirements.

## User Stories

Stories follow the RICE feature order from [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md); enabling dependencies are implemented first.

- As a responding SRE, I want to stream a combined log from a file or stdin so that I can investigate without loading the full file. **P0 / Must.** Acceptance: both inputs produce identical results; UTF-8, escaped quoted fields, IPv6, and final lines without newline work; oversized/malformed lines follow the architecture policy; the reader keeps no record history.
- As a platform engineer, I want exact top-10 IPs, error URLs, hourly percentages, and UA distinctness so that I can explain traffic reliably. **P0 / Must.** Acceptance: known fixtures match oracle counts; ties sort by key ascending; errors combine 400–599; at most 10 leaders are emitted; exactly 24 hour buckets appear; cardinality at the limit succeeds and the next new key exits 4 without a report.
- As a release engineer, I want stable options and exit codes so that pipelines detect failed analysis. **P0 / Must.** Acceptance: the complete 0/1/2/3/4 contract in the architecture is covered; incompatible flags and nonpositive limits exit 2; unreadable input exits 1; strict malformed input exits 3; stderr contains diagnostics without raw log lines.
- As a pipeline author, I want JSON and CSV so that downstream scripts can consume all four metrics. **P0 / Must.** Acceptance: schema version 1 and CSV header/row order match architecture; commas, quotes, and Unicode round-trip; stdout contains no ANSI or warnings; valid records mixed with malformed ones exit 0 with stderr warning unless strict.
- As a duty engineer, I want colored terminal summaries so that I can spot traffic leaders quickly. **P0 / Must.** Acceptance: all four reports and totals are labeled; Rich markup/control-byte attacks are rendered safely; auto color works on a TTY and is absent when redirected or NO_COLOR is set.
- As a maintainer, I want a pip-installed CLI and a repeatable capacity benchmark so that I can trust operational use. **P0 / Must.** Acceptance: a wheel installs and runs in a clean Python 3.11 venv; the specified 1 GB benchmark records hardware, run durations, median, and peak RSS and meets <30 seconds and <512 MiB under its stated conditions.
- As an SRE inspecting rotated logs, I want gzip input so that I can skip manual decompression. **P1 / Should, deferred.** Future acceptance: decompressed records match plain input, with the same exits and bounded reading.
- As an investigator, I want configurable top-N so that I can explore longer tails. **P2 / Could, deferred.** Future acceptance: positive N replaces fixed 10 without changing ranking rules.

## Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| F1 | P0 | Accept one combined-format file or stdin; consume to EOF |
| F2 | P0 | Count valid records by canonical IP and error URL with deterministic top-10 |
| F3 | P0 | Hourly request distribution is percentage `100 × hourly_request_count / total_valid_requests` |
| F4 | P0 | Unique-UA share is `100 × distinct_nonmissing_user_agents / total_valid_requests` |
| F5 | P0 | Default Rich text plus mutually exclusive JSON/CSV exports |
| F6 | P0 | Enforce strict/tolerant parse modes and shared exact-cardinality limit |
| F7 | P0 | Complete exit contract: 0 success, 1 I/O/internal/interruption, 2 usage, 3 parse/no-valid, 4 unique-cardinality exhaustion |
| F8 | P1 | gzip support after MVP |
| F9 | P2 | Custom top-N after MVP |

Hours use each record's logged hour-of-day including its original offset, combined across dates; zero buckets are present. Missing UAs stay in the valid-request denominator but not the unique numerator. Empty input yields zeros and success; all-malformed nonempty input yields code 3. Percentages are zero with zero valid requests and rounded to two decimal places otherwise. Full edge-case semantics live in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md).

## Nonfunctional Requirements

Single process; no full-file buffering or persistent state. Exact counters grow with distinct keys and stop at the configured shared-key cap. Target 1,000,000,000 bytes in <30 seconds on a documented laptop under the architecture's benchmark conditions. No claim of measured performance until implementation. Local-only execution, no telemetry, synthetic fixtures, terminal-safe output, and stable deterministic exports are required.

## Out of Scope

Authentication, database, HTTP API, server, cloud, Kubernetes, Docker setup, live dashboards, follow mode, geolocation, custom formats, date-range filtering, approximate counters, and external log collection. No product code is part of this blueprint session.

## Release and Kill Criteria

Release only when every P0 acceptance criterion and the strategic Definition of Done passes. If throughput remains above 30 seconds after the weekend profiling budget, keep the release blocked and record measurements; do not call it complete or add multiprocessing silently. If exact cardinality cannot meet the documented benchmark memory budget, revise the spec with the owner before release. If the narrow workflow offers no benefit over an existing alternative in pilot use, stop expansion rather than add a platform.

## Delivery Links

[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) defines eight concrete steps. [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md) turns them into prompts; [CLAUDE.md](CLAUDE.md) tracks future execution. [README.md](README.md) describes installation and use.
