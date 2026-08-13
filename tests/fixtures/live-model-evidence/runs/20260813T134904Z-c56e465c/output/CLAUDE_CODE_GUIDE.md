# Claude Code Implementation Guide: Nginx Stream Insights

## How to Use This Guide

Run one prompt at a time, in order, against [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). Before editing, read [PRD.md](PRD.md), [PROJECT_ARCHITECTURE.md](PROJECT_ARCHITECTURE.md), `AGENTS.md`, `.itd/SCOPE_LOCK.md`, and the active Idea to Deploy implementation skill. Preserve WIP=1. Do not mark a step complete from narration: run its stated verification and record actual evidence.

The behavioral source is the PRD and the technical source is the architecture. If implementation pressure suggests changing behavior, update those specifications and scope state before code.

## Non-Negotiable Contract for Every Step

- Python 3.11, Click, Rich, dataclasses, `src/` layout, pip installability.
- Single-process stateless streaming; never read the entire input into memory.
- No authentication, database, HTTP API, server, cloud, Docker requirement, or Kubernetes.
- Hourly percentage is exactly `100 × hourly_request_count / total_valid_requests`.
- The complete exit-code map is `0` success, `1` unexpected internal error, `2` CLI usage/input I/O/encoding error, `3` log-data failure, and `4` unique-cardinality exhaustion. Code `4` must remain distinct in implementation, tests, and docs.
- Normal output uses stdout; diagnostics use stderr. Failed JSON/CSV runs emit no partial document.
- Do not run or fabricate an adversarial architecture review in this implementation session unless a later user explicitly scopes it.

## Prompt 1: Scaffold the Package

> Implement only Step 1 of `IMPLEMENTATION_PLAN.md`. Create the Python 3.11 `src/` package, PEP 621 metadata, console entry point, and Click interface for the exact options under `PROJECT_ARCHITECTURE.md` → `CLI Interface`. Keep analysis behavior unimplemented but make help, version, and validation real and tested. Do not create any server, database, or container files. Run the three Step 1 verification commands, report their actual outcomes, update persistent state only from evidence, and stop before Step 2.

Acceptance focus: clean editable install, exact command/options, validation exits `2`, and no invented runtime behavior.

## Prompt 2: Define Models and Failures

> Implement only Step 2 of `IMPLEMENTATION_PLAN.md`. Add immutable dataclasses and domain exceptions matching the architecture, including a single explicit exit mapping for codes `0/1/2/3/4`. Ensure unique-cardinality exhaustion maps only to `4`. Add the documented fixtures and focused tests without implementing aggregation or rendering. Run the Step 2 verification commands and stop.

Acceptance focus: no Click/Rich dependency in domain models, fixture expectations are documented, and code `4` has an executable assertion.

## Prompt 3: Parse Combined Logs

> Implement only Step 3 of `IMPLEMENTATION_PLAN.md`. Build a precompiled nginx combined-log parser that returns `AccessRecord`, validates required fields, preserves numeric timezone offset and exact request target/User-Agent semantics, and never logs a full malformed raw line. Process individual lines only. Add all listed parser tests and invalid-UTF-8 integration behavior. Run Step 3 tests and branch coverage, then stop.

Acceptance focus: status validation, quoted fields, `-` markers, line numbers, UTF-8 errors mapped to `2`, and no accumulated input.

## Prompt 4: Aggregate Metrics Safely

> Implement only Step 4 of `IMPLEMENTATION_PLAN.md`. Create the streaming aggregator, deterministic ranking ties, status range 400–599, 24 hourly buckets using literal semantics `100 × hourly_request_count / total_valid_requests`, and exact unique User-Agent share. Enforce the combined unique-key ceiling before insertion and raise the domain error mapped to exit `4`. Cover the boundary at the limit and the first key beyond it. Run Step 4 verification and stop.

Acceptance focus: count conservation, exact definitions, stable ties, O(unique tracked keys) state, and cardinality exhaustion distinct from codes `1`, `2`, and `3`.

## Prompt 5: Render Three Formats

> Implement only Step 5 of `IMPLEMENTATION_PLAN.md`. Add isolated Rich text, versioned JSON, and long-form CSV renderers using finalized report dataclasses. Make output deterministic; auto-disable text color for non-TTY stdout; mitigate CSV spreadsheet formulas as specified. Select exactly one renderer after successful finalization. Add parsed and golden tests, run Step 5 verification, and stop.

Acceptance focus: no ANSI in machine output, schema keys/columns match architecture, all 24 hours appear, and diagnostics never enter stdout.

## Prompt 6: Complete CLI Failure Semantics

> Implement only Step 6 of `IMPLEMENTATION_PLAN.md`. Wire file/stdin processing, strict and non-strict malformed behavior, empty-input semantics, concise diagnostics, and atomic machine output. Write integration tests that explicitly exercise all exit codes: `0` success, `1` forced unexpected internal error at a controlled test seam, `2` option/input failure, `3` log-data failure, and `4` unique-cardinality exhaustion. Run Step 6 verification and stop.

Acceptance focus: file/stdin parity, stdout/stderr separation, no partial JSON/CSV, and no omitted or remapped code `4`.

### Required exit-matrix evidence

| Scenario | Expected code | Stdout |
|---|---:|---|
| Valid fixture | `0` | Complete report |
| Controlled internal exception | `1` | Empty for JSON/CSV |
| Missing file or invalid option combination | `2` | Empty |
| Strict malformed input or non-empty all-invalid input | `3` | Empty for JSON/CSV |
| `--max-unique` exceeded | `4` | Empty for JSON/CSV |

## Prompt 7: Validate Correctness and Speed

> Implement only Step 7 of `IMPLEMENTATION_PLAN.md`. Add a deterministic representative-log generator, opt-in performance harness, count-conservation checks, and hourly-percentage property checks. Generate the 1 GB fixture outside timing. On a named laptop, run the full correctness suite and three warm-cache timed analyses with peak RSS. Do not weaken parsing or the unique-cardinality guard for speed. Record real environment and results in `README.md`; if the median is not under 30 seconds, profile and leave the step open. Stop before packaging.

Acceptance focus: reproducibility, measured rather than estimated performance, median under 30 seconds, and the formula `100 × hourly_request_count / total_valid_requests`.

## Prompt 8: Package and Accept the Candidate

> Implement only Step 8 of `IMPLEMENTATION_PLAN.md`. Finalize wheel metadata and user documentation, build the distribution, install it in a fresh Python 3.11 virtual environment, and smoke-test path/stdin plus text/JSON/CSV. Run the full test and coverage gates. Confirm the installed CLI exposes the unchanged `0/1/2/3/4` contract, with `4` meaning unique-cardinality exhaustion. Reconcile project state only with actual evidence and report any unmet gate as open; do not claim release readiness otherwise.

Acceptance focus: clean wheel install, documentation/behavior agreement, all P0 criteria, coverage gate, and recorded benchmark.

## Review Checklist After Each Prompt

- [ ] Only the active implementation-plan step changed.
- [ ] No raw input collection or unbounded tracked-key growth was introduced.
- [ ] Tests include success, boundary, and failure behavior relevant to the step.
- [ ] stdout/stderr and schema stability remain intact.
- [ ] The exit-code contract still includes exact meanings for `0/1/2/3/4`.
- [ ] Verification output was actually observed and persistent status matches it.
- [ ] The next action is explicit, with no product code from the next step started.
