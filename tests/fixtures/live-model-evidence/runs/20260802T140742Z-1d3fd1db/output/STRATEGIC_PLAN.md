# Strategic Plan: nginx-log-report

## 1. Idea Overview

`nginx-log-report` is a local, installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream and produces four immediately useful operational views: top client IPs, top URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agent values. Human-readable colored terminal output is the default; stable JSON and CSV contracts support automation.

The MVP is deliberately narrow: one process, bounded memory, no service to operate, and no data retained after the command exits. It must process a 1 GB log in under 30 seconds on a representative laptop.

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| On-call SRE | Incident responder | Needs a fast first view without uploading sensitive logs or starting a stack | Runs one local command and receives the key traffic/error distributions |
| DevOps engineer | Platform operator | Needs pipeline-friendly summaries in scripts and CI jobs | Uses deterministic `--json` or `--csv` output and meaningful exit codes |
| Backend engineer | Service owner | Needs to identify noisy clients and failing routes during debugging | Gets top-10 IP and error-URL counts while scanning the source once |

## 3. Competitive Analysis

| Alternative | What it does | Weaknesses for this use case | Our distinction |
|---|---|---|---|
| GoAccess | Rich terminal and HTML nginx analytics | Broader UI/configuration surface; HTML reporting is unnecessary for quick pipelines | Smaller fixed report contract and first-class JSON/CSV modes |
| Logstash + Elasticsearch + Kibana | Centralized ingestion, search, dashboards, retention | Significant setup, resources, and operations; violates local/stateless/$0 constraints | Zero-service, local, one-shot processing |
| AWStats | Persistent web statistics and HTML reports | Legacy-oriented workflow, stored state, slower feedback loop | Modern pip-installed CLI with streaming summaries |
| `grep`/`awk`/`sort` | Flexible shell-native log processing | Quoting and format handling are fragile; multiple metrics often require multiple passes | One parse path, one pass, documented schemas and errors |

## 4. Unique Value Proposition

Get the four nginx traffic signals most useful during triage from a gigabyte-scale local log in one bounded-memory pass, with no service, database, or configuration stack.

## 5. Business Model

The project is open source and free to use. There are no paid tiers, hosted services, tracking, or monetization requirements for the MVP. Value is measured through engineering time saved and adoption, not revenue. Maintenance must remain compatible with a $0 infrastructure budget; optional community distribution through PyPI and source hosting uses free tiers.

## 6. Technology Stack

| Component | Technology | Why |
|---|---|---|
| Runtime | Python 3.11 | Approved, portable, mature standard-library streaming I/O |
| CLI | Click | Clear option validation, help text, and exit handling |
| Terminal presentation | Rich | Accessible tables, color, and automatic terminal behavior |
| Domain models | `dataclasses` | Explicit lightweight records without a validation framework |
| Packaging | `pyproject.toml` + pip | Standard installable CLI workflow |
| Testing | pytest | Fast unit/integration tests and fixture support |

## 7. Timeline

| Window | Stage | Result |
|---|---|---|
| Saturday morning | Package, CLI, parser | Installable command parses representative combined logs |
| Saturday afternoon | Streaming aggregation | All four metrics computed in one bounded-memory pass |
| Sunday morning | Text/JSON/CSV renderers | Stable human and pipeline output contracts |
| Sunday afternoon | Performance, tests, docs | 1 GB benchmark evidence, packaging smoke test, release-ready MVP |

## 8. KPIs

| Metric | MVP / first month | 3 months | 6 months |
|---|---:|---:|---:|
| Processing time for 1 GB representative log | <30 s | <25 s | <20 s where profiling supports it |
| Peak resident memory for 1 GB representative log | <256 MB | <192 MB | <128 MB where cardinality permits |
| Valid-line parse rate on supported combined format | >=99.9% | >=99.9% | >=99.9% |
| Automated test coverage | >=85% | >=90% | >=90% |
| Successful pip installation smoke tests | Linux + macOS | Add Windows | Maintain all three |

