# Strategic Plan: Nginx Stream Analyzer

## 1. Product Idea

Nginx Stream Analyzer is a local, pip-installable Python 3.11 CLI for DevOps and SRE engineers. It reads nginx access logs from a file or standard input in one pass and reports the top 10 client IPs, the top 10 URLs returning 4xx/5xx responses, hourly request distribution, and the share of unique User-Agent values. Its default Rich-rendered terminal view is optimized for humans; deterministic JSON and CSV modes support pipelines.

The MVP is intentionally local, stateless, and open source. It has no authentication, database, HTTP API, server process, cloud dependency, or Kubernetes footprint.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Incident responder | Needs a useful traffic/error snapshot without provisioning a stack | One command produces the four operational summaries |
| DevOps engineer | Platform operator | Must inspect large logs locally or over SSH | Streaming input and bounded memory avoid loading the file |
| Automation author | CI/shell pipeline maintainer | Human-only output is brittle to parse | Stable `--json` and `--csv` schemas |

## 3. Competitive Analysis

| Alternative | Strength | Limitation for this use case | Our distinction |
|---|---|---|---|
| GoAccess | Fast, mature, interactive reports | Broader UI/config surface than a four-metric pipeline tool | Smaller contract, JSON/CSV-first automation, Python installation |
| Logstash + Elastic + Kibana | Powerful centralized ingestion and dashboards | Infrastructure, storage, operational cost, and setup overhead | Zero-service local analysis with no retained data |
| AWStats | Established historical reports | Batch-oriented and state/report configuration heavy | Immediate one-shot streaming output |
| `grep`/`awk`/`sort` | Ubiquitous and composable | Complex quoting, repeated passes, format drift, weak structured output | One tested parser and one stable multi-report contract |

## 4. Unique Value Proposition

Get a pipeline-safe, four-signal nginx traffic and error summary from a gigabyte-scale local log in one command, without deploying or operating anything.

## 5. Business Model

The project is free and open source with a $0 product and infrastructure budget. There is no paid tier in the MVP. Success is adoption and operational usefulness rather than revenue; contributors bear only their existing laptop and weekend time. Future sponsorship is possible but is not a delivery dependency.

## 6. Technology Stack

| Component | Technology | Why |
|---|---|---|
| Runtime | Python 3.11 | Required, portable, productive for a one-weekend CLI |
| CLI | Click | Mature option parsing, help, validation, and exit handling |
| Terminal UI | Rich | Readable colored tables with terminal capability detection |
| Domain model | `dataclasses` | Typed records without extra runtime dependencies |
| Parsing/aggregation | Python standard library | Streaming file I/O, regex/datetime parsing, counters, JSON/CSV |
| Packaging | pip-compatible `pyproject.toml` | Standard install and console-script entry point |
| Testing | pytest | Focused parser, aggregation, CLI, and performance tests |

## 7. Timeline

| Period | Stage | Outcome |
|---|---|---|
| Saturday morning | Packaging, contracts, parser | Installable command parses representative combined logs |
| Saturday afternoon | Streaming metrics | All four reports computed in one pass with cardinality guards |
| Sunday morning | Terminal, JSON, CSV | Stable human and machine outputs with complete exit behavior |
| Sunday afternoon | QA, performance, docs | Test suite, 1 GB benchmark, install and usage documentation |

## 8. KPIs

| Metric | 1 month | 3 months | 6 months |
|---|---:|---:|---:|
| 1 GB processing time on reference laptop | <30 s | <30 s | <25 s |
| Valid-line parsing accuracy on fixture corpus | ≥99.9% | ≥99.95% | ≥99.95% |
| Peak memory on documented 1 GB benchmark | <512 MB | <384 MB | <384 MB |
| Successful installs from a clean Python 3.11 environment | 95% | 98% | 99% |
| GitHub stars or equivalent adoption signal | 10 | 50 | 150 |

