# Product Requirements Document: nginx Stream Analytics CLI

## 1. Product Summary

`nginx-stream-report` is a local Python 3.11 CLI that turns an nginx combined-format access-log stream into four focused operational metrics: top 10 IPs, top 10 URLs producing 4xx/5xx responses, hourly request distribution, and unique User-Agent share. It is optimized for incident response and pipelines, not historical analytics.

The durable product contract is this PRD together with `PROJECT_ARCHITECTURE.md`. If implementation behavior changes, update and approve the specification first.

## 2. Problem and Goals

DevOps and SRE engineers regularly need a fast answer from a large access log but do not want to install or operate an analytics stack. Shell one-liners are difficult to make correct across malformed lines, quoted fields, deterministic ties, output formats, and failures.

### Goals

- Produce all four required metrics in one invocation from a file or stdin.
- Process a representative 1 GB log in under 30 seconds on a documented laptop.
- Offer useful colored terminal output and deterministic JSON/CSV output.
- Use one stateless local process with a $0 operational budget.
- Fail explicitly when exact User-Agent cardinality cannot be retained.

### Non-goals

- Authentication, user accounts, authorization, or secrets.
- A database, persisted history, caches, or temporary aggregation files.
- An HTTP API, server, daemon, tail-follow mode, or web UI.
- Cloud infrastructure, containers as a runtime requirement, or Kubernetes.
- Approximate metrics, correlation across multiple invocations, or arbitrary query language.

## 3. Personas

- **On-call SRE:** needs a trustworthy overview during an incident.
- **DevOps automation author:** needs stable JSON/CSV and exit behavior.
- **Service owner:** needs a lightweight local report from a large exported log.

## User Stories

### US-1 — Analyze a file or pipeline

As an on-call SRE, I want to stream an nginx log from a path or stdin so that I can analyze local files and live pipelines with the same command.

Priority: **P0 (Must)**

Acceptance criteria:

- [ ] `nginx-stream-report access.log` reads the file sequentially and does not load the full file into memory.
- [ ] `cat access.log | nginx-stream-report` and `nginx-stream-report -` produce the same report as the file invocation.
- [ ] A mixed input of valid and malformed lines completes with code `0`, includes the malformed count, and computes metrics only from valid records.
- [ ] Missing/unreadable input returns code `2`, writes a concise diagnostic to stderr, and writes no report to stdout.
- [ ] An input with zero valid records returns code `3` and writes no partial report.

### US-2 — Identify the busiest client IPs

As an SRE, I want the top 10 client IPs so that I can identify dominant or suspicious request sources.

Priority: **P0 (Must)**

Acceptance criteria:

- [ ] Every valid record increments exactly one client-IP count.
- [ ] At most 10 entries are returned in count-descending order.
- [ ] Equal counts are ordered by IP text ascending, producing identical output across runs.
- [ ] IPv4 and IPv6 text from valid records is retained without normalization.

### US-3 — Find URLs producing errors

As an on-call engineer, I want the top 10 request targets with 4xx/5xx responses so that I can focus remediation on the most frequent failures.

Priority: **P0 (Must)**

Acceptance criteria:

- [ ] Only status codes `400..599` contribute to this metric.
- [ ] 4xx and 5xx counts are combined per exact request-target string, including its query string.
- [ ] At most 10 entries are returned in count-descending, target-ascending tie order.
- [ ] If no error responses exist, the report represents an empty ranking without treating it as a failure.

### US-4 — Understand hourly traffic shape

As a service owner, I want request distribution by hour of day so that I can see when traffic is concentrated.

Priority: **P0 (Must)**

Acceptance criteria:

- [ ] The report emits all 24 wall-clock-hour buckets (`00` through `23`) in ascending order.
- [ ] Each percentage uses the literal formula `100 × hourly_request_count / total_valid_requests`; it is not an unscaled fraction.
- [ ] Percentages are based only on valid records and serialize rounded to two decimal places.
- [ ] Bucket counts sum to `total_valid_requests`; unrounded percentages sum to 100% within floating-point tolerance.

### US-5 — Quantify User-Agent diversity safely

As an SRE, I want the share of unique User-Agents so that I can quickly estimate client diversity without allowing hostile cardinality to exhaust memory.

Priority: **P0 (Must)**

Acceptance criteria:

- [ ] Distinct, non-empty, non-placeholder User-Agent strings are counted exactly.
- [ ] Share is `100 × distinct_non_placeholder_user_agent_count / total_valid_requests`, serialized to two decimal places.
- [ ] Placeholder `-` does not create a distinct agent but its valid request remains in the denominator.
- [ ] `--max-unique-user-agents` accepts an integer >=1 and defaults to `1_000_000`.
- [ ] Attempting to exceed the configured limit stops processing with code `4`, emits no partial report, and never substitutes an approximation.

### US-6 — Read a clear terminal report

As a human operator, I want a compact colored report so that I can scan results quickly at a terminal.

Priority: **P0 (Must)**

Acceptance criteria:

