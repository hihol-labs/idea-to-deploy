# Product Requirements Document: Nginx Stream Analyzer

## Product Summary

Nginx Stream Analyzer gives DevOps and SRE engineers a fast, local summary of supported nginx access logs. It is a Python 3.11 CLI installed through pip, reads one file or stdin without persistence, and writes colored text by default or stable JSON/CSV for pipelines.

This PRD is the behavioral source of truth. Architecture and interface details live in `PROJECT_ARCHITECTURE.md`; delivery order lives in `IMPLEMENTATION_PLAN.md`.

## Goals

- Produce top 10 client IPs by valid request count.
- Produce top 10 request URLs among 4xx/5xx responses.
- Produce a 24-bucket hourly request distribution as percentages.
- Produce exact unique User-Agent count and its share of valid requests within a safe cardinality bound.
- Process a representative 1 GB log in under 30 seconds on a documented laptop.
- Support human-readable terminal output and deterministic JSON/CSV output.
- Remain local, stateless, free, and installable through pip.

## Non-Goals

- Authentication or user accounts.
- Database, persisted indexes, history, or incremental checkpoints.
- HTTP API, long-running server, web UI, or multi-user access.
- Cloud service, Docker deployment, Kubernetes, or centralized collection.
- Full nginx configuration-language parsing or automatic log-format discovery.
- Silent approximate answers when exact cardinality cannot be maintained.

## Personas and Primary Scenarios

| Persona | Scenario | Success signal |
|---|---|---|
| On-call SRE | Triage a sudden error spike from a copied access log | Finds dominant error URLs and traffic sources with one command |
| Platform engineer | Feed a daily report into `jq` or another job | JSON schema and exits are deterministic |
| DevOps engineer | Pipe `ssh host cat access.log` into local analysis | Stdin works without a temporary database or service |

## User Stories

### US-1 — Analyze a local log

As an on-call SRE, I want to analyze a supported nginx access-log file with one command so that I can identify dominant clients and failures quickly.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Given valid records, the result contains at most 10 IP rows ordered by descending request count and ascending IP for ties.
- [ ] The result contains at most 10 request targets whose statuses are 400–599, ordered by descending error count and ascending target for ties.
- [ ] A successful complete report exits with code 0.

### US-2 — Analyze a pipeline stream

As a DevOps engineer, I want to read from stdin so that I can analyze remote, decompressed, or generated logs without a temporary file.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Omitting `INPUT` or supplying `-` reads lines from stdin.
- [ ] The analyzer processes the input in a single pass and does not retain raw records.
- [ ] File and stdin inputs produce equivalent report data for identical bytes.

### US-3 — Understand hourly load

As an SRE, I want hourly request percentages so that I can see when valid traffic is concentrated.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] The report contains hours `00` through `23` in ascending order, including zero-count hours.
- [ ] Each percentage uses the literal formula `100 × hourly_request_count / total_valid_requests`.
- [ ] Hours are derived from the numeric offset and hour recorded in each log timestamp.
- [ ] Percentages are rounded to two decimal places only when serialized.

### US-4 — Measure User-Agent diversity

As a platform engineer, I want the share of unique User-Agents so that I can estimate client diversity or suspicious automation.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] User-Agent matching is case-sensitive and exact.
- [ ] The report provides `unique_user_agent_count` and `share_percent`, where share is `(unique_user_agent_count / total_valid_requests) × 100`.
- [ ] If an exact-cardinality limit would be exceeded, processing stops without a partial report and exits with code 4.

### US-5 — Consume structured output

As a platform engineer, I want JSON or CSV output so that scripts can consume the result reliably.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] `--json` emits exactly one schema-versioned JSON object to stdout and no ANSI escape sequences.
- [ ] `--csv` emits the documented normalized header and fixed section order with no ANSI escape sequences.
- [ ] `--json` and `--csv` together are rejected as a usage error with exit code 2.
- [ ] Diagnostics are written to stderr and report data to stdout.

### US-6 — Read a concise terminal report

As an on-call engineer, I want a colored terminal report by default so that I can scan important metrics quickly.

**Priority:** P0 (Must)

**Acceptance criteria:**

- [ ] Default interactive output presents the four required metric sections and input totals.
- [ ] Redirected text output does not contain ANSI escape sequences.
- [ ] `--no-color` disables color without changing report values.
- [ ] Untrusted values render as text, not Rich markup or terminal control instructions.

### US-7 — Extend ranking depth later

As an operator, I want configurable top-N output so that I can inspect more than 10 entries when needed.

**Priority:** P1 (Should)

**Acceptance criteria:**

- [ ] A future option preserves 10 as the default and validates a safe positive maximum.
- [ ] JSON and CSV schemas remain backward compatible.

### US-8 — Read additional nginx formats later

As an operator with a custom nginx setup, I want explicit format selection so that I can reuse the analyzer without rewriting logs.

**Priority:** P1 (Should)

**Acceptance criteria:**

- [ ] Any added format is named explicitly and covered by fixtures.
- [ ] Automatic ambiguous format guessing is not introduced.

### US-9 — Read compressed input directly

As an operator, I want direct gzip input so that I can skip a shell decompression stage.

**Priority:** P2 (Could)

**Acceptance criteria:**

- [ ] If implemented, gzip detection is explicit and stdin behavior remains unchanged.

## Functional Requirements

### P0 — Must

