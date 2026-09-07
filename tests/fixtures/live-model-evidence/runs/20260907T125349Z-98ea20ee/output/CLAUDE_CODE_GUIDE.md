# Claude Code Implementation Guide: nginx-stream-insights

Use this guide after the blueprint is accepted. Run one step at a time in the order below. Before each step, read `PROJECT_ARCHITECTURE.md`, the corresponding section of `IMPLEMENTATION_PLAN.md`, and relevant acceptance criteria in `PRD.md`. Do not silently change public behavior: specifications are the source of truth.

## Global Guardrails

- Use Python 3.11, Click, Rich, and dataclasses with the `src/` layout in `PROJECT_ARCHITECTURE.md`.
- Preserve one synchronous process, streaming input, no database, no HTTP API, no server, no authentication, no cloud, and no Kubernetes.
- Keep stdout machine-clean in JSON/CSV modes and place diagnostics on stderr.
- Calculate hourly percentages only as `100 × hourly_request_count / total_valid_requests`.
- Preserve the complete exit-code contract: `0` success; `1` input I/O or interruption; `2` usage/configuration; `3` zero valid requests; `4` unique-cardinality exhaustion.
- Do not remap code 4 or emit a completed-looking result after its failure condition.
- Work WIP=1, record tests for each step, and use the repository Verification Loop for the exact staged candidate before release.

## Prompt 1: Scaffold the Package and CLI

```text
Implement Step 1 from IMPLEMENTATION_PLAN.md only. Create pyproject.toml, the package __init__.py, CLI declarations, and CLI contract tests. Match every option, default, mutual exclusion, and usage failure in PROJECT_ARCHITECTURE.md. Do not implement parsing or aggregation. Run the listed verification commands, report changed files and observed evidence, then stop.
```

Expected evidence: editable install succeeds, help/version work, invalid option combinations exit 2, and focused tests pass.

## Prompt 2: Define Models and Fixtures

```text
Implement Step 2 from IMPLEMENTATION_PLAN.md only. Add explicit dataclasses for parsed records, configuration, ranked/hourly rows, User-Agent summary, and the complete result. Create small representative combined/common/malformed fixtures and expected structured results. Cover ties, error statuses, queries, offsets, Unicode, missing User-Agents, and control characters. Run the step verification and stop.
```

Expected evidence: models compile, fixtures encode every stated invariant, and focused tests pass.

## Prompt 3: Implement the Parser

```text
Implement Step 3 from IMPLEMENTATION_PLAN.md only. Build a line-at-a-time parser for built-in nginx combined and common profiles with precompiled patterns. Return LogRecord or a documented malformed result; never evaluate log content. Add boundary and malformed tests. Do not build renderers or read a whole file. Run the listed tests/lint and stop.
```

Expected evidence: both profiles and all malformed cases are exercised without full-file buffering.

## Prompt 4: Implement Aggregation

```text
Implement Step 4 from IMPLEMENTATION_PLAN.md only. Consume LogRecord values into exact IP/error counters, a fixed 24-hour count structure, and a set of nonempty User-Agents. Rank by count descending then key ascending. Compute hourly distribution using exactly 100 × hourly_request_count / total_valid_requests. Enforce the configured exact User-Agent ceiling before insertion and expose the typed failure that maps to exit 4. Add focused tests and stop after verification.
```

Expected evidence: golden counts/formulas/ties pass, accounting is exact, and the cardinality boundary is tested on both sides.

## Prompt 5: Implement Renderers

```text
Implement Step 5 from IMPLEMENTATION_PLAN.md only. Add Rich text, schema-versioned JSON, and long-form RFC 4180 CSV renderers using the exact structures in PROJECT_ARCHITECTURE.md. Color text only under the documented policy, escape untrusted values, keep structured formats ANSI-free, and render only after aggregation. Add parse/round-trip/snapshot tests, run verification, and stop.
```

Expected evidence: JSON and CSV parse with standard libraries, snapshots pass, and stdout contains no ANSI in structured modes.

## Prompt 6: Integrate the CLI and Failure Contract

```text
Implement Step 6 from IMPLEMENTATION_PLAN.md only. Wire file/stdin streaming, parser, aggregator, and renderer selection in cli.py. Keep diagnostics on stderr, avoid closing caller-owned stdin, and handle expected errors without tracebacks. Implement and integration-test exactly: 0 success, 1 input I/O or interruption, 2 usage/configuration, 3 zero valid requests, 4 unique-cardinality exhaustion. Compare file and stdin results, run the full focused verification, and stop.
```

Expected evidence: tests exercise `0/1/2/3/4` and structured stdout remains parseable for successful runs.

## Prompt 7: Prove Performance

```text
Implement Step 7 from IMPLEMENTATION_PLAN.md only. Add deterministic benchmark data generation, a three-run benchmark harness with environment and peak-RSS metadata, and a CI-safe performance smoke test. Generate the 1 GB fixture outside the repository. Measure before optimizing; change only demonstrated hot paths while preserving tests and specifications. Run the stated verification and report timings as observed evidence, then stop.
```

Expected evidence: three measured runs, median under 30 seconds on the documented laptop, peak RSS recorded, and all correctness tests still pass.

## Prompt 8: Package and Document

```text
Implement Step 8 from IMPLEMENTATION_PLAN.md only. Add the Python 3.11 CI checks, finalize README examples against the actual command, add license/build metadata, build wheel and sdist, and test installation in a clean environment. Do not introduce runtime services or containers. Run build, package validation, and tests, then stop.
```

Expected evidence: clean wheel install exposes the command, distributions validate, and examples match observed output.

## Prompt 9: Verify the Exact Candidate

```text
Execute Step 9 from IMPLEMENTATION_PLAN.md without adding features. Freeze the exact staged candidate, run lint, types, tests, coverage, builds, install smoke tests, all exit-code cases 0/1/2/3/4, and the documented 1 GB benchmark. Run the repository's machine oracle and risk-tier checker as required by .itd/VERIFICATION_CONTRACT.json. Accept completion only from a current revalidated adjudication receipt; otherwise record recovery required. Stop with a concise evidence handoff.
```

Expected evidence: current exact-candidate verification receipt, green functional/static/build checks, performance metadata, and no out-of-scope diff.

## Recovery Prompts

If a step fails, keep the same active unit and use:

```text
Diagnose the observed failing command from the current implementation step. Do not expand scope. Add or refine the smallest regression test, make the minimum correction consistent with PRD.md and PROJECT_ARCHITECTURE.md, rerun the focused check and all previously green checks for this step, and record actual evidence. Do not proceed to the next step while the failure remains.
```

If specifications conflict, stop code changes, treat `PROJECT_ARCHITECTURE.md` as the architecture/interface authority and `PRD.md` as behavior authority, reconcile the documents explicitly, and only then resume implementation.

