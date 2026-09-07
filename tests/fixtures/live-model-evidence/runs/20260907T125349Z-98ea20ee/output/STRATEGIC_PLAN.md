# Strategic Plan: nginx-stream-insights

## 1. Product Idea

`nginx-stream-insights` is a local, pip-installable Python 3.11 command-line tool for DevOps and SRE engineers. It reads nginx access logs as a stream and produces four immediately actionable views: top 10 client IPs, top 10 URLs with 4xx/5xx responses, request distribution by hour, and the share of unique User-Agents. Rich-colored text is the default; stable JSON and CSV modes make the same results usable in shell pipelines.

The MVP is deliberately local and stateless. It does not authenticate users, retain logs, expose a network service, or require infrastructure. The promise is fast incident triage from a file or stdin, including files near 1 GB, without uploading operational data.

## 2. Target Audience

| Persona | Role | Pain | Product response |
|---|---|---|---|
| On-call SRE | Diagnoses production incidents | Needs a quick traffic/error picture before opening a larger observability system | One command summarizes the most useful access-log dimensions |
| DevOps engineer | Operates nginx hosts and CI jobs | Ad hoc `awk` pipelines are fragile and hard to reuse | Stable parser, metrics, exit codes, JSON, and CSV |
| Platform engineer | Builds internal runbooks | Heavy analytics stacks are excessive for local or one-off analysis | Zero-service pip installation and stream processing |

## 3. Problem and Opportunity

Teams often sit between two poor choices: compose disposable shell commands under pressure or deploy a persistent analytics platform. A focused CLI can own the gap: repeatable local answers, bounded memory for ordinary counters, clear failure behavior, and formats that can feed existing automation.

## 4. Competitive Analysis

| Alternative | Strength | Weakness for this use case | Differentiation |
|---|---|---|---|
| GoAccess | Fast, mature, interactive reports | Broader UI/reporting surface than a four-metric pipeline tool | Narrow, script-friendly contract with Python installability |
| Logstash + Elastic + Kibana | Powerful ingestion, search, dashboards | Operational cost, persistent services, indexing, and setup | No server, database, or retained data; $0 runtime |
| AWStats | Established historical web statistics | Batch-oriented reports and older operational workflow | Immediate stdin/file analysis and structured output |
| `grep`/`awk`/`sort` | Ubiquitous and flexible | Quoting, parsing, malformed rows, portability, and repeated work | Tested nginx parsing and one stable command contract |

## 5. Unique Value Proposition

Get a dependable nginx traffic-and-error snapshot from a large local stream in one command, without deploying or maintaining an observability stack.

## 6. Business Model and Economics

The project is open source and free. There is no monetization in the MVP. Value is measured as engineer time saved and runbook consistency. Direct software and infrastructure budget is $0; delivery uses one developer weekend and existing laptop/CI capacity.

## 7. Technology Strategy

| Component | Choice | Reason |
|---|---|---|
| Runtime | Python 3.11 | Approved, portable, strong standard library |
| CLI | Click | Stable option parsing, stdin/file handling, exit behavior |
| Terminal UI | Rich | Readable colored tables with automatic no-color fallback |
| Domain models | `dataclasses` | Explicit records without a framework |
| Packaging | `pyproject.toml`, pip | Standard install and console entry point |
| Processing | Single-process, line-by-line stream | Minimal operational surface and avoids loading the log into memory |

## 8. Timeline

| Window | Stage | Deliverable |
|---|---|---|
| Friday evening | Scaffold and contracts | Package, CLI surface, domain models, fixtures |
| Saturday morning | Parsing and aggregation | Streaming parser and all four metrics |
| Saturday afternoon | Presentation | Rich, JSON, and CSV renderers |
| Sunday morning | Reliability and performance | Error policy, exit codes, tests, 1 GB benchmark |
| Sunday afternoon | Packaging and documentation | Pip-installable release candidate and runbook examples |

## 9. KPIs

| Metric | Launch target | First-month target | Guardrail |
|---|---:|---:|---:|
| 1 GB processing time on reference laptop | <30 s | <30 s at p95 of benchmark runs | No full-file buffering |
| Valid-line accounting accuracy | 100% on golden fixtures | 100% | Parsed + malformed equals total lines |
| Supported output contract tests | All pass | All pass per release | JSON/CSV remain machine-stable |
| Fresh-install time | <2 min | <2 min | Python 3.11 and pip only |
| Critical/high dependency vulnerabilities | 0 known | 0 known | Block release until resolved or accepted |

