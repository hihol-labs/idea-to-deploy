# Strategic Plan: nginx Stream Analytics CLI

## 1. Product Idea

Build a local, pip-installable Python 3.11 command-line tool for DevOps and
SRE engineers who need an immediate operational summary of nginx access logs.
It reads a file or standard input once, keeps only in-process aggregates, and
reports the top 10 client IPs, top 10 error URLs, hourly request percentages,
and the share of unique User-Agents. Rich colored text is the default;
machine-oriented JSON and CSV make the same results usable in pipelines.

The MVP is deliberately narrow: no service to operate, no retained data, and
no external dependency beyond the local Python environment.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Triage a live incident | Full observability stacks may be unavailable or too slow to query | Pipe or read a log and get a stable summary in one command |
| DevOps engineer | Validate a deployment | Needs a scriptable signal for traffic and failures | Use `--json` or `--csv` with documented exit codes |
| Platform engineer | Inspect logs locally | Cannot upload sensitive logs to a hosted service | Process locally with no persistence or network calls |

## 3. Competitive Analysis

| Alternative | Strengths | Weaknesses for this use case | Product differentiation |
|---|---|---|---|
| GoAccess | Fast, mature, interactive and HTML reports | Broader UI and configuration surface than a small pipeline tool | Four opinionated SRE metrics with stable JSON/CSV contracts |
| Logstash + Elastic + Kibana | Powerful ingestion, search, dashboards, retention | Operationally heavy, stateful, and costly in setup time | Zero-server, one-shot local analysis |
| AWStats | Mature historical reporting | Stateful reports and legacy-oriented workflow | Streaming local CLI with modern packaging and pipeline output |
| `grep` / `awk` / `sort` | Ubiquitous, composable, no install in many environments | Quoting and log-format parsing are fragile; four metrics require multiple passes | One validated pass and consistent error handling across metrics |

## 4. Unique Value Proposition

Turn a large nginx access log into the four incident-triage summaries an SRE
usually needs, locally and in one pass, with both human-readable and stable
pipeline output.

## 5. Product and Distribution Model

The tool is open source and free. It is distributed as a Python package and
installed with pip. There is no paid tier, hosted component, telemetry, or
recurring infrastructure. Success is measured by usefulness, reliability,
performance, and adoption rather than revenue. Contributions and maintenance
remain compatible with the approved $0 operating budget.

## 6. Technology Stack

| Component | Choice | Why |
|---|---|---|
| Runtime | Python 3.11 | Approved, portable, strong standard-library streaming support |
| CLI | Click | Predictable commands, options, validation, and exit behavior |
| Terminal rendering | Rich | Accessible colored tables and automatic non-TTY handling |
| Domain models | `dataclasses` | Typed records without a persistence framework |
| Parsing and aggregation | Python standard library | Keeps installation small and avoids infrastructure |
| Packaging | pip-compatible `pyproject.toml` | Standard local and isolated installation |
| Tests and benchmarks | pytest plus generated local fixtures | Deterministic behavior and performance evidence without product dependencies |

## 7. Delivery Timeline

| Block | Effort | Result |
|---|---:|---|
| Saturday morning | 3 hours | Package skeleton, CLI contract, parser, validation |
| Saturday afternoon | 4 hours | Streaming aggregation and the four metrics |
| Sunday morning | 3 hours | Rich, JSON, and CSV renderers; error mapping |
| Sunday afternoon | 4 hours | Tests, 1 GB benchmark, documentation, packaging check |

The timebox is one weekend. Any unplanned feature that threatens the P0
acceptance criteria moves out of the MVP.

## 8. KPIs

