# Strategic Plan: nginx-analyzer

## 1. Product Idea

`nginx-analyzer` is a local, pip-installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads an nginx combined access log from a file or standard input in one pass and reports the top 10 client IPs, the top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agent values. It emits colored terminal text by default and stable JSON or CSV for pipelines.

The first release is deliberately narrow: no authentication, database, HTTP API, server process, cloud integration, or Kubernetes support. The delivery budget is $0 and the target schedule is one weekend.

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| On-call SRE | Investigates incidents from a shell | Needs a fast overview before a larger observability stack is available | Streams a local or piped log and produces the four incident-oriented summaries immediately |
| DevOps engineer | Operates small and medium deployments | Full ELK-style systems are costly to deploy and maintain for an ad-hoc question | Installs with pip and has no service or persistent state to operate |
| Platform engineer | Builds repeatable operational scripts | Colored human output is hard to compose in automation | Selects stable `--json` or `--csv` output and relies on documented exit codes |

## 3. Problem and Value Proposition

Raw nginx logs are easy to access but slow to summarize correctly with improvised shell pipelines. General log platforms solve a much larger problem and impose ingestion, storage, and operational overhead. This tool occupies the useful middle: a purpose-built, streaming summary that is available locally, predictable in pipelines, and fast enough for a 1 GB incident log.

**Unique value proposition:** obtain a reliable nginx traffic-and-error snapshot from a 1 GB log in under 30 seconds on a laptop, with one pip install and no service to configure.

## 4. Competitive Analysis

| Alternative | Strength | Limitation for this use case | nginx-analyzer differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, rich interactive and HTML reporting | Broader interface and configuration surface than a four-metric pipeline tool | Fixed, automation-friendly report contract with JSON/CSV and explicit exit codes |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, retention, querying, and dashboards | Requires multiple services, storage, configuration, and ongoing operations | Zero-service, stateless local analysis with no data retained |
| AWStats | Established historical web analytics | Primarily report-oriented and less natural for one-off streamed incident analysis | Reads stdin or one file and produces an immediate terminal/pipeline result |
| `grep`/`awk`/`sort` | Ubiquitous and dependency-light | Correct parsing, escaping, multi-metric aggregation, and portable JSON/CSV require brittle scripts and repeated passes | One validated parser and one pass produce all required metrics consistently |

## 5. Business Model and Budget

The project is open source and free to use. There is no paid tier, hosted service, advertising, or telemetry. Value is measured by adoption and incident-response utility rather than revenue; CAC and LTV do not apply to this $0 local tool.

| Item | One-time cost | Monthly cost | Assumption |
|---|---:|---:|---|
| Development | $0 | $0 | One weekend of contributor time; labor treated as donated |
| Hosting | $0 | $0 | No server or website required for MVP |
| Dependencies | $0 | $0 | Python, Click, and Rich are open source |
| Distribution | $0 | $0 | Source repository and public Python package hosting |
| CI | $0 | $0 | Optional free open-source allowance; local verification remains sufficient |
| **Total cash budget** | **$0** | **$0** | Must remain zero for MVP |

## 6. Technology Strategy

| Component | Choice | Reason |
|---|---|---|
| Runtime | Python 3.11 | Required stack, broad laptop availability, adequate streaming throughput with disciplined parsing |
| CLI | Click | Stable option parsing, help, validation, and exit behavior |
| Terminal presentation | Rich | Colored, readable tables with automatic terminal capability handling |
| Domain records | `dataclasses` | Typed, dependency-free representation of parsed records and report models |
| Processing | Single-process streaming pipeline | Avoids storage and inter-process overhead; natural fit for one input stream and four aggregations |
| Packaging | Standards-based pip package | Familiar installation and console-script entry point |

## 7. Delivery Timeline

| Window | Focus | Deliverable |
|---|---|---|
| Saturday morning | Package, contracts, parser | Installable CLI skeleton and tested nginx combined-log parsing |
| Saturday afternoon | Aggregations | Top-IP, error-URL, hourly, and User-Agent metrics in one pass |
| Sunday morning | Renderers and failure behavior | Rich, JSON, and CSV outputs with exit codes `0/1/2/3/4` |
| Sunday afternoon | Performance and release checks | 1 GB benchmark evidence, documentation, package build, and smoke tests |

## 8. KPIs

| Metric | Release target | First month | Third month |
|---|---:|---:|---:|
| Processing time for the canonical 1 GB fixture on the reference laptop | < 30 s | p95 < 30 s | p95 < 25 s |
| Peak resident memory on the canonical fixture | < 512 MiB | < 512 MiB | < 384 MiB |
| Correctness on golden log fixtures | 100% | 100% | 100% |
| Successful runs among valid supported inputs | ≥ 99% | ≥ 99% | ≥ 99.5% |
| Fresh installations completing a sample analysis without support | 100% in release test | ≥ 90% | ≥ 95% |

