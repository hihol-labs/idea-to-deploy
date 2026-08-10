# Strategic Plan: nginx-stream-stats

## 1. Product Idea

`nginx-stream-stats` is a local, installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream and produces an operational snapshot without uploading logs or provisioning infrastructure: the top 10 client IPs, the top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agent values. Rich terminal output is the default; stable JSON and CSV modes support automation.

The MVP is deliberately narrow: one local process, bounded-memory aggregation, no retained state, and no network service. The delivery window is one weekend and the monetary budget is $0.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call engineer | SRE investigating an incident | Needs useful traffic signals before a full observability stack is available | One command produces the four agreed metrics from a file or stdin |
| Platform engineer | DevOps owner of CI and shell workflows | Terminal-only tools are hard to compose reliably | `--json` and `--csv` provide machine-readable, deterministic output |
| Systems administrator | Operator of small/self-hosted nginx estates | ELK-style systems are too costly and operationally heavy | Local pip install, no service, database, account, or cloud dependency |

## 3. Competitive Analysis

| Alternative | Strength | Weakness for this use case | Product differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Broader UI/reporting surface than this incident-focused task; additional native binary | Smaller Python CLI with an explicit four-metric contract and pipeline formats |
| Logstash + Elastic + Kibana | Powerful ingestion, search, storage, dashboards | Requires services, persistent storage, setup, and ongoing resources | Zero-service, zero-retention local analysis |
| AWStats | Established historical web analytics | Oriented toward generated historical reports rather than immediate streaming CLI use | Immediate stdout result, stdin support, automation-friendly schemas |
| `grep` / `awk` | Ubiquitous and flexible | Fragile parsing, repeated ad hoc scripts, inconsistent metrics and error handling | Tested nginx parsing and stable output/exit contracts in one command |

## 4. Unique Value Proposition

Turn a large nginx access log into four incident-relevant, pipeline-ready metrics locally in one command—without deploying or operating anything.

## 5. Business Model

The project is open source and free to use. There is no paid tier, telemetry, hosted component, or monetization target. The value is reduced incident-analysis time and a reusable community tool. Acquisition is organic through the package index, source repository, and peer recommendation; CAC and LTV are therefore not commercial KPIs.

## 6. Technology Stack

| Component | Choice | Reason |
|---|---|---|
| Runtime | Python 3.11 | Approved, portable, productive for a one-weekend build |
| CLI | Click | Predictable options, usage errors, and testable entry point |
| Terminal UI | Rich | Colored tables and progress-safe console behavior |
| Data models | `dataclasses` | Lightweight typed records without a validation framework |
| Packaging | `pyproject.toml`, pip | Standard install and console-script distribution |
| Tests | pytest + Click `CliRunner` | Unit and end-to-end CLI coverage with temporary log fixtures |

The detailed module and interface contracts are in [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md).

## 7. Timeline

| Window | Work | Exit result |
|---|---|---|
| Saturday morning | Package skeleton, data contracts, parser | Valid combined-format lines become typed records; invalid lines are counted |
| Saturday afternoon | Streaming aggregators and cardinality guard | All four metrics work with bounded failure behavior |
| Sunday morning | Click CLI and text/JSON/CSV renderers | Stable input, output, option, and exit-code contract |
| Sunday afternoon | Tests, 1 GB benchmark, packaging, docs | Installable artifact and recorded acceptance evidence |

The executable sequence appears in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## 8. KPIs

