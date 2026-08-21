# Product Requirements Document: Nginx Stream Analyzer

## Product Summary

Build a local Python 3.11 CLI that turns one nginx combined access-log stream into four operational summaries in a single pass. Default output is colored Rich terminal text; JSON and CSV are stable pipeline formats. The product is stateless, pip-installable, open source, and delivered in one weekend for $0.

## Goals

- Give DevOps/SRE users immediate top client, error target, hourly load, and User-Agent diversity signals.
- Process a 1 GB local log in under 30 seconds on the documented reference laptop.
- Preserve exact results within a clear, configurable cardinality envelope.
- Behave predictably in shell pipelines through stdout/stderr separation and exit codes 0/1/2/3/4.

## Non-Goals

Authentication, a database, historical retention, HTTP API, server mode, web UI, cloud service, Kubernetes, distributed processing, arbitrary nginx formats, and replacement of full observability platforms are out of scope.

## User Stories

### US-1 — Stream a local or piped log

As an on-call SRE, I want to analyze either a file or stdin so that I can use the same command locally and over shell pipelines.

Priority: P0

Acceptance criteria:

- [ ] `nginx-analyzer access.log` and `cat access.log | nginx-analyzer -` produce equivalent report data.
- [ ] The analyzer iterates input without a whole-file read.
- [ ] A successful empty input produces a valid zero-valued report and exits 0.
- [ ] An unreadable file exits 3 and writes no success document to stdout.

### US-2 — See top client IPs

As an SRE, I want the ten most frequent client IPs so that I can spot dominant or suspicious sources.

Priority: P0

Acceptance criteria:

- [ ] At most 10 entries are ordered by descending count and ascending IP text for ties.
- [ ] IPv4 and IPv6 textual addresses are accepted.
- [ ] Each entry includes count and percentage of total valid requests.

### US-3 — See top error URLs

As a DevOps engineer, I want the ten request targets with the most 4xx/5xx responses so that I can prioritize broken or failing paths.

Priority: P0

Acceptance criteria:

- [ ] Only statuses 400 through 599 contribute.
- [ ] Rankings use descending count and ascending URL for ties.
- [ ] Request targets are treated as data and safely escaped in terminal, JSON, and CSV output.

### US-4 — Understand hourly traffic

As an incident responder, I want request distribution by logged hour so that I can see when traffic is concentrated.

Priority: P0

Acceptance criteria:

- [ ] All 24 hours `00`–`23` are present, including zero-count buckets.
- [ ] Hour is derived from the timestamp’s logged local hour without timezone conversion.
- [ ] Each percentage uses `100 × hourly_request_count / total_valid_requests`, not an unscaled fraction.
- [ ] A zero-valid-request report uses `0.0` for all hourly percentages.

### US-5 — Measure unique User-Agent share

As an SRE, I want the unique User-Agent count and its share of valid requests so that I can estimate client diversity.

Priority: P0

Acceptance criteria:

- [ ] Distinct strings are counted exactly, with `-` treated as a literal value.
- [ ] Share is `100 × unique_user_agent_count / total_valid_requests` and is `0.0` when the denominator is zero.
- [ ] Count, denominator, and percentage are exposed in structured output.

### US-6 — Consume deterministic machine output

As an automation author, I want JSON and CSV modes so that downstream tools do not scrape terminal formatting.

Priority: P0

Acceptance criteria:

- [ ] `--json` emits one valid versioned JSON object and no ANSI codes.
- [ ] `--csv` emits the documented normalized header and sections and no ANSI codes.
- [ ] `--json --csv` is rejected by Click with exit 2.
- [ ] Warnings/errors go to stderr and do not corrupt stdout.

### US-7 — Fail safely on extreme cardinality

As a laptop user, I want an explicit unique-key limit so that adversarial logs do not consume memory without bound.

Priority: P0

Acceptance criteria:

