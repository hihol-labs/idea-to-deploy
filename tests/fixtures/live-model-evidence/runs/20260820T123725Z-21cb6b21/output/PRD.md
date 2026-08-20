# Product Requirements Document: nginx-analyzer

## Product Summary

`nginx-analyzer` gives DevOps and SRE engineers a fast local summary of an nginx combined access log. It streams one file or stdin and reports top client IPs, error-producing URLs, hourly request percentages, and User-Agent diversity. The default is colored terminal text; JSON and CSV are stable pipeline outputs.

The MVP is an open-source, pip-installable Python 3.11 CLI delivered in one weekend with a $0 cash budget. `PROJECT_ARCHITECTURE.md` is the source of truth for interface and internal design decisions.

## Goals

- Produce all four required summaries from a single streaming pass.
- Process the canonical 1 GB fixture in under 30 seconds on a documented laptop.
- Work naturally with local files and Unix pipelines.
- Provide deterministic, consistent Rich, JSON, and CSV representations.
- Bound exact User-Agent cardinality with an explicit failure contract.
- Require no persistent or remote infrastructure.

## Non-Goals

- Authentication or authorization.
- Database, cache, index, or historical storage.
- HTTP API, daemon, server, web UI, or interactive dashboard.
- Cloud service, telemetry, Kubernetes, or container deployment.
- Multiple simultaneous inputs, tail/follow mode, gzip support, or arbitrary nginx `log_format` configuration in MVP.
- Geographic lookup, bot classification, sessionization, alerting, or request-body analysis.

## Personas

1. **On-call SRE:** needs a rapid, trustworthy incident overview from a copied or piped log.
2. **DevOps engineer:** needs local analytics without deploying and maintaining a log platform.
3. **Platform automation author:** needs stable machine output and exit behavior for scripts and CI jobs.

## User Stories

### US-1 — Stream supported input

As an on-call SRE, I want to analyze one nginx combined log from a file or stdin so that I can use the same tool interactively and in a pipeline.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] `nginx-analyzer access.log` and `cat access.log | nginx-analyzer -` produce semantically identical reports for identical bytes.
- [ ] The process reads incrementally and does not retain raw records after aggregation.
- [ ] Default tolerant mode skips non-empty malformed lines, reports their count, and succeeds if at least one valid record remains.
- [ ] `--strict` stops at the first malformed non-empty line and exits 3 without a report.
- [ ] An unreadable input or an input with zero valid records exits 3.

### US-2 — Identify top client IPs

As an on-call SRE, I want the top 10 client IPs by request count so that I can spot dominant clients quickly.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Every valid record increments the exact logged client IP once.
- [ ] At most 10 rows are returned, ordered by descending count and then ascending lexical IP for ties.
- [ ] IPv4 and IPv6 text values are accepted without network lookup or normalization that merges distinct logged strings.
- [ ] Rich, JSON, and CSV expose the same keys, counts, and ranks.

### US-3 — Find error-producing URLs

As an SRE investigating failures, I want the top 10 request targets with 4xx or 5xx responses so that I can prioritize broken or abused endpoints.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Status codes 400–599 are included; all other status codes are excluded.
- [ ] Counts for 4xx and 5xx responses are combined per exact request target, including its query string.
- [ ] At most 10 rows are returned, ordered by descending error count and then ascending lexical target for ties.
- [ ] Rich, JSON, and CSV expose the same keys, counts, and ranks.

### US-4 — Understand hourly traffic distribution

As a DevOps engineer, I want a 24-hour request distribution so that I can see when traffic is concentrated.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Exactly 24 buckets labeled `00` through `23` are emitted in order, including zero-count hours.
- [ ] The hour comes from the timestamp as logged; no cross-timezone conversion occurs.
- [ ] Each bucket percentage uses the literal formula `100 × hourly_request_count / total_valid_requests`.
- [ ] Percentages are reported as percentages, not unscaled fractions, and are rounded to at most six decimal places in machine output.
- [ ] Unrounded bucket percentages sum to 100% when at least one valid request exists.

### US-5 — Measure User-Agent diversity safely

As a platform engineer, I want the share of distinct User-Agent values so that I can estimate client diversity without retaining the log.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Each exact decoded User-Agent value, including the literal `-`, participates in distinct counting.
- [ ] Share is calculated as `100 × distinct_user_agent_count / total_valid_requests` and is labeled as a percentage.
- [ ] Output includes distinct count, total valid request count, and percentage.
- [ ] The default exact-cardinality ceiling is 1,000,000 and can be changed to another positive integer.
- [ ] Exceeding the ceiling exits 4, identifies unique-cardinality exhaustion on stderr, and emits no partial report.

### US-6 — Use human-readable terminal output

As an on-call SRE, I want a colored terminal report by default so that the important rankings and percentages are easy to scan.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] With no machine-format option, stdout contains a summary and all four report sections.
- [ ] Color is used only when stdout is a TTY and `--no-color` is absent.
- [ ] Log-derived text is escaped or rendered with markup disabled so it cannot inject Rich markup or terminal controls.
- [ ] Redirected terminal text and `--no-color` contain no ANSI escape sequences.

### US-7 — Integrate with pipelines

As an automation author, I want JSON and CSV outputs with stable exit codes so that scripts can consume results safely.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] `--json` emits one valid UTF-8 JSON document with schema version 1 and all four metrics.
- [ ] `--csv` emits parseable UTF-8 CSV with `section,key,count,percentage,rank` and all four metrics.
- [ ] `--json` and `--csv` are mutually exclusive and their combination exits 2.
- [ ] Machine outputs never contain ANSI color or diagnostics on stdout.
- [ ] Integration tests exercise the complete exit-code contract: `0` success, `1` unexpected internal failure, `2` usage error, `3` input/data failure, and `4` unique-cardinality exhaustion.

