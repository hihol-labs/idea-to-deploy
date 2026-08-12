# Strategic Plan: nginx-log-report

## 1. Product Idea

`nginx-log-report` is an installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs once, without loading the file into memory, and reports the top 10 client IPs, the top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agent values. Rich terminal output is the default; deterministic JSON and CSV modes support pipelines.

The MVP is a local, stateless utility delivered over one weekend. It has no authentication, database, HTTP API, server process, cloud dependency, or Kubernetes deployment.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call engineer | SRE responding to an incident | Needs a fast first view of a large access log without provisioning services | One command produces incident-oriented summaries locally |
| Platform engineer | DevOps engineer maintaining nginx hosts | Shell one-liners are brittle and hard to standardize | Stable parsing, output schemas, and exit codes make analysis repeatable |
| Security-minded operator | Engineer investigating abuse or scanning | Needs high-volume IP and error-path visibility without exporting logs | Streaming local processing keeps sensitive logs on the laptop |

## 3. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | Our distinction |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Broader UI and configuration surface than a four-metric pipeline tool | Smaller contract, pip installation, deterministic JSON/CSV |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, storage, and dashboards | Operationally expensive; persistent infrastructure violates local/stateless constraints | Zero-service, zero-budget, single-command analysis |
| AWStats | Established historical web analytics | Report-generation model and dated workflow are less suitable for ad hoc incident analysis | Immediate terminal-first output and pipeline formats |
| `grep`/`awk`/`sort` | Ubiquitous and flexible | Format-sensitive, repeated passes, locale-dependent output, poor structured export | Tested one-pass parser with stable semantics and exit codes |

## 4. Unique Value Proposition

Incident-ready nginx log summaries from a single local, streaming command—without standing up infrastructure or giving up machine-readable output.

## 5. Business Model

The project is open source and free to use. There is no monetization in the MVP; its value is reduced incident-response time and a reusable reference tool. Development and operating budget are both $0, excluding the contributor's one-weekend time.

## 6. Technology Stack

| Component | Technology | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Approved, portable, modern typing and performance baseline |
| CLI | Click | Reliable argument parsing, help text, and usage-error handling |
| Terminal UI | Rich | Accessible colored tables with automatic terminal capability handling |
| Domain models | `dataclasses` | Lightweight typed records without a framework |
| Packaging | `pyproject.toml` + pip | Standard installable console entry point |
| Testing | pytest | Small, readable unit/integration/performance test suite |

See `PROJECT_ARCHITECTURE.md` for component boundaries and data contracts.

## 7. Timeline

| Window | Stage | Result |
|---|---|---|
| Saturday morning | Package, parser, contracts | Installable CLI skeleton and verified line parser |
| Saturday afternoon | Streaming aggregation | Four metrics calculated in one pass with bounded non-cardinality state |
| Sunday morning | Renderers and error semantics | Rich, JSON, and CSV outputs plus `0/1/2/3/4` exit contract |
| Sunday afternoon | Quality and packaging | Tests, 1 GB benchmark, documentation, and distributable wheel |

## 8. KPIs

| Metric | Release target | Month 1 | Month 3 |
|---|---:|---:|---:|
| Processing time for a representative 1 GB log on the reference laptop | < 30 s | < 30 s | < 25 s |
| Peak resident memory on the 1 GB benchmark before unique-UA exhaustion | ≤ 512 MiB | ≤ 512 MiB | ≤ 384 MiB |
| Correctness on maintained parser/aggregation fixtures | 100% | 100% | 100% |
| Installation-to-first-report time | < 2 min | < 2 min | < 1 min |
| Open correctness defects rated high severity | 0 | 0 | 0 |

The reference laptop model, OS, filesystem cache state, fixture generator, and timing command must be recorded with benchmark results so the performance KPI is reproducible.

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from the supported grammar | High | High | Define supported Combined/Common formats, expose `--format`, count malformed lines, and fail fast in strict mode |
| Exact unique User-Agent cardinality can consume unbounded memory | Medium | High | Enforce a configurable hard cap and exit `4` before memory becomes unsafe |
| Python misses the 1 GB/30 s target | Medium | High | Benchmark early; use compiled regex once, local variables in the hot loop, one pass, and no per-record retention |
| CSV semantics become ambiguous across metric types | Medium | Medium | Use one documented long-form schema and golden-file tests |
| Colored output contaminates pipelines | Low | Medium | Color only for terminal mode; structured modes never emit ANSI; diagnostics use stderr |
| IPs and User-Agents may be sensitive operational data | Medium | Medium | Process locally, store nothing, avoid raw-line diagnostics by default |

