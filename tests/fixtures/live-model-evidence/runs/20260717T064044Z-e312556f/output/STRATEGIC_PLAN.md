# Strategic Plan: Nginx Stream Report

## 1. Idea

Nginx Stream Report is a local, installable Python 3.11 CLI for DevOps and SRE engineers. It streams standard nginx combined access logs from a file or stdin and reports the top 10 client IPs, top 10 URLs producing 4xx/5xx responses, request distribution across 24 hours, and the count/share of unique User-Agents. Rich colored terminal output is the default; stable JSON and CSV make the same report suitable for automation.

The product optimizes for a narrow job: obtain useful incident and traffic-shape evidence from a large local log in one command, without deploying or operating an analytics service.

## 2. Target audience

| Persona | Role | Pain | Resolution |
|---|---|---|---|
| On-call SRE | triages production incidents | needs immediate traffic/error concentration data from an exported log | one-pass summary in under 30 seconds for 1 GB |
| DevOps engineer | automates operational checks | ad hoc shell parsing is fragile and hard to consume reliably | stable `--json` and `--csv` schemas with pipeline-safe stdout |
| Platform engineer | supports teams with constrained environments | full observability stacks are unavailable or unjustified | local pip install with no service, database, or network dependency |

## 3. Competitive analysis

| Alternative | What it does well | Weakness for this job | Nginx Stream Report distinction |
|---|---|---|---|
| GoAccess | mature interactive terminal/HTML nginx analytics | broader configuration and UI surface than a four-metric pipeline report | deliberately small command and stable JSON/CSV contract |
| Logstash + Elastic + Kibana | persistent ingestion, search, dashboards, multi-user history | costly setup and resources; needs services and storage | zero-service, zero-persistence, ad hoc local execution |
| AWStats | established historical web traffic reports | batch-oriented, persistent report workflow and older operational model | streaming stdin/file input and automation-first formats |
| `grep`/`awk`/`sort` | ubiquitous, composable, no installation in many environments | nginx quoting/timestamps are easy to parse incorrectly; multiple passes and locale-dependent output | one parser, one pass, tested metric semantics, deterministic ordering |

## 4. Unique value proposition

Turn a gigabyte nginx access log into four incident-ready metrics in one local, pipeline-safe command—without a database, server, or dashboard stack.

## 5. Business and licensing model

This is a free, open-source utility. There are no paid tiers, telemetry, hosted service, or monetization assumptions. Value is measured in engineer time saved, reliability of repeated analysis, and ease of adoption. An OSI-approved permissive license should be selected before the first public release.

## 6. Technology stack

| Component | Technology | Rationale |
|---|---|---|
| Runtime | Python 3.11 | approved, portable, fast enough subject to benchmark |
| CLI | Click | mature option validation, stdin/file conventions, test runner |
| terminal UX | Rich | readable tables, color/TTY behavior, safe rendering |
| domain model | dataclasses | typed, dependency-free report boundaries |
| aggregation | standard library `Counter`, `set`, `datetime` | exact metrics without storage or network services |
| packaging | `pyproject.toml` + pip wheel/sdist | standard local installation and console entry point |
| tests | pytest + Click test utilities | unit, integration, golden-output, and benchmark coverage |

Architecture details are fixed in `PROJECT_ARCHITECTURE.md`.

## 7. One-weekend timeline

| Window | Stage | Result |
|---|---|---|
| Friday evening | runway and contracts | package skeleton, fixtures, output schemas, benchmark harness |
| Saturday morning | parser and aggregation | valid/malformed parsing and all four metrics |
| Saturday afternoon | CLI and renderers | file/stdin plus terminal, JSON, and CSV output |
| Sunday morning | correctness and performance | test suite, file/stdin parity, 1 GB benchmark and profiling |
| Sunday afternoon | packaging and documentation | pip-installable artifact, usage/security notes, release checklist |

## 8. KPIs

| Metric | 1 month | 3 months | 6 months |
|---|---:|---:|---:|
| 1 GiB benchmark on reference laptop | `<30.0 s` | maintain `<30.0 s` | maintain `<30.0 s` |
| Correctness fixtures passing | 100% | 100% | 100% |
| Valid-input crash rate in fixture corpus | 0% | 0% | 0% |
| Machine-output schema regressions | 0 | 0 | 0 |
| Median clean install-to-first-report | `<2 min` | `<90 s` | `<60 s` |
| External adoption signal | 5 users | 25 users | 75 users |

The adoption figures are directional open-source validation goals, not revenue forecasts.

## 9. Risks

