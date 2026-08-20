# Claude Code Guide: Nginx Stream Analytics CLI

## Purpose

Use this guide to execute `IMPLEMENTATION_PLAN.md` one step at a time in a future implementation session. It is planning material, not product code. Start each prompt only after the previous unit has current verification evidence and Idea to Deploy state has been reconciled.

## Non-negotiable Contract for Every Step

- Read `CLAUDE.md`, `.itd/SCOPE_LOCK.md`, `.itd/VERIFICATION_CONTRACT.json`, `PROJECT_ARCHITECTURE.md`, `PRD.md`, and the applicable implementation step before editing.
- Preserve WIP=1 and change only the active unit's declared paths.
- Use Python 3.11, Click, Rich, dataclasses, and pip packaging.
- Keep one local process and stateless streaming. Do not add authentication, a database, HTTP API, server, cloud, Docker runtime requirement, or Kubernetes.
- Do not load the complete input or retain raw/parsed records after aggregation.
- Preserve the exact public exit codes: `0` successful complete report; `1` operational or internal failure; `2` CLI usage error; `3` input data or parse failure; `4` unique-cardinality exhaustion. Code 4 covers guarded distinct IP, error-URL, or User-Agent containers and may not be omitted, remapped, or silently approximated.
- Preserve the literal hourly formula `100 × hourly_request_count / total_valid_requests`.
- Freeze and verify the exact candidate through the repository's current Idea to Deploy verification route before accepting a unit.
- Do not mark a step complete from narration; record the checks named in `IMPLEMENTATION_PLAN.md`.

## Prompt 1 — Package, Contracts, and Harness

```text
Execute STEP 1 of IMPLEMENTATION_PLAN.md only. Bind the active unit and allowed files in .itd/SCOPE_LOCK.md, then create the Python 3.11 package/test/benchmark skeleton and dataclass contracts described by the step. Do not implement parsing, aggregation, or reporters. Keep the console entrypoint thin and initially testable. Run every STEP 1 verification command, record evidence, and use the current verification-loop adjudication before reporting the unit ready. Preserve the complete 0/1/2/3/4 contract from CLAUDE_CODE_GUIDE.md even though outcome translation is implemented later.
```

## Prompt 2 — Streaming Parser

```text
Execute STEP 2 of IMPLEMENTATION_PLAN.md only after STEP 1 is verified. Implement the common/combined line parser in the specified paths, using one compiled anchored parser and typed malformed categories. Parse timezone-aware timestamps and exact request targets/User-Agents; do not read files or print from the parser. Ensure diagnostics can be produced without echoing raw log lines. Add all named unit cases and run STEP 2 checks plus the exact-candidate verification route. Preserve the complete 0/1/2/3/4 contract; parser data failures must remain distinguishable for later exit 3 mapping.
```

## Prompt 3 — Streaming Aggregation

```text
Execute STEP 3 of IMPLEMENTATION_PLAN.md only. Implement single-pass aggregation, deterministic top-10 ties, all 24 hourly buckets, and exact User-Agent uniqueness. Hour percentages must use 100 × hourly_request_count / total_valid_requests; User-Agent share uses the denominator in PROJECT_ARCHITECTURE.md. Check each guarded container before inserting a new distinct key and raise the typed condition reserved for exit 4. Never silently approximate. Run the specified tests/coverage and current exact-candidate verification before accepting the unit. Preserve all exit meanings 0/1/2/3/4.
```

## Prompt 4 — CLI and Failure Boundary

```text
Execute STEP 4 of IMPLEMENTATION_PLAN.md only. Build the Click command and one-pass file/stdin flow with mutually exclusive --json/--csv, --strict, --max-unique, --no-color, --version, and --help. Keep stdout for the report and stderr for sanitized diagnostics; handle normal broken pipes without traceback. Implement and subprocess-test exactly: 0 success, 1 operational/internal failure, 2 CLI usage error, 3 input/parse failure, 4 unique-cardinality exhaustion. Do not allow Click defaults or broad exception handlers to remap code 4. Run every step check and exact-candidate adjudication.
```

## Prompt 5 — Three Reporters

```text
Execute STEP 5 of IMPLEMENTATION_PLAN.md only. Create text, JSON, and CSV reporters that consume the same finalized Report and never recompute metrics. Follow the schema/order/rounding contracts in PROJECT_ARCHITECTURE.md. Escape untrusted terminal values; honor --no-color and NO_COLOR; never emit ANSI in JSON/CSV. Add golden and cross-format tests, run all STEP 5 checks, and adjudicate the exact candidate. Preserve the complete exit contract 0/1/2/3/4 at the CLI boundary.
```

## Prompt 6 — Functional and Safety Acceptance

```text
Execute STEP 6 of IMPLEMENTATION_PLAN.md only. Build acceptance tests traceable to each P0 story in PRD.md, including file/stdin equivalence, malformed/default/strict behavior, exact status boundaries, ties, special characters, redaction, empty input, and all 24 hours. Prove controlled unique-cardinality exhaustion with a small configured limit and exit 4, not real resource exhaustion. Run the full named suites and coverage gate, then the exact-candidate verification route. Require evidence for every outcome 0/1/2/3/4.
```

## Prompt 7 — Performance Proof

```text
Execute STEP 7 of IMPLEMENTATION_PLAN.md only. Generate the ignored deterministic 1 GB fixture, record the reference environment and cache condition, then measure default text mode wall time and peak RSS. If the first run misses 30 seconds, profile before changing code and preserve all output semantics. Measure adversarial cardinality separately and prove code 4. Do not commit benchmark data. Run the listed checks and current risk-tier exact-candidate adjudication; report measured evidence, not estimates. Preserve exit meanings 0/1/2/3/4.
```

## Prompt 8 — Distribution and Release Readiness

```text
Execute STEP 8 of IMPLEMENTATION_PLAN.md only. Finalize user documentation, build wheel/sdist, install the wheel into a clean Python 3.11 environment, and smoke-test both entrypoints plus text/JSON/CSV from file and stdin. Run the complete suite, dependency check, placeholder scan, and repository verification loop. Confirm README documents exactly 0 success, 1 operational/internal failure, 2 usage error, 3 input/parse failure, and 4 unique-cardinality exhaustion. Reconcile durable state and report the next action without publishing or deploying externally.
```

## Recovery Prompt

```text
The active unit failed verification. Do not start another implementation step. Read the current Idea to Deploy state, candidate-bound evidence, and failing command. Classify the smallest root cause, keep .itd/SCOPE_LOCK.md bound to the same unit, repair only in-scope files, rerun the failing check and all unit verification commands, then obtain a current adjudication receipt. Keep outcome semantics fixed at 0/1/2/3/4; never weaken a test or verifier to manufacture success.
```

## Final Handoff Checklist

- [ ] Eight steps are verified in order with WIP=1.
- [ ] P0 story tests and at least 90% branch coverage pass.
- [ ] File and stdin metrics match across text, JSON, and CSV.
- [ ] Hourly percentages use `100 × hourly_request_count / total_valid_requests`.
- [ ] Integration evidence covers exit codes `0/1/2/3/4`, including code 4 cardinality exhaustion.
- [ ] The recorded 1 GB default-text benchmark is under 30 seconds on the declared reference laptop.
- [ ] Wheel and sdist install and pass clean-environment smoke tests.
- [ ] No product server, database, HTTP API, authentication, cloud, or Kubernetes scope has entered the candidate.
- [ ] Idea to Deploy state, evidence, and next action are handoff-ready.