- [ ] `--max-unique` is a positive per-dimension cap for IP, error URL, and User-Agent keys.
- [ ] Adding a new key beyond the cap emits no success report and exits 4.
- [ ] The diagnostic names the exhausted dimension and limit without printing the sensitive value.
- [ ] Existing keys continue to increment when the map/set is exactly at its cap.

### US-8 — Analyze compressed input directly

As a DevOps engineer, I want `.gz` input so that I can avoid a decompression pipeline.

Priority: P1

Acceptance criteria:

- [ ] Post-MVP implementation streams decompression and preserves the same report contract.
- [ ] Until shipped, `gzip -dc file.gz | nginx-analyzer -` is documented.

### US-9 — Parse custom formats

As a platform engineer, I want configurable nginx `log_format` fields so that the analyzer works with organization-specific logs.

Priority: P1

Acceptance criteria:

- [ ] A future design maps required semantic fields without executing user code.
- [ ] Missing required fields fail validation before consuming input.

### US-10 — Configure ranking length

As an interactive user, I want to choose top-N so that I can inspect more than ten entries.

Priority: P2

Acceptance criteria:

- [ ] A future positive option changes both rankings and structured output consistently.

## Functional Requirements

### P0 — Must ship

- FR-1: Accept one combined-format log file, `-`, or omitted path for stdin.
- FR-2: Parse remote address, logged hour, request target, status, and User-Agent.
- FR-3: Count malformed nonblank lines; `--strict` fails on the first one with code 1.
- FR-4: Produce exact top-10 IP and exact top-10 400–599 URL rankings within cardinality limits.
- FR-5: Produce all 24 hourly counts and percentages using `100 × hourly_request_count / total_valid_requests`.
- FR-6: Produce exact unique User-Agent count and percentage within the limit.
- FR-7: Render Rich terminal output by default and stable JSON/CSV on request.
- FR-8: Enforce deterministic ties, two-decimal presentation rounding, and stdout/stderr separation.
- FR-9: Implement the exit-code contract: 0 success, 1 log-data/invariant failure, 2 usage error, 3 I/O failure, 4 unique-cardinality exhaustion.

### P1 — Should follow

- Stream gzip input directly.
- Support declarative custom nginx formats after a separate parser design.

### P2 — Could add

- Configurable top-N.
- Live terminal refresh without changing the final report schema.

## Output Contract

The canonical field names and shapes are defined in `PROJECT_ARCHITECTURE.md` under `## CLI Interface`. JSON carries `schema_version`; CSV uses `schema_version,section,rank,key,count,percentage`. Terminal formatting is not a machine contract, but its values must equal the structured formats for the same input.

## Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-1 | 1 GB in <30 seconds on reference laptop | Repeatable benchmark command and recorded environment |
| NFR-2 | Streaming input | Test/profiling evidence that no whole-file buffer exists |
| NFR-3 | Bounded exact cardinality | Boundary tests for all three dimensions and exit 4 |
| NFR-4 | Python 3.11 and pip installability | Clean-environment build/install smoke test |
| NFR-5 | Deterministic output | Repeated golden JSON/CSV comparisons |
| NFR-6 | No network or persistence | Dependency/code review and offline integration test |
| NFR-7 | Safe untrusted rendering | Markup, JSON, and CSV injection-oriented fixtures |

## Release Acceptance

- All P0 story criteria and the codes 0/1/2/3/4 matrix pass.
- Parser fixtures cover valid and malformed combined logs.
- Terminal, JSON, and CSV values reconcile on the same corpus.
- Clean Python 3.11 installation succeeds.
- The documented reference benchmark meets the 1 GB/30 s target.
- `README.md`, `PROJECT_ARCHITECTURE.md`, and implementation guidance agree.

## Kill Criteria

Stop or re-scope before release if the reference benchmark cannot meet 1 GB under 30 seconds after profiling, exact aggregation cannot be bounded safely with a clear code-4 failure, or delivery requires a database, API, service, paid dependency, cloud, or more than the one-weekend envelope.
