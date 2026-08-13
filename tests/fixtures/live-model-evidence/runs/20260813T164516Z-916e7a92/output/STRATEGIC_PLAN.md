# Strategic Plan: nginx-top

## 1. Product Summary

`nginx-top` is a local, installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream and reports the top 10 client IPs, top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agent values. It defaults to readable colored terminal output and also emits stable JSON or CSV for pipelines.

The product is deliberately local and stateless: no authentication, database, HTTP API, server process, cloud service, or Kubernetes deployment. The delivery target is one weekend, the operating budget is $0, and the performance target is a 1 GB log in under 30 seconds on the reference laptop.

## 2. Target Users

| Persona | Role | Pain | Product response |
|---|---|---|---|
| Incident responder | On-call SRE | Needs a useful traffic/error overview before a dashboard is available | One command produces bounded top lists and distributions locally |
| Service operator | DevOps engineer | Needs to inspect rotated or downloaded logs without shipping them elsewhere | File and stdin streaming keep data on the machine |
| Automation author | Platform engineer | Needs stable output for shell jobs and CI diagnostics | `--json` and `--csv` provide machine-readable schemas and meaningful exit codes |

## 3. Problem and Value Proposition

Operational debugging often starts with a large nginx access log and a narrow question. Full observability stacks take time and infrastructure; ad hoc `grep`, `awk`, and `sort` pipelines are fragile and hard to reproduce. `nginx-top` provides a predictable, zero-service middle ground: useful incident statistics in one local command, with memory use independent of input file size except for explicitly bounded cardinality state.

**Unique value proposition:** actionable nginx traffic and error summaries from gigabyte-scale logs in one local command, without deploying or operating another service.

## 4. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | `nginx-top` distinction |
|---|---|---|---|
| GoAccess | Mature, fast, rich interactive and HTML reports | Broader UI and configuration surface than a small pipeline tool needs | Narrow metrics, simple install, stable JSON/CSV contracts |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, search, retention, and dashboards | Substantial services, storage, setup, and operational cost | No service or database; immediate local analysis |
| AWStats | Established historical web analytics | Batch-oriented, dated workflow, persistent report artifacts | Incident-oriented streaming output to terminal or pipelines |
| `grep`/`awk`/`sort` | Ubiquitous and composable | Easy to misparse quoting; repeated scans and unbounded sort intermediates | One-pass parsing, consistent semantics, tested edge cases |

## 5. Business Model and Budget

The MVP is open source and free to use. There is no monetization requirement in the one-weekend scope; value is measured through adoption, reproducibility, and reduced incident-analysis time rather than revenue, CAC, or LTV.

| Item | Cost | Notes |
|---|---:|---|
| Development tools | $0 | Python and dependencies are open source |
| Hosting/infrastructure | $0 | Local CLI; no hosted component |
| CI | $0 | Optional free tier for an open-source repository |
| Distribution | $0 | Build locally; publish to PyPI when credentials are available |
| Total MVP budget | **$0** | Excludes developer time |

## 6. Technology Strategy

| Component | Choice | Why |
|---|---|---|
| Runtime | Python 3.11 | Required stack; mature text streaming and packaging |
| CLI | Click | Predictable options, help, usage errors, and testing utilities |
| Terminal presentation | Rich | Colored, readable tables with TTY-aware behavior |
| Domain models | `dataclasses` | Lightweight typed records without a persistence layer |
| Tests | pytest + Click `CliRunner` | Fast unit and end-to-end CLI coverage |
| Packaging | `pyproject.toml`, pip | Standard installable CLI distribution |

## 7. Feature Roadmap

### MoSCoW Priorities

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream nginx combined-format input from a file or stdin | **Must** | Foundation for local files and Unix pipelines |
| Top-10 client IPs | **Must** | Core traffic-source diagnostic |
| Top-10 URLs with 4xx/5xx responses | **Must** | Core failure diagnostic |
| Hourly request distribution | **Must** | Shows load shape across the observed period |
| Unique User-Agent share | **Must** | Required client-diversity signal |
| Colored terminal, JSON, and CSV output | **Must** | Required human and pipeline interfaces |
| Parse diagnostics and complete exit-code contract | **Must** | Makes automation safe and failures actionable |
| 1 GB performance benchmark | **Must** | Validates the central scalability promise |
| Gzip input | **Should** | Common for rotated logs, but shell decompression is an MVP workaround |
| Configurable top-N | **Could** | Useful polish; the approved product contract is top 10 |
| Persistent history/dashboard | **Won't** | Conflicts with stateless, local scope |
| Authentication, API, server, cloud, or Kubernetes | **Won't** | No remote trust boundary or deployed service exists |

