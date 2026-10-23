# Strategic Plan: nginx-top

## 1. Product Idea

`nginx-top` is a local, pip-installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream and produces an immediately useful operational summary: top 10 client IPs, top 10 URLs returning 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. Rich colored text is the default; JSON and CSV make the same results usable in pipelines.

The MVP is deliberately local and stateless. It has no account system, database, daemon, HTTP API, cloud dependency, or Kubernetes footprint. The delivery constraint is one weekend and a zero-dollar budget.

## 2. Target Audience

| Persona | Role | Pain | How nginx-top helps |
|---|---|---|---|
| On-call responder | SRE investigating an incident | Needs a useful traffic/error snapshot without building a dashboard | Produces ranked IP and error-URL summaries directly from a file or stdin |
| Platform engineer | DevOps engineer maintaining nginx hosts | Repeats fragile `grep`/`awk` pipelines and needs machine-readable output | Provides stable parsing, metrics, exit codes, JSON, and CSV |
| Developer/operator | Engineer debugging a service locally | Wants fast evidence from a downloaded log without uploading sensitive traffic data | Runs entirely on the laptop and keeps log data local |

## 3. Competitive Analysis

| Alternative | What it does | Weakness for this use case | nginx-top distinction |
|---|---|---|---|
| GoAccess | Rich real-time and historical web-log analytics | Broader UI/configuration surface than a four-metric pipeline tool; separate binary | Narrow Python CLI, deterministic JSON/CSV contract, pip installation |
| Logstash + Elasticsearch + Kibana | Ingests, stores, queries, and visualizes logs at scale | Operationally heavy, persistent, and incompatible with a $0 one-weekend local tool | No services or storage; one process and immediate results |
| AWStats | Generates historical web analytics reports | Report-oriented and dated workflow; not ideal for stdin or shell pipelines | Stream-oriented local execution and current CLI ergonomics |
| `grep` / `awk` / `sort` | Ad hoc shell analysis | Parsing is format-fragile, commands are hard to reuse, multiple passes are common | One pass, explicit malformed-line policy, stable output schemas |

## 4. Unique Value Proposition

Get the four nginx traffic signals an on-call engineer needs from a gigabyte-scale log in one local command, with readable terminal output and pipeline-safe JSON/CSV—without deploying or operating anything.

## 5. Business Model

The project is open source and free. There are no paid tiers, hosted services, telemetry, or usage fees. Value is measured in adoption, reliable incident response, and reduced time spent rebuilding shell pipelines; LTV and CAC are not applicable to this non-commercial MVP.

## 6. Technology Stack

| Component | Technology | Why |
|---|---|---|
| Runtime | Python 3.11 | Required platform; widely available to the target audience |
| CLI | Click | Stable option parsing, help text, validation, and exit handling |
| Terminal presentation | Rich | Accessible tables and color with terminal capability detection |
| Domain models | Standard-library dataclasses | Explicit typed result structures without runtime framework overhead |
| Parsing/aggregation | Python standard library | Streaming iteration, regex/datetime parsing, counters, JSON, and CSV with no extra services |
| Packaging | `pyproject.toml` + pip | Standard install path and console-script entry point |
| Quality | pytest, Ruff, mypy | Fast local tests and static checks suitable for a weekend project |

## 7. Timeline

| Weekend block | Stage | Result |
|---|---|---|
| Saturday morning | Contract, package skeleton, parser | Installable CLI reads combined-format records and rejects bad input predictably |
| Saturday afternoon | Streaming aggregation | All four metrics calculated in one pass with bounded top-10 state except the guarded exact cardinality set |
| Sunday morning | Renderers and CLI integration | Rich, JSON, and CSV outputs share one result model and exit-code contract |
| Sunday afternoon | Tests, benchmark, docs, packaging | Green suite, measured 1 GB performance, install smoke test, release-ready documentation |

## 8. KPIs