| Metric | MVP acceptance | First month target | Three-month target |
|---|---:|---:|---:|
| Processing time for the agreed 1 GB representative fixture | < 30 seconds on the reference laptop | Maintain < 30 seconds | No regression above 10% |
| Correctness against hand-verified fixtures | 100% P0 cases | 100% | 100% |
| Peak memory on representative 1 GB fixture | < 1 GB and no input buffering | Maintain | Improve after profiling if needed |
| Install-and-run success in clean Python 3.11 environment | 100% release check | 95% issue-free installs | 98% issue-free installs |
| Open critical defects | 0 at release | 0 | 0 |

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real nginx formats differ from the supported common/combined contract | Medium | High | Fail or skip according to explicit strictness rules; report invalid-line count; document supported format |
| Exact cardinality sets consume too much memory on adversarial input | Medium | High | Configurable User-Agent cardinality cap and exit code 4; benchmark peak memory |
| Python misses the 1 GB / 30 second target | Medium | High | One pass, compiled regex or dedicated scanner chosen by profiling, buffered reads, no per-line Rich work |
| CSV/JSON semantics drift from terminal output | Low | High | One report dataclass shared by all renderers and golden-output tests |
| Color or locale makes automation unstable | Low | Medium | Disable color for non-TTY; machine formats are UTF-8 with stable schemas |
| Weekend scope expands into a monitoring platform | Medium | Medium | Enforce MoSCoW and the explicit out-of-scope list |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Runtime and libraries | $0 | Python and all selected dependencies are open source |
| Infrastructure | $0 | Local execution; no server, database, or cloud |
| Distribution | $0 | Source repository and pip-compatible local build |
| Test data | $0 | Generated fixtures and user-supplied local logs |
| Labor | One weekend | Approved delivery timebox; no cash budget |

## 11. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream a file or stdin without loading the input | Must | Core value and capacity prerequisite |
| Parse supported nginx common/combined access-log lines | Must | All metrics depend on valid fields |
| Top 10 client IPs | Must | Required incident-triage metric |
| Top 10 URLs with 4xx/5xx responses | Must | Required failure-triage metric |
| Hourly request distribution percentage | Must | Required traffic-shape metric |
| Unique User-Agent share | Must | Required client-diversity metric |
| Rich terminal output plus JSON and CSV | Must | Required human and pipeline interfaces |
| Stable `0/1/2/3/4` exit codes | Must | Required automation contract |
| Strict malformed-line mode and configurable cardinality cap | Should | Improves operational control without defining the core metrics |
| Gzip input | Could | Useful for archived logs, but shell decompression already composes with stdin |
| Custom nginx `log_format` parser | Could | Broadens compatibility but exceeds the weekend parser scope |
| Authentication, database, HTTP API, server, cloud, Kubernetes | Won't | Explicitly prohibited and unnecessary for a local stateless CLI |
| Dashboards, persistence, and live alerting | Won't | Belong to monitoring platforms, not this one-shot analyzer |

### RICE Scoring for Must and Should Features

Scores use `(Reach × Impact × Confidence) / Effort`, with confidence as a
decimal and effort in person-days. They guide ordering but do not override
hard dependencies.

| Feature | Reach | Impact | Confidence | Effort (days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Stream file/stdin | 10 | 5 | 100% | 0.5 | 100.0 |
| Parse nginx lines | 10 | 5 | 90% | 0.75 | 60.0 |
| Top IPs | 9 | 4 | 95% | 0.35 | 97.7 |
| Error URLs | 10 | 5 | 95% | 0.40 | 118.8 |
| Hourly percentages | 8 | 4 | 95% | 0.30 | 101.3 |
| Unique User-Agent share | 8 | 4 | 80% | 0.40 | 64.0 |
| Three output formats | 10 | 5 | 90% | 0.75 | 60.0 |
| Exit-code contract | 8 | 4 | 100% | 0.25 | 128.0 |
| Strict mode and cardinality cap | 6 | 3 | 80% | 0.35 | 41.1 |

Dependency-aware delivery order is: input and parsing, aggregation, report
model, output formats, then operational error controls. Within each dependency
layer, higher RICE scores come first.

## 12. Definition of Done

A feature is Done only when:

- [ ] Its behavior and edge cases match `PRD.md` acceptance criteria.
- [ ] Python 3.11 static checks and unit tests pass.
- [ ] Relevant integration and golden-output tests pass.
- [ ] The candidate package installs in a clean environment and the CLI starts.
- [ ] The representative 1 GB benchmark completes under 30 seconds on the documented reference laptop.
- [ ] Peak memory is recorded and no input-sized buffer is retained.
- [ ] Documentation and pipeline schemas are synchronized with behavior.
- [ ] No known Critical or High security issue remains.
- [ ] A maintainer review is complete before release.

## 13. Product Kill and Pivot Criteria

Stop the weekend release and reduce scope if the parser cannot produce
deterministic results for the declared formats, any renderer changes metric
semantics, or the performance target cannot be reached without violating the
approved stack. Do not pivot to a server or persistent architecture; instead,
publish the measured limitation or defer the release.

