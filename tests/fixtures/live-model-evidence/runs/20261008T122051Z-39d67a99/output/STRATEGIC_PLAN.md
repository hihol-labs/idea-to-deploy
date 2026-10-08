# Strategic Plan: `nginx-top`

## 1. Product Idea

`nginx-top` is a local, pip-installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream and reports the top 10 client IPs, the top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agent values. Its default presentation is colored terminal text, with stable JSON and CSV modes for pipelines.

The MVP is deliberately local and stateless: no authentication, database, HTTP API, resident server, cloud service, or Kubernetes resources. It is designed for a one-weekend delivery, a $0 operating budget, and a target of processing a 1 GB log in under 30 seconds on a representative laptop.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Diagnoses production incidents | Needs a useful traffic/error snapshot before a full observability query is ready | One local command produces four operational summaries with explicit data-quality diagnostics |
| DevOps engineer | Operates nginx hosts and deployment pipelines | Shell one-liners are brittle and hard to reuse in automation | Stable `--json` and `--csv` schemas, deterministic ordering, and documented exit codes |
| Platform engineer | Supports teams with varied observability maturity | Full log stacks are expensive or unavailable for one-off analysis | Pip-installable, zero-service tooling that reads files or stdin |

## 3. Competitive Analysis

| Alternative | Strength | Weakness for this use case | `nginx-top` distinction |
|---|---|---|---|
| GoAccess | Mature, fast, interactive terminal and HTML reporting | Broader feature/configuration surface than the four requested summaries; external binary distribution | Narrow Python CLI contract, pipeline-first JSON/CSV, and explicit invalid-line handling |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, search, dashboards, and retention | Requires services, storage, setup, and operational cost | No service or database; useful for immediate local inspection |
| AWStats | Established historical web analytics | Batch/report configuration and persistent reporting model are heavier than incident triage | Single-run streaming summary with no retained state |
| `grep` / `awk` / `sort` | Ubiquitous and composable | Parsing is fragile, repeated sorts can be costly, and output contracts vary by script | Tested nginx parser, bounded top-k aggregation, and consistent machine formats |

## 4. Unique Value Proposition

Get a trustworthy, pipeline-friendly nginx incident summary from a large local log in one command, without deploying or operating anything.

## 5. Business Model

The project is open source and free. There are no paid tiers, hosted services, telemetry, or usage fees. Success is adoption and operational usefulness rather than revenue; contribution and maintenance costs are bounded by the narrow scope.

## 6. Technology Stack

| Component | Choice | Reason |
|---|---|---|
| Runtime | Python 3.11 | Required stack, broad laptop availability, mature text processing |
| CLI | Click | Predictable option validation, stdin/file handling, and exit behavior |
| Terminal UI | Rich | Accessible colored tables and automatic color/TTY behavior |
| Domain models | Standard-library dataclasses | Explicit typed records without validation-framework overhead |
| Aggregation | Standard-library counters, fixed-size top-k selection | Single-pass ingestion and compact final ranking |
| Packaging | `pyproject.toml`, pip, console script | Standard local installation and reproducible entry point |
| Testing | pytest | Focused unit, integration, golden-output, and performance tests |

## 7. Timeline

| Weekend block | Work | Result |
|---|---|---|
| Saturday morning | Package skeleton, contracts, parser | Installable CLI that safely parses supported nginx combined logs |
| Saturday afternoon | Streaming metrics and cardinality guard | Single-pass summaries with deterministic ranking and bounded failure behavior |
| Sunday morning | Text, JSON, and CSV renderers | Human and pipeline outputs conform to documented schemas |
| Sunday afternoon | Integration, performance, documentation, packaging | Verified candidate ready for a tagged open-source release |

## 8. KPIs

