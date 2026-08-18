# Product Requirements Document: Nginx Insights CLI

## 1. Product Summary

Nginx Insights CLI gives DevOps/SRE engineers fast, local summaries of nginx
access logs without an observability service. It accepts a finite Combined Log
Format stream from a file or stdin and returns terminal, JSON, or CSV output.
Architecture and interface details are normative in `PROJECT_ARCHITECTURE.md`.

## 2. Problem and Goals

During incident triage or routine inspection, engineers need to identify noisy
clients, error-heavy routes, hourly traffic shape, and User-Agent diversity.
Existing choices are either fragile one-off shell pipelines or systems whose
deployment and retention overhead is disproportionate to a one-shot question.

MVP goals are:

- compute the four required summaries exactly for valid input;
- preserve a one-pass, local, stateless workflow;
- provide deterministic human and machine-readable outputs;
- analyze a representative 1 GB log in under 30 seconds on a documented laptop;
- make every automation-relevant failure distinguishable through `0/1/2/3/4`.

## 3. Scope and Priority

### P0 — Must ship

- File and stdin streaming for nginx Combined Log Format.
- Top 10 client IPs by request count.
- Top 10 request targets among 4xx/5xx responses.
- All 24 hourly request percentages.
- Exact unique User-Agent count and share, guarded by a configurable limit.
- Rich colored terminal output, JSON, and CSV.
- Deterministic ordering, metadata, stderr diagnostics, and exit codes.

### P1 — Should ship

- `--strict` fail-fast parsing mode.
- Explicit `--no-color`, `--version`, and detailed CLI help.
- Reproducible 1 GB performance harness and packaging smoke test.

### P2 — Could follow

- Transparent gzip input.
- Named support for additional standard nginx formats.
- Approximate cardinality as an explicitly opt-in mode for very high diversity.

### Out of scope

Authentication, databases, an HTTP API, servers, log retention, cloud services,
Kubernetes, dashboards, live tail/follow mode, custom `log_format` inference,
geo-IP enrichment, bots, and telemetry are excluded.

## User Stories

### US-1 — Find noisy clients

As an on-call SRE, I want the ten IPs with the most valid requests so that I can
quickly identify abusive or unexpectedly active clients.

Priority: P0

Acceptance criteria:

- [ ] Counts include every valid record regardless of response status.
- [ ] At most 10 rows are returned, sorted by count descending then IP text ascending.
- [ ] File and stdin input produce identical rows for identical bytes.

### US-2 — Find failing routes

As a service operator, I want the ten URLs with the most 4xx/5xx responses so
that I can prioritize broken or attacked endpoints.

Priority: P0

Acceptance criteria:

- [ ] Statuses 400 through 599 inclusive contribute; 399 and 600 do not.
- [ ] The request-target token, including its query string, is the grouping key.
- [ ] At most 10 rows are sorted by count descending then target ascending.

### US-3 — See hourly traffic shape

As a capacity engineer, I want each hour's share of valid requests so that I
can spot traffic concentration without loading logs into a dashboard.

Priority: P0

Acceptance criteria:

- [ ] Output always contains buckets `00` through `23` in ascending order.
- [ ] The log timestamp's encoded offset and written hour determine the bucket.
- [ ] Each percentage uses `100 × hourly_request_count / total_valid_requests` and is serialized to two decimal places.
- [ ] Unrounded bucket values sum to 100% when valid requests exist.

### US-4 — Measure User-Agent diversity safely

As an SRE, I want the exact unique User-Agent share so that I can estimate
client diversity without risking unbounded unnoticed memory growth.

Priority: P0

Acceptance criteria:

- [ ] Distinctness compares the complete parsed User-Agent string exactly.
- [ ] Share is `100 × unique_user_agent_count / total_valid_requests`, rounded to two decimal places at output.
- [ ] Before adding a distinct value beyond the configured limit, processing stops with exit code 4.
- [ ] The exhaustion diagnostic does not echo the sensitive User-Agent value.

### US-5 — Use results in automation

As a platform engineer, I want stable JSON and CSV output so that shell and CI
pipelines can consume results without scraping terminal decoration.

Priority: P0

Acceptance criteria:

