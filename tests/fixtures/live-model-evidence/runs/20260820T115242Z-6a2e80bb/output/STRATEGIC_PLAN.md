# Strategic Plan: nginx-insight

## 1. Product Idea

`nginx-insight` is a local, pip-installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx combined access logs as a stream and produces an operational snapshot: top 10 client IPs, top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. Rich colored terminal output is the default; stable JSON and CSV modes support automation.

The MVP is intentionally local and stateless: no service to operate, credentials to manage, or data to retain. A one-weekend delivery and a $0 operating budget favor a focused CLI over a platform.

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| On-call SRE | Incident responder | Needs useful traffic signals before a dashboard or query is ready | Runs one local command against a log or stdin and gets the four agreed metrics |
| DevOps engineer | Service operator | Wants repeatable analysis in shell pipelines and CI jobs | Uses deterministic `--json` or `--csv` output and documented exit codes |
| Platform engineer | Tooling maintainer | Avoids deploying and securing another service | Installs a small open-source Python package with no runtime infrastructure |

## 3. Competitive Analysis

| Alternative | What it does | Weaknesses for this use case | nginx-insight difference |
|---|---|---|---|
| GoAccess | Fast interactive and HTML nginx analytics | Broader UI and configuration surface than a four-metric pipeline tool | Narrow command contract, Python packaging, and stable JSON/CSV output |
| Logstash + Elasticsearch + Kibana | Ingests, stores, searches, and visualizes logs at scale | Requires multiple services, storage, configuration, and operational budget | Zero-service local analysis for an immediate snapshot |
| AWStats | Generates historical web traffic reports | Batch/report-oriented and dated workflow; usually persists history | One-pass local analysis designed for terminals and pipelines |
| `grep`/`awk`/`sort` | Composable tools already present on Unix systems | Correct parsing, multiple metrics, malformed-line handling, and portable structured output require bespoke scripts | One tested command with explicit parsing and output semantics |

## 4. Unique Value Proposition

Get the four nginx incident metrics an SRE needs from a local log in one streaming command, with human-friendly output and pipeline-safe formats, without deploying infrastructure.

## 5. Business Model

The project is free and open source. There are no paid tiers, hosted components, or usage fees. Value is measured by adoption, reliability, and time saved during diagnosis rather than revenue; CAC and LTV are therefore not applicable to the MVP.

## 6. Technology Stack

| Component | Technology | Why |
|---|---|---|
| Runtime | Python 3.11 | Approved, portable, mature standard library |
| CLI | Click | Clear option validation, help text, and exit handling |
| Terminal presentation | Rich | Accessible colored tables with automatic non-TTY behavior |
| Data models | `dataclasses` | Typed, low-overhead records without an ORM |
| Parsing and aggregation | Python standard library | Keeps dependencies and install size small |
| Packaging | `pyproject.toml` + pip | Standard install and console-script entry point |
| Testing | pytest | Fast unit/integration tests and easy fixtures |

## 7. Timeline

| Window | Stage | Result |
|---|---|---|
| Saturday morning | Package, contracts, parser | Installable CLI skeleton and combined-log parser |
| Saturday afternoon | Streaming aggregation | All four metrics calculated in one pass |
| Sunday morning | Renderers and CLI integration | Rich, JSON, and CSV output with complete exit behavior |
| Sunday afternoon | Quality and release | Tests, benchmark evidence, documentation, and buildable package |

## 8. KPIs

| Metric | 1 month | 3 months | 6 months |
|---|---:|---:|---:|
| Valid 1 GB combined-log processing time on reference laptop | <30 s | <30 s | <25 s |
| Correctness fixture pass rate | 100% | 100% | 100% |
| Unhandled exceptions on supported inputs | 0 | 0 | 0 |
| GitHub stars (adoption proxy) | 25 | 100 | 250 |
| Release installs (adoption proxy) | 50 | 300 | 1,000 |

