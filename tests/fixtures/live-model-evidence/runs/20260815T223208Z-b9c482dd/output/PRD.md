# Product Requirements Document: Nginx Stream Analyzer

## 1. Summary

Nginx Stream Analyzer is a local Python 3.11 CLI that streams common or combined nginx access logs and reports top client IPs, top error-producing URLs, hourly request percentages, and unique User-Agent share. It favors a narrow, stable contract over a dashboard or general-purpose log platform.

## 2. Problem and Goals

DevOps/SRE engineers frequently need immediate summaries from large access logs but do not want to deploy or feed data into a persistent stack. Shell one-liners are quick but fragile around quoting, formats, deterministic sorting, and reuse.

Goals:

- Analyze a 1 GB log in under 30 seconds on a documented representative laptop.
- Process sequentially without loading the input file into memory.
- Produce the same metrics as colored terminal text, JSON, or CSV.
- Be installable through pip on Python 3.11.
- Fail deterministically and safely on invalid input or exact-cardinality exhaustion.

Non-goals include authentication, a database, history, an HTTP API, a daemon/server, cloud deployment, Kubernetes, dashboards, alerting, tail-follow mode, and arbitrary log-query language.

## 3. Personas

- **On-call SRE:** wants a fast, readable incident snapshot.
- **DevOps engineer:** wants reproducible release/proxy diagnostics.
- **Platform engineer:** wants stable JSON/CSV and exit codes for automation.

## User Stories

### US-1 — Analyze a local stream

As an SRE, I want to analyze a log path or stdin sequentially so that I can inspect large local logs and shell pipelines without importing them.

Priority: P0

Acceptance criteria:

- [ ] Omitting `INPUT` and passing `-` both read stdin; a path reads that file.
- [ ] File and stdin runs over identical bytes produce semantically identical results.
- [ ] Mixed input counts and skips malformed lines; zero valid records exits 3 without a result.
- [ ] Open/read/decode failures exit 2 and write diagnostics only to stderr.

### US-2 — Identify dominant client IPs

As an on-call SRE, I want the ten most frequent client IPs so that I can spot abusive or unexpectedly concentrated traffic.

Priority: P0

Acceptance criteria:

- [ ] At most ten IP/count pairs are returned from valid records.
- [ ] Ordering is count descending and then IP string ascending for ties.
- [ ] IPv4 and IPv6 text values are supported by the parser.

### US-3 — Identify error-producing URLs

As a DevOps engineer, I want the ten request targets with the most 4xx/5xx responses so that I can prioritize broken or problematic routes.

Priority: P0

Acceptance criteria:

- [ ] Only statuses 400 through 599 contribute.
- [ ] The key is the request-target exactly as logged, including its query string.
- [ ] Ordering is count descending and then URL ascending for ties.

### US-4 — See hourly traffic distribution

As an SRE, I want requests grouped across all 24 logged local-hour buckets so that I can see when traffic occurred.

Priority: P0

Acceptance criteria:

- [ ] Exactly 24 buckets `00`–`23` are emitted on a successful run, including zero-count hours.
- [ ] The logged numeric timezone offset is honored without conversion to the machine timezone.
- [ ] Each percentage uses the literal formula `100 × hourly_request_count / total_valid_requests` and is rounded to two decimal places only for output.

### US-5 — Measure User-Agent diversity safely

As a platform engineer, I want exact unique User-Agent share with a configurable ceiling so that I can quantify diversity without risking uncontrolled memory exhaustion.

Priority: P0

Acceptance criteria:

- [ ] The result includes distinct non-missing User-Agent count, observation count, and `100 × unique_user_agent_count / total_valid_requests`.
- [ ] `-` is missing, while an empty quoted value is a distinct value.
- [ ] Common-format input reports zero User-Agent observations/count/share.
- [ ] Attempting to insert a distinct value beyond the ceiling emits no partial result and exits 4.

### US-6 — Use human and pipeline output

As a platform engineer, I want terminal, JSON, and CSV modes so that the same tool works interactively and in automation.

Priority: P0

Acceptance criteria:

- [ ] Default output is labeled terminal text, colored only when enabled and appropriate.
- [ ] `--json` emits one valid versioned JSON object; `--csv` emits the documented long-form header and rows.
- [ ] Structured output never contains ANSI escapes, and diagnostics never contaminate stdout.
- [ ] `--json` and `--csv` together produce a usage error with exit code 2.

### US-7 — Adjust presentation breadth and time basis

