# Strategic Plan: nginx-stream-stats

## 1. Product Idea

`nginx-stream-stats` is a local, pip-installable Python 3.11 CLI for DevOps and
SRE engineers. It reads nginx combined access logs from a file or standard
input in one pass and reports the top 10 client IPs, top 10 URLs producing
4xx/5xx responses, hourly request distribution, and the share of unique
User-Agent values. Rich colored text is the default; JSON and CSV provide
stable machine-readable output for pipelines.

The product is deliberately narrow: it gives a useful incident snapshot
without shipping logs to a service, deploying infrastructure, or retaining
state. The MVP is an open-source, $0-budget, one-weekend project.

## 2. Target Audience

| Persona | Role | Pain | How the product helps |
|---|---|---|---|
| Incident responder | On-call SRE | Needs a fast traffic/error summary on a laptop or bastion host | Pipes a live or saved log into one command and receives a bounded report |
| Service operator | DevOps engineer | Repeats fragile `grep`, `awk`, and `sort` pipelines | Uses consistent parsing, metrics, exit codes, and deterministic ordering |
| Automation owner | Platform engineer | Needs log summaries in scripts without a service dependency | Selects JSON or CSV and relies on a documented schema and exit-code contract |

## 3. Competitive Analysis

| Alternative | What it does | Weakness for this use case | Our distinction |
|---|---|---|---|
| GoAccess | Rich terminal and HTML nginx analytics | Broader UI/configuration surface than a four-metric pipeline command | Smaller contract, pip installation, and first-class JSON/CSV |
| Logstash + Elastic + Kibana | Centralized ingestion, indexing, search, and dashboards | Requires services, storage, setup, and operational budget | Zero-service, local, one-pass execution |
| AWStats | Persistent web-traffic reporting | Batch-oriented, dated workflow, persistent artifacts | Immediate streaming analysis with modern pipeline outputs |
| `grep`/`awk`/`sort` | Ad hoc shell analysis | Format-fragile, hard to test, repeated full-file passes, inconsistent errors | One tested parser, one pass, stable metrics and exit codes |

## 4. Unique Value Proposition

Get the four nginx traffic signals most useful during triage from a gigabyte of
logs in one local command, with no service, database, or data upload.

## 5. Business Model

The MVP is free, open-source software. There are no paid tiers, hosted costs,
or monetization assumptions. Success is measured by usefulness, adoption, and
maintainability rather than revenue; optional sponsorship can be considered
only after sustained community use and is not part of this scope.

## 6. Technology Stack

| Component | Technology | Why |
|---|---|---|
| Runtime | Python 3.11 | Required, portable, and suitable for local CLI distribution |
| CLI | Click | Mature option validation, help text, and conventional usage exit behavior |
| Terminal UI | Rich | Required colored, readable terminal tables with TTY-aware behavior |
| Domain models | `dataclasses` | Lightweight typed records without an ORM or validation framework |
| Packaging | `pyproject.toml` + pip | Standard install and console-entry-point workflow |
| Tests | pytest | Fast unit, integration, CLI, and performance coverage |

The detailed boundaries and interface are defined in
`PROJECT_ARCHITECTURE.md`; delivery sequencing is in `IMPLEMENTATION_PLAN.md`.

## 7. Timeline

| Weekend window | Stage | Result |
|---|---|---|
| Saturday morning | Packaging, contracts, parser | Installable skeleton and robust combined-log parsing |
| Saturday afternoon | Aggregation and safeguards | One-pass metrics with deterministic top-10 and cardinality protection |
| Sunday morning | Renderers and CLI integration | Text, JSON, and CSV outputs with complete exit behavior |
| Sunday afternoon | Tests, benchmark, documentation | Verified 1 GB target, distributable package, and user docs |

Total planned effort is approximately 16 hours for one developer. The
performance target is a release gate, not an assumption: a representative 1 GB
fixture must complete in under 30 seconds on the documented laptop baseline.

## 8. KPIs

| Metric | Release target | 1 month | 3 months |
|---|---:|---:|---:|
| Representative 1 GB processing time | <30 s | <30 s | <25 s if profiling supports it |
| Peak resident memory on 1 GB benchmark | <512 MiB at default cardinality cap | No regression | No regression |
| Valid-line parsing correctness corpus | 100% | 100% | 100% |
| Output/exit contract integration cases passing | 100% | 100% | 100% |
| Confirmed external users | 1 maintainer | 10 | 50 |

Performance results must name CPU, RAM, OS, storage, Python version, fixture
shape, command, elapsed time, and peak RSS so comparisons remain meaningful.

