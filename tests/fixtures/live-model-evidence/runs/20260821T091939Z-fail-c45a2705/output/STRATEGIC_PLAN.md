# Strategic Plan: nginx-insight

## 1. Product Idea

`nginx-insight` is an installable Python 3.11 command-line tool for DevOps and
SRE engineers. It reads nginx combined access logs as a stream and reports the
top 10 client IPs, the top 10 URLs producing 4xx/5xx responses, the percentage
of valid requests in each hour of the day, and the percentage of distinct
User-Agent values. Rich renders the default colored terminal view; JSON and CSV
provide stable pipeline output.

The MVP is deliberately local, stateless, and single-process. It has no
authentication, database, HTTP API, server process, cloud service, or
Kubernetes dependency. The delivery constraint is one weekend, the operating
budget is $0, and the performance target is a 1 GB log in under 30 seconds on a
representative laptop.

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| On-call SRE | Triage production incidents | Needs immediate traffic and error concentration without opening a dashboard | Streams a local or piped log and prints actionable rankings in one command |
| DevOps engineer | Operates nginx hosts and CI jobs | Existing observability stacks may be unavailable, costly, or too slow to configure | Provides zero-service, pip-installable JSON/CSV output for scripts |
| Platform engineer | Reviews archived access logs | Ad hoc shell pipelines are hard to reproduce and mishandle parsing edge cases | Uses a documented parser, deterministic ordering, and explicit exit codes |

## 3. Competitive Analysis

| Alternative | What it does well | Weakness for this project | nginx-insight differentiation |
|---|---|---|---|
| GoAccess | Fast, mature real-time terminal/HTML log analytics | Broader UI and configuration surface than this focused four-metric workflow | Smaller Python-native CLI with explicit JSON/CSV contracts |
| Logstash + Elastic + Kibana | Powerful ingestion, search, retention, and dashboards | Requires multiple services, storage, setup, and operational cost | No service or persistence; useful during an incident in seconds |
| AWStats | Long-standing web log reports and historical views | Batch/report orientation and dated operational workflow | Streaming stdin/file processing and pipeline-friendly outputs |
| `grep`/`awk`/`sort` | Ubiquitous and flexible for experts | Fragile nginx parsing, repeated scans, locale-dependent output, and poor portability | One-pass parsing, stable semantics, deterministic ties, and installable command |

## 4. Unique Value Proposition

Get four high-value nginx traffic signals from a local file or stdin in one
bounded, reproducible command—without deploying or operating anything.

## 5. Business Model

The project is free, open source, and self-hosted locally. There are no paid
tiers, usage fees, ads, hosted services, or telemetry. Value is measured in
incident-response time saved and reproducibility rather than revenue. Direct
CAC, LTV, and unit hosting cost are all $0 for the MVP; community adoption is
the distribution model.

## 6. Technology Stack

| Component | Technology | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Approved, portable, and sufficient for a focused streaming parser |
| CLI | Click | Mature argument validation and conventional exit behavior |
| Terminal output | Rich | Accessible colored tables with automatic non-TTY handling |
| Data models | `dataclasses` | Typed internal records without a heavy validation dependency |
| Packaging | pip-compatible `pyproject.toml` | Standard installation and console entry point |
| Tests/quality | pytest, Ruff, mypy | Fast local checks appropriate to a weekend project |

## 7. Timeline

| Period | Stage | Result |
|---|---|---|
| Friday evening | Contracts and parser fixtures | Package skeleton, frozen CLI schema, representative nginx lines |
| Saturday morning | Streaming core | One-pass parsing and all four aggregations |
| Saturday afternoon | Output adapters | Rich, JSON, and CSV renderers with deterministic ordering |
| Sunday morning | Quality and performance | Unit/integration tests and a measured 1 GB benchmark |
| Sunday afternoon | Packaging and documentation | pip installation, smoke test, and release-ready docs |

## 8. KPIs

| Metric | 1 month | 3 months | 6 months |
|---|---:|---:|---:|
| Representative 1 GB benchmark duration | < 30 s | < 27 s | < 25 s |
| Correct results on maintained parsing fixtures | 100% | 100% | 100% |
| P0 acceptance checks passing | 100% | 100% | 100% |
| Median time from install to first report | < 3 min | < 2 min | < 2 min |
| Open defects causing incorrect totals | 0 | 0 | 0 |

