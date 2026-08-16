# Product Requirements Document: nginx-stream-stats

## 1. Product Definition

`nginx-stream-stats` gives DevOps/SRE engineers a fast, local summary of nginx combined access logs. It accepts a file or stdin, keeps no persistent state, and emits colored terminal text by default or stable JSON/CSV for pipelines.

The MVP is open source, costs $0, targets Python 3.11, and is delivered in one weekend. The architecture is specified in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md).

## 2. Problem and Goals

During incidents and local investigations, operators often need four answers before a full observability system is available: which IPs dominate traffic, which URLs dominate client/server errors, when requests occurred, and how diverse User-Agents are. Existing platforms are too heavy for one-off local input, while shell pipelines are fragile around quoted log fields.

### Goals

- Process a representative 1 GB combined log in under 30 seconds on a documented laptop.
- Compute exact required metrics in a single streaming pass.
- Provide readable terminal output and deterministic JSON/CSV contracts.
- Fail predictably for bad invocation, input, format, and cardinality exhaustion.
- Install as a normal Python 3.11 package.

### Non-goals

- Authentication, database, persistence, HTTP API, server, cloud, or Kubernetes.
- Dashboards, historical comparison, live file following, log rotation management, or distributed processing.
- nginx formats other than combined format in the MVP.
- Approximate cardinality or silent degradation.

## 3. Personas

- **On-call SRE:** needs a rapid, trustworthy summary during triage.
- **Platform engineer:** embeds deterministic results and exit codes in automation.
- **Developer/operator:** investigates a local service without deploying infrastructure.

## User Stories

### US-01 — Stream local and piped logs

As an on-call SRE, I want to analyze either a file or stdin so that I can use the same tool on saved logs and shell pipelines.

Priority: **P0 (Must)**

Acceptance criteria:

- [ ] Omitting `INPUT` and passing `-` both read stdin line by line.
- [ ] Passing a readable path processes that file without loading it wholly into memory.
- [ ] The same records from file and stdin yield semantically identical reports.
- [ ] Unreadable input exits 1 with a diagnostic only on stderr.

### US-02 — Identify dominant clients

As an SRE, I want the top 10 client IPs so that I can spot abusive or unusually active sources.

Priority: **P0 (Must)**

Acceptance criteria:

- [ ] Every valid record increments exactly one remote-address count.
- [ ] At most 10 rows appear by default, ordered count descending then IP ascending on ties.
- [ ] IPv4 and IPv6 strings are preserved as logged.

### US-03 — Identify failing URLs

As a service owner, I want the top 10 request targets by 4xx/5xx count so that I can prioritize broken routes.

Priority: **P0 (Must)**

Acceptance criteria:

- [ ] Only statuses 400–599 contribute.
- [ ] The request target, including query string, is the grouping key.
- [ ] At most 10 rows appear by default, ordered count descending then target ascending on ties.
- [ ] A valid log with no errors returns an empty ranked list, not a failure.

### US-04 — Understand hourly traffic

As an operator, I want each hour's percentage of requests so that I can see traffic shape at a glance.

Priority: **P0 (Must)**

Acceptance criteria:

- [ ] Output contains all 24 buckets from `00` through `23`, including zeros.
- [ ] The bucket uses the hour and numeric offset recorded in the log timestamp.
- [ ] Each percentage uses `100 × hourly_request_count / total_valid_requests`.
- [ ] Unrounded percentages total approximately 100% within floating-point tolerance.

### US-05 — Measure User-Agent diversity safely

As a platform engineer, I want the share of unique User-Agents with an explicit resource limit so that I get an exact result or a machine-detectable failure.

Priority: **P0 (Must)**

Acceptance criteria:

- [ ] The exact distinct User-Agent count is computed over valid records.
- [ ] Share equals `100 × unique_user_agent_count / total_valid_requests`.
- [ ] Duplicate values count once; the logged empty value is a valid distinct value.
- [ ] A new distinct value beyond the configured cap stops processing, emits no report, and exits 4.
- [ ] The tool never silently substitutes an estimate.

### US-06 — Read a colored terminal report

As an on-call user, I want a concise colored report by default so that the four signals are easy to scan.

Priority: **P0 (Must)**

Acceptance criteria:

- [ ] Default TTY output has labeled Rich sections for all four metrics.
- [ ] Log-derived strings are escaped rather than interpreted as Rich markup.
- [ ] `--no-color` and non-TTY output contain no ANSI escape sequences.

### US-07 — Consume JSON in automation

As a platform engineer, I want `--json` so that a pipeline can parse named fields safely.

Priority: **P0 (Must)**

Acceptance criteria:

