# Claude Code Implementation Guide: nginx-report

## 1. How to Use This Guide

Run one prompt at a time, in order, after reading `CLAUDE.md`, `PRD.md`, `PROJECT_ARCHITECTURE.md`, and the matching step in `IMPLEMENTATION_PLAN.md`. These prompts authorize implementation only when a future user invokes them; this blueprint itself contains no product code.

For every step:

1. Keep WIP at one step and preserve unrelated user changes.
2. Update the specification first if behavior must change.
3. Add tests before or with behavior; run the exact verification commands.
4. Freeze and verify the exact staged candidate under the repository's current Idea to Deploy verification contract before accepting completion.
5. Record evidence and update the status table in `CLAUDE.md`.

The public exit-code contract in every implementation is complete and immutable: `0` success, `1` I/O failure, `2` CLI usage/configuration error, `3` malformed log data, and `4` unique-cardinality exhaustion. Code 4 must remain distinct; do not omit, remap, or silently approximate on exhaustion.

## 2. Prompt for Step 1 — Package and Contracts

```text
Implement only STEP 1 from IMPLEMENTATION_PLAN.md. Read PROJECT_ARCHITECTURE.md sections CLI Interface, Internal Components and Files, and Data Model and Streaming State. Create pyproject.toml, the src/nginx_report package skeleton, immutable report dataclasses, typed expected failures, and tests that freeze exit codes 0/1/2/3/4. Use Python 3.11, Click, Rich, and stdlib dataclasses; add no server, API, database, auth, cloud, Docker, or Kubernetes. Run every STEP 1 verification command. Report changed files and real command results; do not mark the step complete without current evidence.
```

## 3. Prompt for Step 2 — Parser and Early Benchmark

```text
Implement only STEP 2 from IMPLEMENTATION_PLAN.md. Build the byte-oriented nginx combined-log parser, its valid/invalid fixtures, parser tests, deterministic corpus generator, benchmark runner, and benchmark documentation. Parse one line at a time and never retain raw records. A record must update no downstream metric unless every required field validates. Diagnostics must not echo sensitive full lines. Run parser tests and the 100 MB parser-only measurement. Preserve exit codes 0 success, 1 I/O, 2 usage/configuration, 3 malformed data, and 4 unique-cardinality exhaustion even though CLI mapping is finalized later. Record evidence without claiming the final 1 GB target yet.
```

## 4. Prompt for Step 3 — IP and Hourly Aggregation

```text
Implement only STEP 3 from IMPLEMENTATION_PLAN.md. Add atomic streaming aggregation for total lines, valid/invalid records, top 10 IPs, and exactly 24 hourly rows. Use deterministic tie order. Define hourly percentages with the literal formula 100 × hourly_request_count / total_valid_requests, not an unscaled fraction; zero valid requests yields 0.0 for all hours. Add boundary and coverage tests and run every STEP 3 verification command. Do not implement renderers or broaden scope. Preserve the full 0/1/2/3/4 exit contract.
```

## 5. Prompt for Step 4 — Error URLs and User-Agents

```text
Implement only STEP 4 from IMPLEMENTATION_PLAN.md. Count top 10 URLs only for status 400–599. Track exact raw User-Agent identities and enforce the configured maximum before admitting the first excess distinct value. Exhaustion must stop with the typed failure mapped to exit 4 and must never emit an approximate or complete-looking report. Calculate unique User-Agent share as 100 × unique_user_agent_count / total_valid_requests, with 0.0 for empty valid input. Add all specified limit, tie, and status-boundary tests; run STEP 4 verification. Preserve codes 0/1/2/3/4 exactly.
```

## 6. Prompt for Step 5 — Terminal Output

```text
Implement only STEP 5 from IMPLEMENTATION_PLAN.md. Create the Rich terminal renderer for summary counts and all four metrics. Auto-enable color only for a TTY, honor --color/--no-color, and ensure redirected text is ANSI-free by default. Treat report values as untrusted: escape Rich markup and sanitize terminal controls. Add deterministic golden tests and run all STEP 5 commands. Do not change metric calculations, JSON/CSV schemas, or exit codes 0/1/2/3/4.
```