Performance claims apply to the documented reference laptop and canonical fixture; they are not extrapolated to every device or pathological high-cardinality input.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Pure-Python parsing misses the 1 GB/30 s target | Medium | High | Benchmark early; compile the line regex once; parse bytes with minimal allocation; profile before adding complexity |
| nginx format variants are mistaken for supported combined format | High | Medium | State the supported format, count malformed lines, support `--strict`, and return code 3 when no valid records exist |
| User-Agent cardinality consumes excessive memory | Medium | High | Enforce a configurable cardinality ceiling and fail closed with exit code 4 rather than silently approximate |
| JSON/CSV contracts drift from terminal semantics | Medium | Medium | Build one report model and test all renderers against the same golden aggregates |
| ANSI color contaminates redirected output | Low | Medium | Enable color only for terminal text on a TTY; machine formats never contain ANSI codes |
| Scope expands into a persistent log platform | Medium | High | Keep databases, servers, HTTP APIs, cloud, Kubernetes, dashboards, and authentication explicitly out of scope |

## 10. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream a file or stdin in nginx combined format | **Must** | Every report depends on validated input without loading the file into memory |
| Top 10 client IPs | **Must** | Core incident and traffic summary |
| Top 10 URLs by combined 4xx/5xx count | **Must** | Core error hotspot summary |
| Hourly request distribution percentages | **Must** | Required traffic-shape metric |
| Unique User-Agent share | **Must** | Required client-diversity metric |
| Colored terminal report | **Must** | Required default user experience |
| JSON and CSV output | **Must** | Required pipeline interoperability |
| Stable exit-code contract including cardinality exhaustion | **Must** | Required for safe automation and bounded memory |
| Strict malformed-line mode | **Should** | Useful for validation, while tolerant parsing is adequate for the MVP default |
| Configurable User-Agent cardinality ceiling | **Should** | Lets operators trade memory for supported cardinality safely |
| Gzip input | **Could** | Convenient but can follow the uncompressed streaming MVP |
| Custom nginx `log_format` parsing | **Could** | Valuable but substantially broadens parser configuration and tests |
| Database, HTTP API, server, cloud, Kubernetes, or authentication | **Won't** | Contradicts the local, stateless, $0 product boundary |

### RICE Scoring for Must and Should Features

Scores use `(Reach × Impact × Confidence) / Effort`, where confidence is a decimal and effort is person-days. Ties are ordered by dependency.

| Feature | Reach | Impact | Confidence | Effort (days) | RICE Score |
|---|---:|---:|---:|---:|---:|
| Stream file/stdin and parse combined logs | 10 | 5 | 90% | 0.75 | 60.0 |
| Top 10 client IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Top 10 error URLs | 10 | 5 | 95% | 0.35 | 135.7 |
| Hourly request distribution | 9 | 4 | 95% | 0.25 | 136.8 |
| Unique User-Agent share | 8 | 4 | 85% | 0.35 | 77.7 |
| Colored terminal report | 9 | 3 | 90% | 0.35 | 69.4 |
| JSON and CSV output | 8 | 4 | 90% | 0.50 | 57.6 |
| Stable exit-code contract | 8 | 4 | 95% | 0.25 | 121.6 |
| Strict malformed-line mode | 6 | 2 | 85% | 0.20 | 51.0 |
| Configurable cardinality ceiling | 6 | 3 | 85% | 0.20 | 76.5 |

Dependency ordering overrides raw RICE where necessary: parsing precedes every metric, a shared report model precedes renderers, and exit behavior is integrated before end-to-end tests.

## 11. Definition of Done

A release feature is Done when:

- [ ] Behavior and acceptance criteria are reflected in `PRD.md` and `PROJECT_ARCHITECTURE.md`.
- [ ] Python 3.11 code is typed and package builds without errors.
- [ ] Unit and integration tests pass with at least 90% line coverage for product modules.
- [ ] Golden fixtures prove all four metric calculations and malformed-line policy.
- [ ] Rich, JSON, and CSV outputs pass contract tests and contain no conflicting values.
- [ ] Exit codes `0/1/2/3/4` are exercised end to end; code 4 proves unique-cardinality exhaustion.
- [ ] The canonical 1 GB benchmark completes in under 30 seconds on the documented reference laptop with peak RSS recorded.
- [ ] Documentation and CLI help are updated.
- [ ] No known Critical or High security issues remain.
- [ ] The pip-built artifact installs in a clean Python 3.11 environment and completes a smoke analysis.

## 12. Kill and Pivot Criteria

- Stop the one-weekend release if the supported combined-log fixture cannot be parsed correctly without relaxing golden tests.
- Pivot to a compiled implementation only after profiling evidence shows an optimized Python parser cannot meet 1 GB in 30 seconds on the reference laptop.
- Reject any MVP proposal that requires a service, database, paid dependency, or persistent ingestion pipeline.
- Defer high-cardinality datasets that exceed the explicit ceiling; never replace exact behavior with an undocumented approximation.

The detailed system contract is in `PROJECT_ARCHITECTURE.md`; delivery order is in `IMPLEMENTATION_PLAN.md`; requirements and acceptance criteria are in `PRD.md`.