- [ ] Default output contains labeled sections for all four metrics plus total, valid, and malformed counts.
- [ ] Rich color is enabled for a capable TTY and disabled for redirected output or when `NO_COLOR` is present.
- [ ] `--no-color` produces no ANSI escapes; untrusted log fields cannot be interpreted as Rich markup or terminal control sequences.

### US-7 — Integrate with pipelines

As a DevOps automation author, I want JSON or CSV output so that downstream tools can consume the report reliably.

Priority: **P0 (Must)**

Acceptance criteria:

- [ ] `--json` emits one valid schema-versioned JSON object and no ANSI sequences.
- [ ] `--csv` emits the fixed header `section,rank,key,count,percentage` and no ANSI sequences.
- [ ] `--json` and `--csv` are mutually exclusive and an invalid combination returns code `2`.
- [ ] Diagnostics are on stderr and the selected report format alone is on stdout.
- [ ] Golden tests freeze field names, section keys, row ordering, numeric types, and rounding.

### US-8 — Analyze compressed exports

As a platform engineer, I want `.gz` input auto-detection so that I can avoid a separate decompression pipeline.

Priority: **P1 (Should)**

Acceptance criteria:

- [ ] A `.gz` path is decompressed as a stream and yields the same report as its plain-text source.
- [ ] Corrupt gzip input is an input I/O error with code `2` and no partial report.

### US-9 — Adjust ranking size

As a service owner, I want configurable top-N rankings so that I can inspect beyond the default ten when needed.

Priority: **P2 (Could)**

Acceptance criteria:

- [ ] A future `--top INTEGER` retains 10 as the default and validates a bounded positive range.
- [ ] JSON/CSV schema meanings remain stable when the number of ranked entries changes.

## 5. Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-1 | P0 | Accept exactly one plain-text combined-format stream from a path, `-`, or omitted stdin |
| FR-2 | P0 | Parse valid lines, count malformed lines, and never include malformed content in metrics |
| FR-3 | P0 | Compute exact deterministic top-10 IP and 4xx/5xx URL rankings |
| FR-4 | P0 | Compute all 24 hourly counts and percentages using `100 × hourly_request_count / total_valid_requests` |
| FR-5 | P0 | Compute exact unique User-Agent count/share with configurable exhaustion ceiling |
| FR-6 | P0 | Render one of terminal, JSON, or CSV output with no cross-format contamination |
| FR-7 | P0 | Implement exit codes `0/1/2/3/4` exactly as specified in `PROJECT_ARCHITECTURE.md` |
| FR-8 | P1 | Stream `.gz` paths without extraction to disk |
| FR-9 | P2 | Allow a bounded configurable ranking length while preserving top 10 by default |

## 6. Non-functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-1 Performance | Representative 1 GB log completes in <30 seconds on the documented reference laptop | Three measured runs after warm-up; median <30 s |
| NFR-2 Memory | Processing is line-by-line; peak RSS is recorded and User-Agent uniqueness is explicitly capped | Performance test plus cardinality-exhaustion fixture |
| NFR-3 Determinism | Ties, buckets, JSON fields, CSV rows, and rounding are stable across runs/locales | Golden and repeated-run tests |
| NFR-4 Compatibility | Install and execute on CPython 3.11 via pip | Clean-venv wheel installation test |
| NFR-5 Safety | No network, subprocess, dynamic execution, persistence, or terminal-markup interpretation | Static review and malicious-field fixtures |
| NFR-6 Quality | Product modules maintain >=90% line coverage; Ruff and mypy pass | CI/local quality commands |

## 7. Public Output Contract

The authoritative commands, options, input/output shapes, and exit codes are in `PROJECT_ARCHITECTURE.md` under `## CLI Interface`. Terminal output is for people and may receive non-semantic presentation improvements. JSON `schema_version: 1`, JSON field meanings, CSV headers/section keys, metric semantics, and exit meanings are compatibility-controlled interfaces.

## 8. Dependencies and Constraints

- Runtime: Python 3.11, Click, Rich, standard-library dataclasses.
- Installation: pip from wheel/source distribution.
- Cash budget: $0; open source.
- Delivery window: one weekend.
- Runtime architecture: one local stateless process; no database or HTTP API.

## 9. Release Acceptance

The MVP is accepted only when every P0 criterion passes, a clean pip installation works, all quality gates pass, default/JSON/CSV golden outputs agree on metrics, all `0/1/2/3/4` exit paths are exercised, and the documented 1 GB benchmark meets the target on the reference laptop.

## 10. Kill Criteria

- Kill or explicitly rescope if the representative 1 GB benchmark remains >=30 seconds after profiling and bounded optimization in the approved Python single-process design.
- Kill or rescope if exact User-Agent cardinality cannot fail safely at a documented bound without a crash, partial output, or silent approximation.
- Defer P1/P2 work if it threatens any P0 acceptance criterion or the one-weekend limit.
- Do not introduce a database, HTTP service, cloud deployment, paid dependency, or Kubernetes to rescue the MVP.
