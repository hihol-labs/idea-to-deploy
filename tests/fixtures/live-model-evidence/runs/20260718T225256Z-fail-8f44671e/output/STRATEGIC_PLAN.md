# Strategic Plan: nginx-stream-report

## 1. Product idea

`nginx-stream-report` is a local, pip-installable Python 3.11 CLI that reads nginx combined access logs as a stream and produces four operational views: top 10 client IPs, top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the percentage of distinct User-Agent values. It targets DevOps and SRE investigations where data must remain local and a useful summary is needed without deploying an observability stack.

## 2. Target audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call engineer | SRE responding to an incident | Needs a fast first-pass answer from a large log on a laptop | One streaming command, bounded aggregation, terminal summary |
| Platform engineer | Maintains nginx fleets and shell pipelines | Needs machine-readable results for follow-up automation | Stable `--json` and `--csv` output contracts |
| Systems administrator | Operates small or isolated installations | Full analytics stacks are costly or unavailable | Local, stateless, zero-service installation through pip |

## 3. Competitive analysis

| Alternative | Strength | Weakness for this use case | Differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Broader UI and configuration surface than a four-metric incident summary | Narrow, predictable CLI contract with pipeline-first JSON/CSV |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, search, dashboards, retention | Requires multiple services, storage, operations, and materially more setup | No services, persistence, or infrastructure; data stays local |
| AWStats | Established historical web analytics | Oriented toward generated historical reports rather than ad-hoc streaming diagnosis | Immediate stdout report and composable exports |
| `grep`/`awk`/`sort` | Ubiquitous and flexible | Repeated parsing, fragile quoting, multiple passes, and inconsistent schemas | One tested parser and one-pass aggregation with explicit malformed-line policy |

## 4. Unique value proposition

Get the four nginx incident metrics that matter from a gigabyte-scale local log in one command, with no service to deploy and outputs that work equally well for humans and pipelines.

## 5. Business model

The product is open source and free. The success model is adoption and operational utility rather than revenue: no paid tier, telemetry, advertising, or hosted service. Contribution costs are constrained to maintainer time; distribution uses public Python packaging infrastructure at no direct project cost.

## 6. Technology stack

| Component | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Approved, portable, mature standard-library streaming I/O |
| CLI | Click | Stable option parsing, help, exit-code behavior, and test utilities |
| Terminal presentation | Rich | Accessible tables, color, and automatic terminal capability handling |
| Domain models | `dataclasses` | Lightweight typed records without a validation framework |
| Packaging | `pyproject.toml` + pip | Standard installable CLI distribution |
| Verification | pytest, Ruff, mypy, benchmark fixture generator | Correctness, static quality, and the 1 GB performance gate |

## 7. Timeline

| Delivery block | Scope | Outcome |
|---|---|---|
| Saturday morning | Package skeleton, parser, malformed-line policy | Stream of validated access-log records |
| Saturday afternoon | Aggregators and deterministic ranking | Correct four-metric analysis core |
| Sunday morning | text/JSON/CSV renderers and Click interface | End-to-end CLI and pipeline contracts |
| Sunday afternoon | tests, 1 GB benchmark, docs, packaging smoke test | Release candidate with recorded evidence |

## 8. KPIs

| Metric | First month | Three months | Six months |
|---|---:|---:|---:|
| 1 GB processing time on reference laptop | `<30 s` | `<30 s` | `<30 s` |
| Peak memory on the 1 GB benchmark | `<256 MiB` | `<256 MiB` | `<256 MiB` |
| Valid-line parsing accuracy on golden fixtures | `100%` | `100%` | `100%` |
| P0 acceptance tests passing | `100%` | `100%` | `100%` |
| Successful clean-venv install and `--help` smoke test | `100%` per release | `100%` per release | `100%` per release |

