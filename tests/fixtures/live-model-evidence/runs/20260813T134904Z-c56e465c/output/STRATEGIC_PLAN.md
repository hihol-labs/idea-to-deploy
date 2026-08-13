# Strategic Plan: Nginx Stream Insights

## 1. Product Idea

Nginx Stream Insights is a local, installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx combined access logs as a stream and reports top client IPs, URLs causing the most 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. It produces colored terminal output by default and stable JSON or CSV for pipelines.

The MVP is deliberately local and stateless: no log upload, account, daemon, database, or hosted service. This keeps operational risk and cost at zero while making one-off incident triage faster than ad hoc shell pipelines.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Diagnoses production incidents | Needs a useful traffic/error summary within minutes and may be working with a multi-gigabyte file | One command, streaming memory behavior, clear terminal rankings |
| DevOps engineer | Validates nginx changes and investigates abusive clients | Rewrites fragile `awk`/`sort` pipelines and struggles with quoting and status filtering | Repeatable parsing and predefined operational metrics |
| Platform engineer | Feeds local analysis into automation | Human-formatted tools are hard to compose safely | Stable `--json` and `--csv` schemas plus explicit exit codes |

## 3. Competitive Analysis

| Alternative | What it does well | Weakness for this use case | Our differentiation |
|---|---|---|---|
| GoAccess | Mature interactive and HTML nginx analytics | Broader UI/configuration surface than a quick four-metric summary; pipeline schema is not the core experience | Purpose-built, small Python CLI with predictable text/JSON/CSV output |
| Logstash + Elastic + Kibana | Powerful centralized ingestion, search, storage, and dashboards | Requires services, storage, setup, and ongoing operations; violates local zero-cost scope | No infrastructure or persistence; immediate local analysis |
| AWStats | Established historical web analytics | Batch/report orientation and dated operational workflow; usually needs configuration and generated reports | Incident-focused streaming summary directly in the terminal |
| `grep`/`awk`/`sort` | Ubiquitous, free, and flexible | Pipelines are easy to get subtly wrong, often reread/sort the full input, and lack a stable output contract | Tested nginx parsing, single-pass aggregation, defined error behavior |

## 4. Unique Value Proposition

Get an incident-ready nginx traffic and error summary from a local log in one command, without deploying or operating anything.

## 5. Business Model

The project is free and open source. There is no monetization, paid tier, telemetry, or hosted dependency in the MVP. Success is measured by reliability, adoption, and contributor usability rather than revenue; CAC, LTV, and unit economics are therefore not applicable. The chosen model honors the approved $0 budget and makes security review straightforward.

## 6. Technology Stack

| Component | Technology | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Approved, portable, and sufficiently fast with streaming I/O and a compiled regex |
| CLI | Click | Mature argument parsing, help text, validation, and conventional exit handling |
| Terminal presentation | Rich | Accessible tables and optional color without custom ANSI handling |
| Domain models | `dataclasses` | Typed records and result objects without a validation framework |
| Packaging | `pyproject.toml` + pip | Standard installable CLI and reproducible developer workflow |
| Testing | pytest | Fast unit/integration tests and fixture support |

See [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md) for module boundaries and data contracts.

## 7. Timeline

| Window | Work | Deliverable |
|---|---|---|
| Saturday morning | Package skeleton, CLI contract, parser | Installable command that validates input and streams valid records |
| Saturday afternoon | Aggregation and cardinality guard | Correct bounded counters and all four metrics |
| Sunday morning | Text, JSON, and CSV renderers | Stable output formats with no mixed diagnostic data on stdout |
| Sunday afternoon | Tests, benchmark, docs, polish | Release candidate validated against correctness and 1 GB performance target |

The detailed dependency order is in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## 8. KPIs

| Metric | Release target | 1 month | 3 months |
|---|---:|---:|---:|
| 1 GB processing time on reference laptop | < 30 seconds | Maintain | Maintain |
| Peak memory on cardinality-limit benchmark | Within documented bound | No regressions | No regressions |
| Correctness test pass rate | 100% | 100% | 100% |
| Valid-line throughput on reference fixture | >= 34 MB/s | Maintain | Improve by 10% only if measured |
| Unique users installing/running from public package | Not a release gate | 10 | 50 |
| Reported correctness defects | 0 known at release | <= 1 | 0 open high-severity |

