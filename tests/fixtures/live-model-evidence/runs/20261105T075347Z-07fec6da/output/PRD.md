# Product Requirements: Nginx Lens

## Problem and Outcome
DevOps/SRE engineers need quick, reproducible answers from local nginx access logs without running analytics infrastructure. A finite streaming CLI must report top-10 IPs, top-10 paths by combined 4xx/5xx count, hourly request percentages, and unique User-Agent share. Success means correct metrics, pipeline-safe output and a measured 1 GB / under-30-second run on a documented laptop.

## Scope and Priorities
P0 = Must, P1 = Should, P2 = Could, aligned with [STRATEGIC_PLAN.md](STRATEGIC_PLAN.md). P0 is the one-weekend release boundary. The requirements below are pre-approved; no additional confirmation is needed for this blueprint. Stories follow descending RICE value subject to parsing and packaging dependencies.

## User Stories
- As a DevOps engineer, I want to analyze a local combined access log or stdin, so that I can inspect an incident without a service. **S1 — P0 (Must), RICE 160.**
  - Acceptance: file and byte-identical stdin yield identical summaries; default input and `-` both select stdin.
  - Acceptance: strict combined-format parsing counts malformed/oversized lines as invalid; a final valid line without newline is accepted; valid records alone affect metrics.
  - Acceptance: at least one valid request produces a report and exit 0 even with invalid lines; empty/all-invalid input produces stderr, empty stdout and exit 3.
- As a responding SRE, I want the top-10 IPs and error URL paths, so that I can identify traffic sources and failing routes. **S2 — P0 (Must), RICE 160.**
  - Acceptance: IPs count all valid requests; error paths count only statuses 400–599, combining 4xx and 5xx.
  - Acceptance: query/fragment removal merges `/login?a=1` and `/login?a=2` into `/login`; percent encoding and case remain intact.
  - Acceptance: each ranking contains at most 10 entries, sorted by count descending then literal key ascending; fixtures cover ties and status boundaries.
- As a platform engineer, I want hourly request percentages, so that I can see when traffic occurs. **S3 — P0 (Must), RICE 128 shared with S4.**
  - Acceptance: output always includes 24 bins, using each timestamp's logged local hour and merging dates without UTC conversion.
  - Acceptance: each percentage uses `100 × hourly_request_count / total_valid_requests`; 3 requests in one hour out of 4 yields 75.00%.
  - Acceptance: counts sum to valid requests; display uses two decimals and documents rounding drift.
- As an SRE, I want the share of unique User-Agents, so that I can assess request diversity. **S4 — P0 (Must), RICE 128 shared with S3.**
  - Acceptance: report the exact count of distinct nonmissing unescaped User-Agent strings and `100 × distinct_nonmissing_user_agents / total_valid_requests`.
  - Acceptance: UA values A, A, B, `-` across four valid requests yield distinct count 2 and share 50.00%; empty and `-` do not enter the set.
  - Acceptance: differences in case represent distinct UAs; this metric makes no claim about unique users or bot detection.
- As an automation engineer, I want predictable resource failures, so that scripts cannot accept a partial report. **S7 — P0 (Must), RICE 114.29.**
  - Acceptance: entry count is the sum of distinct IPs, error paths, and nonmissing UAs; a repeated key uses no new entry.
  - Acceptance: default --max-unique is 1000000, accepts positive integers only, and checks all additions for a record before mutating counters; exactly at budget succeeds, crossing it exits 4.
  - Acceptance: MemoryError also maps to code 4; resource failures print a brief stderr diagnostic with no aggregate on stdout and never approximate.
- As an on-call engineer, I want colored terminal tables, so that I can read a report quickly. **S5 — P0 (Must), RICE 80 shared with S6.**
  - Acceptance: default output includes all four metrics and valid/invalid totals; color appears only on a TTY with NO_COLOR absent and --no-color unset.
  - Acceptance: raw ANSI/Rich markup in logs is inert in terminal output; diagnostics never echo raw lines.