Performance results are valid only when the laptop profile, input generator,
file size, command, cold/warm-cache condition, and wall-clock measurement are
recorded together.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from the assumed combined format | Medium | High | State the accepted grammar, keep parser isolated, count malformed lines, and test escaping/IPv6/missing User-Agent cases |
| Exact unique User-Agent tracking consumes excessive memory | Medium | High | Enforce a configurable cardinality ceiling and exit with code 4 before unbounded growth |
| Python misses the 1 GB/30 s target | Medium | High | Benchmark early, avoid per-line regex recompilation and full-record retention, profile before optimizing |
| JSON/CSV output drifts and breaks pipelines | Low | High | Version and test a stable schema; keep diagnostics on stderr |
| Terminal color pollutes redirected output | Low | Medium | Enable color only for an interactive terminal and support `--no-color` |
| URL cardinality is pathological | Medium | Medium | Document that exact top URLs require one counter entry per distinct URL; measure peak RSS and fail clearly on memory exhaustion |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python, Click, Rich, and test tooling are open source |
| Infrastructure | $0 | Local CLI; no hosted runtime or database |
| Distribution | $0 | Source repository and pip-compatible build artifacts |
| Labor cash budget | $0 | One-weekend owner contribution; opportunity cost is not booked |
| Total MVP cash budget | **$0** | Hard constraint |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream nginx combined logs from a file or stdin | **Must** | The processing model and all analytics depend on it |
| Top 10 client IPs | **Must** | Core incident-triage signal |
| Top 10 URLs with 4xx/5xx responses | **Must** | Core error-concentration signal |
| Hourly request distribution | **Must** | Required traffic-shape signal |
| Unique User-Agent share | **Must** | Required client-diversity signal |
| Rich terminal, JSON, and CSV outputs | **Must** | Interactive and pipeline use are both explicit product contracts |
| Malformed-line diagnostics and cardinality guard | **Should** | Makes large or imperfect logs operable without changing the value proposition |
| 1 GB repeatable performance harness | **Should** | Required to prove the performance target, but not part of normal CLI use |
| Configurable top-N ranking | **Could** | Useful extension; fixed top 10 is sufficient for MVP |
| Additional custom nginx log formats | **Could** | Broadens adoption after the combined-format parser is stable |
| Database, HTTP API, authentication, cloud, Kubernetes | **Won't** | Explicitly excluded; they add state and operations without helping local triage |

### RICE Scoring (Must + Should)

Scores use `(Reach × Impact × Confidence) / Effort`, with confidence expressed
as a decimal. Estimates are planning assumptions for the first month.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming file/stdin parser | 10 | 5 | 90% | 1.0 | 45.0 |
| Top 10 client IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Top 10 error URLs | 10 | 5 | 95% | 0.35 | 135.7 |
| Hourly request distribution | 8 | 4 | 95% | 0.25 | 121.6 |
| Unique User-Agent share | 7 | 3 | 85% | 0.35 | 51.0 |
| Rich/JSON/CSV outputs | 10 | 5 | 85% | 0.8 | 53.1 |
| Malformed-line and cardinality safeguards | 8 | 4 | 80% | 0.6 | 42.7 |
| Repeatable 1 GB benchmark | 8 | 4 | 75% | 0.6 | 40.0 |

Implementation remains dependency-aware: the parser precedes the apparently
higher-scoring aggregations because every metric consumes its records. Within
that constraint, delivery follows descending value.

## 12. Definition of Done

A product feature is Done only when:

- [ ] Its behavior and edge cases match `PRD.md` acceptance criteria.
- [ ] Python 3.11 code passes formatting, linting, typing, and unit tests.
- [ ] Cross-format integration tests pass for terminal, JSON, and CSV output.
- [ ] The complete exit-code contract `0/1/2/3/4` is exercised.
- [ ] Coverage is at least 90% for the parser, aggregation, and serialization modules.
- [ ] No known Critical or High security issue remains.
- [ ] Documentation and pip installation instructions are current.
- [ ] The 1 GB performance target is measured on a documented laptop profile.
- [ ] The exact candidate is accepted through the project's current Idea to Deploy verification route.

## 13. Kill Criteria

Re-scope or stop the MVP if a representative combined-format 1 GB file cannot
be processed under 30 seconds after profiling and bounded optimization; if
exact required metrics cannot be produced without unbounded memory under the
documented limits; or if the weekend scope expands to require a service,
database, or hosted infrastructure.

Architecture details are authoritative in `PROJECT_ARCHITECTURE.md`; product
acceptance is authoritative in `PRD.md`; execution sequencing is defined in
`IMPLEMENTATION_PLAN.md`.