Performance numbers must be measured on a named reference laptop and fixture; they are not assumed from design alone.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from combined format | Medium | High | State accepted format precisely, fail malformed lines predictably, test escaped fields, defer configurable formats |
| High-cardinality IP/URL/User-Agent data exhausts memory | Medium | High | Configurable unique-key ceiling, deterministic exit code `4`, benchmark adversarial input |
| Python misses the 1 GB/30 s target | Medium | High | Single pass, compiled parser, local bindings, no per-line Rich work, benchmark early and profile before optimization |
| CSV cannot naturally represent four heterogeneous sections | Medium | Medium | Define one long-form schema with a `metric` discriminator and stable columns |
| Terminal colors pollute redirected output | Low | Medium | Auto-disable color when stdout is not a TTY and support `--no-color` |
| Malformed-line handling hides damaged logs | Medium | Medium | Count skipped lines, report the count on stderr/text metadata, and support strict failure behavior |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python, Click, Rich, and pytest are open source |
| Hosting/database/cloud | $0 | None exists in the product architecture |
| Development | $0 cash | One weekend of contributor time |
| CI | $0 | Optional free open-source allowance; local verification remains authoritative |
| Distribution | $0 | pip-compatible source/wheel artifacts; publishing is optional |
| Total cash budget | **$0** | Hard constraint |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream nginx combined-log input from file or stdin | **Must** | Foundation for local and pipeline use |
| Top-10 client IPs by valid request count | **Must** | Core incident-triage metric |
| Top-10 URLs by 4xx/5xx response count | **Must** | Core error investigation metric |
| Hourly request distribution | **Must** | Required traffic-shape metric, calculated as `100 × hourly_request_count / total_valid_requests` |
| Unique User-Agent share | **Must** | Required client-diversity metric |
| Colored terminal, JSON, and CSV renderers | **Must** | Required human and pipeline interfaces |
| Cardinality guard and complete `0/1/2/3/4` exit codes | **Must** | Prevents uncontrolled memory use and enables automation |
| Gzip-compressed input | **Should** | Common operational convenience, but shell decompression works for MVP |
| Configurable top-N | **Should** | Useful beyond the required top 10 without changing aggregation |
| Configurable nginx log formats | **Could** | Broadens adoption but substantially increases parser scope |
| Live refresh UI | **Could** | Helpful for tailing, not needed for a final streamed report |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Explicitly excluded and contrary to the local stateless value proposition |

### RICE Scoring (Must + Should)

Confidence is expressed as a decimal in the formula `(Reach × Impact × Confidence) / Effort`. Scores order work by value while dependencies still take precedence.

| Feature | Reach (1–10) | Impact (1–5) | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming file/stdin parser | 10 | 5 | 90% | 0.75 | 60.0 |
| Top IPs | 9 | 4 | 95% | 0.25 | 136.8 |
| Error URLs | 9 | 5 | 95% | 0.30 | 142.5 |
| Hourly distribution | 8 | 3 | 95% | 0.20 | 114.0 |
| Unique User-Agent share | 7 | 3 | 85% | 0.35 | 51.0 |
| Three output renderers | 10 | 4 | 85% | 0.75 | 45.3 |
| Cardinality guard and exit codes | 8 | 5 | 80% | 0.50 | 64.0 |
| Configurable top-N | 5 | 2 | 80% | 0.15 | 53.3 |
| Gzip input | 5 | 2 | 85% | 0.25 | 34.0 |

Implementation begins with the parser despite higher standalone scores for dependent metrics. Within each dependency layer, the RICE order informs [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and acceptance criteria are represented in [PRD.md](PRD.md).
- [ ] Python 3.11 code imports and the package builds without errors.
- [ ] Unit tests pass with at least 90% branch coverage in parser, aggregation, and rendering modules.
- [ ] CLI integration and golden-output tests pass for text, JSON, and CSV.
- [ ] The 1 GB reference benchmark completes in under 30 seconds on the named laptop.
- [ ] Cardinality-exhaustion tests terminate with exit code `4` without partial machine-readable output.
- [ ] Code review is accepted and no known critical/high security issue remains.
- [ ] README and CLI help match the implemented contract.
- [ ] A local wheel installs in a clean Python 3.11 virtual environment and smoke tests pass.

## 13. Release and Kill Criteria

Ship the MVP only when every P0 acceptance criterion passes and the performance target is measured. Stop or re-scope the weekend release if the parser cannot reliably distinguish valid from malformed combined-log lines, bounded processing cannot be achieved for adversarial cardinality, or the reference 1 GB run remains at or above 30 seconds after profiling. No database, server, or cloud architecture may be added as a shortcut.
