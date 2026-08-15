# Strategic Plan: Nginx Stream Analytics CLI

## 1. Product Idea

Nginx Stream Analytics is a local, installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx combined access logs from a file or standard input in one pass and reports the top 10 client IPs, top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. Human-readable colored terminal output is the default; JSON and CSV make the same results usable in pipelines.

The product is deliberately local and stateless. It has no authentication, database, server, HTTP API, cloud dependency, or Kubernetes footprint. The target is to process a 1 GB log in under 30 seconds on a representative laptop.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Incident responder | Needs a fast traffic/error overview without uploading sensitive logs | One local command, streaming input, actionable terminal summary |
| DevOps engineer | Platform operator | Needs composable results in shell automation | Stable `--json` and `--csv` schemas and documented exit codes |
| Systems engineer | Nginx operator | Finds ad-hoc `grep`/`awk` pipelines fragile and hard to repeat | Tested combined-log parsing and four consistent metrics |

## 3. Problem and Value Proposition

During an incident, existing choices are often too large, too interactive, too dated, or too brittle. The product provides the smallest repeatable path from a local nginx log to the four signals most useful for first-pass triage.

**Value proposition:** get a pipeline-friendly nginx traffic and error summary from gigabyte-scale local logs in under 30 seconds, without deploying or operating another service.

## 4. Competitive Analysis

| Alternative | Strength | Weakness for this use case | Differentiation |
|---|---|---|---|
| GoAccess | Fast, mature, rich interactive reports | More UI/reporting surface than a four-metric pipeline tool needs | Narrow, predictable output contracts in text, JSON, and CSV |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, search, and dashboards | Infrastructure, persistence, and operational cost are disproportionate | Zero-service, zero-database local execution |
| AWStats | Established historical web analytics | Batch-oriented, dated workflow, generated report focus | Immediate streaming analysis and modern pipeline formats |
| `grep`/`awk` | Already installed and flexible | Quoting, log parsing, malformed lines, and metric consistency are fragile | One tested parser and stable semantics across all metrics |

## 5. Business Model and Delivery Economics

This is a $0-budget open-source utility. There is no paid tier or hosted service in scope. Value is measured through adoption, reliability, and reduced incident-triage time rather than revenue, CAC, or LTV. Distribution uses a standard Python package installable with pip; maintainers absorb only volunteer time.

## 6. Technology Strategy

| Component | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Approved stack, broad availability, adequate streaming throughput with disciplined parsing |
| CLI | Click | Stable option validation, help, stdin/file handling, and exit behavior |
| Terminal UI | Rich | Accessible colored tables with automatic no-color behavior for non-TTY output |
| Domain model | `dataclasses` | Typed, low-overhead internal records and result contracts |
| Packaging | pip-compatible `pyproject.toml` | Familiar install path and console-script entry point |
| Processing | Single-process, single-pass streaming | Fits the four aggregations and avoids deployment or concurrency complexity |

## 7. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream nginx combined logs from file or stdin | **Must** | The product cannot analyze realistic logs without bounded-memory input |
| Top 10 client IPs by valid request count | **Must** | Core incident-triage signal |
| Top 10 URLs by combined 4xx/5xx count | **Must** | Core error-localization signal |
| Hourly request distribution as percentages | **Must** | Core traffic-shape signal |
| Unique User-Agent share | **Must** | Core client-diversity signal |
| Colored terminal output | **Must** | Approved default user experience |
| JSON output | **Must** | Required pipeline contract |
| CSV output | **Must** | Required pipeline contract |
| Malformed-line accounting and strict unique-cardinality cap | **Should** | Makes results trustworthy and memory failure explicit |
| Gzip input | **Could** | Useful polish but not required for the one-weekend MVP |
| Custom nginx log formats | **Could** | Broadens adoption after the combined-format contract is stable |
| Authentication, database, HTTP API, cloud, Kubernetes | **Won't** | Contradicts the approved local stateless scope |

### RICE Scoring (Must and Should)

Confidence is expressed as a decimal in the calculation `Reach × Impact × Confidence / Effort`.

