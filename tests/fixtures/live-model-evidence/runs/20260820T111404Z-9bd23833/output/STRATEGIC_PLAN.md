# Strategic Plan: Nginx Stream Analytics CLI

## 1. Product Idea

Build an open-source, local Python 3.11 command-line tool for DevOps and SRE engineers that reads nginx access logs as a stream and emits an immediately useful operational summary. It reports the top 10 client IPs, the top 10 URLs producing 4xx/5xx responses, hourly request distribution, and the share of unique User-Agents. The default is colored terminal text, with deterministic JSON and CSV modes for pipelines.

The MVP is deliberately local and stateless: no authentication, database, HTTP API, server, cloud service, or Kubernetes. It must process a 1 GB log in under 30 seconds on a representative laptop while keeping memory independent of file size except for explicitly bounded aggregation state and guarded unique-cardinality tracking.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Diagnoses incidents from a shell | Needs a useful snapshot before a dashboard or log platform is available | One command produces the four core signals without an external service |
| DevOps engineer | Operates nginx fleets and automation | Ad hoc `awk` pipelines are fragile and difficult to integrate consistently | Stable parsing, exit codes, JSON, and CSV provide a repeatable contract |
| Platform engineer | Supports developer teams | Full observability stacks are excessive for local files and quick triage | Pip-installable, zero-service tool with bounded operational scope |

## 3. Competitive Analysis

| Alternative | What it does well | Weakness for this use case | Product differentiation |
|---|---|---|---|
| GoAccess | Fast, mature interactive nginx analytics | Larger report surface and interactive/dashboard orientation can be more than a pipeline needs | Four focused metrics, explicit pipeline formats, Python-native installation |
| Logstash + Elasticsearch + Kibana | Powerful ingestion, storage, querying, and dashboards | Requires services, configuration, resources, and ongoing operations | Zero-service, stateless analysis for a local file or stdin |
| AWStats | Established historical web-log reporting | Batch/reporting workflow and persistent artifacts are poorly suited to quick shell triage | Streaming execution and modern JSON/CSV contracts |
| `grep` / `awk` / `sort` | Ubiquitous and flexible | Parsing is easy to get wrong; multiple passes and locale-dependent output reduce repeatability | One tested parser, one pass, stable semantics and exit codes |

## 4. Unique Value Proposition

Turn a local nginx access log into four incident-ready signals in one fast, dependency-light command, with human-readable output and automation-safe formats.

## 5. Business Model

The project is free and open source. There are no paid tiers, hosted services, telemetry, or usage fees. Success is measured through usefulness, correctness, adoption, and maintainability rather than revenue; CAC and LTV are therefore not applicable to the one-weekend MVP.

## 6. Technology Stack

| Component | Technology | Why |
|---|---|---|
| Runtime | Python 3.11 | Approved, widely available, productive for a weekend delivery |
| CLI | Click | Mature argument parsing, stdin/file handling, and predictable usage errors |
| Terminal UI | Rich | Colored, readable tables and explicit terminal capability handling |
| Data models | `dataclasses` | Typed internal records without a validation framework |
| Packaging | `pyproject.toml` + pip | Standard install and console-script distribution |
| Tests | pytest | Fast unit, integration, golden-output, and performance-contract tests |

## 7. Timeline

| Period | Stage | Result |
|---|---|---|
| Friday evening | Contract and scaffold | Package, CLI skeleton, fixtures, output schemas, benchmark protocol |
| Saturday morning | Streaming core | Combined/common parsing, counters, top-10 aggregation, error handling |
| Saturday afternoon | Reporters | Rich text, JSON, CSV, deterministic ordering |
| Sunday morning | Verification | Unit/integration tests, malformed-input cases, cardinality guard |
| Sunday afternoon | Performance and release | 1 GB benchmark, documentation, wheel/sdist smoke test |

## 8. KPIs

| Metric | Launch target | Month 1 target | Month 3 target |
|---|---:|---:|---:|
| 1 GB processing time on reference laptop | < 30 s | < 30 s | < 25 s |
| Valid combined/common fixture accuracy | 100% | 100% | 100% |
| P0 automated acceptance tests passing | 100% | 100% | 100% |
| Peak aggregation memory on standard benchmark | < 256 MB | < 256 MB | < 192 MB |
| Confirmed successful real-world log samples | 2 | 10 | 30 |

