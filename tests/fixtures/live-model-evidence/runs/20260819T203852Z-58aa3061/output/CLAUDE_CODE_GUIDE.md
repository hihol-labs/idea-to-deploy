# Claude Code Implementation Guide: Nginx Stream Report

Use these prompts sequentially to implement `IMPLEMENTATION_PLAN.md`. Run only one step at a time (WIP=1), inspect the current repository before editing, and stop on failed evidence. Each prompt requires the applicable Idea to Deploy lifecycle skill and current repository contracts. Do not claim a step complete from prose: freeze the exact candidate, run the machine oracle and risk-tier checker, and require a current revalidated adjudication receipt.

## Non-Negotiable Contract for Every Step

- Remain a local Python 3.11 CLI using Click, Rich, and dataclasses.
- Do not add authentication, a database, an HTTP API, a server, cloud resources, Docker, or Kubernetes.
- Stream input; never retain the full log.
- Keep exact metric semantics, including `100 × hourly_request_count / total_valid_requests`.
- Keep stdout for the selected report and stderr for diagnostics.
- Preserve all exit codes: `0` success (including malformed-line partial success), `1` unexpected internal/output I/O failure, `2` CLI usage error, `3` input/read/parse failure including no valid records, and `4` unique-cardinality exhaustion. Never omit or remap code 4.
- Do not advance with failing tests, undeclared overlays, or stale acceptance evidence.

## Prompt 1: Package and CLI Contract

```text
Execute Step 1 of IMPLEMENTATION_PLAN.md using the smallest applicable Idea to Deploy implementation skill. Read PROJECT_ARCHITECTURE.md under “CLI Interface” and PRD.md before editing. Create only the Python 3.11 src-layout packaging, console entry point, Click option surface, and CLI contract tests named in Step 1. Do not implement parsing or metrics yet. Enforce --json/--csv exclusivity and validate --top and --max-unique. Run every Step 1 verification command, record evidence in the active Idea to Deploy state, and accept only the frozen exact candidate with a revalidated adjudication receipt. Preserve exit codes 0 success, 1 internal/output failure, 2 usage error, 3 input/read/parse failure, and 4 unique-cardinality exhaustion.
```

## Prompt 2: Models, Errors, and Fixtures

```text
Execute Step 2 of IMPLEMENTATION_PLAN.md with WIP=1. Inspect the accepted Step 1 candidate and read the model, output, and error contracts in PROJECT_ARCHITECTURE.md. Add the exact frozen/slotted dataclasses, narrow domain errors, representative combined-log fixtures, and tests listed in Step 2. Fixtures must cover IPv4, IPv6, ties, query strings, malformed input, and high cardinality without containing real secrets. Model the complete mapping: 0 success, 1 internal/output failure, 2 usage error, 3 input/read/parse failure, and 4 unique-cardinality exhaustion. Run the Step 2 checks and the current Verification Loop; do not mark complete without current exact-candidate evidence.
```

## Prompt 3: Streaming Parser

```text
Execute Step 3 of IMPLEMENTATION_PLAN.md. Implement only the buffered file/stdin adapter and documented nginx combined-log parser. Compile parsing machinery once, yield one AccessRecord at a time, keep line number and malformed count, avoid retaining or echoing raw sensitive lines, and do not close stdin owned by the caller. Accept only the grammar in PROJECT_ARCHITECTURE.md; do not add custom log-format configuration. Add every parser edge-case test listed in the step. Run pytest and Ruff plus the current exact-candidate verification flow. Preserve exit codes 0/1/2/3/4 exactly, with code 4 reserved for unique-cardinality exhaustion.
```

## Prompt 4: Exact Bounded Aggregation

```text
Execute Step 4 of IMPLEMENTATION_PLAN.md. Add one-pass exact aggregation for total valid requests, IP counts, 400–599 URL counts, 24 recorded clock-hour buckets, and distinct literal User-Agent strings. Rank by descending count then ascending key. Calculate hourly percentages using the literal formula 100 × hourly_request_count / total_valid_requests. Apply --max-unique independently to IP, error URL, and User-Agent dimensions; reject a new key beyond any ceiling with code 4 and no partial report. Test formulas, ties, empty error rankings, malformed exclusion, top sizes, and every cardinality boundary. Run all Step 4 and Verification Loop checks. Keep codes 0 success, 1 internal/output, 2 usage, 3 input/read/parse, and 4 unique-cardinality exhaustion.
```