## 10. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Real logs use formats outside the supported combined/common profile | Medium | High | Explicit `--log-format`, clear parse counters, representative fixtures |
| Exact unique User-Agent tracking consumes excessive memory | Medium | High | Configurable cardinality ceiling and exit code 4 on exhaustion |
| Python misses the 1 GB/30 s target | Medium | High | Benchmark early; compile regex once; avoid per-line Rich work; profile hot path |
| CSV representation is ambiguous for multiple metric tables | Medium | Medium | Fixed long-form schema with `metric`, `key`, `value`, `rank` columns |
| Terminal color contaminates redirected output | Low | Medium | Enable color only for a TTY; structured modes never emit ANSI sequences |
| Malformed or truncated lines hide operational problems | Medium | Medium | Count malformed rows, warn in text mode, expose counts in structured metadata |

## 11. Budget

| Item | Cost | Comment |
|---|---:|---|
| Libraries | $0 | Open-source Python dependencies |
| Infrastructure | $0/month | Local execution; no hosted components |
| Distribution | $0 | Source distribution/wheel through pip-compatible tooling |
| Labor | One weekend | Approved delivery constraint; opportunity cost only |

## 12. Feature Roadmap

### MoSCoW

| Feature | Priority | Rationale |
|---|---|---|
| Stream nginx log from file or stdin | Must | Foundation of local and pipeline workflows |
| Top 10 client IPs | Must | Rapidly exposes dominant clients and abuse patterns |
| Top 10 URLs by 4xx/5xx count | Must | Finds failing routes during triage |
| Hourly request distribution percentage | Must | Shows time concentration using `100 × hourly_request_count / total_valid_requests` |
| Unique User-Agent share | Must | Gives a compact client-diversity signal |
| Colored terminal output | Must | Default human workflow |
| JSON and CSV output | Must | Required pipeline compatibility |
| Explicit malformed-input and exit-code policy | Must | Automation must distinguish result, input, parse, and resource failures |
| Configurable top-N | Should | Useful beyond the default top 10 but not essential to the promise |
| Custom nginx format template | Should | Broadens compatibility after core combined/common support |
| Gzip input | Could | Convenient for archives but shell decompression is an adequate fallback |
| Persistent history/dashboard | Won't | Conflicts with local stateless scope |
| Auth, database, HTTP API, cloud, Kubernetes | Won't | Adds no value to the approved CLI use case |

### RICE Scoring (Must and Should)

Scores use `(Reach × Impact × Confidence) / Effort`, with confidence as a decimal. Ordering breaks ties by dependency.

| Feature | Reach | Impact | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Stream file/stdin | 10 | 5 | 100% | 0.75 | 66.7 |
| Explicit failure policy | 10 | 4 | 90% | 0.75 | 48.0 |
| Top IPs | 9 | 4 | 95% | 0.75 | 45.6 |
| Error URLs | 9 | 5 | 95% | 1.00 | 42.8 |
| Hourly distribution | 8 | 4 | 95% | 0.75 | 40.5 |
| Unique User-Agent share | 8 | 4 | 85% | 0.75 | 36.3 |
| Colored text output | 9 | 3 | 95% | 0.75 | 34.2 |
| JSON and CSV output | 8 | 4 | 95% | 1.00 | 30.4 |
| Configurable top-N | 5 | 2 | 90% | 0.25 | 36.0 |
| Custom format template | 5 | 4 | 60% | 1.50 | 8.0 |

The implementation sequence in `IMPLEMENTATION_PLAN.md` respects both this value order and technical dependencies.

## 13. Definition of Done

A feature is done when:

- [ ] Behavior and acceptance criteria in `PRD.md` are implemented without expanding scope.
- [ ] Python 3.11 static checks and unit tests pass with at least 90% coverage of parser and aggregation modules.
- [ ] Integration tests cover file input, stdin, text, JSON, CSV, and exit codes `0/1/2/3/4`.
- [ ] The 1 GB reference benchmark completes in under 30 seconds on the documented laptop profile.
- [ ] Packaging installs into a clean environment and exposes the console command.
- [ ] Documentation and examples match the shipped CLI.
- [ ] No known critical/high security issue remains unaddressed.
- [ ] Review and exact-candidate verification evidence required by `.itd/VERIFICATION_CONTRACT.json` is current.

## 14. Success and Kill Criteria

Proceed to release if golden-output correctness, clean pip installation, and the performance target all pass. Re-scope the parser or evaluate a faster implementation language only if profiling shows the approved Python design cannot meet 1 GB in 30 seconds after bounded optimization. Stop the MVP if the CLI cannot provide deterministic structured output or bounded failure for User-Agent cardinality.

