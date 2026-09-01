# Strategic Plan: nginx-stream-insights

## 1. Product Idea

`nginx-stream-insights` is a local, installable Python 3.11 CLI for DevOps and SRE engineers. It reads nginx access logs as a stream and produces an immediate operational summary: top 10 client IPs, top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. Rich colored terminal text is the default; stable JSON and CSV modes make the same results usable in pipelines.

The MVP is intentionally local and stateless. It has no authentication, database, HTTP API, server process, cloud dependency, or Kubernetes footprint. The delivery constraint is one weekend at a cash budget of $0.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call operator | SRE handling an incident | Needs quick traffic and error concentration signals without deploying a stack | One command summarizes a local file or stdin with readable terminal output |
| Platform engineer | DevOps engineer maintaining hosts and pipelines | Needs deterministic machine-readable output for shell automation | `--json` and `--csv` expose stable schemas and meaningful exit codes |
| Service owner | Backend engineer investigating nginx behavior | Needs to see error-heavy URLs and traffic timing on a laptop | Streaming aggregation provides top error URLs and hourly percentages without loading the log into memory |

## 3. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | Product differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Larger feature surface; interactive/HTML workflow can be more than an incident needs | Narrow, script-friendly four-metric summary with explicit JSON/CSV contracts |
| Logstash / Elastic / Kibana | Powerful ingestion, search, dashboards, retention | Requires services, storage, setup, and operational cost | Zero-service local execution and no retained data |
| AWStats | Established historical web analytics | Batch-oriented, dated workflow, and generated reports | Immediate streaming CLI output designed for current DevOps practice |
| `grep` / `awk` | Already installed, composable, fast for simple questions | Fragile parsing, repeated scans, inconsistent metrics, difficult JSON/CSV | One validated parse and aggregation pass with stable semantics |

## 4. Unique Value Proposition

Get the four nginx incident signals most often needed from a gigabyte-scale log in one local, pipeline-safe command, without deploying or operating anything.

## 5. Business Model

The project is open source and free. There is no monetization requirement, paid service, telemetry, or hosted tier. Value is measured in operator time saved and reproducibility rather than revenue; acquisition is through source distribution and `pip` installation, so direct CAC and infrastructure cost are $0.

## 6. Technology Stack

| Component | Technology | Why |
|---|---|---|
| Runtime | Python 3.11 | Approved, portable, productive for a one-weekend CLI |
| CLI | Click | Mature argument parsing, help text, validation, and exit handling |
| Terminal presentation | Rich | Accessible color, tables, and automatic no-color behavior for non-TTY output |
| Domain records | `dataclasses` | Typed, lightweight records with no extra runtime dependency |
| Packaging | `pyproject.toml` + pip | Standard installable console entry point |
| Tests | pytest | Focused parser, aggregation, output-contract, and performance regression tests |

## 7. Timeline

| Block | Focus | Result |
|---|---|---|
| Saturday morning | Packaging, contracts, parser | Installable skeleton and streaming combined-log parser |
| Saturday afternoon | Aggregation | Four required metrics computed in one pass |
| Sunday morning | Terminal, JSON, CSV | Stable human and pipeline output modes |
| Sunday afternoon | Tests, benchmark, docs | Verified 1 GB performance target and release-ready package |

## 8. KPIs