| Metric | Release target | First month target | Three-month target |
|---|---:|---:|---:|
| Performance on representative 1 GB fixture | Under 30 seconds | Under 30 seconds at p95 across documented benchmark laptops | No regression beyond 10% |
| Peak resident memory | At or below 512 MiB on the benchmark | At or below 512 MiB | At or below 512 MiB |
| Valid-line parsing accuracy on supported combined format corpus | 100% | 100% for reported regressions | 100% |
| Machine-output contract regressions | 0 | 0 | 0 |
| Invalid-line diagnostic accuracy | Exact count | Exact count | Exact count |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from the supported combined-log grammar | High | High | State the accepted grammar, count invalid lines, support format extension after MVP |
| High-cardinality IP, URL, or User-Agent values exhaust laptop memory | Medium | High | Define configurable hard limits, fail deterministically with exit code 4, and benchmark adversarial fixtures |
| Python misses the 1 GB / 30 second target | Medium | High | Avoid per-line regex recompilation and object retention; profile before release; keep parsing single-pass |
| CSV cannot naturally represent four differently shaped reports | Medium | Medium | Use a normalized row schema with a `report` discriminator and stable columns |
| Terminal color contaminates redirected output | Low | Medium | Enable color only for TTY output by default; machine modes never emit ANSI escapes |
| Malformed logs silently distort percentages | Medium | High | Base metrics only on valid records and expose total, valid, and invalid counts in every format |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python and dependencies are open source |
| Hosting and storage | $0 | Local CLI; no hosted runtime or persistence |
| CI | $0 | Use a free open-source allowance or run checks locally |
| Labor | One weekend | Owner-delivered MVP; no cash budget assumed |
| Total operating budget | $0/month | No required external service |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream file or stdin without loading the input | **Must** | Required for large logs and Unix pipelines |
| Parse the documented nginx combined access-log format with invalid-line counts | **Must** | All metrics depend on trusted records |
| Top 10 IPs | **Must** | Core incident-triage metric |
| Top 10 URLs restricted to 4xx/5xx responses | **Must** | Core error-diagnosis metric |
| Hourly request percentages | **Must** | Core traffic-shape metric |
| Unique User-Agent share | **Must** | Core client-diversity metric |
| Rich colored terminal output | **Must** | Required default experience |
| JSON and CSV output | **Must** | Required pipeline interoperability |
| Gzip input | **Should** | Common archive format, but decompression can be piped for MVP |
| Configurable top-N | **Should** | Useful extension; fixed top 10 satisfies MVP |
| Additional nginx `log_format` templates | **Could** | Broadens adoption after the base grammar is stable |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Conflicts with the local stateless product boundary |

### RICE Scoring (Must + Should)

Scores use `(Reach × Impact × Confidence) / Effort`, with confidence as a decimal. They order implementation by value while dependency order remains authoritative.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming input + parser | 10 | 5 | 95% | 0.75 | 63.3 |
| Four core aggregations | 10 | 5 | 90% | 1.00 | 45.0 |
| JSON output | 8 | 4 | 95% | 0.25 | 121.6 |
| CSV output | 7 | 4 | 90% | 0.25 | 100.8 |
| Rich terminal output | 10 | 3 | 95% | 0.50 | 57.0 |
| Cardinality guard and exit contract | 10 | 4 | 90% | 0.50 | 72.0 |
| Gzip input | 5 | 2 | 70% | 0.25 | 28.0 |
| Configurable top-N | 4 | 2 | 80% | 0.25 | 25.6 |

The plan implements the parser before renderers despite renderer scores because renderers depend on valid aggregated data. Within the same dependency layer, higher RICE scores go first.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and acceptance criteria are reflected in `PRD.md` and `PROJECT_ARCHITECTURE.md`.
- [ ] Python 3.11 code is formatted, type-checked, and free of compile errors.
- [ ] Unit and integration tests pass with at least 90% line coverage for `src/nginx_top`.
- [ ] Golden tests prove text, JSON, and CSV contracts without ANSI leakage in machine modes.
- [ ] The representative 1 GB benchmark completes in under 30 seconds on the documented laptop and records peak memory.
- [ ] Code review is accepted and no known Critical or High security issue remains.
- [ ] `README.md`, CLI help, and changelog are updated when behavior changes.
- [ ] The installable wheel is tested in a clean Python 3.11 virtual environment.

## 13. Release and Kill Criteria

Release the MVP only when all P0 acceptance criteria in `PRD.md` pass and the performance target is measured rather than inferred. Re-scope or stop the project if two profiling/optimization passes cannot reach the 1 GB / 30 second target on the named benchmark laptop, or if exact User-Agent cardinality cannot be bounded with a clear failure contract while staying within the memory budget.