| Feature group | Reach (1–10) | Impact (1–5) | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming parser and input handling | 10 | 5 | 90% | 1.0 | 45.0 |
| Four core aggregations | 10 | 5 | 90% | 1.5 | 30.0 |
| JSON output | 8 | 4 | 90% | 0.5 | 57.6 |
| Colored terminal output | 9 | 3 | 90% | 0.5 | 48.6 |
| CSV output | 7 | 3 | 90% | 0.5 | 37.8 |
| Malformed-line and cardinality safeguards | 8 | 4 | 80% | 0.75 | 34.1 |

Dependency order takes precedence where a high-scoring renderer depends on the parser and aggregation model. Within each dependency layer, implementation follows descending RICE score.

## 8. One-Weekend Timeline

| Block | Outcome |
|---|---|
| Saturday morning | Package skeleton, CLI contract, fixture corpus, streaming parser |
| Saturday afternoon | Aggregations, malformed-line behavior, exact cardinality cap |
| Sunday morning | Text, JSON, and CSV renderers plus end-to-end tests |
| Sunday afternoon | 1 GB benchmark, documentation, packaging smoke test, release candidate |

## 9. KPIs

| Metric | Release target | First-month signal |
|---|---:|---:|
| Performance | 1 GB in <30 seconds on the documented laptop profile | Target maintained across releases |
| Correctness | 100% of golden fixtures match expected metrics | No known P0 correctness defect |
| Memory behavior | Bounded except documented unique-value sets; exhaustion returns 4 | No uncontrolled OOM in benchmark corpus |
| Installability | Clean Python 3.11 environment installs and runs help command | Successful install reports from two OS families |
| Pipeline stability | JSON/CSV schemas covered by snapshot/contract tests | No accidental schema break in patch releases |

## 10. Budget

| Item | Cost | Notes |
|---|---:|---|
| Runtime and libraries | $0 | Python, Click, Rich, and test tools are open source |
| Hosting and infrastructure | $0 | No hosted runtime or database |
| Distribution | $0 | Source repository and package index publishing are free |
| Delivery labor | One weekend | Maintainer time; no cash spend |

## 11. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Python parsing misses the 1 GB/30 s target | Medium | High | Benchmark early; avoid regex backtracking and per-line object churn; profile before optimizing |
| Malformed or variant log lines skew results | High | Medium | Define combined-format grammar, skip-and-count malformed lines, offer strict failure mode |
| Exact unique User-Agent tracking exhausts memory | Medium | High | Enforce a configurable hard cardinality limit and exit with code 4 rather than approximating silently |
| JSON/CSV interpretations drift from terminal output | Medium | High | Render all formats from one immutable summary model and add cross-format contract tests |
| Ties produce nondeterministic top-10 results | Medium | Medium | Specify count-descending, key-ascending ordering |
| Scope expands toward a monitoring platform | Medium | High | Preserve explicit Won't list and CLI-only architecture decision |

## 12. Definition of Done

A release feature is Done when:

- [ ] The behavior and acceptance criteria are present in `PRD.md`.
- [ ] Code targets Python 3.11 and passes formatting, linting, type, unit, and integration checks.
- [ ] P0 behavior has automated tests; overall line coverage is at least 90%.
- [ ] The 1 GB benchmark completes in under 30 seconds on the documented laptop profile.
- [ ] Text, JSON, and CSV outputs agree on the same summary model.
- [ ] Packaging installs in a clean environment and exposes the console command.
- [ ] Documentation is current and no Critical or High security issue is known.
- [ ] The exact candidate satisfies the project verification contract before acceptance.

## 13. Product Kill Criteria

Re-scope or stop the MVP if a representative 1 GB combined log cannot meet the performance target after profiling, if exact unique-cardinality tracking cannot fail safely under a documented cap, or if the four output metrics cannot remain consistent across all three formats. Do not introduce a server, database, or distributed architecture to rescue this deliberately local product.

## 14. Related Documents

Technical decisions are in `PROJECT_ARCHITECTURE.md`; behavior is authoritative in `PRD.md`; delivery sequencing is in `IMPLEMENTATION_PLAN.md`.
