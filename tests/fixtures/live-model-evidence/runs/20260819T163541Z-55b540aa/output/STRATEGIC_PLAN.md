# Strategic Plan: Nginx Insight

## 1. Product Idea

Nginx Insight is a local, installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream and produces four immediately useful operational views: the top 10 client IPs, top 10 URLs producing 4xx/5xx responses, request distribution by hour, and the share of unique User-Agents. Rich-colored terminal output serves interactive diagnosis, while JSON and CSV support automation.

The MVP is deliberately narrow: one local process, no persisted state, and no service to operate. Its value is a fast answer from a large log without first deploying an analytics stack.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Investigates an incident from a host or downloaded log | Needs a useful traffic/error summary in minutes | One command streams a file or stdin and prints ranked metrics |
| DevOps engineer | Builds shell-based operational pipelines | Interactive-only tools are hard to compose | Stable JSON and CSV schemas, deterministic sorting, meaningful exit codes |
| Platform engineer | Supports constrained/offline environments | Cannot justify or deploy a database/dashboard stack for an ad-hoc question | Local pip install, $0 runtime, no server or credentials |

## 3. Competitive Analysis

| Alternative | What it does well | Weakness for this use case | Nginx Insight differentiation |
|---|---|---|---|
| GoAccess | Mature real-time terminal and HTML analytics | Broader UI/config surface than the four required metrics; native binary deployment may be undesirable in Python environments | Minimal Python CLI with pipeline-first JSON/CSV contracts |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, retention, search, and dashboards | Operationally heavy, persistent, resource-intensive, and far beyond a weekend/$0 local tool | No services, database, indexing cluster, or ongoing administration |
| AWStats | Established historical web analytics reports | Report-oriented and commonly persistence/config heavy; less natural for stdin pipelines | Immediate streaming summary with machine-readable output |
| grep/awk/sort/uniq | Ubiquitous, flexible, zero install | Brittle nginx parsing, repeated passes, difficult combined metrics, and inconsistent error handling | One pass, documented semantics, bounded state, tested output schemas |

## 4. Unique Value Proposition

Get the four nginx incident metrics an SRE most often needs from a gigabyte-scale log in one local, pipeline-safe command—without deploying or maintaining an analytics service.

## 5. Business Model

Nginx Insight is open-source and free. There is no monetization in the MVP, no hosted tier, and no telemetry. The success model is utility and adoption: reproducible incident analysis at zero infrastructure cost. Any future sponsorship or support offering is outside this blueprint and cannot add a runtime dependency or data collection without a new product decision.

## 6. Technology Stack

| Component | Choice | Why |
|---|---|---|
| Runtime | Python 3.11 | Approved, widely available in DevOps environments, fast enough with line streaming and precompiled parsing |
| CLI | Click | Stable option parsing, help text, validation, and exit behavior |
| Terminal UI | Rich | Accessible tables, progress-free streaming, and automatic color handling |
| Domain model | Standard-library dataclasses | Typed, dependency-light aggregation and report records |
| Packaging | `pyproject.toml` + pip console script | Standard install path and isolated CLI entry point |
| Tests/quality | pytest, Ruff, mypy | Fast local verification for parsing, output contracts, and typing |

## 7. Timeline

| Window | Stage | Result |
|---|---|---|
| Saturday morning | Package skeleton, domain contracts, parser | Installable command and validated combined-log records |
| Saturday afternoon | Streaming aggregation | Correct top lists, hourly percentages, and unique-UA share |
| Sunday morning | Rich, JSON, and CSV renderers | Stable human and pipeline outputs with exit-code contract |
| Sunday afternoon | Performance, tests, documentation | 1 GB benchmark evidence, distributable package, usage guide |

## 8. KPIs

| Metric | Launch target | Month 1 | Month 3 |
|---|---:|---:|---:|
| Processing time for a representative 1 GB combined log on the reference laptop | <30 s | <30 s | <25 s if profiling supports it |
| Peak resident memory on the representative dataset | <512 MB | <512 MB | <384 MB where cardinality permits |
| P0 acceptance tests passing | 100% | 100% | 100% |
| Valid-line agreement against a fixture oracle | 100% | 100% | 100% |
| Pipeline formats with backward-compatible documented schema | 2 | 2 | 2 |

