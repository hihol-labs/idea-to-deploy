# Strategic Plan: nginx-report

## 1. Product Idea

`nginx-report` is a local, pip-installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx combined access logs as a stream, keeps bounded aggregate state rather than retaining requests, and reports the top 10 client IPs, top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. Human-readable colored terminal output is the default; stable JSON and CSV outputs support pipelines.

The MVP is an open-source utility delivered in one weekend with no paid services. It is intentionally not an observability platform: there is no database, service, authentication, HTTP API, cloud component, or Kubernetes deployment.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Diagnoses incidents from a shell | Needs a rapid traffic/error overview without shipping logs elsewhere | One local command provides the four operational summaries |
| DevOps engineer | Builds repeatable operational pipelines | Ad hoc `awk` scripts are fragile and difficult to integrate safely | Stable JSON/CSV schemas and documented exit codes |
| Privacy-conscious operator | Works with sensitive or air-gapped logs | Hosted analytics and central ingestion may be prohibited or excessive | Stateless local processing; no network or persistence |

## 3. Competitive Analysis

| Alternative | What it does well | Weakness for this use case | Our distinction |
|---|---|---|---|
| GoAccess | Mature, fast, interactive nginx analytics | Broader UI/configuration surface than a four-metric pipeline tool | Smaller contract, Python installation, deterministic JSON/CSV |
| Logstash + Elasticsearch + Kibana | Powerful centralized search and dashboards | Operationally heavy, stateful, costly in time and resources | Zero-service, zero-database local analysis |
| AWStats | Established historical web analytics | Persistent reports and dated operational workflow | Immediate streaming CLI output with no retained state |
| `grep`/`awk` pipelines | Ubiquitous and flexible | Quoting, parsing, portability, and schema consistency are left to users | Tested combined-log parsing and stable outputs in one command |

## 4. Unique Value Proposition

Get the four nginx incident summaries an operator needs from a gigabyte-scale log with one local, pipeline-safe command and no observability stack.

## 5. Business Model and Licensing

The product is free and open source. There are no paid tiers, hosted services, telemetry, or monetization requirements for the MVP. Value is measured by operator time saved and trustworthy automation, not revenue. A permissive OSI-approved license should be selected before public release.

## 6. Technology Strategy

| Component | Choice | Why |
|---|---|---|
| Runtime | Python 3.11 | Approved, broadly available to the target users |
| CLI | Click | Predictable option parsing, help, and usage errors |
| Terminal rendering | Rich | Accessible tables, color control, terminal detection |
| Domain models | `dataclasses` | Explicit lightweight records without a framework |
| Packaging | `pyproject.toml` + pip | Standard install and console entry point |
| Testing | pytest | Fast unit, integration, golden-output, and performance checks |

## 7. Timeline

| Window | Work | Outcome |
|---|---|---|
| Saturday morning | Packaging, contracts, parser | Installable skeleton and validated combined-log records |
| Saturday afternoon | Streaming aggregates | All four metrics computed in one pass |
| Sunday morning | Text, JSON, CSV renderers and CLI | Complete user-facing behavior and exit codes |
| Sunday afternoon | Tests, 1 GB benchmark, docs, release check | Evidence-backed MVP ready to publish |

## 8. KPIs

| Metric | Launch target | One-month target | Three-month target |
|---|---:|---:|---:|
| Performance on a representative 1 GB combined log | <30 seconds on reference laptop | Maintained | Maintained across releases |
| Peak resident memory on the same benchmark | Documented and within laptop-safe bound | No regression >10% | No regression >10% |
| Correctness golden cases | 100% | 100% | 100% |
| Output/exit-code compatibility regressions | 0 | 0 | 0 |
| Installation-to-first-report time | <2 minutes | <2 minutes | <2 minutes |