The reference-laptop CPU, memory, OS, storage, Python version, cold/warm-cache state, and benchmark generator seed must be recorded with results so the time target is reproducible rather than a marketing claim.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Regex parsing is too slow for 1 GB / 30 s | Medium | High | Use a compiled, anchored parser; profile representative input; avoid per-line object churn |
| Unbounded distinct IP, URL, or User-Agent values exhaust memory | Medium | High | Define memory guards; fail explicitly with exit code 4 for unique-cardinality exhaustion; benchmark adversarial cardinality |
| nginx custom log formats are mistaken for supported input | High | Medium | Support only documented common/combined formats in MVP and count malformed records; reject zero-valid-record inputs |
| CSV cannot naturally represent four differently shaped reports | Medium | Medium | Specify a normalized row schema with a `section` discriminator |
| Pipeline consumers depend on unstable ordering | Medium | High | Define deterministic tie-breaks and versioned JSON/CSV schemas |
| Colored output contaminates redirected output | Low | Medium | Color only the text reporter and respect terminal capability / `NO_COLOR`; structured output never contains ANSI escapes |

## 10. Budget

| Item | Cost | Notes |
|---|---:|---|
| Software and libraries | $0 | Python, Click, Rich, and pytest are open source |
| Hosting and infrastructure | $0 | Local-only CLI; no services |
| Distribution | $0 | Build locally; publish to PyPI only if a free account is used later |
| Labor | One weekend | Scope is fixed; no monetary spend approved |
| Total cash budget | **$0** | Hard constraint |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream common/combined logs from a file or stdin | **Must** | Foundation for local and pipeline use |
| Top 10 client IPs | **Must** | Core incident signal |
| Top 10 URLs by combined 4xx/5xx count | **Must** | Core failure signal |
| Hourly request percentage distribution | **Must** | Core traffic-shape signal |
| Unique User-Agent share | **Must** | Core client-diversity signal |
| Colored terminal report | **Must** | Approved default experience |
| JSON output | **Must** | Required pipeline contract |
| CSV output | **Must** | Required pipeline contract |
| Deterministic malformed-line diagnostics and exit codes `0/1/2/3/4` | **Must** | Required for trustworthy automation |
| `.gz` input | **Should** | Common operational convenience, but shell decompression is an MVP workaround |
| Configurable top-N | **Could** | Useful flexibility outside the fixed top-10 requirement |
| Custom nginx `log_format` parser | **Could** | Broadens compatibility but materially increases parser scope |
| Authentication, database, HTTP API, server, cloud, Kubernetes | **Won't** | Conflicts with the local, stateless CLI value proposition |
| Live dashboard and historical persistence | **Won't** | Belongs to GoAccess or an observability stack, not this MVP |

### RICE Scoring (Must and Should)

Confidence is expressed as a decimal in the calculation.

| Feature group | Reach (1–10) | Impact (1–5) | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Streaming parser + file/stdin contract | 10 | 5 | 90% | 1.0 | 45.0 |
| Top-IP and error-URL aggregations | 10 | 5 | 90% | 1.0 | 45.0 |
| Hourly distribution + User-Agent share | 9 | 4 | 85% | 0.75 | 40.8 |
| Stable `0/1/2/3/4` errors and malformed-line handling | 10 | 5 | 90% | 1.25 | 36.0 |
| Rich terminal output | 9 | 3 | 90% | 0.75 | 32.4 |
| JSON and CSV reporters | 8 | 4 | 90% | 1.0 | 28.8 |
| `.gz` input | 6 | 2 | 75% | 0.5 | 18.0 |

Implementation order follows dependency constraints first, then descending RICE within the available dependency frontier.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and edge cases match `PRD.md` and `PROJECT_ARCHITECTURE.md`.
- [ ] Code runs on Python 3.11 and packaging metadata builds without errors.
- [ ] Unit and integration tests pass with at least 90% branch coverage in parser, aggregation, and reporter modules.
- [ ] P0 acceptance tests pass, including all exit codes `0/1/2/3/4`.
- [ ] Text, JSON, and CSV golden-output tests pass without nondeterministic ordering.
- [ ] The recorded reference-laptop benchmark processes 1 GB in under 30 seconds.
- [ ] An adversarial-cardinality test proves controlled exit code 4 rather than an uncontrolled memory failure.
- [ ] Documentation and CLI help are current.
- [ ] No known Critical or High security issues remain.
- [ ] A wheel and sdist install into a clean Python 3.11 environment and the console command passes a smoke test.

## 13. Strategic Boundaries and Kill Criteria

Stop or rescope the MVP if the selected Python parser cannot meet the reproducible 1 GB / 30 s target after profiling and one focused optimization pass; if exact unique User-Agent tracking cannot remain safe under the documented guard; or if supporting real target logs requires arbitrary custom-format parsing. Do not hide these failures by adding services, persistence, or a different architecture without revising this plan and `PROJECT_ARCHITECTURE.md`.
