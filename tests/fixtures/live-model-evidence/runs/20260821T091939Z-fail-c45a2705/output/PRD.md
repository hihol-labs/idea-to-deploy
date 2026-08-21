# Product Requirements Document: nginx-insight

## Product Summary

`nginx-insight` lets DevOps and SRE users turn a local nginx combined access
log or stdin stream into four exact operational summaries without deploying a
service. Default output is colored terminal text; JSON and CSV are stable
pipeline interfaces. The MVP is open source, costs $0 to operate, and is
delivered in one weekend.

## Goals and Success Criteria

- Produce exact top-10 IP and 4xx/5xx URL rankings in one pass.
- Report all 24 hourly bins using
  `100 × hourly_request_count / total_valid_requests`.
- Report exact unique User-Agent count and its percentage of valid requests.
- Keep JSON/CSV stdout machine-readable by sending diagnostics to stderr.
- Process a documented representative 1 GB log in under 30 seconds on a
  laptop, with peak RSS recorded.
- Install into Python 3.11 through pip and expose `nginx-insight`.

## Non-Goals

Authentication, a database, persistence, an HTTP API, a server, a graphical or
web UI, cloud services, Kubernetes, log shipping, live file-following, multiple
input files per invocation, and arbitrary nginx log-format configuration are
out of scope. The MVP does not replace a retained observability platform.

## User Stories

### US-1 — Identify dominant clients

As an on-call SRE, I want the ten client IPs with the most valid requests so
that I can identify concentrated traffic during an incident.

Priority: **P0**

Acceptance criteria:

- [ ] Only successfully parsed lines contribute to IP counts.
- [ ] At most ten entries are ordered by count descending, then IP string ascending.
- [ ] IPv4 and IPv6 addresses from valid combined-format lines are supported.
- [ ] Terminal, JSON, and CSV represent the same IPs and counts.

### US-2 — Find URLs causing client/server errors

As a DevOps engineer, I want the ten URLs with the most 4xx/5xx responses so
that I can focus remediation on the largest error sources.

Priority: **P0**

Acceptance criteria:

- [ ] Statuses 400 through 599 inclusive contribute; all other statuses do not.
- [ ] Query strings remain part of the URL key.
- [ ] At most ten entries are ordered by count descending, then URL ascending.
- [ ] An input with no 4xx/5xx records succeeds and returns an empty ranking.

### US-3 — Understand hourly traffic shape

As an SRE, I want request volume broken into 24 hourly percentages so that I
can spot peak periods in the log sample.

Priority: **P0**

Acceptance criteria:

- [ ] Every hour from 00 through 23 appears, including zero-count bins.
- [ ] The hour is taken from the timestamp and offset written in each valid log line.
- [ ] Each percentage uses the literal formula `100 × hourly_request_count / total_valid_requests`.
- [ ] Across unrounded numeric values, the 24 percentages total 100% within floating-point tolerance.

### US-4 — Measure User-Agent diversity

As a platform engineer, I want the percentage of distinct User-Agent values so
that I can gauge client diversity or suspicious automation.

Priority: **P0**

Acceptance criteria:

- [ ] The exact distinct User-Agent count includes the valid nginx `-` sentinel as a value.
- [ ] Percentage equals `100 × unique_user_agent_count / total_valid_requests`.
- [ ] A new value beyond the configured exact-cardinality ceiling stops the run with exit 4.
- [ ] Cardinality exhaustion writes no partial report to stdout.

### US-5 — Compose analysis in pipelines

As a DevOps engineer, I want stable JSON and CSV output so that I can consume
the report from CI jobs and shell scripts.

Priority: **P0**

Acceptance criteria:

- [ ] `--json` emits the documented schema and valid JSON to stdout.
- [ ] `--csv` emits the documented header and RFC 4180-compatible rows to stdout.
- [ ] The flags are mutually exclusive and conflict with exit 2.
- [ ] Warnings and errors go only to stderr.
- [ ] Ties and row ordering are deterministic across runs.

### US-6 — Tolerate imperfect logs

As an on-call SRE, I want malformed lines skipped and counted so that a small
amount of noise does not hide valid incident data.

Priority: **P1**

Acceptance criteria:

