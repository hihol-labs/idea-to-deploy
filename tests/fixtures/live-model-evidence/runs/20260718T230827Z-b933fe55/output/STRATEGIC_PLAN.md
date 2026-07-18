# Strategic Plan: Nginx Stream Analyzer

## 1. Product Idea

Nginx Stream Analyzer is a local, installable Python 3.11 CLI for DevOps and SRE engineers. It reads nginx combined-format access logs as a stream and reports the top 10 client IPs, top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of distinct User-Agent strings. Human-friendly colored terminal output is the default; JSON and CSV outputs make the same results usable in pipelines.

The MVP is deliberately narrow: no service to operate, no persisted state, and no external dependencies at runtime beyond the Python package. The target is to process a 1 GB log in under 30 seconds on a representative laptop.

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| On-call SRE | Triage production incidents | Needs a fast first view without uploading sensitive logs | Runs one local command and receives four actionable summaries |
| DevOps engineer | Maintains reverse proxies and deployment pipelines | Existing one-liners are fragile and hard to reuse | Gets stable JSON/CSV schemas and predictable exit behavior |
| Platform engineer | Supports multiple internal teams | Heavy observability stacks are excessive for ad-hoc files | Installs a lightweight open-source CLI through pip |

## 3. Competitive Analysis

| Alternative | What it does | Weakness for this use case | Our distinction |
|---|---|---|---|
| GoAccess | Rich real-time terminal/HTML web analytics | Broader configuration and UI surface than a four-metric pipeline tool | Narrow command contract, native JSON/CSV, pip install |
| Logstash + Elasticsearch + Kibana | Centralized ingestion, search, dashboards | Operational overhead, storage, services, and cost | Zero-service local processing with no retained data |
| AWStats | Mature periodic web-log reports | File-based historical reporting and dated workflow | Immediate streaming CLI output for incident triage |
| grep/awk/sort | Ubiquitous ad-hoc text processing | Quoting, parsing, portability, and multi-pass memory/time pitfalls | Tested nginx parser and all metrics in one pass |

## 4. Unique Value Proposition

Turn a large local nginx access log into the four SRE summaries that matter most, in one command and one pass, without deploying or operating anything.

## 5. Business Model

The project is free and open source. There is no paid tier, CAC, or direct LTV target for the one-weekend MVP. Value is measured as engineering time saved and adoption; permissive licensing and a public package reduce distribution friction. The approved budget is $0.

## 6. Technology Stack

| Component | Technology | Why |
|---|---|---|
| Runtime | Python 3.11 | Approved, portable, mature text-processing ecosystem |
| CLI | Click | Stable argument validation, help, and exit behavior |
| Terminal UI | Rich | Colored tables and readable diagnostics |
| Domain models | `dataclasses` | Explicit lightweight records without framework overhead |
| Packaging | `pyproject.toml` + pip | Standard installable CLI distribution |
| Tests | pytest | Fast unit, integration, and performance-smoke coverage |

See [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) for module boundaries and decisions.

## 7. Timeline

| Window | Stage | Result |
|---|---|---|
| Saturday morning | Packaging, contracts, parser | Installable command and validated streaming records |
| Saturday afternoon | Aggregation and formats | One-pass metrics plus JSON/CSV renderers |
| Sunday morning | Rich output, errors, tests | Human output and edge cases verified |
| Sunday afternoon | Benchmark, documentation, release | 1 GB target measured and package ready to publish |

## 8. KPIs