| Metric | Launch target | 1-month target | Measurement |
|---|---:|---:|---|
| Processing performance | 1 GB in under 30 seconds on the reference laptop | No regression beyond 10% | Timed benchmark using a documented local fixture |
| Correctness | 100% of golden fixtures match expected metrics | Zero open correctness defects rated high | pytest golden-output assertions |
| Memory behavior | Does not grow with total line count except unique-key maps | Guard exits deterministically at the configured unique-key ceiling | Peak RSS benchmark and exhaustion test |
| Installability | Fresh Python 3.11 venv installs and runs | Published release remains reproducible | Build/install smoke test |
| Pipeline stability | JSON and CSV schemas pass contract tests | No unannounced breaking schema change | Snapshot/schema tests |

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Real logs use a format that differs from nginx combined format | Medium | High | State the supported format, fail on zero valid records, count malformed lines, document extension seam |
| High unique cardinality exhausts laptop memory | Medium | High | Configurable hard ceiling over tracked unique IP/URL/User-Agent keys; exit code `4` on exhaustion |
| Python misses the 1 GB/30 s target | Medium | High | Single-pass parsing, compiled regex, minimal allocations, benchmark before polish; stop/re-scope if target is missed |
| CSV interpretation is ambiguous for heterogeneous metrics | Medium | Medium | Use one long-form schema with `metric`, `rank_or_bucket`, `key`, `count`, and `percentage` columns |
| Color/control bytes leak into pipelines | Low | Medium | Color only for TTY text mode; JSON/CSV never use Rich styling; tests assert clean bytes |
| Corrupt or unreadable input produces misleading partial output | Low | High | Separate fatal I/O/encoding failures from tolerated malformed lines through the exit-code contract |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Libraries and runtime | $0 | Open-source Python ecosystem |
| Hosting, database, cloud | $0 | None exists in this product |
| Delivery labor | $0 cash budget | One weekend of contributor time |
| Ongoing operations | $0 | Local execution; no managed infrastructure |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Streaming nginx combined-log parsing from file and stdin | **Must** | Foundation for all value and for bounded processing of large files |
| Top-10 IPs by valid request count | **Must** | Required incident signal |
| Top-10 URLs by combined 4xx/5xx count | **Must** | Required error hotspot signal |
| Hourly request distribution in percentages | **Must** | Required traffic-shape signal |
| Unique User-Agent share | **Must** | Required client-diversity signal |
| Colored terminal, JSON, and CSV renderers | **Must** | Required human and pipeline interfaces |
| Pip-installable package with stable exit codes | **Must** | Required distribution and automation contract |
| Malformed-line summary and configurable cardinality ceiling | **Should** | Makes partial data and memory safety explicit |
| Direct `.gz` input | **Could** | Useful convenience, but shell decompression can cover MVP |
| Custom nginx `log_format` grammar | **Could** | Broadens adoption but threatens the weekend scope |
| Database, HTTP API, server, auth, cloud, Kubernetes | **Won't** | Contradicts local stateless CLI scope and adds no MVP value |

### RICE Scoring (Must + Should)

Scores use `(Reach × Impact × Confidence) / Effort`, with confidence expressed as a decimal. They prioritize implementation rather than claim measured demand.

| Feature | Reach (1–10) | Impact (1–5) | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Top-10 IP aggregation | 9 | 4 | 95% | 0.25 | 136.8 |
| Error-URL aggregation | 9 | 5 | 95% | 0.35 | 122.1 |
| Hourly percentage distribution | 8 | 4 | 95% | 0.25 | 121.6 |
| Unique User-Agent share | 8 | 4 | 85% | 0.30 | 90.7 |
| Packaging + exit contract | 10 | 4 | 90% | 0.50 | 72.0 |
| Streaming parser + file/stdin input | 10 | 5 | 90% | 0.75 | 60.0 |
| Terminal/JSON/CSV renderers | 10 | 5 | 85% | 0.75 | 56.7 |
| Diagnostics + cardinality ceiling | 7 | 5 | 80% | 0.50 | 56.0 |

Dependency order overrides raw score where necessary: parser first, aggregators second, interfaces third, hardening and packaging last.

## 12. Definition of Done

A feature is Done only when:

- [ ] Its behavior and acceptance criteria agree with [PRD.md](PRD.md).
- [ ] Python 3.11 code is formatted, statically checked, and builds without error.
- [ ] Unit and CLI integration tests pass with at least 90% line coverage for `src/nginx_stream_stats`.
- [ ] JSON/CSV contract tests and terminal golden tests pass.
- [ ] Relevant README and CLI help text are updated.
- [ ] No known Critical or High security issue remains.
- [ ] The exact release candidate passes the 1 GB performance test on the documented laptop and the smoke install in a clean venv.
- [ ] A manual local run confirms readable terminal output; no staging environment is required for this local-only tool.

## 13. Success and Stop Conditions

Ship the MVP when every P0 criterion in [PRD.md](PRD.md) and the Definition of Done above passes. Apply the PRD kill criteria if the performance target or bounded-memory contract cannot be met within the weekend without changing the approved architecture.