Performance claims apply to the documented reference laptop, uncompressed local input, warm filesystem cache, default options, and benchmark fixture; results on other hardware are reported separately.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Unexpected nginx formats create malformed lines | High | High | Combined-format MVP contract, counted skips, samples in diagnostics, nonzero threshold policy |
| Exact unique sets exhaust memory on hostile/high-cardinality input | Medium | High | `--max-unique` cap and dedicated exit code 4; document trade-off |
| Python misses the 1 GB/30 s target | Medium | High | Single pass, precompiled parser, no per-line Rich work, benchmark before polish |
| CSV multi-report shape surprises consumers | Medium | Medium | One normalized schema, version field in JSON, golden contract tests |
| Terminal colors leak into redirected output | Low | Medium | Auto-disable on non-TTY and for JSON/CSV; explicit `--color/--no-color` |
| Scope expands toward a monitoring platform | Medium | High | Won't list, no persistence/server boundary, one-weekend timebox |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Development | $0 | One weekend of contributor time; no cash expense |
| Runtime/infrastructure | $0/month | Runs locally; no hosted components |
| Dependencies | $0 | Open-source Python packages |
| Distribution | $0 | Source repository and standard package tooling |
| Total cash budget | $0 | Hard constraint |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream file/stdin in one pass | Must | Foundation for local and piped operation |
| Parse nginx combined access logs with diagnostics | Must | Every metric depends on trustworthy fields |
| Top-10 client IPs | Must | Required traffic signal |
| Top-10 4xx/5xx URLs | Must | Required error signal |
| Hourly request percentages | Must | Required temporal signal |
| Unique User-Agent share | Must | Required client-diversity signal |
| Rich colored terminal output | Must | Required default experience |
| Stable JSON and CSV output | Must | Required pipeline support |
| Cardinality limit with exit code 4 | Must | Required safe failure for bounded local resources |
| Gzip input | Should | Common operational convenience, but shell decompression works |
| Custom nginx `log_format` templates | Should | Broadens compatibility after the MVP parser is proven |
| Configurable top-N | Could | Useful polish; top 10 is the explicit product contract |
| Live refresh dashboard | Could | Helpful interactively but not needed for one-shot reports |
| Authentication, database, HTTP API, server, cloud, Kubernetes | Won't | Contradicts the local stateless CLI scope |

### RICE Scoring (Must + Should)

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE Score |
|---|---:|---:|---:|---:|---:|
| Stream file/stdin in one pass | 10 | 5 | 100% | 0.5 | 100.0 |
| Parse combined logs with diagnostics | 10 | 5 | 90% | 0.75 | 60.0 |
| Rich terminal output | 9 | 3 | 90% | 0.5 | 48.6 |
| Top-10 client IPs | 8 | 4 | 95% | 0.75 | 40.5 |
| Top-10 error URLs | 8 | 4 | 95% | 0.75 | 40.5 |
| Hourly request percentages | 8 | 3 | 95% | 0.5 | 45.6 |
| Unique User-Agent share | 7 | 3 | 90% | 0.5 | 37.8 |
| JSON and CSV output | 8 | 4 | 90% | 1.0 | 28.8 |
| Cardinality limit / exit 4 | 7 | 5 | 90% | 0.75 | 42.0 |
| Gzip input | 5 | 2 | 75% | 0.5 | 15.0 |
| Custom log formats | 5 | 4 | 60% | 2.0 | 6.0 |

Dependency order can override raw RICE: the stream and parser precede derived metrics, while safety limits are built with aggregation rather than bolted on later.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and acceptance criteria are reflected in `PRD.md` and `PROJECT_ARCHITECTURE.md`.
- [ ] Python 3.11 code passes formatting, linting, and type checks selected during implementation.
- [ ] Unit and CLI integration tests pass with at least 90% statement coverage.
- [ ] P0 golden-output tests pass for terminal, JSON, and CSV modes.
- [ ] The 1 GB reference benchmark completes in under 30 seconds and records peak memory.
- [ ] A clean virtual environment can install the package and run the console command.
- [ ] Documentation is updated and contains no stale interface examples.
- [ ] No known critical or high-severity security issue remains.
- [ ] Review and the project’s current verification contract accept the exact candidate.

## 13. Kill Criteria

Re-scope or stop the MVP if a representative optimized prototype cannot process 1 GB under 30 seconds on the reference laptop, exact required metrics cannot stay within a documented safe memory ceiling, or the delivery cannot remain a local $0 one-weekend CLI without adding a service or persistent store.
