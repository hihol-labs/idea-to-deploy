# Product Requirements Document: Nginx Log Lens

## 1. Product Objective

Provide DevOps/SRE engineers with a fast local command that extracts four
high-value operational summaries from nginx combined access logs without
requiring a service, database, network connection, or bespoke shell pipeline.

## 2. Problem Statement

During incidents and one-off reviews, engineers often need basic traffic and
error distributions immediately. grep/awk pipelines are fragile; observability
stacks are costly to deploy for local files. The product must occupy the
middle: one reliable, installable, composable command.

## 3. Scope and Principles

- Python 3.11, Click, Rich, and dataclasses.
- Local file or stdin, single streaming pass, no persistent state.
- Default colored terminal output with JSON and CSV alternatives.
- Exact top-10 results and explicit malformed-input accounting.
- Binary chunks are 64 KiB and a physical line over 1 MiB is counted once as
  malformed, bounding record assembly even when input has no newline.
- Target: a deterministic 1 GB fixture in under 30 seconds on a documented
  reference laptop.
- $0 budget and one-weekend delivery.

## User Stories

### US-1: Analyze a large local log

As an on-call SRE, I want to pass an nginx access-log path to one command so
that I can see the principal traffic and error patterns without deploying
infrastructure.  
**Priority:** P0

**Acceptance criteria:**

- [ ] `nginx-log-lens access.log` reads the file incrementally and exits 0.
- [ ] Output includes top IPs, top error URLs, 24 hourly buckets, UA diversity,
      and valid/malformed totals.
- [ ] A 1 GB reference fixture has measured median time under 30 seconds on the
      documented reference laptop.

### US-2: Use the command in a pipe

As a DevOps engineer, I want to stream logs through stdin so that the analyzer
composes with shell tools and remote log retrieval.  
**Priority:** P0

**Acceptance criteria:**

- [ ] Omitting `INPUT` or passing `-` reads stdin.
- [ ] File and stdin analysis of the same bytes produce equivalent reports.
- [ ] A closed downstream pipe does not produce a traceback.

### US-3: Feed JSON to automation

As a platform engineer, I want versioned JSON output so that a script can
consume metrics without parsing terminal presentation.  
**Priority:** P0

**Acceptance criteria:**

- [ ] `--json` emits one valid JSON document matching schema version 1.
- [ ] stdout contains no ANSI escapes, progress text, or diagnostics.
- [ ] All four reports and valid/malformed counts are represented.

### US-4: Feed CSV to tabular tools

As an operations analyst, I want stable CSV output so that I can load a report
into standard command-line or spreadsheet tools.  
**Priority:** P0

**Acceptance criteria:**

- [ ] `--csv` emits the exact `section,key,count,value` header.
- [ ] Fields with commas, quotes, or newlines are RFC 4180-escaped.
- [ ] The UA share uses six decimal places and hours use `00`–`23`.
- [ ] The first data row is `meta,schema_version,,1`, followed by the exact
      row ordering defined in `PROJECT_ARCHITECTURE.md`.

### US-5: Understand imperfect input

As an SRE handling real logs, I want malformed records counted and skipped so
that one bad line does not erase a useful incident report.  
**Priority:** P0

**Acceptance criteria:**

- [ ] A mixed valid/malformed input exits 0 and reports both counts.
- [ ] A non-empty input with zero valid records exits 4 with a concise stderr
      diagnostic.
- [ ] Expected input failures never expose a traceback or echo log contents.

### US-6: Read compressed archives directly

As an SRE reviewing rotations, I want gzip logs to be recognized automatically
so that I do not need a separate decompression pipe.  
**Priority:** P1

### US-7: Analyze a custom nginx log format

As a platform owner, I want to describe a supported custom `log_format` so
that the tool works beyond the standard combined format.  
**Priority:** P1

### US-8: Choose a different top-N

As an investigator, I want to change the ranking size so that I can explore a
broader tail after the initial summary.  
**Priority:** P2

