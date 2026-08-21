# Strategic Plan: Nginx Stream Analytics CLI

## 1. Product Idea

Build a local, pip-installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx combined-format access logs from a file or standard input in one pass and reports the top 10 client IPs, top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. Rich colored terminal output is the default; deterministic JSON and CSV outputs support pipelines.

The MVP is deliberately local and stateless. It has no authentication, database, HTTP API, server process, cloud dependency, or Kubernetes deployment. The delivery window is one weekend and the operating budget is $0.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call engineer | SRE responding to an incident | Needs a quick traffic/error picture without shipping sensitive logs elsewhere | One local command produces the four operational summaries |
| Platform engineer | Maintains hosts and deployment pipelines | Needs predictable machine-readable output | Stable `--json` and `--csv` schemas and documented exit codes |
| Systems administrator | Operates small or isolated installations | Full observability stacks are too costly or unavailable | Offline pip-installable tool with bounded, streaming processing |

## 3. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | Product differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive dashboards | Broader UI and configuration surface than a four-metric pipeline command | Narrow, script-friendly contract and native JSON/CSV |
| Logstash + Elastic + Kibana | Powerful ingestion, search, retention, visualization | Requires services, storage, setup, and ongoing resources | Zero-service, zero-storage, single-process analysis |
| AWStats | Established historical reporting | Persistent reports and dated workflow; not stream/pipeline oriented | Immediate stdin/file analysis with modern CLI ergonomics |
| `grep`/`awk` pipelines | Ubiquitous and flexible | Fragile quoting/parsing, repeated scans, inconsistent output contracts | One tested parser, one pass, four consistent summaries |

## 4. Unique Value Proposition

Get a trustworthy, pipeline-ready nginx traffic and error snapshot from a gigabyte-scale log using one local command, without deploying or operating an observability stack.

## 5. Business Model

The project is open source and free. There are no paid tiers, telemetry, hosted services, or monetization requirements. Success is measured by operational usefulness, predictable behavior, and low maintenance rather than revenue, CAC, or LTV.

## 6. Technology Stack

| Component | Technology | Why |
|---|---|---|
| Runtime | Python 3.11 | Approved, portable, modern typing and performance baseline |
| CLI | Click | Reliable option parsing, help, errors, and exit integration |
| Terminal output | Rich | Accessible colored tables with automatic non-TTY behavior |
| Domain models | `dataclasses` | Lightweight typed records without extra runtime dependencies |
| Packaging | `pyproject.toml` + pip | Standard install and console-script entry point |
| Tests | pytest | Focused parser, aggregation, output, CLI, and performance tests |

## 7. Timeline

| Window | Stage | Result |
|---|---|---|
| Saturday morning | Packaging, contracts, parser | Installable CLI skeleton and resilient combined-log parsing |
| Saturday afternoon | Streaming aggregation | All four metrics computed in one pass with bounded failure behavior |
| Sunday morning | Renderers and CLI integration | Rich, JSON, and CSV contracts implemented |
| Sunday afternoon | Tests, benchmark, documentation | Release candidate validated against correctness and 1 GB target |

## 8. KPIs

| Metric | Release target | First month | Third month |
|---|---:|---:|---:|
| Processing time for 1 GB on reference laptop | < 30 seconds | Maintain < 30 seconds | Maintain < 30 seconds |
| Peak resident memory on representative 1 GB input | ≤ 256 MiB before exact-cardinality guard trips | No unbounded regressions | No unbounded regressions |
| Correctness fixtures passing | 100% | 100% | 100% |
| Valid-line loss on supported combined format | 0% | 0 confirmed defects | 0 confirmed defects |
| Installation-to-first-report time | < 2 minutes | < 2 minutes median | < 2 minutes median |