Performance targets are measured on a documented representative laptop, Python version, input fixture generator, and cold/warm-run protocol; results without that context do not count.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| High-cardinality IP/URL/User-Agent values grow memory | Medium | High | Document bounded-cardinality assumption, benchmark adversarial data, fail clearly on memory exhaustion; consider approximate counters only after MVP evidence |
| Real nginx formats differ from Combined Log Format | High | Medium | Define the supported format precisely, count malformed lines, expose strict mode, keep parser isolated for later formats |
| Python misses the 1 GB/30 s target | Medium | High | Benchmark early, avoid per-line Rich work, precompile parsing, profile before optimizing |
| CSV cannot naturally represent heterogeneous metrics | Medium | Medium | Use a documented normalized row schema with `metric`, `rank`, `key`, `value`, and `unit` |
| Color or diagnostics corrupt pipeline output | Low | High | Disable color for JSON/CSV and non-TTY output; send diagnostics to stderr only |
| Weekend scope expands into a monitoring platform | Medium | High | Enforce MoSCoW exclusions and the CLI-only/stateless architecture decision |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python, Click, Rich, pytest are open source |
| Development infrastructure | $0 | Local development and free source-hosting/CI tiers |
| Database, servers, cloud, Kubernetes | $0 | Explicitly absent |
| Distribution | $0 | pip installation from source or free PyPI hosting |
| Total | **$0** | One-weekend labor is the only investment |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Streaming parser for nginx Combined Log Format | **Must** | All metrics depend on reliable single-pass parsing |
| Top-10 client IPs | **Must** | Core triage signal |
| Top-10 URLs with 4xx/5xx responses | **Must** | Core error diagnosis signal |
| Hourly request distribution | **Must** | Core traffic-shape signal |
| Unique User-Agent share | **Must** | Explicit product output |
| Colored terminal report | **Must** | Default user experience |
| Stable JSON output | **Must** | Required pipeline contract |
| Stable CSV output | **Must** | Required pipeline contract |
| Strict malformed-line mode and summary diagnostics | **Should** | Improves trust and automation without defining the core value |
| Read continuously appended input with `--follow` | **Could** | Useful operational polish, but one-shot streaming satisfies MVP |
| Custom nginx `log_format` grammar | **Could** | Expands compatibility at meaningful parser cost |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Contradicts the approved local stateless product boundary |

### RICE Scoring (Must + Should)

| Feature | Reach (1-10) | Impact (1-5) | Confidence | Effort (person-days) | RICE Score |
|---|---:|---:|---:|---:|---:|
| Streaming parser | 10 | 5 | 95% | 0.75 | 63.3 |
| Top-10 client IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Top-10 error URLs | 10 | 5 | 95% | 0.35 | 135.7 |
| Hourly distribution | 9 | 4 | 95% | 0.25 | 136.8 |
| Unique User-Agent share | 8 | 3 | 90% | 0.25 | 86.4 |
| Colored terminal report | 8 | 3 | 90% | 0.50 | 43.2 |
| JSON output | 9 | 4 | 95% | 0.30 | 114.0 |
| CSV output | 8 | 4 | 90% | 0.30 | 96.0 |
| Strict malformed-line handling | 7 | 3 | 85% | 0.25 | 71.4 |

Dependency order overrides raw score where necessary: the parser is implemented first, then aggregations, then renderers. Within each dependency layer, higher RICE scores determine order. See `IMPLEMENTATION_PLAN.md`.

## Definition of Done

A feature is "Done" when:

- [ ] Its behavior and acceptance criteria are current in `PRD.md`.
- [ ] Code runs on Python 3.11 and lint/type checks pass.
- [ ] Unit tests pass and total coverage is at least 85%.
- [ ] Applicable CLI integration and packaging smoke tests pass.
- [ ] Code review passes with no unresolved critical or high findings.
- [ ] User-facing documentation and output schemas are updated.
- [ ] No known critical/high security issue remains.
- [ ] Performance-sensitive changes include reproducible benchmark evidence.
- [ ] The pip-installed command is manually verified on a clean environment.

## Strategic Boundaries

This plan is the product-strategy source of truth. `PROJECT_ARCHITECTURE.md` owns technical constraints, `PRD.md` owns observable behavior, and `IMPLEMENTATION_PLAN.md` owns delivery sequencing. Changes to behavior begin in those specifications before implementation.
