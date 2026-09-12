# Claude Code Implementation Guide: nginx-log-top

This is a prompt-by-prompt execution guide for a later implementation session. Follow `IMPLEMENTATION_PLAN.md` with WIP=1, update the spec before changing behavior, and do not implement multiple steps in one prompt.

## Global Guardrails

- Read `PRD.md`, `PROJECT_ARCHITECTURE.md`, and the active step before editing.
- Keep the product a local single-process Python 3.11 CLI using Click, Rich, and dataclasses.
- Do not add authentication, a database, an HTTP API, a server, cloud resources, Docker, or Kubernetes.
- Preserve streaming: never call `read()`, `readlines()`, or materialize all records.
- Preserve exit codes `0/1/2/3/4`: 0 success; 1 input I/O failure; 2 CLI usage error; 3 strict parse or output/data failure; 4 unique-cardinality exhaustion.
- Run the active step's verification before claiming it complete and record the evidence.

## Prompt 1 — Package and CLI Contract

> Implement STEP 1 from `IMPLEMENTATION_PLAN.md`. Create only the packaging/entry-point/error-contract files and their focused tests. Use Python 3.11, Click, Rich, and a `src/` layout. Encode the complete `0/1/2/3/4` exit contract without building parsing or rendering early. Run all STEP 1 verification commands and report changed files and actual results.

## Prompt 2 — Parser and Models

> Implement STEP 2 from `IMPLEMENTATION_PLAN.md`. Use the exact `AccessRecord` contract and supported combined format in `PROJECT_ARCHITECTURE.md`. Cover IPv4, IPv6, offsets, placeholders, escaped quoted fields, and malformed input. Do not retain input or add alternate formats. Run the focused tests and coverage gate; report evidence.

## Prompt 3 — Aggregation

> Implement STEP 3 from `IMPLEMENTATION_PLAN.md`. Compute top IPs, 4xx/5xx URL rankings, all 24 hourly buckets, and exact unique User-Agent share in one pass. Use `100 × hourly_request_count / total_valid_requests` for hourly percentages. Apply deterministic tie sorting. Enforce the configured User-Agent ceiling before an inexact result can be returned, mapped to exit code 4. Run focused tests and report evidence.

## Prompt 4 — Rich Text

> Implement STEP 4 from `IMPLEMENTATION_PLAN.md`. Add only the Rich text renderer and its tests. Treat all log-derived strings as untrusted plain text, make labels meaningful without color, and ensure redirected output has no ANSI codes by default. Do not change metric computation. Run the renderer tests and report evidence.

## Prompt 5 — JSON and CSV

> Implement STEP 5 from `IMPLEMENTATION_PLAN.md`. Add JSON schema v1 and normalized RFC 4180 CSV exactly as specified in `PROJECT_ARCHITECTURE.md`. Both must consume the canonical `AnalysisResult`, serialize numeric fields as numbers, emit UTF-8, and contain no ANSI escapes. Run golden and parser validation tests and report evidence.

## Prompt 6 — CLI Integration

> Implement STEP 6 from `IMPLEMENTATION_PLAN.md`. Wire buffered file/stdin iteration to parser, aggregator, and exactly one renderer. Implement strict/lenient behavior, diagnostics on stderr, option validation, and clean write-failure handling. Add integration tests that trigger every exit code `0/1/2/3/4`, with code 4 reserved for unique-cardinality exhaustion. Do not emit a completed-looking partial report after a fatal error. Run the entire suite and report evidence.

## Prompt 7 — Performance Gate

> Implement STEP 7 from `IMPLEMENTATION_PLAN.md`. Build a deterministic known-result 1 GB generator and an opt-in benchmark. First verify output correctness, then record hardware, Python version, wall time, and peak RSS. If the under-30-second gate fails, profile before making a bounded optimization. Do not replace exact metrics with approximation or persistence. Run the documented checks and report measurements without deleting user data.

## Prompt 8 — Release Candidate

> Implement STEP 8 from `IMPLEMENTATION_PLAN.md`. Finish user documentation, CI, license/changelog, builds, metadata checks, and a clean Python 3.11 wheel smoke test. Confirm core coverage is at least 90%, every P0 acceptance criterion is covered, and no forbidden infrastructure has appeared. Report commands and their actual outcomes.

## Final Review Prompt

> Review the exact release candidate against `PRD.md`, `PROJECT_ARCHITECTURE.md`, and `STRATEGIC_PLAN.md`. Check output equivalence, the full exit contract including code 4, streaming/resource behavior, unsafe terminal content, package contents, and the recorded 1 GB performance result. Do not add new features during review. Return findings by severity and cite files/lines; accept only when release criteria have current evidence.