As an experienced operator, I want configurable top-N and timezone conversion so that I can tailor reports after the fixed MVP is proven.

Priority: P1

Acceptance criteria:

- [ ] A future release may add these options only with versioned schema and backward-compatibility tests.

### US-8 — Read compressed logs

As an operator, I want gzip input so that I can inspect rotated logs without manually decompressing them.

Priority: P2

Acceptance criteria:

- [ ] Deferred until all P0 release gates pass.

## 5. Functional Requirements

| ID | Priority | Requirement |
|---|---|---|
| FR-1 | P0 | Accept one optional path or stdin and process it in one sequential pass |
| FR-2 | P0 | Parse documented nginx common and combined records with explicit malformed-line accounting |
| FR-3 | P0 | Return deterministic top 10 IPs over valid requests |
| FR-4 | P0 | Return deterministic top 10 request targets restricted to status 400–599 |
| FR-5 | P0 | Return all 24 hourly count/percentage buckets using the logged offset |
| FR-6 | P0 | Return exact User-Agent count/share and enforce a positive configurable ceiling |
| FR-7 | P0 | Render equivalent terminal, versioned JSON, and long-form CSV results |
| FR-8 | P0 | Implement exit codes: 0 success, 1 internal error, 2 usage/input I/O/decode, 3 no valid records, 4 unique-cardinality exhaustion |
| FR-9 | P1 | Add configurable top-N/timezone only after schema review |
| FR-10 | P2 | Add gzip input after the MVP gates pass |

## 6. Output Contract

The normative schemas, ordering, rounding, stdout/stderr rules, and option details are in `PROJECT_ARCHITECTURE.md` under `## CLI Interface`. Terminal, JSON, and CSV are representations of one `AnalysisResult`, not separately computed reports.

Hourly request distribution must be a percentage, specifically `100 × hourly_request_count / total_valid_requests`; it is not an unscaled fraction. Percentages use all valid requests as the denominator even when malformed lines exist.

The exit-code contract is complete and stable: `0` success; `1` unexpected internal error; `2` usage/configuration or input open/read/decode failure; `3` no valid records; `4` unique-cardinality exhaustion. No result is emitted for codes 1–4.

## 7. Non-Functional Requirements

| ID | Requirement | Verification |
|---|---|---|
| NFR-1 Performance | A deterministic 1,000,000,000-byte fixture completes in <30.0 s on the recorded laptop profile | Release benchmark with elapsed time, peak RSS, hardware/OS/Python metadata |
| NFR-2 Memory | Input is never retained as a whole; hot path is streaming; UA exact set stops at its ceiling | Review plus peak-RSS/cardinality-boundary tests |
| NFR-3 Determinism | Equal inputs/options produce equal semantic results and stable tie ordering | Repeated contract tests |
| NFR-4 Pipeline safety | Results use stdout; diagnostics use stderr; structured modes contain no ANSI | CLI integration tests |
| NFR-5 Portability | Installable via pip and runnable on Python 3.11 | Clean-wheel environment smoke test |
| NFR-6 Security | Log fields remain inert data and terminal markup/control content is escaped | Adversarial fixtures and rendering tests |
| NFR-7 Cost | No paid/runtime service or infrastructure | Architecture/package inspection |

## 8. Supported and Unsupported Input

The MVP supports the documented common/combined grammars selected by `--log-format`. It does not promise automatic grammar inference, arbitrary nginx `log_format` compilation, multiline records, compressed input, follow/tail mode, or recovery of partially corrupted quoted fields. Malformed physical lines are counted and skipped. File-level decoding and I/O failures stop the run.

## 9. Dependencies and Constraints

- Python 3.11, Click, Rich, dataclasses, standard packaging, and pip installation are fixed decisions.
- The single-process streaming architecture is approved.
- Budget is $0 and delivery is one weekend.
- No authentication, database, API/server, cloud, Docker requirement, or Kubernetes.
- `STRATEGIC_PLAN.md` governs scope/value; `PROJECT_ARCHITECTURE.md` governs technical conflicts; `IMPLEMENTATION_PLAN.md` sequences delivery.

## 10. Release and Kill Criteria

Release when every P0 acceptance criterion has executable evidence, all output modes agree semantically, the clean wheel installs, the complete exit contract is tested, and the exact candidate meets the measured performance target. Re-scope or stop if correct parsing cannot meet the target after profiling, exact cardinality cannot fail safely, or supported nginx formats cannot be specified deterministically. Do not release by silently sampling, approximating, or ignoring a failed gate.