KPIs are engineering release gates because the budget and local-tool scope do not justify analytics or user tracking.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Python parsing misses the 30-second target | Medium | High | Benchmark early; avoid per-line regex recompilation and object retention; profile before optimizing |
| Real nginx formats differ from combined format | High | Medium | State the supported format, fail clearly on systematic mismatch, and defer configurable formats |
| High-cardinality User-Agents consume memory | Medium | High | Specify an exact-set memory limit behavior; document the trade-off and measure peak RSS |
| CSV representation of multi-section results is ambiguous | Medium | Medium | Use a normalized row schema with a `section` column and stable headers |
| Rich color leaks into redirected output | Low | Medium | Color only for interactive text; JSON/CSV never emit ANSI; test redirection |
| Malformed or truncated lines distort operator conclusions | Medium | High | Count skipped lines, report the count, and support strict failure mode as P1 |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime/frameworks | $0 | Open-source Python, Click, and Rich |
| Local development and benchmark | $0 | Existing laptop and generated local fixtures |
| Hosting/database/cloud | $0 | Explicitly absent |
| Package distribution | $0 | Public package index workflow; publishing credentials are outside MVP implementation |
| Delivery labor | One weekend | Time-boxed scope; no monetary project budget |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream combined-format input from a file or stdin | **Must** | Foundation of local and pipeline use |
| Top 10 client IPs | **Must** | Core incident view |
| Top 10 URLs by 4xx/5xx count | **Must** | Core failure diagnosis view |
| Hourly request distribution | **Must** | Core traffic-shape view |
| Unique User-Agent share | **Must** | Core client-diversity view |
| Colored terminal report | **Must** | Default human-facing contract |
| Stable JSON and CSV exports | **Must** | Required pipeline contract |
| Malformed-line count and deterministic ties | **Must** | Required for trustworthy results |
| Strict malformed-line mode | **Should** | Useful in automated validation but not essential to first summary |
| `--no-color` override | **Should** | Improves accessibility and unusual terminal behavior |
| Top-N configurability | **Could** | Useful generalization, but top 10 is the approved product |
| Configurable nginx log formats | **Could** | Broadens use but adds parsing and support risk |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Contradicts the local stateless CLI purpose and approved scope |

### RICE scoring (Must + Should)

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming file/stdin parser | 10 | 5 | 90% | 0.75 | 60.0 |
| Top IP aggregation | 10 | 4 | 95% | 0.25 | 152.0 |
| Error URL aggregation | 10 | 5 | 95% | 0.35 | 135.7 |
| Hourly distribution | 9 | 4 | 95% | 0.25 | 136.8 |
| Unique User-Agent share | 8 | 3 | 80% | 0.35 | 54.9 |
| Colored terminal report | 9 | 3 | 90% | 0.40 | 60.8 |
| JSON and CSV exports | 8 | 4 | 90% | 0.50 | 57.6 |
| Trustworthy malformed-line/tie behavior | 10 | 5 | 90% | 0.50 | 90.0 |
| Strict malformed-line mode | 5 | 2 | 75% | 0.25 | 30.0 |
| `--no-color` | 4 | 2 | 90% | 0.10 | 72.0 |

The implementation order in `IMPLEMENTATION_PLAN.md` respects dependencies first, then applies RICE order within each dependency layer.

## 12. Definition of Done

A feature is Done when:

- [ ] Its P0 acceptance criteria in `PRD.md` have executable tests.
- [ ] Ruff and mypy pass with no ignored new violations.
- [ ] Unit and CLI integration tests pass; coverage is at least 90% for parser, aggregation, and serializers.
- [ ] JSON/CSV fixtures and terminal snapshots contain no accidental ANSI sequences.
- [ ] The 1 GB reference benchmark completes in under 30 seconds on the recorded laptop profile and peak RSS is reported.
- [ ] A clean Python 3.11 virtual environment can install the package and run `--help`.
- [ ] Documentation and `CLAUDE.md` status are reconciled.
- [ ] No known Critical or High security issue remains.

## 13. Strategic kill criteria

Re-scope or stop the MVP if a representative 1 GB combined-format log cannot meet the 30-second target after profiling, if exact User-Agent cardinality cannot fit the `<256 MiB` working-memory objective on the agreed benchmark, or if reliable parsing requires supporting arbitrary nginx formats in the first release. Any relaxation must update `PRD.md`, `PROJECT_ARCHITECTURE.md`, and the performance acceptance evidence together.
