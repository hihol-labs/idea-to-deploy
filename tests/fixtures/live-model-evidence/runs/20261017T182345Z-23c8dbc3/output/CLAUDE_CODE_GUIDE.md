# Claude Code Implementation Guide: nginx-stream-report

This guide turns `IMPLEMENTATION_PLAN.md` into bounded prompts. Run one step at a time, inspect the diff, and require its verification before continuing. Do not implement authentication, storage, an HTTP server, cloud resources, or Kubernetes.

## Global Contract for Every Step

- Read `PRD.md`, `PROJECT_ARCHITECTURE.md`, and the current step in `IMPLEMENTATION_PLAN.md` before editing.
- Preserve streaming behavior and stdout/stderr separation.
- Add or update tests with every behavior change.
- Do not alter the public interface without first updating the source specifications.
- Preserve the complete `0/1/2/3/4` exit-code contract: 0 success, 1 internal error, 2 usage/input error, 3 zero valid requests, and 4 unique-cardinality exhaustion.
- Do not emit partial output after a fatal error.
- End with changed files, commands run, results, and the next uncompleted step.

## Prompt 1 — Package and CLI Skeleton

> Implement Step 1 from `IMPLEMENTATION_PLAN.md`. Create only the packaging files, package skeleton, console entry point, and initial CLI tests named there. Use Python 3.11, Click, Rich, src layout, and pip-compatible `pyproject.toml`. Run the specified install/help/tests and report factual results. Do not implement parsing or reports yet.

## Prompt 2 — Models, Errors, and Fixtures

> Implement Step 2 from `IMPLEMENTATION_PLAN.md`. Define frozen/slotted dataclasses and typed operational failures consistent with `PROJECT_ARCHITECTURE.md`. Add only synthetic fixtures and invariant tests. Keep models free of I/O and UI dependencies. Run the step verification.

## Prompt 3 — Streaming Parser

> Implement Step 3 from `IMPLEMENTATION_PLAN.md`. Parse supported nginx combined log lines lazily and deterministically. Compile the pattern once, treat fields as data, handle invalid UTF-8 as specified, and never retain the entire input. Add the listed edge-case tests and run the step verification.

## Prompt 4 — Aggregations

> Implement Step 4 from `IMPLEMENTATION_PLAN.md`. Compute the two top-10 lists, all 24 hourly percentages using `100 × hourly_request_count / total_valid_requests`, and exact unique User-Agent share in one pass. Enforce the hard User-Agent cardinality ceiling before insertion. Add tests for ties, statuses, percentages, empty input, and exhaustion. Run the step verification.

## Prompt 5 — Terminal Renderer

> Implement Step 5 from `IMPLEMENTATION_PLAN.md`. Add a Rich renderer with four clearly labeled sections, totals, malformed count, and correct automatic/forced color behavior. Keep rendering separate from aggregation and add stable tests that do not overfit terminal width. Run the step verification.

## Prompt 6 — JSON and CSV

> Implement Step 6 from `IMPLEMENTATION_PLAN.md`. Add JSON schema version 1 and normalized CSV renderers exactly as documented. Machine output must contain no ANSI and must remain parseable. Make `--json` and `--csv` mutually exclusive, test both with parsers, and run the step verification.

## Prompt 7 — Exit Codes and Diagnostics

> Implement Step 7 from `IMPLEMENTATION_PLAN.md`. Wire typed failures to the complete public exit-code contract and keep diagnostics on stderr. Exercise codes 0, 1, 2, 3, and 4 in tests, including no partial report on code 4. Run the exact step verification commands.

## Prompt 8 — Performance

> Implement Step 8 from `IMPLEMENTATION_PLAN.md`. Build deterministic streaming fixture generation and a benchmark wrapper that records environment, elapsed time, peak memory, and counts. Exclude fixture generation from timing. Profile before optimizing, preserve correctness, and run the smoke test. Run the 1 GB gate only where the benchmark file and reference-laptop resources are available; otherwise label it not run, never passed.

## Prompt 9 — Release Quality

> Implement Step 9 from `IMPLEMENTATION_PLAN.md`. Reconcile README behavior with the specifications, build wheel and sdist, run coverage/static checks, and smoke-install the wheel in a clean environment. Do not publish, push, deploy, or delete anything. Report all verification results and remaining gaps.

## Final Acceptance Prompt

> Verify the finished product against every P0 acceptance criterion in `PRD.md` and the Definition of Done in `STRATEGIC_PLAN.md`. Run the full test suite, 90% coverage gate, artifact checks, clean wheel install, all three output modes, every exit code in `0/1/2/3/4`, and the documented 1 GB benchmark. Produce an evidence-only report; fix in-scope defects and rerun affected checks, but do not publish or deploy.

