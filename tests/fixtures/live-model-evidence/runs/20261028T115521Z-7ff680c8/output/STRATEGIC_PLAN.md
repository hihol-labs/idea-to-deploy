# Strategic Plan: nginx-stream-report

## 1. Product Idea

`nginx-stream-report` is a local, pip-installable Python 3.11 CLI for DevOps and SRE engineers. It reads nginx access logs as a stream and produces an operational snapshot: top client IPs, URLs responsible for 4xx/5xx responses, hourly traffic percentages, and the share of unique User-Agents. It works without sending logs off the laptop or provisioning infrastructure.

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| On-call engineer | SRE/DevOps | Needs a fast incident overview from a large log | One command returns the four agreed indicators |
| Platform engineer | Infrastructure owner | Needs repeatable output for shell pipelines | Stable JSON and CSV schemas complement colored text |
| Security-minded operator | Systems administrator | Cannot upload sensitive access logs | All processing is local, read-only, and stateless |

## 3. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | Product differentiation |
|---|---|---|---|
| GoAccess | Mature, fast, interactive reports | Broader UI/configuration surface than a focused pipeline tool | Smaller contract, native JSON/CSV, pip install |
| Logstash + Elastic + Kibana | Powerful ingestion, storage, and dashboards | Operationally heavy, persistent, and costly for one-off local analysis | Zero services, zero persistence, immediate local result |
| AWStats | Established historical reports | Batch/report-server orientation and dated workflow | Stream-first CLI for current SRE workflows |
| `grep`/`awk` pipelines | Ubiquitous and flexible | Fragile parsing, hard-to-reuse metrics, inconsistent outputs | Tested nginx parsing and a stable metric contract |

## 4. Unique Value Proposition

Get a pipeline-friendly nginx incident summary from a gigabyte-scale local log in one command, without a database, server, or data egress.

## 5. Business Model

The project is open source and free. There is no monetization in the one-weekend scope; value is measured through operator time saved and community adoption. The license should be permissive (MIT or Apache-2.0, selected before publication).

## 6. Technology Stack

| Component | Technology | Rationale |
|---|---|---|
| Runtime | Python 3.11 | Required, widely available to target users |
| CLI | Click | Stable commands, options, validation, and exit behavior |
| Terminal UI | Rich | Readable colored tables with automatic non-TTY fallback |
| Data model | `dataclasses` | Typed records without validation-framework overhead |
| Packaging | `pyproject.toml` + pip | Standard install and console-script distribution |
| Tests | pytest | Fast unit, CLI, integration, and performance tests |

## 7. Timeline

| Period | Milestone | Result |
|---|---|---|
| Saturday morning | Package, parser, aggregation core | Valid lines stream into bounded counters |
| Saturday afternoon | Metrics and serializers | Text, JSON, and CSV contracts work |
| Sunday morning | CLI, error handling, tests | Complete exit codes and regression suite |
| Sunday afternoon | 1 GB benchmark, documentation, packaging | Release candidate meets the performance target |

## 8. KPIs

| Metric | Release target | Month 1 | Month 3 |
|---|---:|---:|---:|
| Processing time for 1 GB on reference laptop | <30 s | <30 s | <25 s |
| Peak RSS on 1 GB bounded-cardinality fixture | <250 MB | <250 MB | <200 MB |
| Valid-line parsing accuracy on fixtures | 100% | 100% | 100% |
| Install-to-first-report time | <5 min | <5 min | <3 min |
| Critical defects | 0 | 0 | 0 |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| nginx log formats differ from the supported combined format | High | High | Explicit format contract, malformed-line counts, representative fixtures |
| Exact unique User-Agent tracking exhausts memory on adversarial input | Medium | High | Configurable cardinality ceiling and exit code 4 before unsafe growth |
| Python misses the 1 GB/30 s target | Medium | High | Profile early; single-pass parsing; avoid per-line regex compilation and retained records |
| CSV representation of multiple report sections is ambiguous | Medium | Medium | One normalized schema with `section`, `key`, `count`, and `percentage` columns |
| Terminal color contaminates redirected output | Low | Medium | Enable color only for a TTY; JSON/CSV never contain ANSI sequences |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Development tools | $0 | Open-source Python toolchain |
| Runtime infrastructure | $0 | Local CLI; no hosted services |
| Distribution | $0 | Source repository and public package index |
| Total | $0 | One-weekend owner effort is the only input |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream nginx combined logs from file or stdin | **Must** | Foundation for every report and pipeline use |
| Top-10 client IPs | **Must** | Core incident indicator |
| Top-10 4xx/5xx URLs | **Must** | Locates failing routes |
| Hourly request distribution | **Must** | Reveals load shape; percentages use the PRD formula |
| Unique User-Agent share | **Must** | Required audience-diversity signal |
| Colored text, JSON, and CSV outputs | **Must** | Required human and pipeline interfaces |
| Malformed-line tolerance and diagnostics | **Must** | Real logs are imperfect |
| Configurable top-N and timezone normalization | **Should** | Useful extension, not needed for the agreed top-10 MVP |
| Additional nginx log formats | **Could** | Broadens adoption after the core is proven |
| Database, HTTP API, dashboards, auth, cloud, Kubernetes | **Won't** | Contradicts the local stateless CLI boundary |

### RICE Scoring (Must + Should)

| Feature | Reach (1-10) | Impact (1-5) | Confidence | Effort (person-days) | RICE Score |
|---|---:|---:|---:|---:|---:|
| Streaming parser and diagnostics | 10 | 5 | 90% | 1.0 | 45.0 |
| Top IP aggregation | 9 | 4 | 95% | 0.5 | 68.4 |
| Error URL aggregation | 9 | 5 | 95% | 0.5 | 85.5 |
| Hourly distribution | 8 | 4 | 90% | 0.5 | 57.6 |
| Unique User-Agent share and safety ceiling | 8 | 4 | 80% | 0.75 | 34.1 |
| Text/JSON/CSV rendering | 10 | 4 | 90% | 1.0 | 36.0 |
| Configurable top-N/timezone | 5 | 2 | 70% | 0.75 | 9.3 |

Dependency order takes precedence where a high-scoring report depends on the parser. Within each dependency layer, implementation follows descending RICE score.

## 12. Definition of Done

A feature is done when:

- [ ] Its behavior and output schema match `PRD.md` and `PROJECT_ARCHITECTURE.md`.
- [ ] Type checking/linting configured for the project pass.
- [ ] Unit and CLI tests pass, with at least 90% line coverage for parser, aggregation, and rendering modules.
- [ ] Integration tests pass for file input, stdin, text, JSON, CSV, malformed lines, and all exit codes.
- [ ] The 1 GB reference benchmark completes in under 30 seconds on the documented laptop and records peak RSS.
- [ ] Documentation is updated and contains no unresolved placeholders.
- [ ] No known critical or high-severity security issues remain.
- [ ] A local pip installation and smoke test succeed in a clean Python 3.11 environment.

## 13. Kill Criteria

Stop or rescope the MVP if a profiled single-pass implementation cannot process the reference 1 GB fixture under 30 seconds, exact unique-cardinality safety cannot be bounded predictably, or the agreed combined-log grammar cannot produce reliable metrics. Do not solve these failures by adding persistent or hosted infrastructure.