| Metric | 1 month | 3 months | 6 months |
|---|---:|---:|---:|
| 1 GB processing time on reference laptop | <30 s | <25 s | <20 s if profiling supports it |
| Peak resident memory on both 1 GB benchmark profiles | ≤512 MiB release gate | <384 MiB | <256 MiB if profiling supports it |
| Valid-line parsing accuracy on fixture corpus | ≥99.9% | ≥99.95% | ≥99.99% |
| CLI installs / internal users | 10 | 50 | 100 |
| Unhandled crashes on malformed input | 0 | 0 | 0 |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| High-cardinality IP, URL, or User-Agent sets exhaust memory | Medium | High | Document exactness trade-off; benchmark adversarial cardinality; define a clear failure mode |
| nginx log formats differ from combined format | High | Medium | Declare supported format; count malformed lines; make parser boundaries extensible |
| Python misses the 1 GB / 30 s target | Medium | High | Keep a single pass, minimize allocations, profile before optimizing, benchmark from a local file |
| CSV shape is ambiguous for four heterogeneous reports | Medium | Medium | Specify a normalized `report,key,value,rank` schema |
| Terminal color corrupts redirected output | Low | Medium | Enable color only for a TTY; JSON/CSV contain no ANSI escapes |
| Counting distinct User-Agents conflicts with strict bounded memory | Medium | Medium | Define the exact metric and measure cardinality; defer approximate counting unless required |

## 10. Budget

| Item | One-time | Monthly | Comment |
|---|---:|---:|---|
| Development tools | $0 | $0 | Open-source stack and existing laptop |
| Hosting/infrastructure | $0 | $0 | Local CLI; no service |
| Package distribution | $0 | $0 | Public Python package index |
| Test data | $0 | $0 | Generated fixtures and sanitized local samples |
| Total | **$0** | **$0** | Fits approved budget |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream nginx combined logs from a file or stdin | **Must** | Foundation for local files and Unix pipelines |
| Top 10 client IPs | **Must** | Core traffic-source summary |
| Top 10 URLs by 4xx/5xx count | **Must** | Core incident/error summary |
| Hourly request distribution | **Must** | Core time-pattern summary |
| Unique User-Agent share | **Must** | Core client-diversity summary |
| Colored terminal report | **Must** | Approved default user experience |
| JSON output | **Must** | Required pipeline contract |
| CSV output | **Must** | Required pipeline contract |
| Malformed-line accounting and deterministic exit behavior | **Should** | Important operational trust signal, while valid logs still provide core value |
| Configurable top-N | **Could** | Useful extension but top 10 is explicitly sufficient |
| Additional nginx log-format templates | **Could** | Broadens adoption after MVP stability |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Explicitly out of scope and contrary to local stateless positioning |

### RICE Scoring (Must + Should)

Confidence is expressed as a fraction in the formula `(Reach × Impact × Confidence) / Effort`.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming file/stdin ingestion | 10 | 5 | 95% | 0.50 | 95.0 |
| Top 10 IPs | 9 | 4 | 95% | 0.20 | 171.0 |
| Top 10 error URLs | 10 | 5 | 95% | 0.30 | 158.3 |
| Hourly distribution | 8 | 3 | 95% | 0.20 | 114.0 |
| Unique User-Agent share | 7 | 3 | 80% | 0.35 | 48.0 |
| JSON output | 8 | 4 | 95% | 0.25 | 121.6 |
| CSV output | 7 | 3 | 90% | 0.25 | 75.6 |
| Colored terminal report | 9 | 3 | 95% | 0.30 | 85.5 |
| Malformed-line accounting and exits | 9 | 4 | 90% | 0.35 | 92.6 |

Implementation order in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) respects dependencies first, then uses RICE order within each dependency layer.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and acceptance criteria are reflected in [PRD.md](PRD.md).
- [ ] Code is written for Python 3.11 and static checks pass.
- [ ] Unit tests pass with at least 90% coverage of the package.
- [ ] CLI integration tests pass for terminal, JSON, and CSV paths where applicable.
- [ ] Review is accepted with no unresolved critical/high findings.
- [ ] User documentation and command help are updated.
- [ ] No known critical/high security issue remains.
- [ ] The installable package is manually verified in a clean virtual environment.
- [ ] The 1 GB benchmark is recorded and meets the <30 second target before release.

## 13. Kill Criteria

Stop or redesign the MVP if a representative 1 GB combined log cannot be processed under 30 seconds after profiling and one bounded optimization cycle, if exact required metrics cannot fit within practical laptop memory on an agreed high-cardinality corpus, or if users require a persistent multi-user service rather than a local CLI. The latter would be a different product, not an MVP extension.
