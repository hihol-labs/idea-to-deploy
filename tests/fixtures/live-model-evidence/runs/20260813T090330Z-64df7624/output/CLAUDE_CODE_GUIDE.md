# Claude Code Implementation Guide: Nginx Insights CLI

Use these prompts one at a time after the blueprint is accepted. Each prompt corresponds to one step in `IMPLEMENTATION_PLAN.md`; do not combine steps. Before editing, read `AGENTS.md`, `CLAUDE.md`, `.itd/SCOPE_LOCK.md`, `PRD.md`, and `PROJECT_ARCHITECTURE.md`. Product specifications are the durable source of truth.

## Non-Negotiable Contract

- Python 3.11, Click, Rich, dataclasses, and pip packaging.
- One local process, one streaming pass, no authentication, database, HTTP API, server, cloud, Docker, or Kubernetes.
- Hourly percentage formula: `100 × hourly_request_count / total_valid_requests`.
- Complete exit codes: `0/1/2/3/4` — 0 success; 1 input I/O or decoding; 2 CLI usage; 3 log-data failure; 4 unique-cardinality exhaustion. Code 4 must never be omitted, remapped, or treated as partial success.
- No product implementation step is complete until its specified tests actually run and pass.

## Prompt 1 — Installable CLI Skeleton

> Execute only Step 1 of `IMPLEMENTATION_PLAN.md`. Create the Python 3.11 `src/` package, Click entry point, and packaging metadata at the exact documented paths. Keep the command behavior skeletal except for help, version, and option validation. Add and run the Step 1 tests and installation checks. Do not begin parsing or aggregation. Reconcile the active Idea to Deploy state and report the commands actually run.

## Prompt 2 — Domain and Exit Contracts

> Execute only Step 2 of `IMPLEMENTATION_PLAN.md`. Implement the dataclasses and typed failures from `PROJECT_ARCHITECTURE.md`; wire and test the exact `0/1/2/3/4` contract, including code 4 for unique-cardinality exhaustion. Do not implement the parser or metrics. Run the specified verification and preserve WIP=1.

## Prompt 3 — Combined-Log Parser

> Execute only Step 3 of `IMPLEMENTATION_PLAN.md`. Implement the standard combined-format parser, file/stdin line streaming, timestamp offset handling, and strict/default malformed behavior. Use safe diagnostics without raw log content. Add domain fixtures and tests, run the specified commands, and stop after Step 3 acceptance.

## Prompt 4 — Required Aggregations

> Execute only Step 4 of `IMPLEMENTATION_PLAN.md`. Implement one-pass IP, error-URL, hourly, and User-Agent aggregation. Enforce statuses 400–599 for error URLs, deterministic ties, and all 24 hours. Use the literal hourly formula `100 × hourly_request_count / total_valid_requests`; do not implement it as an unscaled fraction. Run focused aggregation tests and stop.

## Prompt 5 — Cardinality Guard

> Execute only Step 5 of `IMPLEMENTATION_PLAN.md`. Enforce `--max-unique` independently before inserting a new IP, error URL, or User-Agent key. On exhaustion, emit no partial report and exit 4. Add boundary and CLI tests proving code 4 is distinct from codes 0/1/2/3. Run all specified checks and stop.

## Prompt 6 — Output Renderers

> Execute only Step 6 of `IMPLEMENTATION_PLAN.md`. Implement escaped Rich terminal tables and deterministic schema-versioned JSON and normalized CSV. Keep diagnostics on stderr and machine output ANSI-free. Add golden tests, validate JSON, and do not alter formulas or exit mappings.

## Prompt 7 — Pipeline Hardening

> Execute only Step 7 of `IMPLEMENTATION_PLAN.md`. Complete broken-pipe, encoding, input, no-partial-output, and privacy behaviors. Test stdin/file equivalence and every failure class. The complete exit contract remains `0/1/2/3/4`, where code 4 means unique-cardinality exhaustion. Run the Step 7 verification commands and stop.

## Prompt 8 — Performance and Packaging

> Execute only Step 8 of `IMPLEMENTATION_PLAN.md`. Add the deterministic benchmark generator, CI-safe streaming regression, documentation, and release build. Run the full correctness, coverage, clean-wheel, and documented 1 GB performance gates. Do not claim the <30-second target without recorded runtime evidence from the reference laptop. Do not add deployment services.

## Review Prompt After Each Step

> Review only the current step's diff against `PRD.md`, `PROJECT_ARCHITECTURE.md`, the active scope lock, and that step's acceptance commands. Flag any undocumented behavior, full-input buffering, unsafe Rich markup, partial output, unstable ordering, or exit-code drift. Do not broaden scope or perform the separately scheduled architecture adversarial review.

## Final Release Checklist

- [ ] All P0 stories and acceptance criteria pass.
- [ ] Top IP and 4xx/5xx URL rankings are exact and deterministic.
- [ ] Hourly output has 24 percentage buckets using the documented formula.
- [ ] User-Agent output includes unique count, eligible count, total valid requests, and percentage.
- [ ] Terminal, JSON, and CSV golden tests pass.
- [ ] Codes `0/1/2/3/4` are integration-tested; code 4 proves unique-cardinality exhaustion and no partial output.
- [ ] The 1 GB performance gate is measured and below 30 seconds on the documented laptop.
- [ ] A clean Python 3.11 environment installs and runs the wheel.
- [ ] No prohibited service or persistence component exists.