- [ ] Blank and non-matching lines increment `malformed_lines` and do not affect metrics.
- [ ] A stream with at least one valid line can succeed despite malformed lines.
- [ ] A stream with no valid lines exits 3 and emits no report.

### US-7 — Verify laptop-scale throughput

As a maintainer, I want a repeatable 1 GB benchmark so that performance claims
are measurable and regressions are visible.

Priority: **P1**

Acceptance criteria:

- [ ] The input generator is deterministic and its record mix is documented.
- [ ] The benchmark records environment, elapsed time, and peak RSS.
- [ ] The installed CLI completes in under 30 seconds on the reference laptop.
- [ ] Benchmark output matches independently asserted expected aggregates.

### US-8 — Adjust ranking depth

As an analyst, I want a configurable top-N value so that I can inspect more
than ten entries without post-processing.

Priority: **P2**

Acceptance criteria:

- [ ] Deferred until after the fixed top-10 MVP contract is stable.

## Functional Requirements

### P0 — Must ship

1. Accept one optional file path; use stdin when absent or `-`.
2. Parse UTF-8 nginx combined-format input one line at a time.
3. Count total, valid, and malformed lines.
4. Produce the four metrics and deterministic rankings defined above.
5. Render Rich terminal output by default, with safe automatic color handling.
6. Support mutually exclusive `--json` and `--csv` formats.
7. Support `--no-color`, `--version`, and `--help`.
8. Support a positive `--max-unique-user-agents` limit with a default of 1,000,000.
9. Implement the exit contract exactly: 0 success, 1 unexpected internal
   failure, 2 CLI usage error, 3 input/read/decode or zero-valid-record
   failure, and 4 unique-cardinality exhaustion.
10. Install with pip on Python 3.11 as the `nginx-insight` command.

### P1 — Should ship

1. Count and report malformed lines without failing an otherwise valid run.
2. Provide representative fixtures for nginx escaping, IPv6, query strings,
   boundary statuses, missing User-Agent, ties, and mixed timestamp offsets.
3. Provide a reproducible 1 GB performance harness with elapsed-time and peak-RSS evidence.

### P2 — Could ship later

1. Configurable top-N output.
2. Explicit custom nginx log-format templates.
3. Compressed-file input after measuring decompression effects separately.

## Output Contract

The authoritative command, option, JSON, CSV, terminal, and exit-code schemas
are in `PROJECT_ARCHITECTURE.md` under `## CLI Interface`. JSON numbers remain
numeric. CSV percentages use six decimal places. Terminal percentages may use
two decimals. Output order is stable, and all untrusted log values are escaped
appropriately for their renderer.

## Quality Attributes

| Attribute | Requirement |
|---|---|
| Performance | Representative 1 GB input completes in < 30 s on the documented laptop |
| Memory | No raw input/record retention; measure peak RSS; enforce exact User-Agent ceiling |
| Correctness | One-pass totals match fixture oracles; deterministic ties |
| Portability | Python 3.11 on Linux and macOS; Windows is best-effort for MVP |
| Reliability | Malformed records are isolated; expected failures map to stable exit codes |
| Security | Never execute/fetch log content; no network, credentials, or persistence |
| Accessibility | Non-color meaning remains clear; `--no-color` and non-TTY behavior supported |

## Release Acceptance

- [ ] All P0 story criteria pass on Python 3.11.
- [ ] Cross-format golden tests prove equivalent metrics.
- [ ] Exit codes `0/1/2/3/4` are each covered by an integration test.
- [ ] pip wheel installation and console entry point are smoke-tested in a clean environment.
- [ ] The documented benchmark meets the target on the recorded reference laptop.
- [ ] No P0 behavior relies on a database, HTTP API, server, cloud, or Kubernetes.

## Kill Criteria

Pause release and revisit the architecture if measured single-process Python
cannot meet the 1 GB/30 s target after profiling; if exact required output
cannot fit within a documented laptop resource envelope; or if any new
requirement mandates persistence or a network service. Do not silently weaken
exact metrics or remap exit code 4 to ship on schedule.

## Dependencies and Traceability

`STRATEGIC_PLAN.md` owns priorities and business constraints.
`PROJECT_ARCHITECTURE.md` owns technical contracts. `IMPLEMENTATION_PLAN.md`
maps every P0 story to concrete files and verification. Behavioral changes
must update this PRD before implementation.
