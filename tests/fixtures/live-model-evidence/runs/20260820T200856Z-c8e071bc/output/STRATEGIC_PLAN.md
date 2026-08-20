# Strategic Plan: nginx-report

## 1. Product Idea

`nginx-report` is a local, pip-installable Python 3.11 command-line tool for DevOps and SRE engineers. It streams nginx access logs from a file or standard input and produces four operational views: the top 10 client IPs, the top 10 request targets returning 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. Human-readable colored terminal output is the default; JSON and CSV provide stable pipeline interfaces.

The MVP is deliberately local and stateless. It does not authenticate users, retain logs, expose a network service, or require infrastructure. Its performance objective is to process a representative 1 GB access log in under 30 seconds on a documented laptop baseline.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Diagnoses incidents under time pressure | Needs a quick traffic and error summary without standing up a platform | One command, streaming input, useful terminal defaults |
| DevOps engineer | Builds shell-based operational workflows | Existing ad hoc parsing is fragile and output formats vary | Stable `--json` and `--csv` contracts with meaningful exit codes |
| Platform engineer | Reviews logs locally or in restricted environments | Central log systems may be unavailable, expensive, or inappropriate | Offline execution, no data upload, zero runtime services |

## 3. Problem and Value Proposition

Teams frequently need a bounded answer from a large nginx log before a full observability stack is available or justified. General-purpose shell pipelines are fast to start but difficult to make correct around quoting, malformed records, timestamps, deterministic ties, and machine-readable output.

**Unique value proposition:** obtain deterministic, pipeline-safe nginx traffic and error summaries locally in one command, with no service, database, account, or operating cost.

## 4. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | nginx-report distinction |
|---|---|---|---|
| GoAccess | Mature, fast, interactive terminal and HTML analytics | Broader feature surface and presentation model than a small pipeline command needs | Narrow four-metric contract and simple JSON/CSV automation |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, search, dashboards, and retention | Infrastructure, memory, setup, and operational cost are disproportionate for local one-shot analysis | No daemon, persistence, network, or deployment |
| AWStats | Established historical reporting | Oriented toward generated reports and accumulated statistics rather than stdin pipelines | Immediate streaming analysis and modern machine-readable output |
| `grep` / `awk` / `sort` | Ubiquitous and composable | Correct parsing is format-sensitive; multiple passes and locale-dependent sorting are easy to introduce | One validated parser, one pass, deterministic schemas and failures |

## 5. Business Model and Budget

The product is free and open source. There is no hosted tier, telemetry, advertising, or paid dependency. Value is measured through engineering time saved and operational reliability rather than revenue.

| Item | Cost | Notes |
|---|---:|---|
| Python, Click, Rich, standard library | $0 | Open-source stack |
| Source hosting and public package publishing | $0 | Free public tiers |
| Development | $0 cash | One weekend of maintainer time |
| Runtime infrastructure | $0 | Runs on the user's laptop |
| Total cash budget | **$0** | No cloud or service commitments |

## 6. Technology Strategy

| Component | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Required platform; productive delivery within one weekend |
| CLI | Click | Mature option validation, help, file/stdin handling, and exit behavior |
| Terminal UI | Rich | TTY-aware color and readable tables |
| Domain models | `dataclasses` | Explicit lightweight records without a framework |
| Aggregation | Standard-library counters, fixed buckets, and sets | Single-process streaming with no external state |
| Packaging | `pyproject.toml`, pip, console script | Familiar local installation and reproducible entry point |

## 7. Feature Roadmap

### MoSCoW Prioritization

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream combined-format logs from a file or stdin | **Must** | Without bounded-memory streaming input, the core use case and performance target fail |
| Top 10 client IPs | **Must** | Required operational view |
| Top 10 request targets by 4xx/5xx count | **Must** | Required error-diagnosis view |
| Hourly request percentage distribution | **Must** | Required traffic-shape view |
| Unique User-Agent share | **Must** | Required client-diversity view |
| Colored terminal, JSON, and CSV renderers | **Must** | Human and pipeline outputs are explicit product requirements |
| Malformed-line accounting and stable exit codes | **Must** | Prevents silently trustworthy-looking results |
| Configurable top-N and cardinality limits | **Should** | Useful control, while defaults can ship first |
| Gzip input | **Could** | Convenient, but shell decompression already provides a workaround |
| Additional nginx log formats | **Could** | Broadens adoption after the combined-format MVP is proven |
| Database, HTTP API, auth, server, cloud, Kubernetes | **Won't** | Contradicts the local stateless product and budget |
| Live dashboard or historical retention | **Won't** | Belongs to established observability platforms, not this MVP |

