# Strategic Plan: Nginx Insights CLI

## 1. Product Idea

Nginx Insights CLI is a local, installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads an nginx access-log file or standard input once, keeps bounded aggregate state in memory, and reports the top 10 client IPs, top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. Rich colored text is the default; JSON and CSV provide stable pipeline outputs.

The MVP is deliberately local and stateless. It has no authentication, database, HTTP API, server, cloud service, or Kubernetes dependency.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Diagnoses an incident under time pressure | Needs a useful summary without importing logs into a service | One command, streaming input, terminal-first output |
| DevOps engineer | Investigates deployments and proxy errors | Ad hoc shell pipelines are brittle and hard to reproduce | Defined metrics and stable JSON/CSV schemas |
| Platform engineer | Builds operational scripts | Interactive tools are awkward in automation | stdin support, machine formats, explicit exit codes |

## 3. Competitive Analysis

| Alternative | Strength | Weakness for this use case | Nginx Insights difference |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Broader feature set and UI than a focused pipeline may need | Smaller, explicit four-metric contract and JSON/CSV-first automation |
| Logstash + Elastic + Kibana | Powerful ingestion, search, and dashboards | Operationally heavy, stateful, and costly in setup time | Zero-service local execution and no persistent data |
| AWStats | Established historical reporting | Oriented toward generated reports and retained history | Immediate one-pass incident summary |
| `grep`/`awk`/`sort` | Available nearly everywhere | Parsing and metric definitions vary by operator; multiple passes are common | Reproducible parsing, one pass, stable outputs and failures |

## 4. Unique Value Proposition

Get a reproducible, pipeline-friendly nginx incident summary from a large local log in one command, without deploying or operating anything.

## 5. Business Model

The product is free and open source. There are no paid tiers, hosted services, or usage fees. Value is measured through adoption, reliability, and reduced incident-analysis time rather than revenue. Distribution is through a public Python package and source repository; the one-weekend delivery budget is $0.

## 6. Technology Stack

| Component | Choice | Why |
|---|---|---|
| Runtime | Python 3.11 | Approved, portable, and productive for a weekend CLI |
| CLI | Click | Mature argument validation and conventional exit behavior |
| Terminal UI | Rich | Accessible colored tables with automatic non-TTY behavior |
| Domain model | `dataclasses` | Explicit typed records without extra runtime dependencies |
| Packaging | pip-installable package | Familiar installation and console entry point |
| Tests | pytest | Fast unit and CLI integration testing |

## 7. Timeline

| Weekend block | Work | Outcome |
|---|---|---|
| Saturday morning | Package skeleton, CLI contract, parser | Valid combined-log records stream from file/stdin |
| Saturday afternoon | Aggregation and cardinality guard | Four metrics computed in one pass |
| Sunday morning | Rich, JSON, and CSV renderers | Human and pipeline outputs conform to documented schemas |
| Sunday afternoon | Tests, benchmark, documentation, packaging | Release candidate meets functional and performance gates |

## 8. KPIs