## 5. Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-1 | P0 | Accept one readable file path, `-`, or omitted input for stdin |
| FR-2 | P0 | Parse standard nginx combined-format lines with timestamp offsets |
| FR-3 | P0 | Count exact requests per IP and return at most 10 |
| FR-4 | P0 | Count exact request targets with status 400–599 and return at most 10 |
| FR-5 | P0 | Return all 24 hourly buckets using the hour encoded in each record |
| FR-6 | P0 | Compute distinct non-empty UAs / valid requests, or 0 for no requests |
| FR-7 | P0 | Count and skip malformed lines; distinguish all-malformed data |
| FR-8 | P0 | Render safe Rich text by default and auto-detect terminal color |
| FR-9 | P0 | Render stable schema-versioned JSON with data-only stdout |
| FR-10 | P0 | Render stable normalized CSV with data-only stdout |
| FR-11 | P0 | Reject mutually exclusive output modes and invalid color combinations |
| FR-12 | P0 | Use exit codes 0, 1, 2, 3, and 4 per the architecture contract |
| FR-13 | P1 | Auto-detect and stream gzip files |
| FR-14 | P1 | Support an explicitly documented custom-format configuration |
| FR-15 | P2 | Permit configurable ranking size |
| FR-16 | P2 | Provide a periodically refreshed live view |

## 6. Output Semantics

- “URL” means the raw request target in the request field, including query
  string; no normalization occurs in P0.
- “Error” means HTTP status 400 through 599 inclusive.
- Top-list ordering is count descending, then key ascending.
- “Hourly” means the local hour encoded in each record; records are not
  converted to one global timezone.
- “Unique User-Agent share” means distinct non-empty UA values divided by all
  valid requests, a ratio between 0 and 1.
- Machine schemas and exit codes are normative in
  `PROJECT_ARCHITECTURE.md` under `## CLI Interface`.

## 7. Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-1 | Python 3.11 and pip-installable wheel/sdist | Clean-environment wheel smoke test |
| NFR-2 | One pass; never load complete input | Code review and peak-RSS benchmark |
| NFR-3 | 1 GB median under 30 s on named reference laptop | Three-run benchmark protocol |
| NFR-4 | No unhandled malformed-input exceptions | Parser corpus and robustness tests |
| NFR-5 | No network, persistence, telemetry, temp files, or services | Dependency/code review and offline test |
| NFR-6 | stdout is data-only in JSON/CSV modes | Golden CLI tests splitting stdout/stderr |
| NFR-7 | At least 90% line coverage for product code | pytest coverage report |
| NFR-8 | Deterministic output for identical input/options | Repeated golden-output tests |

Exact aggregation is not constant-memory in cardinality. Performance
acceptance must therefore include both representative and high-cardinality
fixtures and publish peak RSS.

The representative 1 GB fixture is capped at 100,000 distinct IPs, error
URLs, and User-Agents and must meet <30 seconds/<256 MB. The near-unique 1 GB
fixture is an adversarial safety measurement: an OS kill or unhandled failure
blocks architecture acceptance even though no universal memory ceiling is
promised for unbounded cardinality.

## 8. Error and Exit Contract

| Condition | Exit | stdout | stderr |
|---|---:|---|---|
| Success or empty stream | 0 | Selected report | Empty or non-data text-mode notices |
| Unexpected internal failure | 1 | No partial machine document | Concise error |
| Usage/option error | 2 | No report | Click usage error |
| File/read failure | 3 | No report | Path-safe concise error |
| Non-empty, zero valid records | 4 | No report | Counts and data error |

## 9. Out of Scope

- Authentication and user accounts.
- Database, persistent history, indexing, or cache.
- HTTP API, daemon, web UI, server, or remote upload.
- Cloud services, containers as a runtime requirement, and Kubernetes.
- Multi-file merging, directory recursion, tail/follow mode, geo-IP, bots,
  bandwidth totals, latency percentiles, and arbitrary queries in P0.
- gzip/custom formats in P0; these remain P1 and do not block launch.

## 10. Release Acceptance

Release requires all P0 acceptance criteria, output goldens, exit-code tests,
parser robustness tests, wheel/sdist validation, ≥90% product-code coverage,
and the recorded reference benchmark. Documentation must match `--help`.

## 11. Kill Criteria

Pause release and re-plan if:

- the documented reference benchmark exceeds 30 seconds after evidence-based
  profiling within the approved stack;
- representative combined-format fixtures parse below 99.9%;
- high-cardinality peak RSS makes the CLI unsuitable for the reference laptop;
- stable JSON/CSV contracts cannot represent all four reports without
  ambiguous semantics.

## 12. Dependencies

Architecture and public interfaces are defined in
`PROJECT_ARCHITECTURE.md`. Prioritization and business constraints are defined
in `STRATEGIC_PLAN.md`. Verification sequencing is defined in
`IMPLEMENTATION_PLAN.md`.