## 9. Risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Python parser misses the 1 GB/30 s target | Medium | High | Avoid regex-heavy hot paths, profile representative input, and fail the release gate if the benchmark misses |
| Unexpected nginx formats create misleading counts | High | High | Support combined format explicitly, count malformed lines, provide `--strict`, and document non-goals |
| User-Agent cardinality exhausts memory | Medium | High | Bound the exact set with `--max-unique-user-agents`; stop with exit code 4 rather than approximate silently |
| JSON/CSV schemas drift | Medium | Medium | Golden-output tests and versioned field names shared across renderers |
| Rich color corrupts redirected output | Low | Medium | Disable color when non-TTY and always disable it for JSON/CSV |
| Weekend scope expands into a log platform | Medium | High | Enforce MoSCoW exclusions and the CLI-only stateless architecture |

## 10. Budget

| Item | Cost | Comment |
|---|---:|---|
| Python, Click, Rich, pytest | $0 | Open-source dependencies |
| Hosting, database, cloud, Kubernetes | $0 | Explicitly absent |
| CI | $0 | Local verification or free open-source allowance |
| Developer cash budget | $0 | One-weekend personal delivery; time is constrained, not purchased |
| Total | **$0** | No recurring infrastructure |

## 11. Feature Roadmap

### MoSCoW

| Feature | MoSCoW | Rationale |
|---|---|---|
| Stream nginx combined logs from a file or stdin | **Must** | The product has no value without local one-pass input |
| Top 10 client IPs | **Must** | Core traffic concentration signal |
| Top 10 URLs by combined 4xx/5xx count | **Must** | Core error-triage signal |
| Hourly request percentage distribution | **Must** | Core temporal signal; defined as `100 × hourly_request_count / total_valid_requests` |
| Unique User-Agent share with cardinality limit | **Must** | Core diversity signal that requires an explicit memory guardrail |
| Rich text, JSON, and CSV outputs | **Must** | Required human and pipeline interfaces |
| Strict malformed-line mode and stable exit codes | **Must** | Prevents silent misuse in automation |
| Gzip input | **Should** | Common archive workflow, but decompression is not essential to MVP value |
| User-selectable top-N | **Could** | Useful flexibility after the top-10 contract is stable |
| Additional nginx `log_format` definitions | **Could** | Broadens adoption but significantly expands parser scope |
| Database, HTTP API, auth, server, cloud, Kubernetes | **Won't** | Conflicts with local, stateless, $0 product constraints |
| Approximate User-Agent cardinality | **Won't** | The MVP must fail explicitly instead of silently changing metric semantics |

### RICE Scoring (Must + Should)

Confidence is expressed as a decimal in the calculation. Scores are ordered
descending and guide `IMPLEMENTATION_PLAN.md`, subject to technical dependencies.

| Feature | Reach (1–10) | Impact (1–5) | Confidence | Effort (person-days) | RICE score |
|---|---:|---:|---:|---:|---:|
| Top 10 client IPs | 10 | 4 | 95% | 0.25 | 152.0 |
| Hourly percentage distribution | 9 | 4 | 95% | 0.25 | 136.8 |
| Error URL top 10 | 10 | 5 | 95% | 0.35 | 135.7 |
| Stream file/stdin input | 10 | 5 | 100% | 0.50 | 100.0 |
| Strict mode and exit codes | 8 | 5 | 95% | 0.40 | 95.0 |
| Unique User-Agent share and cap | 9 | 4 | 90% | 0.40 | 81.0 |
| Text/JSON/CSV output | 10 | 5 | 90% | 0.75 | 60.0 |
| Gzip input | 5 | 2 | 80% | 0.30 | 26.7 |

Implementation begins with packaging and streaming input because every
higher-scoring metric depends on those foundations, then delivers metrics in
value order and renderers after the shared report model.

## 12. Definition of Done

A feature is Done when:

- [ ] Its behavior and acceptance criteria agree with `PRD.md` and
  `PROJECT_ARCHITECTURE.md`.
- [ ] Code runs on Python 3.11 and formatting, linting, and type checks pass.
- [ ] Unit and CLI integration tests pass with at least 90% line coverage for
  parser, aggregation, and renderer modules.
- [ ] Malformed input and exit codes `0/1/2/3/4` are tested where applicable.
- [ ] Performance-sensitive changes pass the documented 1 GB/<30 s benchmark.
- [ ] User-facing behavior is reflected in README and `--help`.
- [ ] No known Critical or High security defects remain.
- [ ] The package installs in a clean virtual environment and the console command
  is manually smoke-tested.

## 13. Release and Kill Criteria

Release the MVP only if all P0 acceptance criteria pass, a clean pip install
works on Python 3.11, all three output modes validate, and the benchmark meets
the stated machine-bound target. Re-scope or stop the weekend release if the
1 GB run remains at or above 30 seconds after one measured optimization cycle,
exact User-Agent tracking cannot be bounded safely, or core combined-format
parsing cannot be made deterministic without expanding the scope.