- [ ] Stdout is exactly one valid JSON document following the architecture schema.
- [ ] Percentages are JSON numbers at six-decimal precision.
- [ ] Diagnostics remain on stderr and ANSI codes never appear.

### US-08 — Consume CSV in automation

As a platform engineer, I want `--csv` so that I can load results into tabular tools.

Priority: **P0 (Must)**

Acceptance criteria:

- [ ] Stdout is parseable RFC 4180-style UTF-8 CSV with the documented single header.
- [ ] All metric types and 24 hour buckets are present.
- [ ] Embedded commas, quotes, and newlines are safely quoted by the CSV writer.
- [ ] `--csv` and `--json` together exit 2 without reading input.

### US-09 — Enforce log quality

As an automation author, I want strict malformed-line handling so that a corrupt source fails my job rather than being partially accepted.

Priority: **P1 (Should)**

Acceptance criteria:

- [ ] Lenient mode skips/counts malformed lines but succeeds if at least one line is valid.
- [ ] `--strict` stops on the first malformed non-empty line and exits 3.
- [ ] Zero valid records and invalid UTF-8 exit 3.

### US-10 — Adjust ranking depth

As an investigator, I want to adjust top-N so that I can inspect beyond the default ten when needed.

Priority: **P2 (Could)**

Acceptance criteria:

- [ ] `--top` accepts positive integers and defaults to 10.
- [ ] Zero, negative, and non-integer values exit 2.

## 5. Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-01 | P0 | Read one file or stdin incrementally in strict UTF-8 |
| FR-02 | P0 | Parse nginx combined format with quoted/escaped fields and timezone-aware timestamp |
| FR-03 | P0 | Count and deterministically rank client IPs, default top 10 |
| FR-04 | P0 | Count and rank request targets whose status is 400–599, default top 10 |
| FR-05 | P0 | Emit 24 hourly counts and percentages using the required formula |
| FR-06 | P0 | Compute exact unique User-Agent count/share with a configurable hard cap |
| FR-07 | P0 | Render colored Rich terminal output by default with safe escaping |
| FR-08 | P0 | Render stable JSON with numeric percentages |
| FR-09 | P0 | Render stable tidy CSV with standard quoting |
| FR-10 | P0 | Preserve stdout for report and stderr for diagnostics |
| FR-11 | P0 | Implement the complete `0/1/2/3/4` exit contract |
| FR-12 | P1 | Support strict failure versus lenient skip/count behavior |
| FR-13 | P2 | Support configurable ranking depth |

## 6. CLI and Exit Contract

The command and full option/output schemas are under the exact `## CLI Interface` heading in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md).

| Code | Required meaning |
|---:|---|
| `0` | Success, help, or version |
| `1` | Operational I/O or unexpected internal failure |
| `2` | Invalid CLI invocation |
| `3` | Log data/format failure |
| `4` | Unique-cardinality exhaustion |

No implementation guide may omit or remap code 4.

## 7. Non-functional Requirements

| ID | Requirement | Evidence |
|---|---|---|
| NFR-01 | 1 GB valid representative input completes under 30 seconds on a named laptop | Reproducible generator plus wall-clock measurement |
| NFR-02 | Raw lines and parsed records are not retained | Streaming-spy test and code inspection |
| NFR-03 | Results are deterministic across repeated runs | Golden tests including ties |
| NFR-04 | Python 3.11 wheel installs with pip in a clean environment | Build/install smoke test |
| NFR-05 | Machine output contains no ANSI and remains schema-stable | JSON/CSV integration tests |
| NFR-06 | Exact UA memory is bounded by the explicit cap | Boundary tests and exit 4 integration test |
| NFR-07 | Runtime has no network or persistent state | Dependency/file-boundary review |
| NFR-08 | Statement coverage is at least 90% | Coverage gate |

## 8. Scope Priorities

P0 equals MoSCoW Must, P1 equals Should, and P2 equals Could. Database, auth, HTTP API/server, cloud, Kubernetes, persistence, dashboard, and live follow mode are Won't for the MVP. The full MoSCoW and RICE rationale is in [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md).

## 9. Release Acceptance

The MVP is accepted only when all P0 criteria pass, semantic results match across terminal/JSON/CSV, every exit code `0/1/2/3/4` is integration-tested, the clean-wheel smoke test passes, and the documented 1 GB benchmark meets the target.

## 10. Kill and Rescope Criteria

- Stop release if exact correctness requires retaining raw input.
- Rescope/parser-optimize if the named benchmark remains at or above 30 seconds after profiling.
- Stop feature expansion if it introduces a database, server, authentication, cloud, or paid service.
- Defer P1/P2 if any P0 behavior or performance gate remains open at the end of the weekend.
- Reconsider Python only in a future major version if measured profiles show the approved stack cannot meet the core target without unsafe complexity.
