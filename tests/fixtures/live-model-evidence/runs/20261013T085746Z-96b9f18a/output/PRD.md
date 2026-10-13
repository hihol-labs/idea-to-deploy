# Product Requirements: Nginx Lens

## Problem and Goal

DevOps/SRE engineers need a fast, reproducible summary of local nginx access logs without deploying an analytics service. Deliver a Python 3.11 CLI installable through pip, with four exact metrics and terminal/JSON/CSV outputs. Budget is $0 and delivery is one weekend. See [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) for personas, alternatives, and prioritized roadmap.

## User Stories

Stories follow descending RICE priority within P0, subject to dependencies. All acceptance criteria below are required, not claims of existing functionality.

- As a DevOps engineer, I want to stream a combined access-log file or stdin so that I can inspect large logs without loading them entirely into memory.
  Priority: P0 / Must; RICE 160.
  Acceptance: a file and identical stdin yield identical report data; a valid final line without newline is accepted; empty input yields zero metrics and exit 0; malformed lines are skipped and counted, with exit 3 after report output; file failure returns 1. Oversize lines are bounded and counted once. Unsupported custom formats are diagnosed through malformed counts.

- As a responding SRE, I want the top ten IPs and error URLs so that I can identify dominant clients and failing paths.
  Priority: P0 / Must; RICE 106.67 (shared metric feature).
  Acceptance: IPs rank by all valid requests; paths rank by combined 4xx/5xx counts with separate family counts; query strings are removed; ties sort lexically; fewer than ten distinct values produce fewer rows. A fixture with a URL having two 404s and one 500 yields error_count 3, errors_4xx 2, errors_5xx 1. Exactly reaching the shared key budget succeeds; the next insertion that exceeds it returns 4 without a report.

- As an on-call engineer, I want hourly request percentages so that I can see when traffic concentrates.
  Priority: P0 / Must; RICE 106.67 (shared metric feature).
  Acceptance: use `100 × hourly_request_count / total_valid_requests`; convert timestamp offsets to UTC and aggregate hour-of-day across dates; emit every hour 00–23. A valid sample with counts 3 and 1 in two hours yields 75% and 25%; empty input yields 24 zero percentages. Include a timezone conversion that crosses midnight.

- As an SRE, I want the share of unique User-Agent strings so that I can assess client diversity in a request sample.
  Priority: P0 / Must; RICE 106.67 (shared metric feature).
  Acceptance: compute `100 × distinct_nonmissing_user_agents / total_valid_requests`. Four valid requests with UAs A, A, B, and `-` yield unique count 2 and share 50%; a zero denominator yields 0%. Strings are case-sensitive after nginx escape decoding; empty and `-` are missing. This is not a unique visitor estimate.

- As a terminal user, I want a readable colored report so that I can spot traffic patterns during an incident.
  Priority: P0 / Must; RICE 86.4.
  Acceptance: default output includes all summaries; TTY output uses Rich color; redirected output, NO_COLOR, and --no-color suppress ANSI. Untrusted strings appear literally, with terminal controls escaped. Terminal percentages show two decimal places.

- As a platform engineer, I want JSON and CSV reports so that automation can consume the same statistics reliably.
  Priority: P0 / Must; RICE 68.27.
  Acceptance: --json emits one schema-versioned object and --csv one table conforming to [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md#cli-interface); neither emits ANSI or stderr text to stdout. Counts match terminal report data; percentages use six decimal places of precision. CSV values containing quotes/commas round-trip through a CSV reader. Specifying both formats returns 2 with no report.

- As a DevOps engineer, I want pip installation, help, and reliable exit codes so that I can use the tool locally and in scripts.
  Priority: P0 / Must; RICE 57.6.
  Acceptance: a clean Python 3.11 environment can install the wheel and invoke nginx-lens; --help and --version return 0. The contract is 0/1/2/3/4: success, operational failure, usage error, skipped malformed input, unique-cardinality exhaustion. Integration tests exercise each code and confirm fatal errors do not emit completed reports.

- As an operator, I want native gzip input so that I can skip a decompression pipeline.
  Priority: P1 / Should; RICE 28. Deferred beyond the weekend; gzip -dc with shell pipe failure handling is the MVP workaround. Future acceptance requires parity with decompressed input and explicit corrupt-stream failures.

- As a frequent CLI user, I want shell completion so that repeated invocations require less typing.
  Priority: P2 / Could. Deferred; future completion must match documented options without runtime network access.

## Functional Requirements

P0 includes combined-format parsing, bounded input, all four exact metrics, deterministic sorting, resource-limit failure, terminal/JSON/CSV rendering, and pip packaging. The architecture's grammar, dataclasses, CSV row ordering, and exit precedence are normative. Stdout carries reports; stderr carries sanitized diagnostic summaries. No partial successful report is allowed after input failure or budget exhaustion. An output failure may leave partial bytes and must return 1.

## Nonfunctional Requirements

- Target 1 GB under 30 seconds on a recorded laptop with a bounded-cardinality benchmark; performance is not yet measured.
- One sequential input pass; no retained raw log history, disk spill, database, or runtime network access.
- Exact counters grow only within the configured aggregate key budget; reject overflow rather than approximate.
- Python 3.11 is the release verification baseline. Linux/macOS are primary local targets.
- Privacy: strip URL queries, never echo raw malformed lines, escape terminal controls, document sensitive reports.
- Reproducible test fixtures must be labeled synthetic and contain no production secrets.

## Scope and Release Gates

Out of scope: authentication, database, HTTP API, server, cloud, Kubernetes, arbitrary nginx log formats, follow mode, persistent history, dashboards, approximate statistics, automatic publication, and product telemetry. No additional product code is part of this planning session.

Kill/defer criteria: if the exact parser cannot reach the performance target after the planned profiling window, withhold the performance claim and release decision; record measurements and propose a new scope before further optimization. If exact key limits cannot be enforced or exports disagree, do not ship. Defer P1/P2 whenever P0 verification is incomplete. Stop optional feature work at the weekend budget; document unfinished P0 instead of silently relaxing it.

## Acceptance Evidence

Implementation must retain test results, core branch coverage, clean-wheel smoke output, and benchmark metadata/results. [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) maps these gates to steps; [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md) supplies execution prompts. External architecture review is pending and is not satisfied by this document.