## 7. Prompt for Step 6 — JSON and CSV

```text
Implement only STEP 6 from IMPLEMENTATION_PLAN.md. Create schema-version-1 JSON and the fixed metric,rank,key,count,percentage CSV contract in canonical row order. Output UTF-8, terminate with a newline, never emit ANSI, quote per RFC 4180, and protect formula-leading text cells as specified by PROJECT_ARCHITECTURE.md. Use the same canonical Report model as text output. Add golden and edge-case tests; run all STEP 6 commands. Do not alter the complete 0/1/2/3/4 exit contract.
```

## 8. Prompt for Step 7 — CLI and Exit Integration

```text
Implement only STEP 7 from IMPLEMENTATION_PLAN.md. Wire Click, binary file/stdin iteration, aggregation, and renderer selection in src/nginx_report/cli.py. Enforce --json/--csv mutual exclusion, one stdin marker, a positive exact-cardinality ceiling, strict/default malformed behavior, and stdout/stderr separation. Integration-test every public outcome: 0 success, 1 I/O failure, 2 CLI usage/configuration error, 3 malformed log data, and 4 unique-cardinality exhaustion. Apply precedence 1 over 4 over 3 over 0 after parsing. Expected failures must not show tracebacks. Run every STEP 7 verification command and report actual results.
```

## 9. Prompt for Step 8 — Performance and Robustness

```text
Implement only STEP 8 from IMPLEMENTATION_PLAN.md. Add deterministic arbitrary-byte parser tests and regressions for huge fields, terminal/control injection, CSV formulas, cardinality, and write failures. Measure the complete installed pipeline on the representative 1 GB corpus, recording hardware, OS, Python, cache state, elapsed time, throughput, and peak RSS. Profile before optimizing and preserve exact semantics, schemas, and exit codes 0/1/2/3/4. The acceptance formula for each hour remains 100 × hourly_request_count / total_valid_requests. Run the full suite and the <=30-second benchmark. If the gate fails, report recovery evidence and invoke the PRD reassessment criteria; do not claim success.
```

## 10. Prompt for Step 9 — Release Candidate

```text
Implement only STEP 9 from IMPLEMENTATION_PLAN.md. Finish user documentation, license/changelog decisions, clean wheel installation testing, and release evidence. README must document inputs, outputs, percentage formulas, privacy boundary, exact-cardinality ceiling, and the complete exit-code mapping: 0 success, 1 I/O, 2 usage/configuration, 3 malformed data, 4 unique-cardinality exhaustion. Build and install the wheel in a fresh Python 3.11 environment. Freeze the exact staged candidate, run the current repository machine oracle, apply the risk-tier checker, and require a current revalidated adjudication receipt. Update CLAUDE.md status only from that evidence.
```

## 11. Review Prompt

```text
Review the exact staged nginx-report candidate against PRD.md and PROJECT_ARCHITECTURE.md. Prioritize correctness of combined-log parsing, atomic invalid-line handling, deterministic top-10 ties, the percentage formula 100 × hourly_request_count / total_valid_requests, exact User-Agent cardinality, terminal/CSV injection, stdout/stderr separation, and all codes 0/1/2/3/4 including exhaustion code 4. Check that processing is genuinely streaming and that no database, HTTP API, server, authentication, network call, cloud, or Kubernetes element entered scope. Cite file/line evidence, run only authorized verification, and do not accept without a current exact-candidate adjudication receipt.
```

## 12. Scope Change Protocol

Live follow mode, configurable log formats, compressed input, and configurable top-N require a new scoped unit and specification update. Approximate cardinality, a different language, multiprocessing, native extensions, persistence, or any service boundary requires a new architecture decision. Never introduce one as an incidental optimization.