### US-8 — Reject malformed data immediately when requested

As a platform automation author, I want strict parsing so that a validation job cannot overlook corrupt input.

**Priority:** P1 (Should)

**Acceptance criteria:**

- [ ] `--strict` reports the first malformed line number without echoing raw sensitive content.
- [ ] The command exits 3 and emits no report after the strict failure.

### US-9 — Read compressed logs directly

As a DevOps engineer, I want gzip input so that I can avoid a decompression pipeline.

**Priority:** P2 (Could)

**Acceptance criteria:**

- [ ] If scheduled after MVP, `.gz` input preserves the same parser, metrics, output, and exit contracts.

### US-10 — Parse custom nginx formats

As a DevOps engineer, I want declarative custom `log_format` support so that nonstandard installations can use the analyzer.

**Priority:** P2 (Could)

**Acceptance criteria:**

- [ ] If scheduled after MVP, format configuration explicitly maps all five required record fields and rejects incomplete mappings.

## Functional Requirements

### P0 — Must ship

| ID | Requirement | Trace |
|---|---|---|
| FR-1 | Accept one path, `-`, or omitted input for stdin and stream bytes once | US-1 |
| FR-2 | Parse the documented nginx combined grammar and track valid/malformed totals | US-1 |
| FR-3 | Produce deterministic top 10 client IPs | US-2 |
| FR-4 | Produce deterministic top 10 exact request targets for statuses 400–599 | US-3 |
| FR-5 | Produce all 24 hourly counts and percentages | US-4 |
| FR-6 | Produce exact distinct User-Agent count and share up to the configured ceiling | US-5 |
| FR-7 | Render TTY-aware Rich text by default | US-6 |
| FR-8 | Render schema-versioned JSON and normalized CSV | US-7 |
| FR-9 | Implement exit codes `0/1/2/3/4` without omission or remapping | US-1, US-5, US-7 |
| FR-10 | Install on Python 3.11 through pip with a `nginx-analyzer` console command | All |

### P1 — Should ship if the core is green

| ID | Requirement | Trace |
|---|---|---|
| FR-11 | Strict first-malformed-line failure mode | US-8 |
| FR-12 | User-configurable positive cardinality ceiling | US-5 |

### P2 — Could follow MVP

| ID | Requirement | Trace |
|---|---|---|
| FR-13 | Transparently read gzip files | US-9 |
| FR-14 | Parse an explicitly configured custom nginx format | US-10 |

## CLI and Exit-Code Contract

The normative commands, options, inputs, outputs, and exit behavior are under `## CLI Interface` in `PROJECT_ARCHITECTURE.md`. All implementation and tests must preserve the complete contract:

| Code | Required meaning |
|---:|---|
| `0` | Successful report, help, or version output |
| `1` | Unexpected internal/runtime failure |
| `2` | CLI usage or option-validation error |
| `3` | Input/data failure, including unreadable input, strict malformed input, or zero valid records |
| `4` | Unique-cardinality exhaustion |

No implementation guide may omit or remap code 4.

## Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-1 Performance | Canonical 1 GB fixture completes in under 30 seconds on the documented reference laptop | Timed benchmark after warm-up |
| NFR-2 Memory | Canonical fixture peak RSS stays below 512 MiB; User-Agent cardinality never exceeds its configured ceiling | Peak-RSS benchmark and exhaustion test |
| NFR-3 Determinism | Identical input and options produce semantically identical reports; ties follow documented ordering | Repeat-run golden tests |
| NFR-4 Portability | Clean installation and execution on supported Python 3.11 environments | Wheel install smoke test |
| NFR-5 Privacy | No network, telemetry, persistence, DNS resolution, or raw-log echo in normal diagnostics | Static review and integration tests |
| NFR-6 Safety | Untrusted fields cannot inject Rich markup or ANSI control sequences | Adversarial fixture tests |
| NFR-7 Testability | Product modules maintain at least 90% line coverage and all P0 criteria have automated evidence | Coverage and acceptance suite |

## Analytics Semantics

- `total_valid_requests` is the number of successfully parsed, non-empty log records.
- Client-IP ranking uses all valid requests.
- Error-URL ranking uses valid records with status 400–599.
- Hourly percentages use `100 × hourly_request_count / total_valid_requests`.
- User-Agent share uses distinct logged User-Agent values divided by total valid requests, scaled by 100.
- Query strings remain part of the target, and timestamp hours remain in their logged offsets.
- Tie-breaking is ascending UTF-8 lexical value after descending count.

## Dependencies and Assumptions

- Python 3.11 is installed locally.
- Runtime dependencies are Click and Rich; `dataclasses` is from the standard library.
- Input is an uncompressed nginx combined-format byte stream.
- The performance fixture and reference laptop specification will be recorded with benchmark evidence.
- No internet or elevated privileges are required at runtime.

## Release Acceptance

Release is accepted only when every P0 user-story criterion has automated or recorded evidence, the complete `0/1/2/3/4` exit contract passes end to end, the clean-wheel smoke test passes, and the 1 GB benchmark meets the target. A partial machine report after exit 3 or 4 is a release blocker.

## Kill Criteria

- Stop and re-scope if an exact supported-format parser cannot pass the golden fixtures.
- Do not ship a Python performance claim if the canonical 1 GB benchmark is 30 seconds or slower; profile and revise the architecture first.
- Do not ship if meeting the target requires a database, HTTP API, server, cloud resource, Kubernetes, paid service, or hidden approximation.
- Do not ship if code 4 is omitted, remapped, or produces a partial report.

The implementation sequence is specified in `IMPLEMENTATION_PLAN.md`; developer prompts are in `CLAUDE_CODE_GUIDE.md`.
