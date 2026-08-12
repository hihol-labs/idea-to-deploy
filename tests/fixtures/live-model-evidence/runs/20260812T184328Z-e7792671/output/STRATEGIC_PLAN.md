# Strategic Plan: nginx-insights

## 1. Product Idea

`nginx-insights` is a local, installable Python 3.11 CLI for DevOps and SRE engineers. It reads an nginx combined access-log stream once and reports the top 10 client IPs, the top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agent values. Its default presentation is colored terminal text, while JSON and CSV modes provide deterministic, machine-readable output for pipelines.

The MVP is deliberately narrow: a stateless process, no network listeners, no persistent state, and no paid infrastructure. It is intended to be built over one weekend and released as open source.

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| On-call SRE | Diagnoses incidents from a shell | Needs a useful traffic/error summary before a full observability query is available | Produces the four agreed views with one local command |
| DevOps engineer | Maintains nginx hosts and CI jobs | Wants pipe-safe output without operating another service | Reads files or stdin and emits JSON/CSV with stable schemas |
| Backend engineer | Investigates an application regression | Grep/awk pipelines are slow to compose and easy to miscount | Uses a tested combined-log parser and explicit invalid-line accounting |

## 3. Competitive Analysis

| Alternative | What it does | Weakness for this use case | Our distinction |
|---|---|---|---|
| GoAccess | Rich interactive and HTML nginx analytics | Broader UI and configuration surface than a four-metric pipeline tool | Smaller CLI contract and first-class JSON/CSV output |
| Logstash + Elasticsearch + Kibana | Centralized ingestion, search, storage, and dashboards | Operationally heavy, stateful, and costly for a local one-off analysis | Zero-service, stateless, local execution |
| AWStats | Persistent web analytics and generated reports | Oriented to historical reports and configured deployments | Immediate one-pass terminal analysis |
| grep/awk/sort | Ubiquitous ad hoc shell analysis | Brittle parsing, repeated passes, locale variance, and hard-to-reuse schemas | One tested pass with stable definitions and exit codes |

These are alternatives, not dependencies. The project does not attempt to replace centralized observability or long-term analytics.

## 4. Unique Value Proposition

Get a dependable, pipeline-friendly nginx incident snapshot from a local stream in one command, without deploying or paying for anything.

## 5. Business Model

The MVP is free and open source. There are no paid tiers, hosted services, telemetry, or commercial dependencies. Development budget is $0; contribution value comes from reduced incident-analysis time. If the tool gains users, maintenance remains community-driven and any future commercial packaging requires a separate product decision.

## 6. Technology Stack

| Component | Technology | Why |
|---|---|---|
| Runtime | Python 3.11 | Approved target; widely available to operators |
| CLI | Click | Clear option validation, help text, and exit handling |
| Terminal rendering | Rich | TTY-aware color and readable tables |
| Domain models | `dataclasses` | Lightweight typed records without runtime framework overhead |
| Aggregation | Python standard library (`collections`, `datetime`, `csv`, `json`) | One-pass implementation with no service dependencies |
| Packaging | `pyproject.toml` and pip | Standard install and console-script workflow |
| Quality | pytest, Ruff, mypy | Fast local tests and static checks |

## 7. Timeline

| Window | Stage | Result |
|---|---|---|
| Friday evening | Contract and package skeleton | CLI surface, schemas, fixtures, and quality gates fixed |
| Saturday morning | Parser and stream pipeline | Valid/invalid line handling and all aggregators work |
| Saturday afternoon | Renderers | Rich, JSON, and CSV outputs conform to one result model |
| Sunday morning | Performance and fault behavior | 1 GB benchmark, bounded cardinality, and exit codes verified |
| Sunday afternoon | Packaging and documentation | Pip-installable release candidate with usage examples |

## 8. KPIs

| Metric | Release target | 1 month | 3 months |
|---|---:|---:|---:|
| Processing time for a representative 1 GB combined log on the reference laptop | <30 s | <30 s | <25 s if profiling supports it |
| Peak resident memory on that benchmark | <512 MiB before configured cardinality guard | Same | Same or lower |
| Correctness fixtures passing | 100% | 100% | 100% |
| Supported output contracts passing golden tests | 3/3 | 3/3 | 3/3 |
| Median time from install to first report in usability check | <5 min | <5 min | <3 min |
| Critical/high known security defects | 0 | 0 | 0 |

