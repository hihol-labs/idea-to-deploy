# Product Requirements Document: Nginx Stream Insights

## 1. Purpose

Provide DevOps/SRE engineers with fast, private, local answers to four common nginx traffic questions, in both human-readable and pipeline-safe forms. The specification is the source of truth; implementation changes must update this document first when behavior changes.

## 2. Goals and non-goals

### Goals

- Analyze a file or stdin without loading the whole log.
- Report top-10 IPs, top-10 4xx/5xx URLs, 24-hour distribution, and unique User-Agent share.
- Produce colored terminal text by default and stable JSON/CSV on request.
- Process a representative 1 GB log in under 30 seconds on a documented laptop.
- Install through pip on Python 3.11 with no paid or hosted dependency.

### Non-goals

Authentication, database storage, HTTP APIs, servers, cloud resources, Kubernetes, a browser UI, cross-run history, live dashboards, arbitrary query languages, and exact support for every custom nginx `log_format` are out of scope.

## 3. Users and user stories

### US-1 — Immediate incident summary

As an on-call SRE, I want to analyze an nginx access-log file in one command so that I can identify dominant clients and traffic shape during an incident.  
**Priority:** P0  
**Acceptance criteria:**

- [ ] Given the golden combined-format fixture, default output shows top 10 IPs and all 24 hourly buckets with exact expected counts.
- [ ] More than 10 distinct IPs are ranked by count descending and key ascending for ties.
- [ ] A readable file completes with exit code 0 and does not write raw log lines.

### US-2 — Error hotspot ranking

As a service owner, I want URLs ranked only by 4xx and 5xx responses so that I can focus remediation on failing routes.  
**Priority:** P0  
**Acceptance criteria:**

- [ ] 2xx and 3xx records never contribute to the error URL ranking.
- [ ] 4xx and 5xx records contribute to one combined top-10 ranking.
- [ ] Query strings remain part of the URL key in MVP and this is documented.

### US-3 — User-Agent diversity

As a security-minded operator, I want the share of unique User-Agents so that I can spot unusually homogeneous or diverse client traffic.  
**Priority:** P0  
**Acceptance criteria:**

- [ ] The share equals distinct present User-Agent values divided by valid records containing a User-Agent.
- [ ] Common-format records without User-Agent do not enter the denominator.
- [ ] Zero observations produce `0.0`, never division-by-zero or NaN.

### US-4 — Pipeline automation

As a platform engineer, I want JSON and CSV modes so that downstream scripts can consume reports without scraping terminal text.  
**Priority:** P0  
**Acceptance criteria:**

- [ ] `--json` emits one valid versioned JSON document and no ANSI escapes on stdout.
- [ ] `--csv` emits the documented normalized header and correctly quoted rows with no ANSI escapes.
- [ ] `--json --csv` is rejected as a usage error with exit code 2.
- [ ] Diagnostics go to stderr and never corrupt machine-readable stdout.
- [ ] Golden files prove the literal schema version, types, ordering, six-decimal share policy, 24 CSV hour rows, and empty-output mapping.

### US-5 — Unix streaming input

As a DevOps engineer, I want to pipe decompressed or filtered records over stdin so that temporary expanded files are unnecessary.  
**Priority:** P0  
**Acceptance criteria:**

- [ ] `LOG_PATH=-` reads stdin sequentially and produces the same report as the equivalent file.
- [ ] Empty stdin succeeds with zero-valued output.
- [ ] The implementation does not call `read()` without a bounded size or materialize all lines.

### US-6 — Data-quality visibility

As an operator, I want malformed records counted while valid records continue so that partial log corruption does not hide the useful report.  
**Priority:** P0  
**Acceptance criteria:**

- [ ] Each malformed line increments `malformed_lines` once and processing continues.
- [ ] Raw malformed content is not echoed by default.
- [ ] An unreadable input file fails with exit code 1 and a concise stderr message.
- [ ] Invalid UTF-8 or a record over 1 MiB counts as malformed; expected I/O failures never show a traceback.