### RICE Scoring for Must and Should Features

Scores use `(Reach × Impact × Confidence) / Effort`, with confidence as a decimal. They are planning estimates for the first month, not measured adoption data.

| Feature | Reach (1–10) | Impact (1–5) | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Stream file/stdin and parse combined format | 10 | 5 | 90% | 0.75 | 60.0 |
| Top client IPs and error request targets | 10 | 5 | 90% | 0.75 | 60.0 |
| Hourly distribution and User-Agent share | 9 | 4 | 90% | 0.50 | 64.8 |
| Terminal, JSON, and CSV renderers | 10 | 5 | 85% | 1.00 | 42.5 |
| Malformed-line accounting and exit codes | 9 | 5 | 90% | 0.50 | 81.0 |
| Configurable top-N and cardinality limits | 6 | 3 | 70% | 0.25 | 50.4 |

Dependency order takes precedence where a high RICE item requires the parser or aggregation core. The implementation sequence is therefore contracts and parser, aggregation, renderers, then packaging and performance verification.

## 8. Delivery Timeline

| Window | Outcome |
|---|---|
| Saturday morning | Package skeleton, CLI contract, data models, combined-log parser |
| Saturday afternoon | Streaming aggregation and all four metrics |
| Sunday morning | Text, JSON, and CSV rendering; error and exit behavior |
| Sunday afternoon | Tests, 1 GB benchmark, packaging, and documentation polish |

## 9. Success Metrics

| Metric | MVP / first month target | Three-month target | Measurement |
|---|---:|---:|---|
| Representative 1 GB processing time | < 30 seconds | Maintain < 30 seconds | Versioned local benchmark on documented laptop |
| Valid fixture correctness | 100% expected aggregates | No regression | Automated unit and end-to-end tests |
| Peak resident memory | < 512 MiB on representative benchmark | Maintain or improve | Benchmark process RSS |
| Machine-output stability | JSON/CSV golden tests pass | No unannounced breaking change | Schema/golden tests |
| Installation smoke test | Fresh Python 3.11 venv succeeds | Maintained per release | CI package install and invocation |

## 10. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from combined format | Medium | High | State the supported grammar, reject/account for malformed lines, add format extensibility later |
| High cardinality causes excessive memory use | Medium | High | Configurable exact-cardinality guard; fail with exit code `4` instead of returning an inexact share |
| Python misses the 1 GB / 30-second target | Medium | High | Avoid per-line regex recompilation and object retention; benchmark representative data before release |
| JSON/CSV changes break pipelines | Medium | High | Version and golden-test stable schemas; deterministic ordering |
| Terminal color contaminates redirected output | Low | Medium | Enable color only for TTY output and provide `--no-color` |
| Malformed data creates misleading percentages | Medium | High | Base metrics only on valid requests and report invalid-line count |

## 11. Kill and Reassessment Criteria

Pause release and reconsider implementation if a representative 1 GB log cannot meet 30 seconds after profiling, exact metrics cannot stay within the documented memory guard, or combined-format parsing cannot reach deterministic fixture correctness. Do not solve these failures by adding a database or hosted service; reassess language/runtime or narrow the input contract first.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and acceptance criteria are reflected in `PRD.md` and `PROJECT_ARCHITECTURE.md`.
- [ ] Python 3.11 code is formatted, statically checked, and installs from a built wheel.
- [ ] Unit and end-to-end tests pass with at least 90% line coverage for parser, aggregation, and renderers.
- [ ] JSON and CSV schemas have deterministic golden tests.
- [ ] The representative 1 GB benchmark meets the documented time and memory targets.
- [ ] No known critical or high-severity security issue remains.
- [ ] User and implementation documentation is current.
- [ ] The package is manually verified in a fresh local virtual environment; no staging deployment applies to this local-only CLI.

## 13. Document Map

The product contract is in `PRD.md`; technical decisions and interfaces are in `PROJECT_ARCHITECTURE.md`; sequencing is in `IMPLEMENTATION_PLAN.md`; and step prompts are in `CLAUDE_CODE_GUIDE.md`.