Reference laptop hardware, OS, filesystem cache policy, corpus hash, and benchmark command must be recorded with results so the performance KPI is reproducible.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Python parsing misses the 1 GB/30 s target | Medium | High | Parse bytes in one pass, avoid per-line regex churn where profiling supports it, benchmark early |
| Log-format variations cause false invalid records | High | Medium | Scope MVP to nginx combined format, expose format selection only after fixtures exist, count and signal invalid lines |
| Exact unique User-Agent cardinality exhausts memory | Medium | High | Enforce a documented cardinality ceiling and exit with code 4; never silently approximate |
| JSON/CSV schemas drift | Medium | High | Version and golden-test serialized contracts |
| Terminal color contaminates redirected output | Low | Medium | Enable color only for a TTY by default and support `--no-color` |
| Sensitive log values leak through diagnostics | Low | High | Do not echo full malformed lines; report source and line number only |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Open-source Python ecosystem |
| Infrastructure | $0 | Local execution only |
| Hosting, database, cloud | $0 | Explicitly absent |
| Development | $0 cash budget | One-weekend owner effort |
| Total MVP cash budget | **$0** | No paid dependency or service |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream nginx combined-log input from files or stdin | **Must** | Foundation for all value and bounded-memory behavior |
| Top 10 client IPs | **Must** | Core incident summary |
| Top 10 error URLs for 4xx/5xx responses | **Must** | Core failure diagnosis |
| Hourly request distribution | **Must** | Core traffic-shape summary |
| Exact unique User-Agent share with an exhaustion guard | **Must** | Core requested metric without silent approximation |
| Colored terminal report | **Must** | Default operator experience |
| Stable `--json` and `--csv` reports | **Must** | Required pipeline interoperability |
| Live `--follow` mode | **Should** | Useful operationally, but finite streams deliver the MVP value |
| Configurable nginx log formats | **Should** | Broadens adoption after combined-format correctness is proven |
| Compressed file input | **Could** | Convenient but shell decompression already composes with stdin |
| Configurable top-N | **Could** | Adds flexibility beyond the requested top 10 |
| Database, HTTP API, server, auth, cloud, Kubernetes | **Won't** | Contradicts the local stateless CLI boundary |
| Approximate User-Agent cardinality | **Won't** | Would change the promised exact metric in v1 |

### RICE Scoring (Must + Should)

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Stream files/stdin and parse combined format | 10 | 5 | 90% | 0.75 | 60.0 |
| Single-pass four-metric aggregation | 10 | 5 | 85% | 1.00 | 42.5 |
| Colored terminal report | 9 | 3 | 90% | 0.35 | 69.4 |
| JSON and CSV reports | 8 | 4 | 90% | 0.50 | 57.6 |
| Exact User-Agent exhaustion guard | 7 | 4 | 80% | 0.35 | 64.0 |
| Live follow mode | 5 | 3 | 65% | 0.75 | 13.0 |
| Configurable log formats | 6 | 3 | 55% | 1.00 | 9.9 |

Within dependency constraints, implementation follows descending RICE value. Parser and aggregator foundations precede renderers even where a renderer has a higher standalone score.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and acceptance criteria are reflected in `PRD.md` and `PROJECT_ARCHITECTURE.md`.
- [ ] Code is typed, formatted, and imports on Python 3.11.
- [ ] Unit and integration tests pass with at least 90% line coverage for parser, aggregation, serialization, and exit-code modules.
- [ ] JSON/CSV golden contracts pass where relevant.
- [ ] No known Critical or High security issues remain.
- [ ] User documentation and `--help` are current.
- [ ] The exact staged candidate passes the project verification oracle and applicable risk-tier review.
- [ ] The representative 1 GB benchmark is recorded and meets the <30-second target before release.

## 13. MVP Kill and Reassessment Criteria

Reassess the MVP if a profiled Python 3.11 implementation cannot process the representative 1 GB corpus in under 30 seconds after two bounded optimization attempts, if exact User-Agent tracking cannot stay within the documented laptop memory budget for representative data, or if combined-format fixtures cannot produce deterministic cross-format reports. The response is to narrow or revise the product contract explicitly, not silently weaken accuracy.

## 14. Related Specifications

Technical boundaries are defined in `PROJECT_ARCHITECTURE.md`; replayable product behavior is defined in `PRD.md`; delivery order and evidence are defined in `IMPLEMENTATION_PLAN.md`.