## Prompt 5: Rich Text Renderer

```text
Execute Step 5 of IMPLEMENTATION_PLAN.md. Build the default Rich report through the renderer boundary only; do not change parser or metric semantics. Include summary, top IPs, top error URLs, all 24 hours, and User-Agent count/share. Safely render log-controlled strings so markup and control characters cannot alter terminal behavior. Honor terminal color capability and --no-color, and write malformed warnings only to stderr. Add the named golden and safety tests, then run the step checks and exact-candidate acceptance flow. Preserve the full 0/1/2/3/4 contract; code 4 continues to mean unique-cardinality exhaustion.
```

## Prompt 6: JSON and CSV Renderers

```text
Execute Step 6 of IMPLEMENTATION_PLAN.md. Implement JSON schema version 1 and normalized CSV with the exact header section,rank,key,count,percentage. Structured outputs must contain the same metrics as text, numeric percentages, deterministic ordering, correct standard-library escaping, and no ANSI bytes. Keep diagnostics on stderr. Add golden/schema/parse tests and run every Step 6 check plus exact-candidate verification. Do not alter the complete exit mapping: 0 success, 1 internal/output failure, 2 usage error, 3 input/read/parse failure, 4 unique-cardinality exhaustion.
```

## Prompt 7: CLI Integration and Failures

```text
Execute Step 7 of IMPLEMENTATION_PLAN.md. Wire input, parser, aggregator, and renderers in cli.py with narrow expected-exception handling. Demonstrate file/stdin equivalence and stdout/stderr isolation. Test all outcomes: 0 for a successful report even with skipped malformed lines; 1 for unexpected internal or output I/O failure; 2 for invalid usage; 3 for missing/unreadable, empty, or all-invalid input; and 4 for exhaustion of any configured unique-key dimension. Fatal outcomes must not emit a partial report. Run integration tests and the repository Verification Loop, and require a current adjudication receipt before completing the step.
```

## Prompt 8: Performance and Hardening

```text
Execute Step 8 of IMPLEMENTATION_PLAN.md. First create the deterministic benchmark generator, expected-metric metadata, and benchmark runner. Record fixture identity, hardware/OS/Python profile, elapsed wall time, peak RSS, command, and oracle result. Profile before optimizing. Preserve exact semantics and one-pass operation; do not introduce sampling, a database, network service, or multiprocessing without updating the approved architecture. Run the full suite, coverage, Ruff, mypy, and the representative 1 GB under-30-second benchmark. Recheck exit codes 0/1/2/3/4, especially code 4 for unique-cardinality exhaustion. Accept only the frozen candidate with current verification evidence.
```

## Prompt 9: Release Candidate

```text
Execute Step 9 of IMPLEMENTATION_PLAN.md. Update user documentation to match only tested behavior, add the initial changelog, build both wheel and sdist, install the wheel in a clean environment, and smoke-test text, JSON, and CSV through the real nginx-report entry point. Run the entire test/static/package/performance set and the active risk-tier checks. Confirm the public exit contract remains 0 success, 1 internal/output failure, 2 usage error, 3 input/read/parse failure, and 4 unique-cardinality exhaustion. Reconcile Idea to Deploy state and finish only when the exact staged release candidate has a current revalidated adjudication receipt.
```

## Recovery Rules

If a verification command fails, keep the current step active, record the failure as recovery evidence, diagnose the smallest cause, and rerun affected checks before the full step gate. If performance misses 30 seconds, attach the profile and remain in Step 8. If a requested change affects metric meaning, CLI schemas, exit codes, or excluded architecture, update `PRD.md`, `PROJECT_ARCHITECTURE.md`, `.itd/SCOPE_LOCK.md`, and active state before implementation.