Performance is accepted only against a documented reference laptop, warm/cold-cache conditions, and a representative 1 GB fixture; the timing target is not claimed from design alone.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from combined format | High | High | Make supported syntax explicit; fail or count malformed lines consistently; defer configurable formats |
| High-cardinality IPs, URLs, or User-Agents consume memory | Medium | High | Stream raw input, set and document a User-Agent cardinality limit, benchmark representative and adversarial fixtures |
| Python misses the 1 GB / 30 s target | Medium | High | Keep the hot loop allocation-light, profile before optimizing, and preserve a representative benchmark |
| Color or progress output corrupts pipelines | Low | High | Put reports on stdout, diagnostics on stderr, disable decoration for JSON/CSV and non-TTY contexts |
| CSV representation becomes ambiguous across multiple metrics | Medium | Medium | Use a normalized schema with metric, rank/bucket, value, count, and percentage columns |
| A broad feature set exceeds one weekend | Medium | Medium | Enforce MoSCoW scope and ship only Must items |

## 10. Budget

| Item | One-time | Monthly | Comment |
|---|---:|---:|---|
| Development tools | $0 | $0 | Open-source stack and existing laptop |
| Runtime infrastructure | $0 | $0 | Local CLI; no server or database |
| Package hosting | $0 | $0 | Public Python package index and source hosting |
| Domain, monitoring, paid APIs | $0 | $0 | Not required |
| Total | $0 | $0 | Meets approved budget |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream combined logs from files or stdin | **Must** | Foundation for local and pipeline use |
| Top 10 client IPs | **Must** | Required operational metric |
| Top 10 error URLs (4xx/5xx) | **Must** | Required failure-localization metric |
| Hourly request distribution | **Must** | Required traffic-shape metric |
| Unique User-Agent share | **Must** | Required client-diversity metric |
| Rich terminal, JSON, and CSV renderers | **Must** | Required interactive and pipeline interfaces |
| Explicit malformed-input and exit-code behavior | **Must** | Required for automation and trustworthy results |
| Configurable top-N | **Should** | Useful extension after the fixed top-10 MVP |
| Follow a growing file | **Should** | Helpful for live incidents but complicates completion semantics |
| Custom nginx `log_format` templates | **Could** | Broadens compatibility but is too large for the weekend MVP |
| GeoIP, dashboards, and stored history | **Won't** | Conflicts with $0 stateless local scope |
| Authentication, database, HTTP API, cloud, or Kubernetes | **Won't** | Explicitly excluded and adds no MVP value |

### RICE Scoring (Must + Should)

Confidence is expressed as a decimal in the calculation. Scores are planning estimates, not measured usage data.

| Feature | Reach (1–10) | Impact (1–5) | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Stream files/stdin + parse combined format | 10 | 5 | 90% | 0.75 | 60.0 |
| Top 10 error URLs | 10 | 5 | 90% | 0.50 | 90.0 |
| Top 10 client IPs | 9 | 4 | 90% | 0.35 | 92.6 |
| Hourly request distribution | 9 | 4 | 90% | 0.35 | 92.6 |
| Unique User-Agent share + limit | 8 | 4 | 80% | 0.50 | 51.2 |
| Rich/JSON/CSV renderers | 10 | 4 | 85% | 0.75 | 45.3 |
| Error and exit-code contract | 10 | 5 | 90% | 0.50 | 90.0 |
| Configurable top-N | 4 | 2 | 70% | 0.25 | 22.4 |
| Follow a growing file | 5 | 3 | 60% | 0.75 | 12.0 |

Implementation order follows dependencies first, then the descending RICE signal among unblocked features. For example, parsing must precede its higher-scoring aggregations.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and acceptance criteria are reflected in `PRD.md`.
- [ ] Python 3.11 code is formatted, type-checked, and imports without errors.
- [ ] Unit tests pass with at least 90% line coverage for parser, aggregation, and renderers.
- [ ] CLI integration tests pass for terminal, JSON, CSV, stdin, malformed input, and exit codes `0/1/2/3/4`.
- [ ] The representative 1 GB benchmark completes under 30 seconds on the documented reference laptop.
- [ ] Code review is accepted and no known Critical or High security issue remains.
- [ ] `README.md`, CLI help, and examples match observed behavior.
- [ ] A wheel builds and installs in a clean Python 3.11 environment.

## 13. MVP Kill Criteria

Re-scope or stop the MVP if, after profiling and one focused optimization pass, representative 1 GB logs cannot be processed in 30 seconds on the reference laptop; if exact required metrics cannot fit within a documented laptop memory envelope; or if reliable combined-log parsing requires a configuration language too large for a one-weekend release.