## 10. Budget

| Item | One-time | Monthly | Comment |
|---|---:|---:|---|
| Open-source dependencies | $0 | $0 | Python, Click, Rich, pytest |
| Hosting/infrastructure | $0 | $0 | None; local CLI only |
| Database/observability services | $0 | $0 | Explicitly excluded |
| Distribution | $0 | $0 | Local wheel or public package index |
| Contributor time | One weekend | $0 cash | Approved delivery constraint |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Streaming Combined/Common log parsing | **Must** | Every metric depends on valid records without whole-file loading |
| Top 10 client IPs | **Must** | Core incident triage question |
| Top 10 error URLs for 4xx/5xx | **Must** | Core reliability diagnostic |
| Hourly request percentages | **Must** | Core traffic-shape diagnostic |
| Exact unique User-Agent share with safety cap | **Must** | Required metric with explicit resource protection |
| Rich terminal, JSON, and CSV rendering | **Must** | Required human and pipeline interfaces |
| Deterministic exit codes and strict parsing | **Must** | Required for automation and trustworthy failure handling |
| Compressed `.gz` input | **Should** | Common archive format, but decompression is not required for MVP value |
| Custom nginx `log_format` grammar | **Should** | Broadens compatibility but substantially expands parser scope |
| Live `tail -F` behavior | **Could** | Useful operational polish; finite stream/stdin processing already meets MVP |
| Persistent history/dashboard | **Won't** | Conflicts with stateless, zero-infrastructure scope |
| Auth, HTTP API, cloud, Kubernetes | **Won't** | Explicitly excluded and unnecessary for a local CLI |

### RICE Scoring (Must and Should)

Scores use `(Reach × Impact × Confidence) / Effort`, with confidence expressed as a decimal. They order delivery but do not weaken dependencies.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Top 10 client IPs | 9 | 4 | 90% | 0.25 | 129.6 |
| Top 10 error URLs | 9 | 5 | 90% | 0.35 | 115.7 |
| Hourly request percentages | 8 | 4 | 95% | 0.30 | 101.3 |
| Deterministic exit codes and strict parsing | 8 | 4 | 90% | 0.35 | 82.3 |
| Rich terminal, JSON, and CSV rendering | 10 | 4 | 90% | 0.50 | 72.0 |
| Streaming Combined/Common parsing | 10 | 5 | 80% | 0.75 | 53.3 |
| Exact unique User-Agent share with safety cap | 7 | 3 | 80% | 0.40 | 42.0 |
| Compressed `.gz` input | 5 | 2 | 75% | 0.40 | 18.8 |
| Custom nginx `log_format` grammar | 4 | 3 | 50% | 1.50 | 4.0 |

Implementation begins with the parser because it is an architectural dependency, then follows descending user value within that dependency boundary. Should items remain post-MVP unless the Must scope is complete.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and acceptance criteria are defined in `PRD.md`.
- [ ] Code runs on Python 3.11 and formatting, linting, and type checks pass.
- [ ] Unit and integration tests pass with at least 90% line coverage for the package.
- [ ] A reviewer accepts the change; self-review is labeled when no independent reviewer is available.
- [ ] User-facing documentation and output schema examples are current.
- [ ] No known critical or high-severity security issue remains.
- [ ] The exact release candidate passes the representative 1 GB benchmark in under 30 seconds on the recorded reference laptop.
- [ ] The wheel installs in a clean environment and the console command completes a smoke test.

## 13. Release and Kill Criteria

Release the MVP only when all Must features and the Definition of Done pass. Re-scope or stop the weekend release if the one-pass design cannot process the reference 1 GB fixture in under 30 seconds, exact UA tracking cannot remain within the declared safety bound, or structured output cannot remain backward-stable without redesign. Do not add infrastructure to rescue the MVP; revisit the product premise instead.

