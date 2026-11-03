# Product Requirements: Nginx Pulse

## Product and Problem
DevOps/SRE engineers need a quick offline summary of nginx access logs without deploying a service. A finite-stream CLI reads a file or stdin and reports exactly four views. See [strategy](STRATEGIC_PLAN.md) for positioning, [architecture](PROJECT_ARCHITECTURE.md) for the precise interface, and [plan](IMPLEMENTATION_PLAN.md) for delivery.

## Scope and Priorities
P0 = Must: combined-log streaming, four exact metrics, safe diagnostics/resource bounds, colored terminal text, JSON/CSV, pip installability and benchmark validation. P1 = Should: gzip input and time-range filtering after MVP. P2 = Could: alternate theme. Won't: authentication, database, HTTP API, server, cloud, Kubernetes, tail-follow, dashboard, custom format support, approximate counting or persisted reports.

## User Stories
Stories are in RICE feature order, with shared safety built into each dependent feature.

- As a DevOps engineer, I want to process a local combined log or stdin once so that I can inspect incidents without infrastructure. (S1, P0)
  Acceptance: file and stdin yield identical results; malformed/blank/oversized/invalid UTF-8 lines are counted and skipped; mixed input gives one stderr warning and exit 0; empty or all-malformed input gives exit 3 with no report. Memory use does not grow with the number of repeated records.
- As a responding SRE, I want the ten busiest IPs and ten paths with the most 4xx/5xx responses so that I can find traffic sources and failures. (S2, P0)
  Acceptance: IPs count every valid request; URL counts combine statuses 400–599 only; query strings are stripped; ranking is count descending then key ascending; emit fewer than ten rows when fewer keys exist. A fixture tied at rank ten has a stable winner. An input without errors produces an empty error ranking.
- As a site operator, I want hourly request percentages so that I can see when traffic peaks. (S3, P0)
  Acceptance: emit all 24 buckets with counts and percentage `100 × hourly_request_count / total_valid_requests`; buckets use each log timestamp's local hour across all dates; malformed requests never enter the denominator. A fixture with three valid requests in one hour and one in another yields 75% and 25%. Round percentages only at output to six decimal places.
- As an SRE, I want the share of unique User-Agents so that I can quantify client-string diversity. (S4, P0)
  Acceptance: share = `100 × unique_nonmissing_user_agent_count / total_valid_requests`; exact case-sensitive unescaped UA strings define uniqueness; `-`/empty UA is excluded from the set but included in valid-request count. Four valid requests with A, A, B and missing UA yield count 2 and share 50%. Raw UAs never appear in reports.
- As an on-call engineer, I want a colored terminal summary so that I can read the four views quickly. (S5, P0)
  Acceptance: default TTY output includes all views, totals and skipped count; redirection, `NO_COLOR` and `--no-color` remove ANSI escapes; markup/control-looking log paths do not execute or alter terminal formatting. No-error input has a clear empty state.
- As a DevOps engineer, I want JSON and CSV so that I can consume the same results in pipelines. (S6, P0)
  Acceptance: `--json`/`--csv` follow architecture schema v1, with deterministic rankings, complete hourly rows and correct quoting. Parsed exports equal the independent fixture oracle. stdout contains no progress, colors or warnings; both flags together exit 2. A clean wheel installation exposes the same command behavior.
- As an SRE handling untrusted logs, I want explicit failure when uniqueness budgets are exhausted so that I never trust an incomplete exact report. (S7, P0)
  Acceptance: default combined distinct-key budget is 250000 and key-byte budget is 64 MiB. Boundary cases succeed; one new entry or byte beyond the relevant budget gives code 4 and no final report. Existing keys remain allowed at the limit; cross-container duplicates occupy separate slots. `--max-unique` overrides slots only. A failing record does not partially update metrics.
- As a DevOps engineer, I want compressed input directly so that I can skip an external decompressor. (S8, P1, deferred)
  Future acceptance: identical summaries for compressed and plain equivalent inputs; specification changes precede implementation.
- As a responding SRE, I want a time-range filter so that I can isolate an incident window. (S9, P1, deferred)
  Future acceptance: explicit boundary/timezone semantics and denominator tests must be specified before work.
- As a terminal user, I want an alternate theme so that I can match my terminal contrast preferences. (S10, P2, deferred)

## Functional Requirements
FR1: One finite standard combined-format stream; no hidden configuration or network access. FR2: exact metrics and deterministic ordering. FR3: valid timestamps/status/IPs, bounded reading and counted skips. FR4: final report only after EOF. FR5: versioned JSON/CSV and readable terminal presentation. FR6: stable exit codes **0/1/2/3/4**: success, I/O failure, usage error, no-valid-input/interruption/processing failure, unique-cardinality exhaustion, respectively. FR7: no auth or persistent data. The architecture defines detailed options, fields and error precedence.

## Nonfunctional Requirements
- Python 3.11, Click, Rich and dataclasses; installable using pip.
- One process, sequential streaming with bounded line and retained-key resources; no full input load or disk spill.
- Process 1,000,000,000 bytes in <30 seconds end-to-end; peak RSS ≤512 MiB on a documented laptop with a seeded below-budget corpus. Every one of three runs must pass. This is an acceptance target pending implementation, not measured evidence.
- Resource exhaustion is an expected explicit error, not a memory-management promise for arbitrary logs. Test high-cardinality failure separately.
- No runtime network, telemetry, credentials or writes to source. Use synthetic fixtures and literal terminal text handling.
- $0 cash budget, one weekend approximately 14 hours. Tests and documentation are part of delivery.

## Acceptance and Traceability
| Stories / requirement | Planned evidence |
|---|---|
| S1 | reader/parser/CLI fixtures, bounded draining and stdin parity |
| S2–S4 | hand-calculated aggregate oracle, ties, offsets and missing UA |
| S5 | TTY/redirection/control-character terminal tests |
| S6 | parsed JSON/CSV parity and installed-wheel smoke tests |
| S7, FR6 | boundary/byte-cap tests and complete subprocess exit matrix |
| Performance | benchmark report with hardware, corpus and three actual runs |
Each P0 story is release-blocking. [Implementation guide](CLAUDE_CODE_GUIDE.md) provides prompts and commands; no such product tests ran in this planning session.

## Release and Kill Criteria
Release only after P0 acceptance, core ≥90% branch coverage, complete green suite, local wheel verification and measured performance acceptance. Publishing requires later human authorization. If the throughput target fails after the allotted profiling time, stop release, retain the failing measurement and revisit design/time budget explicitly. If safety requires approximation or a database to complete a dataset, exit 4 under this design rather than changing the promised product. If ordinary target logs repeatedly exhaust the cap, reassess limits using measured RSS before release. Never claim success by excluding malformed counts or silently using a smaller denominator.

## Status
Blueprint authored; implementation pending. External harness owns adversarial review in a fresh session. No independent review verdict or performance result is asserted here.
