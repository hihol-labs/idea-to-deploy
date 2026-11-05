# Product Requirements: Nginx Lens

## Problem and Goals

DevOps/SRE engineers need repeatable local nginx summaries during incidents without provisioning a service. Deliver the four required metrics through a pip-installable Python 3.11 CLI over a weekend for $0. [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) defines exact parsing, ordering, schemas and failure behavior. [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md) records priorities and planning assumptions.

## User Stories

Stories follow RICE order, subject to dependencies. P0 = Must, P1 = Should, P2 = Could.

- As a DevOps engineer, I want to stream a combined-log file or stdin so that large logs do not have to fit in memory. Priority: P0.
  - [ ] File and stdin produce identical summaries; no read-all operation is used.
  - [ ] Escaped quoted fields, IPv6, invalid UTF-8, oversized lines and missing final newline follow the architecture grammar.
  - [ ] Invalid lines increment invalid_lines and do not affect valid-request aggregates.
- As a SRE, I want the ten busiest IPs and ten paths with the most 4xx/5xx responses so that I can locate concentrated traffic and errors. Priority: P0.
  - [ ] Counts match hand-calculated fixtures; 4xx and 5xx counts sum to each error total.
  - [ ] Ties sort lexically; fewer than ten candidates produce fewer rows; query strings do not split paths.
- As an incident responder, I want hourly percentages and the share of unique User-Agents so that I can understand traffic timing and client diversity. Priority: P0.
  - [ ] UTC conversion occurs before the 24 hour-of-day buckets are populated.
  - [ ] Hourly percentage uses `100 × hourly_request_count / total_valid_requests`.
  - [ ] Unique-UA percentage is 100 times exact distinct nonmissing UAs divided by requests with a nonmissing UA; report both counts. Two distinct UAs over four eligible requests yields 50%.
  - [ ] Empty/all-invalid input yields zero metrics and 24 zero hour rows, exit 0.
- As a platform engineer, I want JSON and CSV reports so that shell pipelines can consume stable structured output. Priority: P0.
  - [ ] JSON schema_version is 1; field names and CSV header match the architecture.
  - [ ] Unicode, quotes, commas and control characters serialize correctly without ANSI codes.
  - [ ] Mutually exclusive output flags produce exit 2 and no report.
- As an on-call engineer, I want readable colored terminal summaries so that I can inspect results quickly. Priority: P0.
  - [ ] Default text shows all four metrics and valid/invalid totals.
  - [ ] --no-color, NO_COLOR and redirected stdout disable color; log values cannot inject Rich markup or terminal control sequences.
- As a reliability engineer, I want explicit resource and failure outcomes so that an incomplete computation cannot appear successful. Priority: P0.
  - [ ] Exit contract is 0/1/2/3/4: success, I/O/runtime failure, usage error, interruption, unique-cardinality exhaustion respectively.
  - [ ] Cardinality boundary success and first over-budget record failure are tested across all three collections; exit 4 emits no report.
  - [ ] Read failures emit no report; interrupted processing returns 3; write failures return 1 even if output is partially written.
- As a maintainer, I want a pip-installable package so that users can run the same command in a fresh environment. Priority: P0.
  - [ ] A built wheel installs locally on Python 3.11; help, version and a fixture invocation succeed outside the source directory.
- As a new operator, I want extra troubleshooting examples so that I can diagnose rejected custom log formats. Priority: P1.
- As a frequent shell user, I want shell completion so that command entry is easier. Priority: P2.

## Functional Requirements

P0: one finite file or stdin, documented combined grammar, bounded reader, exact aggregation, deterministic top ten, all UTC buckets, unique-UA share, text/JSON/CSV renderers, stderr diagnostics, full exit contract, local pip install. P1: additional troubleshooting examples beyond the MVP Quick Start. P2: shell completion. Optional features must not delay P0 acceptance.

## Nonfunctional Requirements

Python 3.11, Click, Rich and dataclasses; no network access or persistent data store. Runtime target is 1 GB under 30 seconds under the architecture's declared benchmark protocol. Memory grows with bounded distinct keys, never total line count. No telemetry or external data transfer. Source code is open under MIT; use synthetic test fixtures rather than copied production logs.

## Scope Exclusions

No auth, database, HTTP API, server, cloud, Kubernetes, Docker requirement, custom format auto-detection, compressed input, live follow, date-specific trend history, geolocation, dashboards or approximate counting. No product implementation is part of this blueprint session.

## Success, Kill Criteria and Release Gate

Release only after all P0 stories and the [strategic DoD](STRATEGIC_PLAN.md) pass with recorded evidence. Stop the weekend release if exact counts are incorrect, default-budget workloads exceed resource limits unexpectedly, the benchmark misses 30 seconds after focused profiling, or packaging/failure tests remain red. Defer P1/P2 first; changing exactness, runtime language or scope requires an explicit new decision. Do not relax criteria to declare success.

## Traceability

Parser story -> implementation steps 1–2; metric stories -> step 3; exports -> step 4; text -> step 5; failures -> steps 3 and 6; packaging and speed -> steps 7–8 in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md) supplies prompts; [CLAUDE.md](CLAUDE.md) tracks implementation status.
