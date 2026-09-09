# Strategic Plan: nginx-insight

## 1. Product Summary

`nginx-insight` is a local, installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream and produces four operational views without uploading or persisting log data: the top 10 client IPs, the top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. Rich-colored terminal text is the default; JSON and CSV are stable pipeline formats.

The MVP is a $0, open-source, one-weekend delivery. It is intentionally not a monitoring server or observability platform.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call engineer | SRE responding to an incident | Needs a fast local summary before deciding where to investigate | One command over a file or stdin; no service setup |
| Platform engineer | Operates reverse proxies and CI jobs | Needs machine-readable summaries in shell pipelines | Deterministic `--json` and `--csv` output |
| Security-minded operator | Handles logs that cannot leave the laptop | SaaS upload and persistent indexing are unacceptable | Offline, stateless, read-only streaming analysis |

## 3. Problem and Positioning

The target user needs more structure than ad hoc shell commands but far less operational weight than an indexed analytics stack. The positioning is: **a safe, fast, zero-infrastructure nginx triage report that works both for humans and Unix pipelines.**

## 4. Competitive Analysis

| Alternative | Strength | Limitation for this use case | nginx-insight distinction |
|---|---|---|---|
| GoAccess | Mature interactive and HTML nginx analytics | Broader UI and configuration surface than a four-metric pipeline tool | Narrow stable output contract and Python/pip workflow |
| Logstash + Elastic + Kibana | Powerful persistent search and dashboards | Requires services, storage, setup, and ongoing operations | No database or server; immediate local result |
| AWStats | Established historical reports | Oriented toward generated reports and retained history | Single-run streaming triage and JSON/CSV output |
| `grep`/`awk`/`sort` | Ubiquitous and composable | Fragile parsing, duplicated recipes, high sort memory, no unified schema | One tested parser and consistent metrics/exit codes |

These are relevant alternatives, not claims of feature parity. The MVP wins on constrained scope and operational simplicity.

## 5. Value and Business Model

The project is open source and free. Its return is reduced incident-triage time, reproducible team workflows, and community trust; there is no paid tier, CAC, or revenue assumption in the MVP. Distribution is via a standard pip-installable package.

## 6. Technology Strategy

| Component | Choice | Why |
|---|---|---|
| Runtime | Python 3.11 | Required, portable, mature text-processing ecosystem |
| CLI | Click | Predictable argument validation, help, and exit handling |
| Human output | Rich | Readable colored tables with terminal-awareness |
| Domain state | Standard-library dataclasses | Explicit typed aggregation state without a framework |
| Parsing/aggregation | Standard library | Keeps install size and runtime overhead low |
| Packaging | `pyproject.toml`, pip | Standard install and console-script entry point |

## 7. Delivery Timeline

| Window | Outcome |
|---|---|
| Saturday morning | Package skeleton, CLI contract, nginx combined-log parser |
| Saturday afternoon | Streaming aggregators and exact metric semantics |
| Sunday morning | Rich, JSON, and CSV renderers; error/exit behavior |
| Sunday afternoon | Tests, 1 GB benchmark, packaging, documentation, release candidate |

The detailed dependency order is in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## 8. Success Metrics

| Metric | Release target | First month | Three months |
|---|---:|---:|---:|
| Processing time for representative 1 GB log on documented laptop baseline | <30 s | <30 s | <25 s where profiling supports it |
| Peak RSS on representative 1 GB log | Bounded by unique-key cardinality and documented cap | No unbounded regressions | 10% improvement if profiling identifies opportunity |
| Correctness fixture pass rate | 100% | 100% | 100% |
| Supported output formats | 3 | 3 | 3 stable formats |
| Install-to-first-report time | <2 min | <2 min | <1 min with release packaging |