Performance claims are accepted only on a documented reference laptop, generated representative fixture, cold/warm-run method, elapsed time, and peak RSS. The 30-second target is a release gate, not an assumed property of Python.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from combined format | High | Medium | Explicit supported-format contract, malformed-line count, actionable code `3`, fixture corpus |
| Exact unique User-Agent storage grows beyond memory budget | Medium | High | Configurable cardinality ceiling and fail-fast code `4`; document exactness boundary |
| Python misses the 1 GB / 30 s target | Medium | High | Benchmark early; bytes-oriented hot path, single pass, profiling, no per-line Rich work |
| CSV cannot naturally represent four differently shaped reports | Medium | Medium | Define one normalized long-form schema with metric/category/value/count/share fields |
| Terminal colors corrupt redirected output | Low | Medium | Color only for TTY by default; machine formats never emit ANSI sequences |
| Invalid inputs silently produce misleading summaries | Medium | High | Track total/valid/malformed lines and fail with code `3` when no valid records exist |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Software and libraries | $0 | Open-source Python, Click, Rich, pytest |
| Infrastructure | $0 | Local execution; no hosted runtime or database |
| Distribution | $0 | Source distribution/wheel may be published to free package infrastructure |
| Delivery labor | One weekend | Fixed scope; deferred features are not allowed to displace Must items |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream a file or stdin in nginx combined format | **Must** | Foundation for local and pipeline use |
| Top-10 client IPs | **Must** | Required traffic concentration signal |
| Top-10 URLs by 4xx/5xx error count | **Must** | Required failure hot-spot signal |
| Hourly request distribution | **Must** | Required load-shape signal |
| Exact unique User-Agent share with exhaustion guard | **Must** | Required diversity signal with explicit memory safety |
| Rich terminal, JSON, and CSV renderers | **Must** | Required human and pipeline interfaces |
| Malformed-line accounting and complete exit codes | **Must** | Prevents silent operational misinterpretation |
| Gzip input | **Should** | Common log archival format but shell decompression is an MVP workaround |
| Configurable top-N | **Could** | Useful flexibility after the fixed top-10 contract is proven |
| Additional nginx `log_format` definitions | **Could** | Broadens adoption but expands parser scope |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Conflicts with the approved local stateless product boundary |

### RICE Scoring (Must + Should)

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE Score |
|---|---:|---:|---:|---:|---:|
| File/stdin streaming and parser | 10 | 5 | 90% | 0.75 | 60.0 |
| Malformed-line and exit contract | 10 | 4 | 90% | 0.5 | 72.0 |
| Top-10 IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Top-10 error URLs | 9 | 5 | 95% | 0.35 | 122.1 |
| Hourly distribution | 8 | 4 | 95% | 0.25 | 121.6 |
| Unique User-Agent share and guard | 8 | 4 | 80% | 0.5 | 51.2 |
| Three output renderers | 10 | 5 | 85% | 0.75 | 56.7 |
| Gzip input | 5 | 2 | 80% | 0.25 | 32.0 |

Dependency ordering takes precedence where a high-scoring metric requires the parser or output contract. Within each dependency layer, implementation follows descending RICE score.

## 12. Definition of Done

A feature is done when:

- [ ] Its behavior and acceptance criteria are represented in `PRD.md`.
- [ ] Python 3.11 code is formatted, typed, and installable through pip.
- [ ] Unit and CLI tests pass, with at least 90% statement coverage for parser, aggregation, and renderers.
- [ ] Integration fixtures cover valid, malformed, empty, and mixed-status logs.
- [ ] JSON and CSV outputs parse without ANSI codes or diagnostic contamination.
- [ ] The 1 GB benchmark meets the documented < 30-second target on the reference laptop.
- [ ] No known Critical or High security findings remain.
- [ ] `README.md`, command help, and implementation status are updated.

## 13. Kill Criteria

- Stop the release if supported valid records are parsed incorrectly or included inconsistently across metrics.
- Re-scope the implementation if a profiled, optimized single-pass Python implementation cannot process 1 GB within 30 seconds on the reference laptop.
- Do not ship an “approximate” User-Agent share under the exact metric name; either exact counting succeeds or execution ends with code `4`.
- Reject additions requiring a background service, persistence layer, or paid infrastructure for the MVP.