Performance claims are accepted only against a recorded laptop specification, generated fixture profile, command, elapsed time, and peak RSS.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from the supported combined format | High | Medium | State the grammar, count malformed lines, provide an invalid-line policy, and defer custom formats |
| High-cardinality values exhaust memory | Medium | High | Enforce `--max-unique`, stop deterministically, and return exit code 4 |
| Python misses the 1 GB / 30 s target | Medium | High | Use one pass, avoid per-line regex recompilation, benchmark early, and profile before optimizing |
| CSV encoding of multiple report sections is ambiguous | Medium | Medium | Publish one normalized row schema with a `section` discriminator |
| Broken pipes or unreadable files produce misleading partial success | Medium | High | Centralize error mapping and never emit a successful report after an I/O failure |
| Colored output contaminates redirected pipelines | Low | Medium | Enable color only for the Rich terminal mode and a compatible TTY; JSON/CSV never contain ANSI escapes |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Open-source Python ecosystem |
| Infrastructure | $0 | Local CLI; no server or database |
| Development | $0 cash | One weekend of contributor time |
| CI | $0 | Optional free open-source allowance; local gates remain authoritative |
| Distribution | $0 | Source repository and standard Python package metadata |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| One-pass parsing of nginx combined logs from a file or stdin | **Must** | Every report depends on a bounded-memory stream reader |
| Top-10 client IPs | **Must** | Core incident and traffic view |
| Top-10 error URLs for 4xx/5xx | **Must** | Core application-error view |
| Hourly request distribution | **Must** | Core load-shape view |
| Unique User-Agent share | **Must** | Core client-diversity view |
| Rich, JSON, and CSV renderers | **Must** | Explicit human and pipeline output contract |
| Deterministic malformed-input, I/O, and cardinality handling | **Should** | Required for dependable automation but can follow the happy-path slice |
| Pip packaging, quality gates, and performance benchmark | **Should** | Required for release readiness |
| `tail -f`-style indefinite follow mode | **Could** | Useful operational polish, but finite stdin already supports streaming producers |
| Database, HTTP API, authentication, server, cloud, or Kubernetes | **Won't** | Explicitly out of scope and contrary to the local stateless product |
| Arbitrary nginx `log_format` configuration | **Won't** | Too large for the one-weekend MVP; combined format is the fixed contract |

### RICE Scoring (Must + Should)

Scores use `(Reach × Impact × Confidence) / Effort`, with confidence expressed as a decimal.

| Feature | Reach (1–10) | Impact (1–5) | Confidence | Effort (person-days) | RICE Score |
|---|---:|---:|---:|---:|---:|
| One-pass combined-log parser and stream reader | 10 | 5 | 90% | 0.75 | 60.0 |
| Top-10 IP aggregation | 9 | 4 | 95% | 0.25 | 136.8 |
| Hourly request distribution | 8 | 4 | 95% | 0.25 | 121.6 |
| Top-10 error URL aggregation | 9 | 5 | 95% | 0.40 | 106.9 |
| Unique User-Agent share and guard | 7 | 3 | 85% | 0.35 | 51.0 |
| Rich, JSON, and CSV renderers | 10 | 4 | 85% | 0.75 | 45.3 |
| Deterministic failure handling | 9 | 5 | 90% | 0.50 | 81.0 |
| Packaging, quality gates, and benchmark | 8 | 4 | 85% | 0.75 | 36.3 |

Dependency order overrides a higher isolated score: the parser must precede all aggregators, and the shared result model must precede renderers. Within those constraints, implementation follows descending RICE value.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and acceptance criteria in [PRD.md](PRD.md) are satisfied.
- [ ] Python 3.11 code is formatted, linted, type-checked, and importable.
- [ ] Unit tests and relevant CLI integration tests pass; total coverage is at least 90%.
- [ ] Golden-output tests pass for every affected renderer.
- [ ] No known critical or high security issue remains.
- [ ] User-facing changes are reflected in help text and documentation.
- [ ] The exact performance candidate passes the recorded 1 GB / 30 s benchmark when performance is affected.
- [ ] Review evidence is recorded for the exact candidate.

The release is Done only when the pip-installed console script passes smoke tests on Python 3.11 and all exit-code paths `0/1/2/3/4` are exercised.

## 13. Success and Stop Conditions

Proceed to an MVP release when all P0 requirements pass and the reference benchmark completes under 30 seconds. Re-scope or stop if Python cannot meet the target after profiling, exact aggregation cannot remain within the declared guard on representative logs, or the weekend scope expands to require a persistent service. See [PRD.md](PRD.md) for explicit kill criteria and [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for delivery order.