### RICE Scoring for Must and Should Features

Scores use `(Reach × Impact × Confidence) / Effort`, with confidence expressed as a decimal. Estimates prioritize delivery order rather than claim measured demand.

| Feature | Reach (1–10) | Impact (1–5) | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming parser and aggregation core | 10 | 5 | 90% | 1.0 | 45.0 |
| Complete exit and diagnostic contract | 9 | 4 | 90% | 0.5 | 64.8 |
| Terminal output | 9 | 4 | 90% | 0.5 | 64.8 |
| JSON and CSV output | 8 | 4 | 90% | 0.5 | 57.6 |
| Four required metrics | 10 | 5 | 90% | 1.0 | 45.0 |
| 1 GB benchmark and optimization | 8 | 5 | 70% | 1.0 | 28.0 |
| Gzip input | 5 | 2 | 70% | 0.5 | 14.0 |

Dependency order takes precedence where equal or higher RICE features require the parser and domain model first.

## 8. Delivery Timeline

| Window | Outcome |
|---|---|
| Friday evening | Package skeleton, contracts, parser fixtures, exit behavior |
| Saturday morning | One-pass aggregation and all four metrics |
| Saturday afternoon | Rich, JSON, and CSV renderers |
| Sunday morning | CLI integration, malformed-input behavior, unit/integration tests |
| Sunday afternoon | 1 GB benchmark, profiling, documentation, release build |

## 9. Success Metrics

| Metric | Launch target | First month target | Measurement |
|---|---:|---:|---|
| Processing time for a 1 GB representative log | <30 seconds | Maintain <30 seconds | Repeatable benchmark on named reference laptop |
| Peak resident memory | <256 MiB on benchmark | No regression >10% | `/usr/bin/time -v` or platform equivalent |
| Correctness of fixture outputs | 100% | 100% | Golden terminal-neutral JSON tests |
| P0 acceptance tests passing | 100% | 100% | Automated test suite |
| Time to first useful report | <30 seconds after install | <30 seconds | Manual golden flow |

## 10. Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from combined format | High | High | Make supported format explicit; count malformed lines; keep parser isolated for later formats |
| Exact unique User-Agent tracking grows with cardinality | Medium | High | Enforce a configurable hard cap and exit `4` rather than exhausting memory silently |
| Python misses the 1 GB/30 s target | Medium | High | Benchmark early, compile the regex once, avoid per-line object churn, profile before optimizing |
| CSV representation is ambiguous for multiple report sections | Medium | Medium | Use a documented long-form `record_type` schema |
| Broken pipes are mistaken for tool failures | Medium | Medium | Treat expected downstream pipe closure as a clean termination where no prior error exists |
| Locale/timezone assumptions alter hourly buckets | Medium | Medium | Use the hour encoded in each nginx timestamp; do not convert timezone in MVP |

## 11. Definition of Done

A feature is done when:

- [ ] Its behavior and acceptance criteria are documented in `PRD.md`.
- [ ] Code is implemented for Python 3.11 with no placeholder paths.
- [ ] Unit and CLI integration tests pass with at least 90% line coverage for first-party modules.
- [ ] Format-specific golden tests pass for terminal-neutral data, JSON, and CSV.
- [ ] The complete `0/1/2/3/4` exit-code contract is tested.
- [ ] Performance evidence shows a representative 1 GB log completes in under 30 seconds on the named reference laptop.
- [ ] Peak-memory evidence is recorded and unique-cardinality exhaustion exits safely with code `4`.
- [ ] User-facing documentation is current and the pip-built wheel installs in a clean Python 3.11 environment.
- [ ] No known critical or high-severity security issue remains.

## 12. MVP Boundaries and Kill Criteria

Do not add persistence, remote services, authentication, an HTTP API, cloud deployment, or Kubernetes to meet an MVP need. Reassess the approach if profiling shows the required 1 GB workload cannot finish within 30 seconds after focused optimization, or if exact User-Agent uniqueness cannot be bounded without violating the documented CLI contract. These are redesign triggers, not reasons to silently weaken results.

The technical contract is defined in `PROJECT_ARCHITECTURE.md`; delivery sequencing is defined in `IMPLEMENTATION_PLAN.md`; product acceptance is defined in `PRD.md`.