### US-7 — Custom nginx formats

As a platform engineer, I want a documented way to describe a custom nginx format so that the tool can analyze nonstandard deployments.  
**Priority:** P1  
**Acceptance criteria:** Deferred until the P0 standard common/combined implementation and performance target are complete.

### US-8 — Ranking-size override

As an analyst, I want to change the ranking size so that I can inspect beyond the top 10.  
**Priority:** P2  
**Acceptance criteria:** Deferred; MVP ranking size is fixed at 10.

## 4. Functional requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-1 | P0 | Accept one file path or `-` for stdin and process sequentially |
| FR-2 | P0 | Parse documented nginx common and combined access-log records |
| FR-3 | P0 | Count valid records and malformed lines separately |
| FR-4 | P0 | Return top 10 IPs by request count with deterministic ties |
| FR-5 | P0 | Return top 10 request targets among status 400–599 |
| FR-6 | P0 | Return counts for every hour 00 through 23 using the logged timezone/hour |
| FR-7 | P0 | Return distinct User-Agent count, observation count, and share in [0,1] |
| FR-8 | P0 | Default to Rich terminal output with non-TTY/no-color safety |
| FR-9 | P0 | Support mutually exclusive `--json` and `--csv` stable schemas |
| FR-10 | P0 | Use documented exit codes and stdout/stderr separation |
| FR-11 | P1 | Support explicitly configured custom nginx formats |
| FR-12 | P2 | Allow a ranking-size override |

## 5. Non-functional requirements

| ID | Requirement | Evidence |
|---|---|---|
| NFR-1 | Python 3.11 and pip-installable wheel/sdist | Clean-environment install and smoke test |
| NFR-2 | Architecture `baseline-v1` completes in <30 s and <250 MB RSS | Median of three recorded warm runs plus peak RSS |
| NFR-3 | Streaming input; memory independent of byte size, subject to documented key cardinality | Code review plus peak-RSS benchmark |
| NFR-4 | No network access or persistent application data | Dependency/code audit |
| NFR-5 | Deterministic output for identical input/options | Golden-output tests |
| NFR-6 | Parser, aggregator, and renderer coverage >=90% | Coverage report |
| NFR-7 | Log-derived values cannot inject Rich markup or break CSV/JSON | Adversarial fixtures |
| NFR-8 | `cardinality-v1` stays below 750 MB RSS or fails according to the exact-mode contract | High-cardinality benchmark and failure tests |

## 6. Output acceptance examples

The canonical exact machine-output example lives in future `tests/expected/golden_report.json`. JSON keys and CSV columns are defined in `PROJECT_ARCHITECTURE.md`; changing them requires a `schema_version` decision and PRD update.

## 7. Release acceptance

- All P0 stories and functional requirements pass automated tests.
- The clean pip install, file flow, stdin flow, JSON flow, and CSV flow are manually verified.
- Benchmark correctness matches golden aggregates before the time result is evaluated.
- The 1 GB median is under 30 seconds on the documented reference laptop.
- Documentation states supported formats, exact User-Agent formula, URL key policy, privacy limitations, and cardinality memory behavior.

## 8. Kill criteria

Stop or explicitly re-scope the MVP if:

- A profiled, correct Python 3.11 implementation cannot meet the 1 GB/30 s target on the agreed reference laptop.
- Representative standard nginx common/combined fixtures cannot be parsed without material ambiguity.
- Exact distinct-key memory is unacceptable on representative logs and stakeholders reject approximation or a documented limit.
- Delivering requires authentication, a database, an HTTP service, paid infrastructure, or more than the approved one-weekend scope.

## 9. Dependencies

Architecture decisions are in `PROJECT_ARCHITECTURE.md`, delivery steps in `IMPLEMENTATION_PLAN.md`, and product priority/risk in `STRATEGIC_PLAN.md`.
