# Strategic Plan: nginx-log-report

## 1. Product Idea

`nginx-log-report` is a local, pip-installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream and produces four immediately useful diagnostics: top 10 client IPs, top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agent strings. The default is a colored terminal report; stable JSON and CSV contracts make the same analysis usable in shell pipelines.

The MVP is deliberately local and stateless: no credentials, persistence, service process, network listener, or infrastructure are required. The source of truth for behavior is [PRD.md](PRD.md); technical decisions are in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md).

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| On-call engineer | SRE responding to an incident | Needs a fast traffic/error overview without provisioning a stack | Runs one command against a file or stdin and gets a compact report |
| Platform engineer | Maintains nginx fleets and shell automation | Ad-hoc grep/awk scripts are brittle and hard to reuse | Uses documented JSON/CSV schemas and deterministic exit codes |
| Developer/operator | Troubleshoots a local or small deployment | Full observability products are disproportionate | Installs with pip and analyzes locally at zero infrastructure cost |

## 3. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | nginx-log-report distinction |
|---|---|---|---|
| GoAccess | Fast, mature, interactive terminal/HTML analytics | Broader UI and configuration surface than the four required signals | Narrow report contract, Python/pip distribution, pipeline-first JSON/CSV |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, search, dashboards, retention | Multiple services, storage, operational cost, and setup time | One local process, no service or persisted index |
| AWStats | Mature historical web analytics | Batch/reporting orientation and dated operational workflow | Immediate CLI diagnostics with machine-readable output |
| grep/awk/sort/uniq | Ubiquitous and composable | Format assumptions, quoting, multiple passes, and inconsistent error handling | One tested parser, one pass, explicit schemas and exit codes |

## 4. Unique Value Proposition

Get the four nginx incident signals that matter in one local, zero-setup command, while retaining stable JSON and CSV output for automation.

## 5. Business Model

The project is open source and free to use. There is no paid tier, telemetry, hosted component, CAC, or direct LTV. Value is measured as engineer time saved and reduced incident-analysis setup. Maintenance is community/owner time; the MVP must not introduce recurring infrastructure cost.

## 6. Technology Stack

| Component | Technology | Reason |
|---|---|---|
| Runtime | Python 3.11 | Approved, widely available to target users |
| CLI | Click | Predictable argument parsing, help, and exit behavior |
| Terminal rendering | Rich | TTY-aware color and readable tables |
| Domain models | `dataclasses` | Small typed records without framework overhead |
| Packaging | pip-compatible `pyproject.toml` | Standard local installation and console entry point |
| Testing | pytest | Lightweight unit, CLI, golden-output, and performance tests |

## 7. Timeline

| Period | Stage | Result |
|---|---|---|
| Weekend, block 1 | Packaging, parser, aggregation | Installable CLI core processes representative combined logs |
| Weekend, block 2 | Text/JSON/CSV renderers | All required reports and stable output contracts work |
| Weekend, block 3 | Robustness, performance, documentation | Error paths tested and 1 GB benchmark meets target |

## 8. KPIs

| Metric | Launch target | Month 1 | Month 3 |
|---|---:|---:|---:|
| Decimal 1 GB processing time on reference laptop | <30 s | <30 s | <25 s if profiling supports it |
| Required report/output acceptance tests passing | 100% | 100% | 100% |
| Valid combined-log lines parsed in compatibility corpus | >=99.9% | >=99.9% | >=99.9% |
| Recurring infrastructure cost | $0 | $0 | $0 |
| Median clean-install-to-first-report time | <5 min | <5 min | <3 min |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| nginx log formats vary beyond the supported combined format | High | High | State the format contract, allow `--format`, report malformed-line counts, preserve raw fixtures for extensions |
| Exact unique User-Agent tracking consumes memory on high-cardinality data | Medium | High | Document exact semantics, store only normalized strings, benchmark peak RSS, defer approximate counting unless needed |
| Python misses the decimal 1 GB/30 s target | Medium | High | Avoid regex backtracking and per-line Rich work, profile on a frozen corpus, optimize parser hot path before adding scope |
| CSV representation is ambiguous for multiple report shapes | Medium | Medium | Use one documented long-form schema with section/rank/key/value/percentage columns and golden tests |
| Users mistake skipped malformed lines for complete analysis | Medium | High | Print counts to stderr, include metadata in structured output, fail when no valid records exist |
| Scope expands toward a monitoring platform | Medium | Medium | Keep server, database, auth, cloud, and dashboards explicitly out of scope |

