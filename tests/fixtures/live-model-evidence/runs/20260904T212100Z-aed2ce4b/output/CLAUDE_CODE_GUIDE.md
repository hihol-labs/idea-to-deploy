# Claude Code Implementation Guide: nginx-log-report

This guide turns `IMPLEMENTATION_PLAN.md` into bounded implementation prompts. Run one prompt at a time and keep work in progress at one step. Do not implement from this guide until the planning documents are accepted. Before each step, read `CLAUDE.md`, `PROJECT_ARCHITECTURE.md`, the named PRD requirements, and the active Idea to Deploy contracts.

The non-negotiable exit contract in every step is: `0` success; `1` unexpected internal error; `2` usage or input I/O error; `3` no-valid-data or strict malformed-data error; `4` unique-cardinality exhaustion. Preserve the exact lowercase phrase `unique-cardinality exhaustion` in user-facing documentation. Never omit code 4, remap it, emit a partial report, or silently approximate after the limit is crossed.

## Prompt 1: Package and CLI Skeleton

> Implement Step 1 only from `IMPLEMENTATION_PLAN.md`. Create the pip-installable Python 3.11 `src/` package, Click command, options, console entry point, and CLI contract tests. Do not add parsing or aggregation. Run the step’s three verification commands and report file-level changes plus actual results. Preserve exit codes 0/1/2/3/4 as a forward contract.

## Prompt 2: Domain Models and Errors

> Implement Step 2 only. Add the dataclasses and typed failure hierarchy exactly as specified in `PROJECT_ARCHITECTURE.md`. Centralize mapping for 0/1/2/3/4, with code 4 dedicated to unique-cardinality exhaustion. Add tests that force each mapping; do not build the parser. Run mypy and the focused tests.

## Prompt 3: Combined-Log Parser

> Implement Step 3 only. Parse the documented conventional nginx combined format into `AccessRecord`. Treat input fields as untrusted, retain timestamp offsets, normalize a missing User-Agent to `(missing)`, and return classified parse failures without printing. Add hand-auditable fixtures and all parser edge tests. Run Ruff and focused pytest.

## Prompt 4: Streaming Inputs

> Implement Step 4 only. Add context-managed iterators for stdin, plain files, gzip files, and multiple file paths. Prove no unbounded read occurs. Keep stdout empty on an input failure, map I/O/invalid-gzip to 2, and preserve 1/3/4 mappings. Run focused input and CLI tests.

## Prompt 5: Aggregation and Cardinality

> Implement Step 5 only. Compute exact top IPs, 4xx/5xx URL counts, 24 hourly buckets, and User-Agent cardinality in one pass. Hourly percentages must use `100 × hourly_request_count / total_valid_requests`. Enforce the per-collection limit before inserting a distinct key and exit 4 without partial output. Test deterministic ties, formula scale, reconciliation, and the exact boundary.

## Prompt 6: Rich Terminal Output

> Implement Step 6 only. Render the finalized `Report` with Rich; do not recompute metrics. Honor TTY color behavior and both color flags, escape control sequences in untrusted values, and keep diagnostics on stderr. Test semantic content and ANSI behavior. Preserve the full 0/1/2/3/4 contract.

## Prompt 7: JSON and CSV Output

> Implement Step 7 only. Add mutually exclusive JSON and CSV modes from the same `Report`. Match the exact JSON fields and CSV columns/order in `PROJECT_ARCHITECTURE.md`; use standard serializers; emit no ANSI or diagnostics on stdout. Add hand-verified golden files and schema/parser tests. Preserve code 4 unchanged.

## Prompt 8: End-to-End Hardening

> Implement Step 8 only. Add end-to-end and invariant tests covering all inputs, three outputs, malformed and strict behavior, redacted diagnostics, broken pipe, deterministic order, and every exit code 0/1/2/3/4. Configure and run coverage, Ruff, mypy, and dependency checks. Fix implementation defects, not tests or thresholds.

## Prompt 9: Benchmark and Package

> Implement Step 9 only. Add a deterministic streaming corpus generator and CI-sized performance smoke test. Generate a 1 GB corpus outside the repository, measure wall time and peak RSS on named hardware, then build and clean-install wheel/sdist artifacts. Do not claim the under-30-second goal from an estimate. Freeze and adjudicate the exact candidate per the repository verification contract.

## Review Handoff

After all nine steps, request independent correctness/security review of the exact candidate. Supply the architecture, PRD acceptance criteria, test outputs, benchmark environment/result, package artifacts, and current diff. Do not treat this guide or implementation-agent narration as review evidence.