The benchmark must record hardware, OS, Python version, input hash/size, elapsed time, and peak RSS; “laptop” alone is not reproducible evidence.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from combined format | High | High | Declare one exact MVP grammar, actionable line diagnostics, future custom-format parser boundary |
| High-cardinality IP/URL/User-Agent values exhaust memory | Medium | High | Configurable unique-cardinality cap, fail closed with exit code 4, benchmark adversarial data |
| Python misses the 1 GB/30 s target | Medium | High | Byte-efficient iteration, compile parser once, profile before optimizing, avoid per-line object retention |
| CSV representation is interpreted inconsistently | Medium | Medium | One normalized long-form schema with explicit metric/value/count/rank fields |
| Malformed lines silently distort results | Medium | High | Count and skip invalid lines, emit diagnostics separately, return partial-data exit code 3 |
| Terminal decoration contaminates pipelines | Low | High | Color only for terminal mode; stdout contains data, stderr contains diagnostics |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Open-source Python ecosystem |
| Hosting/database/cloud | $0 | None exists in the architecture |
| Distribution | $0 | Source repository and pip-compatible artifact |
| Delivery labor | One weekend | Explicit time constraint; no monetary spend assumed |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream combined-format logs from file or stdin | Must | Foundation for every metric and pipeline use case |
| Top 10 IPs | Must | Core incident-triage view |
| Top 10 URLs by 4xx/5xx errors | Must | Core failure-localization view |
| Hourly request distribution | Must | Core traffic-shape view |
| Unique User-Agent share | Must | Core client-diversity view |
| Rich terminal output | Must | Required default experience |
| JSON and CSV output | Must | Required pipeline contract |
| Explicit diagnostics and exit codes | Must | Required for reliable automation |
| Gzip input | Should | Common log-rotation convenience, not necessary for MVP value |
| `--no-color` override | Should | Useful for captured human output; terminal detection covers the baseline |
| Additional nginx log formats | Could | Valuable but expands parser/configuration scope |
| Approximate cardinality mode | Could | Could reduce memory, but compromises exactness and needs a new contract |
| Auth, database, HTTP API, server, cloud, Kubernetes | Won't | Explicitly outside the local stateless CLI product |

### RICE Scoring (Must and Should)

Scores use `(Reach × Impact × Confidence) / Effort`, with confidence as a decimal. They are directional planning inputs, not measured adoption data.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| JSON output | 8 | 4 | 90% | 0.35 | 82.3 |
| Explicit diagnostics and exit codes | 10 | 4 | 90% | 0.5 | 72.0 |
| `--no-color` override | 4 | 2 | 90% | 0.1 | 72.0 |
| CSV output | 7 | 4 | 85% | 0.35 | 68.0 |
| Rich terminal output | 10 | 3 | 90% | 0.5 | 54.0 |
| Stream parser and aggregation core | 10 | 5 | 90% | 1.0 | 45.0 |
| Four required metric views | 10 | 5 | 90% | 1.0 | 45.0 |
| Gzip input | 5 | 2 | 75% | 0.3 | 25.0 |

Implementation order also respects dependencies: a renderer cannot precede the parser merely because its isolated score is higher.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and acceptance criteria are reflected in [PRD.md](PRD.md).
- [ ] Python 3.11 code is formatted, type-checked, and has no syntax errors.
- [ ] Unit and integration tests pass with at least 90% line coverage for parser, aggregation, and renderers.
- [ ] Golden CLI tests cover terminal, JSON, CSV, and exit codes `0/1/2/3/4`.
- [ ] The representative 1 GB benchmark finishes in under 30 seconds on the recorded laptop baseline.
- [ ] Documentation and packaging metadata are current.
- [ ] No known Critical or High security issue remains.
- [ ] A review is accepted under the repository’s verification contract.

## 13. Kill and Re-scope Signals

- Stop the release if exact required metrics cannot be computed within the performance target on representative input.
- Re-scope the parser if representative logs cannot be parsed without per-install custom code.
- Defer non-Must work if the one-weekend constraint is threatened.
- Do not turn the tool into a hosted service to rescue adoption; validate the CLI value proposition first.