| Metric | Launch target | First month target | Guardrail |
|---|---:|---:|---:|
| Processing time for a representative 1 GB log | <30 seconds | <30 seconds on documented reference laptop | Benchmark must include wall time and peak RSS |
| Valid-line parse accuracy on fixtures | 100% | 100% | Malformed lines are counted, never silently treated as valid |
| Peak memory, excluding exact unique-UA storage | Bounded by fixed counters/top-k state | No growth proportional to request count | Cardinality exhaustion exits with code 4 |
| Output contract stability | All golden tests pass | No unannounced schema changes | JSON/CSV changes require PRD and version update |
| Time to first useful report | One command | Under 60 seconds including installation for a prepared environment | No service setup |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from the supported combined format | High | High | Declare the accepted format, reject/count malformed lines, and defer configurable formats |
| Python misses the 1 GB / 30 second target | Medium | High | One pass, precompiled parsing, no per-line Rich work, benchmark early, and profile before adding features |
| Exact unique User-Agent cardinality consumes excessive memory | Medium | High | Enforce a configurable hard cardinality ceiling and exit 4 rather than degrade silently |
| CSV representation of multiple result sections confuses consumers | Medium | Medium | Use a normalized row schema with a `metric` discriminator and golden fixtures |
| Terminal color pollutes redirected output | Low | Medium | Enable color only for TTY by default and support `--no-color` |
| Ambiguous timezone/hour semantics mislead operators | Medium | Medium | Use the hour encoded in each valid log timestamp and document the 24 fixed buckets |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python, Click, Rich, and pytest are open source |
| Infrastructure | $0 | Local execution; no server, database, cloud, or Kubernetes |
| Distribution | $0 | Source and local `pip` installation; public index publication is optional |
| Labor | One weekend | Approved delivery envelope; no cash budget |
| Total cash budget | **$0** | Scope must contract rather than add paid infrastructure |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream a file or stdin in one pass | **Must** | Foundation for local and pipeline usage |
| Top 10 client IPs | **Must** | Required traffic-concentration signal |
| Top 10 URLs by 4xx/5xx count | **Must** | Required error hotspot signal |
| Hourly request distribution as `100 × hourly_request_count / total_valid_requests` | **Must** | Required normalized time distribution |
| Unique User-Agent share | **Must** | Required client-diversity signal |
| Colored terminal output | **Must** | Required default experience |
| JSON and CSV output | **Must** | Required pipeline integration |
| Malformed-line summary and stable exit codes | **Must** | Prevents silent data-quality failures |
| Gzip input | **Should** | Common operational convenience but shell decompression can cover MVP |
| Custom top-N | **Could** | Useful flexibility, but the brief fixes top 10 |
| Custom nginx log formats | **Could** | Broadens adoption but risks the weekend and parser correctness |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Contradicts the approved local stateless CLI scope |

### RICE Scoring (Must + Should)

| Feature | Reach (1–10) | Impact (1–5) | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Stream file/stdin + parse validation | 10 | 5 | 90% | 0.60 | 75.0 |
| Top IP aggregation | 9 | 4 | 95% | 0.20 | 171.0 |
| Top error-URL aggregation | 10 | 5 | 95% | 0.25 | 190.0 |
| Hourly percentage distribution | 8 | 4 | 95% | 0.15 | 202.7 |
| Unique User-Agent share + ceiling | 8 | 4 | 80% | 0.25 | 102.4 |
| Terminal presentation | 9 | 3 | 90% | 0.30 | 81.0 |
| JSON and CSV contracts | 8 | 5 | 90% | 0.45 | 80.0 |
| Malformed-line summary + exit codes | 9 | 5 | 90% | 0.25 | 162.0 |
| Gzip input | 5 | 2 | 70% | 0.25 | 28.0 |

Dependency order overrides raw RICE where necessary: parsing precedes every aggregation, aggregation precedes renderers, and the performance benchmark gates release.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and acceptance criteria are reflected in `PRD.md`.
- [ ] Python 3.11 code is formatted and passes static checks.
- [ ] Unit and integration tests pass with at least 90% statement coverage for product modules.
- [ ] Golden tests pass for terminal (color disabled), JSON, and CSV contracts.
- [ ] The representative 1 GB benchmark completes in under 30 seconds on the documented laptop and records peak RSS.
- [ ] Exit codes `0/1/2/3/4` are exercised, including unique-cardinality exhaustion for code 4.
- [ ] No known Critical or High security issues remain.
- [ ] User-facing documentation and help text are current.
- [ ] The package installs through pip in a clean Python 3.11 environment.

## 13. Strategic Boundaries and Kill Criteria

Proceed only while the four required metrics remain correct, the package remains local and stateless, and the benchmark is attainable within a weekend. Stop or reduce scope if Python cannot process the representative 1 GB fixture under 30 seconds after profiling, exact User-Agent tracking cannot be safely bounded, or stable pipeline schemas cannot be delivered without sacrificing parser correctness.

`PROJECT_ARCHITECTURE.md` is the technical source of truth; `PRD.md` defines observable behavior; `IMPLEMENTATION_PLAN.md` sequences delivery.