## 10. Budget

| Item | One-time | Monthly | Comment |
|---|---:|---:|---|
| Open-source dependencies | $0 | $0 | Python, Click, Rich, pytest |
| Hosting/cloud/database | $0 | $0 | None by design |
| Delivery labor | One weekend | $0 cash budget | Owner/community time only |
| CI for public repository | $0 | $0 | Optional free tier; local verification remains authoritative |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream combined-format logs from a path or stdin | **Must** | Required input foundation and avoids loading the entire file |
| Top 10 client IPs | **Must** | Core incident signal |
| Top 10 error URLs for 4xx/5xx | **Must** | Core failure signal |
| Hourly request distribution | **Must** | Core traffic-shape signal |
| Unique User-Agent share | **Must** | Core client-diversity signal |
| Colored terminal report | **Must** | Required default experience |
| Stable `--json` and `--csv` output | **Must** | Required pipeline support |
| Malformed-line accounting and deterministic exit codes | **Must** | Required for trustworthy automation |
| Configurable top-N | **Should** | Useful extension, but top 10 satisfies MVP |
| Live `--follow` mode | **Could** | Helpful for tailing but complicates final structured reports |
| Custom nginx `log_format` grammar | **Could** | Broadens adoption after the combined-format MVP |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Conflicts with the approved local stateless CLI scope |

### RICE Scoring for Must and Should Features

Scores use `(Reach × Impact × Confidence) / effort`; confidence is a decimal in the calculation. Values are comparative planning estimates, not usage measurements.

| Feature | Reach (1–10) | Impact (1–5) | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming input + combined parser | 10 | 5 | 90% | 1.0 | 45.0 |
| Malformed-line and exit contract | 9 | 4 | 90% | 0.5 | 64.8 |
| Top 10 IPs | 10 | 4 | 95% | 0.5 | 76.0 |
| Top 10 error URLs | 10 | 5 | 95% | 0.5 | 95.0 |
| Hourly distribution | 8 | 4 | 95% | 0.4 | 76.0 |
| Unique User-Agent share | 7 | 3 | 85% | 0.5 | 35.7 |
| Colored terminal output | 9 | 3 | 90% | 0.7 | 34.7 |
| JSON and CSV output | 9 | 5 | 90% | 1.0 | 40.5 |
| Configurable top-N | 5 | 2 | 75% | 0.3 | 25.0 |

Dependency order takes precedence where a high-scoring report still requires the parser. Within a dependency layer, implementation follows descending RICE value as reflected in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## 12. Success and Kill Criteria

Proceed to release when every P0 acceptance criterion in [PRD.md](PRD.md) passes and the reference benchmark processes exactly 1,000,000,000 bytes in under 30 seconds within the architecture's memory envelope. Re-scope or stop the MVP if, after profiling and one bounded optimization pass, the approved Python stack cannot meet that target, or if reliable parsing requires an unbounded custom-format engine incompatible with weekend delivery.

## Definition of Done

A feature is done when:

- [ ] Its behavior and edge cases match the PRD acceptance criteria.
- [ ] Python 3.11 type/static checks and formatting checks pass.
- [ ] Unit and CLI integration tests pass with at least 85% line coverage overall.
- [ ] Renderer golden tests pass for terminal, JSON, and CSV contracts where applicable.
- [ ] No known Critical or High security issue remains.
- [ ] User-facing documentation is updated.
- [ ] Performance-sensitive changes are checked against the fixed benchmark corpus.
- [ ] A clean virtual environment can install the package and run the documented Quick Start.