| Metric | MVP target | First month | Three months |
|---|---:|---:|---:|
| Processing time for a representative 1 GB log | <30 seconds on the reference laptop | Maintain <30 seconds | Maintain <30 seconds |
| Peak RSS on representative 1 GB log | ≤512 MiB under default cardinality limit | Maintain ≤512 MiB | Maintain ≤512 MiB |
| Valid combined-log lines parsed in compatibility corpus | 100% | ≥99.9% of reported real samples | ≥99.9% |
| Automated test line coverage | ≥90% | ≥90% | ≥90% |
| Fatal malformed-input surprises | 0 known | 0 unresolved P0 defects | 0 unresolved P0 defects |
| Adoption proxy | Release artifact installs locally | 25 unique repository cloners/stars combined | 100 combined |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Python parser misses the 1 GB/30 s target | Medium | High | Benchmark early with a generated representative corpus; profile parser before polish; avoid per-line object churn |
| Exact unique User-Agent tracking exhausts memory | Medium | High | Enforce a documented cardinality ceiling and terminate with exit code 4 rather than returning a false metric |
| nginx format variations are mistaken for combined format | High | Medium | State supported format explicitly, count malformed lines, support `--strict`, and add a compatibility corpus |
| CSV representation is ambiguous across different metrics | Medium | Medium | Define one long-form schema with explicit metric/rank/key/count/percentage columns |
| Color contaminates redirected output | Low | Medium | Enable color only for terminal text on a TTY and never for JSON/CSV |
| A malformed or unreadable source yields partial data that looks complete | Low | High | Separate diagnostics to stderr and use exit codes 1, 2, and 3 consistently |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python and selected dependencies are open source |
| Hosting/database/cloud | $0 | None exists in scope |
| Development | $0 cash | One weekend of contributor time |
| CI | $0 | Use an open-source project allowance or run checks locally |
| Distribution | $0 | Source repository and pip-compatible artifacts |
| **Total cash budget** | **$0** | Hard constraint |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream nginx combined logs from files or stdin | **Must** | Foundation for every metric and local/pipeline use |
| Top-10 client IPs | **Must** | Core incident-triage signal |
| Top-10 URLs by 4xx/5xx count | **Must** | Core error hotspot signal |
| Hourly request distribution | **Must** | Required traffic-shape metric; each bucket is `100 × hourly_request_count / total_valid_requests` |
| Unique User-Agent share with guarded exact cardinality | **Must** | Required diversity signal and explicit safe failure behavior |
| Rich terminal, JSON, and CSV renderers | **Must** | Human readability plus pipeline interoperability |
| Strict malformed-line mode | **Should** | Useful for validation but not necessary for a default best-effort summary |
| Gzip-compressed input | **Could** | Convenient but shell decompression already provides a workaround |
| Custom nginx `log_format` parser | **Could** | Broadens compatibility but exceeds weekend parser scope |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Contradicts the local stateless CLI product boundary |
| Persistent history or live dashboard | **Won't** | Covered by heavier alternatives and requires storage/service operation |

### RICE Scoring for Must and Should

Scores use `(Reach × Impact × Confidence) / Effort`, with confidence represented as a decimal.

| Feature | Reach (1–10) | Impact (1–5) | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Stream files/stdin and parse combined format | 10 | 5 | 90% | 0.75 | 60.0 |
| Top-10 client IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Top-10 error URLs | 10 | 5 | 95% | 0.25 | 190.0 |
| Hourly request distribution | 8 | 4 | 95% | 0.25 | 121.6 |
| Unique User-Agent share and ceiling | 8 | 4 | 80% | 0.50 | 51.2 |
| Rich/JSON/CSV renderers | 10 | 4 | 90% | 0.75 | 48.0 |
| Strict malformed-line mode | 5 | 3 | 90% | 0.25 | 54.0 |

Dependency order takes precedence where a high-scoring metric depends on the lower-scoring parser foundation. Within each dependency layer, implementation follows descending RICE score.

## 12. Definition of Done

A feature is done when:

- [ ] Its behavior and acceptance criteria agree with `PRD.md` and `PROJECT_ARCHITECTURE.md`.
- [ ] Python 3.11 code is typed and passes Ruff and mypy without errors.
- [ ] Unit and integration tests pass with at least 90% line coverage.
- [ ] Output-schema and exit-code contract tests pass for text, JSON, and CSV.
- [ ] The relevant documentation and `--help` output are updated.
- [ ] No known Critical or High security issue remains.
- [ ] A clean virtual-environment pip install and CLI smoke test pass locally.
- [ ] The 1 GB benchmark is recorded and completes in under 30 seconds on the named reference laptop.

## 13. Kill Criteria

Stop or re-scope the MVP if profiling shows that a representative 1 GB combined-format log cannot reach the 30-second target on the reference laptop without native extensions, if exact User-Agent cardinality cannot stay within the 512 MiB target at the documented ceiling, or if supporting real nginx combined logs requires a general log-format language. In each case, preserve the CLI contract and explicitly choose either a narrower supported format/cardinality limit or a different implementation language in a new decision record.