| ID | Requirement |
|---|---|
| FR-001 | Accept zero or one positional `INPUT`; zero or `-` means stdin |
| FR-002 | Parse the declared nginx combined/common-compatible record fields into a typed record |
| FR-003 | Skip and count malformed lines without retaining or echoing full raw lines |
| FR-004 | Count valid requests per client IP and return a deterministic top 10 |
| FR-005 | Count request targets only for HTTP statuses 400–599 and return a deterministic top 10 |
| FR-006 | Return all 24 hourly buckets with count and percentage `100 × hourly_request_count / total_valid_requests` |
| FR-007 | Return exact unique User-Agent count and percentage share within hard cardinality limits |
| FR-008 | Render Rich terminal text by default, with color only when appropriate |
| FR-009 | Render schema-versioned JSON with the architecture-defined fields |
| FR-010 | Render normalized CSV with the architecture-defined header and section order |
| FR-011 | Enforce the complete public exit contract `0/1/2/3/4`, with 4 meaning unique-cardinality exhaustion |
| FR-012 | Terminate before adding a distinct key beyond any configured hard limit; never emit a partial success report |
| FR-013 | Install on Python 3.11 through pip and expose `nginx-stream-analyzer` |

### P1 — Should

| ID | Requirement |
|---|---|
| FR-101 | Add bounded configurable top-N without changing the default |
| FR-102 | Add explicitly selected, fixture-backed nginx format variants |

### P2 — Could

| ID | Requirement |
|---|---|
| FR-201 | Read gzip-compressed file input directly |
| FR-202 | Add an opt-in approximate cardinality mode with clearly distinct semantics |

## Exit-Code Contract

| Code | Meaning | Required examples |
|---:|---|---|
| 0 | Complete success | Help/version or a fully written report |
| 1 | Input/output failure | Missing/unreadable input, read failure, output-write failure |
| 2 | Usage failure | Unknown option, incompatible `--json --csv`, too many inputs |
| 3 | Invalid log data | EOF reached with zero valid supported records |
| 4 | Unique-cardinality exhaustion | A distinct IP, error URL, or User-Agent would exceed its exact-state limit |

The contract is always `0/1/2/3/4`; implementations and guides must not omit or remap code 4.

## Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-001 | Representative 1 GB input completes in under 30 seconds on a documented laptop | Timed benchmark with hardware/Python/output conditions recorded |
| NFR-002 | Memory never exceeds explicit distinct-key bounds | Adversarial-cardinality fixture exits 4 at the boundary |
| NFR-003 | Processing is single-pass and stateless | Design inspection plus large-stream test using non-seekable stdin |
| NFR-004 | Equal inputs yield equal JSON and CSV data ordering | Repeated golden-output tests |
| NFR-005 | No network, server, database, authentication, or cloud dependency | Dependency/configuration inspection |
| NFR-006 | Terminal/CSV injection controls are enforced | Crafted-value security tests |
| NFR-007 | Core parser, aggregation, and renderer modules reach at least 90% coverage | Coverage report on exact candidate |

## Input Rules and Edge Cases

- Empty input, whitespace-only input, and all-malformed input exit 3.
- A mix of valid and malformed lines succeeds; summary counts expose malformed lines.
- Status 399 is not an error URL; 400 and 599 are; 600 is invalid for the supported parser.
- Duplicate User-Agent strings count once in the numerator but every valid request remains in the denominator.
- Missing User-Agent represented by `-` is treated as a literal User-Agent value for deterministic exactness.
- Query strings remain part of the request-target ranking key.
- Ties use ascending key order and are stable across formats and runs.
- A cardinality failure, input failure, or output failure must not leave a success-looking partial report on stdout.

## Analytics Definitions

| Metric | Numerator / ranking | Denominator | Presentation |
|---|---|---|---|
| Top IPs | Valid requests grouped by exact client IP | N/A | First 10 after count-desc/key-asc sort |
| Top error URLs | Valid requests with status 400–599 grouped by exact request target | N/A | First 10 after count-desc/key-asc sort |
| Hourly distribution | Valid requests in a logged hour | `total_valid_requests` | `100 × hourly_request_count / total_valid_requests` |
| Unique User-Agent share | Count of exact distinct User-Agent strings | `total_valid_requests` | Percentage, two decimals on serialization |

## Release Acceptance

The MVP can ship only when all P0 acceptance criteria pass, pip installation works on Python 3.11, golden output covers all three formats, each exit code `0/1/2/3/4` is exercised, and the 1 GB benchmark meets the documented target. Acceptance must use the repository Verification Loop against the frozen exact candidate; prose alone is not evidence.

## Kill Criteria

Pause or re-scope the MVP if any of these is true at the end of the one-weekend time box:

- The representative 1 GB benchmark remains at or above 30 seconds after profiling-led optimizations.
- Exact User-Agent cardinality cannot be bounded with a clear exit-4 behavior.
- The declared format cannot achieve deterministic parser fixtures without broad automatic guessing.
- JSON or CSV requires a breaking ambiguity that cannot be resolved with the documented schemas.
- Scope expands to a database, server, authentication, cloud, or Kubernetes requirement.

## Dependencies and Traceability

`PROJECT_ARCHITECTURE.md` owns component boundaries, schemas, and CLI details. `IMPLEMENTATION_PLAN.md` maps FR/NFR requirements to concrete files and verification commands. `CLAUDE_CODE_GUIDE.md` provides execution prompts without changing this contract.
