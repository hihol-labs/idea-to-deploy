# Product Requirements Document: nginx-stream-report

## Product Summary

`nginx-stream-report` lets DevOps and SRE engineers analyze nginx combined access logs locally in a single streaming pass. It provides four fixed metrics in colored terminal text, JSON, or CSV without deploying or operating a service.

## Goals

- Produce top 10 client IPs and top 10 URLs with 4xx/5xx statuses.
- Produce all 24 hourly request buckets, where each percentage is `100 × hourly_request_count / total_valid_requests`.
- Produce the exact number and percentage share of unique User-Agents within a safe configurable cap.
- Accept both file and stdin input and support reliable pipeline output.
- Process a representative 1 GB log in under 30 seconds on a documented laptop.

## Non-Goals

- Authentication, authorization, user accounts, or secrets management.
- Database, retained history, HTTP API, daemon, web dashboard, cloud, or Kubernetes.
- Arbitrary nginx log-format configuration in the MVP.
- Approximate metrics, cross-file sessions, live tail-follow mode, or geolocation.

## User Stories

- As a DevOps engineer, I want to stream a local nginx access log and see the top 10 client IPs so that I can identify abusive or unexpectedly noisy clients. **Priority: P0; acceptance criteria: FR-1 and FR-2.**
- As an on-call SRE, I want the top 10 URLs returning 4xx/5xx statuses so that I can focus incident investigation on failing routes. **Priority: P0; acceptance criteria: FR-3.**
- As a service owner, I want hourly traffic percentages so that I can see when traffic concentrated during the log period. **Priority: P0; acceptance criteria: FR-4.**
- As a platform engineer, I want JSON output so that I can consume the report in automation without scraping terminal text. **Priority: P0; acceptance criteria: FR-6 and FR-7.**
- As a platform engineer, I want normalized CSV output so that I can feed the report to standard data tools. **Priority: P0; acceptance criteria: FR-6 and FR-7.**
- As a security-conscious operator, I want bounded exact User-Agent cardinality so that adversarially diverse input cannot consume memory without an explicit failure. **Priority: P0; acceptance criteria: FR-5 and FR-7.**

## Functional Requirements

### P0 — Must

#### FR-1: Streaming input and parsing

The CLI accepts a file path, `-`, or stdin and parses standard nginx combined-format lines without loading the entire input.

Acceptance criteria:

- [ ] A fixture read from a file and the same bytes read from stdin yield identical reports.
- [ ] IPv4, IPv6, timezone offsets, quoted User-Agents, and `-` response sizes parse correctly.
- [ ] Non-strict mode counts and skips malformed lines; strict mode exits `3` on the first malformed line.
- [ ] Empty input produces a valid all-zero report and exits `0`.

#### FR-2: Top IP addresses

Count valid requests by client IP and return at most ten entries.

Acceptance criteria:

- [ ] Entries sort by count descending and IP text ascending for ties.
- [ ] Every output format contains the same keys, counts, and ranks.

#### FR-3: Top error URLs

Count request-targets only for HTTP statuses 400–599 and return at most ten entries.

Acceptance criteria:

- [ ] 399 is excluded; 400, 499, 500, and 599 are included; 600 is rejected as malformed.
- [ ] Query strings remain part of the URL key in MVP.
- [ ] Ties use deterministic lexical ordering.

#### FR-4: Hourly distribution

Return 24 ordered buckets based on the local hour encoded in each parsed timestamp. Each bucket's percentage is `100 × hourly_request_count / total_valid_requests`.

Acceptance criteria:

- [ ] Hours `00` through `23` appear exactly once and in order.
- [ ] Counts sum to `total_valid_requests`.
- [ ] Unrounded percentages sum to 100 for non-empty input within floating-point tolerance; empty input reports zero.
- [ ] Serialized percentages use two decimal places/numeric precision consistently.

#### FR-5: Unique User-Agent share and safety cap

Return exact distinct User-Agent count and `100 × unique_user_agents / total_valid_requests` while the configured cap is not exceeded.

Acceptance criteria:

- [ ] Repeated identical User-Agents count once.
- [ ] Exactly the configured number of unique values succeeds.
- [ ] The next new value causes unique-cardinality exhaustion, emits no partial report, and exits `4`.

#### FR-6: Output modes

Default output is Rich terminal text; `--json` and `--csv` select machine-readable output.

Acceptance criteria:

- [ ] `--json` emits one valid UTF-8 JSON document matching the architecture schema.
- [ ] `--csv` emits RFC 4180-compatible rows with `section,rank,key,count,percentage` headers.
- [ ] JSON and CSV contain no ANSI escape sequences.
- [ ] `--json --csv` is rejected with exit `2`.
- [ ] Text color follows `auto|always|never` and untrusted log values are not interpreted as Rich markup.

#### FR-7: Exit behavior

The complete public exit contract is `0/1/2/3/4`: success, internal error, usage error, input error, and unique-cardinality exhaustion respectively.

Acceptance criteria:

- [ ] CLI integration tests exercise every code.
- [ ] Known errors produce concise stderr diagnostics and no traceback.
- [ ] stdout contains only a complete report on success.

### P1 — Should

- Automatically detect and stream gzip-compressed file input while preserving stdin behavior.
- Add property-based malformed-input tests.
- Publish reproducible wheel and source-distribution checks in CI.

### P2 — Could

- Allow a configurable `--top N` after the fixed top-10 schema is versioned.
- Add optional query-string stripping or normalization.
- Support named nginx log formats through an explicit format specification.

## Quality Attributes

| Attribute | Requirement |
|---|---|
| Performance | 1 GB representative log in <30 seconds on documented reference laptop |
| Memory | ≤256 MiB peak RSS for benchmark; deterministic exit `4` at UA cap |
| Correctness | 100% expected output for golden fixtures; deterministic ties |
| Portability | Python 3.11 on Linux/macOS; Windows best effort unless added to CI |
| Privacy | No network, persistence, telemetry, or implicit log upload |
| Usability | Useful `--help`, file/stdin symmetry, clear stderr messages |

## Output Contract Stability

JSON field names, CSV columns/section names, ranking rules, formulas, and exit codes are public contracts. Additive fields require a minor version and documentation; removal, rename, semantic change, or approximate replacement requires a major version.

## Dependencies and Assumptions

- Input follows nginx combined format and represents one or more timezones as encoded per line.
- The reference 1 GB corpus includes successes, 4xx/5xx responses, varied IPs, and varied User-Agents.
- Python 3.11, Click, and Rich are available through pip without paid infrastructure.
- Architecture details in `PROJECT_ARCHITECTURE.md` control if another document is ambiguous.

## Kill Criteria

Do not release the MVP if any P0 acceptance test fails, if JSON/CSV are nondeterministic, if the exact cardinality cap can be bypassed, or if the reproducible benchmark remains above 45 seconds after profiling. If the benchmark is 30–45 seconds, rescope P1/P2 and profile before release; do not silently weaken the target.