The reference laptop, dataset generator, Python version, warm-up policy, and timing command must be recorded with benchmark results; the target is not claimed from design alone.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Python parsing misses the 1 GB/30 s target | Medium | High | Avoid per-line regex recompilation and object churn; benchmark early; profile before optimizing |
| nginx formats differ from the supported combined format | High | Medium | State the supported grammar, count malformed lines, offer strict/non-strict modes, defer custom format DSL |
| Adversarial unique cardinality exhausts memory | Medium | High | Enforce a configurable unique-cardinality ceiling and exit with code 4 rather than silently approximate |
| JSON/CSV schema drift breaks pipelines | Medium | High | Version JSON schema, define CSV columns, golden-test both formats |
| Ambiguous timestamps produce incorrect hourly buckets | Medium | Medium | Bucket by the `00`–`23` hour encoded in each valid nginx timestamp and document it explicitly |
| Terminal color contaminates redirected output | Low | Medium | Color only the Rich text renderer and disable it automatically when appropriate; JSON/CSV never contain ANSI escapes |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Development tooling | $0 | Python and selected dependencies are open source |
| Runtime infrastructure | $0 | Local CLI; no database, server, or cloud resources |
| Distribution | $0 | Source repository and local/wheel installation; public index publication is optional |
| Weekend labor | One weekend | Fixed approved delivery window; not represented as cash spend |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream combined nginx logs from files and stdin | **Must** | Without ingestion there is no product |
| Top 10 client IPs | **Must** | Core incident and abuse signal |
| Top 10 URLs by 4xx/5xx count | **Must** | Core failure triage signal |
| Hourly request distribution | **Must** | Core traffic-shape signal |
| Exact unique User-Agent share | **Must** | Required client-diversity signal |
| Rich colored terminal report | **Must** | Approved default interactive experience |
| Stable JSON and CSV outputs | **Must** | Required pipeline integration |
| Strict parsing mode and complete exit codes | **Should** | Important for automation correctness; non-strict analysis can still provide MVP value |
| Multiple input files in one aggregate report | **Should** | Common operational workflow, but stdin plus one file remains useful |
| Custom nginx `log_format` grammar | **Could** | Broadens compatibility but threatens weekend scope |
| Configurable top-N | **Could** | Useful polish; requirement is fixed at 10 |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Contradicts the approved local stateless CLI boundary |

### RICE Scoring (Must + Should)

RICE uses `(Reach × Impact × Confidence) / Effort`, with confidence as a decimal. Scores guide implementation order but dependencies may move packaging/parser work earlier.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Stream files/stdin and parse combined logs | 10 | 5 | 100% | 0.75 | 66.7 |
| Rich terminal report | 9 | 3 | 90% | 0.5 | 48.6 |
| Top 10 client IPs | 9 | 4 | 95% | 0.75 | 45.6 |
| Top 10 error URLs | 9 | 5 | 95% | 1.0 | 42.8 |
| Hourly request distribution | 8 | 4 | 95% | 0.75 | 40.5 |
| JSON and CSV outputs | 8 | 4 | 90% | 0.75 | 38.4 |
| Exact unique User-Agent share | 7 | 3 | 90% | 0.75 | 25.2 |
| Strict mode and exit codes | 7 | 4 | 95% | 1.25 | 21.3 |
| Multiple input files | 6 | 3 | 85% | 0.75 | 20.4 |

Implementation order is dependency-aware: ingestion and parsing first, then aggregators, then renderers and operational hardening.

## 12. Definition of Done

A feature is done when:

- [ ] The behavior and acceptance criteria in `PRD.md` are implemented without expanding excluded scope.
- [ ] Python 3.11 code installs through pip and the console command starts.
- [ ] Ruff and mypy pass with no unexplained suppressions.
- [ ] Unit and integration tests pass; core parser/aggregation coverage is at least 90%.
- [ ] Golden tests prove terminal semantics and exact JSON/CSV schemas.
- [ ] The representative 1 GB benchmark completes in under 30 seconds on the recorded reference laptop.
- [ ] No known Critical or High security issue remains.
- [ ] User-facing documentation and `--help` match the implementation.
- [ ] Exit codes remain `0/1/2/3/4`: success, processing/data error, CLI usage error, input/output error, and unique-cardinality exhaustion respectively.

## 13. Strategic Guardrails and Kill Criteria

- Stop or reduce scope if the one-pass implementation cannot approach the 30-second target after profiling; do not add a server or persistent index to rescue it.
- Do not ship pipeline formats until golden fixtures prove deterministic ordering and ANSI-free output.
- Do not silently approximate unique counts. If the configured ceiling is exceeded, fail with exit code 4 and explain remediation.
- Revisit the product thesis if representative users consistently require retained history, dashboards, or arbitrary log-format support; those are separate products, not hidden MVP work.

See `PROJECT_ARCHITECTURE.md` for the technical contract, `PRD.md` for accepted behavior, and `IMPLEMENTATION_PLAN.md` for the weekend execution sequence.