| Risk | Probability | Impact | Mitigation/trigger |
|---|---|---|---|
| Python parser misses the 1 GB/30 s target | Medium | High | benchmark early; profile timestamp/regex hot paths; optimize before considering multiprocessing |
| Exact User-Agent/IP sets consume high memory on adversarial cardinality | Medium | Medium | document complexity, record peak RSS, add an approximate P2 mode only from measured need |
| Real nginx formats differ from combined format | High | Medium | state the MVP grammar clearly; count malformed lines; consider configurable formats after corpus evidence |
| JSON/CSV semantics drift from terminal output | Medium | High | one report dataclass and golden cross-renderer tests |
| Sensitive IP/URL/User-Agent data leaks through redirected reports | Medium | High | no telemetry/networking, stderr hygiene, README privacy warning |
| Scope expands into a dashboard or observability platform | Medium | High | enforce Won't list and the CLI-only architecture decision |

## 10. Budget

| Item | One-time | Monthly | Comment |
|---|---:|---:|---|
| Development tools | $0 | $0 | Python and chosen libraries are open source |
| Runtime infrastructure | $0 | $0 | local CLI; no server, database, cloud, or Kubernetes |
| Package hosting | $0 | $0 | use a free public Python package index or local wheel |
| Test/benchmark hardware | $0 | $0 | existing laptop |
| Total cash budget | **$0** | **$0** | one-weekend contributor time is the only cost |

## 11. Feature roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| streaming file and stdin ingestion | **Must** | required for local logs and Unix pipelines without loading 1 GB into memory |
| combined-log parsing with malformed count | **Must** | all metrics depend on trustworthy, resilient parsing |
| top-10 IPs | **Must** | explicit core incident metric |
| top-10 4xx/5xx URLs | **Must** | explicit core failure-concentration metric |
| hourly request distribution | **Must** | explicit core traffic-shape metric |
| unique User-Agent count/share | **Must** | explicit core client-diversity metric |
| Rich terminal report | **Must** | approved default interaction |
| JSON and CSV output | **Must** | approved pipeline interfaces |
| performance benchmark and pip package | **Must** | delivery and performance are explicit constraints |
| configurable nginx log formats | **Should** | useful for real deployments, but combined format can validate MVP |
| gzip input | **Should** | common operational convenience; shell decompression is a viable MVP workaround |
| approximate unique counting | **Could** | limits cardinality memory only if evidence shows need |
| top-N option | **Could** | useful flexibility but top 10 is the approved contract |
| authentication/database/HTTP API/server/cloud/Kubernetes | **Won't** | explicitly excluded and contrary to the local stateless product |
| dashboards and historical trend storage | **Won't** | belongs to GoAccess/Elastic-class products, not this MVP |

### RICE scoring for Must and Should features

Confidence is represented as a fraction in the formula. Scores are planning estimates, not measured demand.

| Feature group | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| streaming parser + resilient input | 10 | 5 | 90% | 0.75 | 60.0 |
| core four-metric aggregation | 10 | 5 | 95% | 1.0 | 47.5 |
| JSON and CSV pipeline output | 8 | 4 | 90% | 0.5 | 57.6 |
| Rich terminal report | 9 | 4 | 90% | 0.5 | 64.8 |
| benchmark + pip packaging | 10 | 4 | 85% | 0.75 | 45.3 |
| configurable log format | 6 | 3 | 60% | 1.5 | 7.2 |
| gzip input | 6 | 2 | 80% | 0.5 | 19.2 |

Implementation order in `IMPLEMENTATION_PLAN.md` respects dependencies as well as RICE: the high-scoring Rich renderer cannot precede the parser/report model it consumes.

## 12. Definition of Done

A feature is Done only when:

- [ ] behavior and acceptance criteria in `PRD.md` are implemented without expanding the locked scope;
- [ ] Python 3.11 type/static checks configured by the project pass;
- [ ] unit and applicable CLI integration tests pass with project coverage at or above 90%;
- [ ] terminal, JSON, and CSV behavior remain consistent where applicable;
- [ ] code review passes at least 8/10 and no Critical/High security finding remains;
- [ ] README and schemas are updated;
- [ ] a clean virtual environment can build, install, and run the wheel;
- [ ] performance-sensitive changes include recorded benchmark evidence;
- [ ] no required verification is replaced by narrative.

Staging deployment is intentionally not part of this DoD because `PROJECT_ARCHITECTURE.md` forbids a server; the equivalent release verification is a clean local wheel install.

## 13. Kill and pivot criteria

- Stop release if the representative 1 GiB benchmark remains `>=30.0 s` after profiling and bounded optimization.
- Stop release if common combined-log fixtures cannot be parsed without silent metric corruption.
- Revisit exact unique counting if peak RSS exceeds an agreed laptop-safe threshold in the benchmark corpus.
- Do not pivot into persistent dashboards; recommend an established alternative instead.