| Metric | Launch target | 1 month | 3 months |
|---|---:|---:|---:|
| Processing time for a representative 1 GB log on the reference laptop | <30 s | <30 s | <25 s if profiling supports it |
| Correctness fixtures passing | 100% | 100% | 100% |
| Peak memory on the cardinality benchmark | Within documented bound | No regressions | No regressions |
| Time for a new user to obtain a report | <30 s after install | <30 s | <30 s |
| Open critical correctness defects | 0 | 0 | 0 |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from the supported combined format | Medium | High | Fail clearly on zero valid records; document the grammar; retain malformed-line counts |
| Python misses the 1 GB/30 s target | Medium | High | Benchmark early, parse line-by-line, avoid per-line regex recompilation and profile before optimization |
| High-cardinality inputs exhaust memory | Medium | High | Enforce `--max-unique`; stop deterministically with exit code 4 |
| CSV schema becomes ambiguous across unlike metrics | Medium | Medium | Use one normalized schema and golden-output tests |
| Color codes leak into redirected output | Low | Medium | Enable color only for a TTY unless explicitly forced by Rich behavior |
| “Unique User-Agent share” is misunderstood | Medium | Medium | Define it as a percentage in PRD, architecture, help text, and output metadata |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Development | $0 cash | One-weekend owner contribution |
| Runtime and hosting | $0/month | Runs locally; no hosted component |
| Dependencies | $0 | Open-source Python packages |
| Distribution | $0 | Public source and standard Python package infrastructure |
| Total | **$0** | No paid service is required |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream combined nginx logs from a file or stdin | **Must** | Required for local and pipeline use |
| Top 10 client IPs | **Must** | Core incident-triage metric |
| Top 10 URLs by combined 4xx/5xx count | **Must** | Core error diagnosis metric |
| Hourly request percentages | **Must** | Required traffic-shape metric |
| Unique User-Agent share | **Must** | Required client-diversity metric |
| Rich terminal, JSON, and CSV outputs | **Must** | Required human and pipeline interfaces |
| Cardinality safety limit and exit code 4 | **Must** | Prevents uncontrolled memory use |
| Custom nginx log-format grammar | **Should** | Extends adoption beyond the combined format after MVP |
| gzip input | **Could** | Convenient but shell decompression is an adequate fallback |
| Persistent history and dashboards | **Won't** | Conflicts with stateless local scope |
| Authentication, HTTP API, cloud, or Kubernetes | **Won't** | Explicitly outside the product boundary |

### RICE Scoring (Must and Should)

`RICE = Reach × Impact × Confidence / Effort`; confidence is used as a decimal. Scores guide dependency-aware ordering rather than replacing it.

| Feature | Reach (1–10) | Impact (1–5) | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Stream file/stdin and parse combined logs | 10 | 5 | 90% | 1.0 | 45.0 |
| Top IPs and error URLs | 10 | 5 | 90% | 1.0 | 45.0 |
| Hourly distribution and User-Agent share | 9 | 4 | 90% | 0.75 | 43.2 |
| Rich terminal, JSON, and CSV outputs | 10 | 4 | 85% | 1.0 | 34.0 |
| Cardinality guard and exit contract | 8 | 5 | 90% | 1.25 | 28.8 |
| Custom log-format grammar | 5 | 3 | 60% | 2.0 | 4.5 |

Implementation order is adjusted for dependencies: parser and data model precede aggregations, and aggregations precede renderers.

## 12. Product Metric Definitions

- Hourly request distribution is the percentage for each hour `00`–`23`, using `100 × hourly_request_count / total_valid_requests`. Empty hours are reported as 0%.
- Unique User-Agent share is `100 × distinct_nonempty_user_agents / total_valid_requests`. It can exceed neither 100% nor the share of records that contain a nonempty User-Agent; the report also includes both counts.
- Error URL ranking counts valid requests whose status is 400–599, grouped by the request-target path exactly as parsed, with deterministic tie-breaking by URL ascending.
- Top IP ranking counts all valid requests, with deterministic tie-breaking by IP string ascending.

## 13. Definition of Done

A feature is Done when:

- [ ] Behavior and acceptance criteria are reflected in `PRD.md` and `PROJECT_ARCHITECTURE.md`.
- [ ] Product code is implemented later, type-checks/lints without errors, and introduces no undocumented interface changes.
- [ ] Unit tests and CLI integration tests pass with at least 90% line coverage for the parser, aggregation, and rendering packages.
- [ ] Golden outputs pass for terminal-without-ANSI, JSON, and CSV modes.
- [ ] A representative 1 GB benchmark completes in under 30 seconds on the documented reference laptop.
- [ ] Cardinality exhaustion is tested and returns exit code 4 without partial output.
- [ ] Documentation and `--help` are current.
- [ ] No known critical or high security issue remains.
- [ ] The pip-built wheel installs in a clean Python 3.11 environment and the smoke test passes.

## 14. Strategic Kill Criteria

Pause or re-scope the MVP if the representative 1 GB benchmark cannot meet 30 seconds after profiling and one bounded optimization pass, if correct parsing requires a general nginx configuration interpreter, or if the core use case requires retained history or multi-user service operation. Those outcomes would invalidate the approved local Python streaming premise rather than justify silent scope growth.