- [ ] `--json` emits one valid JSON document and `--csv` emits the documented header and row schema.
- [ ] `--json` and `--csv` are mutually exclusive and conflict with exit code 2.
- [ ] Structured stdout contains no ANSI codes, warnings, or progress messages.
- [ ] All formats derive from the same result and match on counts and percentages.

### US-6 — Handle imperfect logs predictably

As an operator, I want malformed records handled predictably so that I can
choose between best-effort triage and validation.

Priority: P1

Acceptance criteria:

- [ ] Default mode skips malformed lines, reports their count, and succeeds if at least one record is valid.
- [ ] `--strict` stops at the first malformed non-empty line with exit code 3.
- [ ] Empty input or input with no valid record exits 3 and emits no data document.

### US-7 — Install without infrastructure

As a Python-using engineer, I want a normal pip-installable console command so
that I can run the tool in an isolated environment without a server or container.

Priority: P1

Acceptance criteria:

- [ ] A clean Python 3.11 virtual environment can install the wheel and invoke `nginx-insights --help`.
- [ ] Runtime dependencies are limited to Click and Rich beyond the standard library.

### US-8 — Read compressed logs directly

As an archive operator, I want gzip autodetection so that I can avoid a
decompression pipeline.

Priority: P2

Acceptance criteria:

- [ ] This story is not required for MVP; `gzip -cd file.gz | nginx-insights --json` is documented as the workaround.

## 5. Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-1 | P0 | Process the input incrementally, retaining no raw lines or record list |
| FR-2 | P0 | Parse the Combined Log Format fields defined in `PROJECT_ARCHITECTURE.md` |
| FR-3 | P0 | Track valid and malformed line counts separately |
| FR-4 | P0 | Produce deterministic top-IP and error-target rankings limited to 10 |
| FR-5 | P0 | Produce 24 hourly percentage buckets using the normative formula |
| FR-6 | P0 | Produce exact unique User-Agent count/share within a positive configured limit |
| FR-7 | P0 | Render the canonical result as terminal, JSON, or CSV |
| FR-8 | P0 | Keep stdout data and stderr diagnostics separate |
| FR-9 | P0 | Implement the complete exit-code contract `0/1/2/3/4`, with 4 reserved for unique-cardinality exhaustion |
| FR-10 | P1 | Support strict parsing, explicit no-color, help, and version behavior |

## 6. Non-Functional Requirements

- **Performance:** a representative 1 GB input completes in under 30 seconds on
  the documented reference laptop, measured with output redirected.
- **Memory:** processing is one-pass; exact cardinality growth is guarded at a
  default of 1,000,000 distinct User-Agents. Peak RSS is recorded in benchmarks.
- **Compatibility:** CPython 3.11 on Linux and macOS; terminal output degrades
  cleanly without color, while JSON/CSV are locale-independent.
- **Privacy:** no network I/O, telemetry, retained input, or database.
- **Determinism:** ties, hours, schemas, and rounding do not depend on hash order
  or locale.
- **Quality:** at least 90% branch coverage for parser, aggregator, and renderers,
  plus integration and golden-output tests.

## 7. Complete Exit-Code Contract

| Code | Required behavior |
|---:|---|
| `0` | Successful analysis/help/version, or graceful downstream broken pipe |
| `1` | I/O or unexpected runtime/output failure |
| `2` | CLI usage or option-validation failure |
| `3` | Strict malformed input, empty input, or no valid records |
| `4` | Unique-cardinality exhaustion before exceeding the configured limit |

No implementation guide may omit or remap code 4.

## 8. Release Acceptance and Kill Criteria

Release requires all P0 acceptance criteria, a clean pip installation smoke
test, semantic parity across three output formats, and the documented 1 GB
benchmark under 30 seconds. A benchmark fixture must resemble real Combined Log
Format diversity rather than repeat one constant line.

Pause release and redesign if either condition holds:

- two measured parser/aggregation optimization passes still exceed 36 seconds
  on the fixed reference fixture;
- exact User-Agent exhaustion can produce partial structured output, an
  incorrect success code, or memory growth beyond the configured guard.

## 9. Dependencies and Traceability

The feature priority originates in `STRATEGIC_PLAN.md`. Runtime components and
schemas are defined in `PROJECT_ARCHITECTURE.md`. Delivery steps and evidence
are in `IMPLEMENTATION_PLAN.md`; future implementation behavior must change this
spec first when requirements change.