- As a pipeline author, I want JSON and CSV exports, so that I can consume the same metrics automatically. **S6 — P0 (Must), RICE 80 shared with S5.**
  - Acceptance: --json produces one schema-version-1 object; --csv produces the exact normalized header and rows in architecture; both contain all metrics and totals, without ANSI or diagnostics on stdout.
  - Acceptance: conflicting --json/--csv exits 2 before opening input; quoting and Unicode round-trip in machine modes.
  - Acceptance: file/stdin I/O failures, broken pipe and unexpected runtime failures exit 1; help/version exit 0. The complete public exit contract is 0/1/2/3/4 as defined below.
- As a laptop operator, I want a pip-installable fast tool, so that I can use it during an incident. **S8 — P0 (Must), RICE 60.**
  - Acceptance: a clean Python 3.11 virtual environment installs the wheel and executes nginx-lens without source-checkout imports.
  - Acceptance: benchmark processes a full 1,000,000,000-byte valid file below the default entry cap; median of three warm laptop runs is under 30 s including startup/report output; hardware, cache state, versions and RSS are recorded.
- As an operator with rotated archives, I want direct gzip input, so that I can avoid an explicit decompression pipeline. **S9 — P1 (Should), RICE 28; deferred after weekend.**
- As an operator with a custom nginx format, I want format configuration, so that I can analyze nonstandard logs. **S10 — P2 (Could); deferred pending demand and parser design.**

## Functional Contract
The precise command is `nginx-lens [OPTIONS] [INPUT]`. Options are --json, --csv, --max-unique INTEGER, --no-color, --help, --version. One file or finite stdin stream is supported; EOF triggers output. The [architecture CLI Interface](PROJECT_ARCHITECTURE.md#cli-interface) and output schemas are normative for keys, CSV order, escaping, input grammar and failure precedence.

| Exit | Meaning |
|---|---|
| 0 | Successful complete report with valid input, or help/version |
| 1 | I/O, interruption, or unexpected runtime failure |
| 2 | CLI usage error |
| 3 | No valid requests |
| 4 | unique-cardinality exhaustion, including MemoryError |

## Nonfunctional Requirements
- Python 3.11; Click, Rich, dataclasses; pip installability; $0 infrastructure budget.
- Single process, incremental reads, bounded line payload (65,536 bytes), explicit aggregate cardinality cap. No retention of full log records.
- Exact counts while within cap; no silent samples, eviction, approximation or truncation.
- Local operation without authentication, database, HTTP API, server, cloud, Kubernetes or telemetry.
- Deterministic output, Unicode-safe escaping, stderr-only diagnostics, and no raw-line disclosure.
- Performance goal is a release criterion requiring measurement; it is not a guarantee for arbitrary laptop hardware or adversarial cardinality.

## Out of Scope
Persistent historical dashboards, auth/access management, live tailing, multiple input files, direct gzip input for MVP, custom format parsing for MVP, HTTP endpoints, containers, deployment automation, approximate unique counts, URL query analytics and bot/user attribution.

## Kill Criteria and Release Gate
Do not release if golden metrics or any exit code fail, if the installed wheel cannot run offline after dependency installation, if reports silently truncate on resource failure, or if measured benchmark misses the target. If performance cannot be achieved within the weekend, stop release and present evidence and scope options; do not silently change language or architecture. Reconsider further investment if volunteer trials find no repeat incident-use value.

## Traceability
Stories S1–S2 map to implementation steps 1–3; S3–S4/S7 to step 4; S5–S6 to steps 5–6; S8 to steps 7–8. All P0 stories also receive end-to-end checks. See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md), [CLAUDE_CODE_GUIDE.md](CLAUDE_CODE_GUIDE.md), [CLAUDE.md](CLAUDE.md) and [README.md](README.md). This blueprint does not implement or test the product.
