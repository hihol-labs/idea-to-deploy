# Claude Code Guide: Nginx Stream Insights

This guide turns `IMPLEMENTATION_PLAN.md` into handoff-ready prompts. Execute one step at a time (WIP=1). Before each step, read `AGENTS.md`, `.itd/`, `.itd-memory/STATE.json`, `PRD.md`, `PROJECT_ARCHITECTURE.md`, and the named plan step. Do not broaden scope silently. No prompt authorizes a database, HTTP API, server, cloud, Docker, Kubernetes, or product behavior outside the specification.

## Common completion contract

Append this to every implementation prompt:

> Implement only this step using tests as executable acceptance evidence. Run every verification command listed for the step and report exact results. Preserve machine-readable stdout and send diagnostics to stderr. Update `.itd-memory/STATE.json` with evidence and the next action. If a check is not run or fails, mark the unit recovery-required rather than complete. Do not start the next step.

## Prompt 1 — Package skeleton

> Execute Step 1 of `IMPLEMENTATION_PLAN.md`. Create only the packaging, initial Click command, and help/version tests named there. Use Python 3.11, Click, Rich, a `src/` layout, and pip-standard `pyproject.toml`. Do not implement parsing or reports yet.

## Prompt 2 — Models and contracts

> Execute Step 2. Define the exact dataclasses from `PROJECT_ARCHITECTURE.md` and small golden fixtures with hand-calculated outputs. Keep domain models independent of Click and Rich. Treat `PRD.md` as the behavior source of truth.

## Prompt 3 — Parser and input

> Execute Step 3. Implement sequential file/stdin iteration and bounded parsing for the documented common/combined formats. A malformed line must return a structured failure and never terminate the whole stream. Add every parser/input edge case listed by the plan.

## Prompt 4 — Aggregation

> Execute Step 4. Implement one-pass exact aggregation and deterministic top-10 tie-breaking. Include all 24 hours and the exact User-Agent denominator from PRD US-3. Do not retain raw `AccessRecord` objects after update.

## Prompt 5 — Terminal output

> Execute Step 5. Render the immutable report with Rich, escape log-derived markup, preserve semantic output without color, and test TTY/non-TTY/`--no-color` behavior. Do not leak presentation concerns into aggregation.

## Prompt 6 — JSON output

> Execute Step 6. Implement the explicit versioned JSON mapping from `PROJECT_ARCHITECTURE.md`. Ensure stdout contains JSON only, compare against the golden document, and keep ordering deterministic for tests.

## Prompt 7 — CSV output

> Execute Step 7. Use the standard-library CSV writer and the normalized schema from `PROJECT_ARCHITECTURE.md`. Test quotes, commas, empty fields, sections, and absence of ANSI sequences. Enforce JSON/CSV mutual exclusion in Click.

## Prompt 8 — Golden-flow integration

> Execute Step 8. Complete orchestration, error messages, stderr separation, and exit codes. Exercise file, stdin, empty, mixed-invalid, terminal, JSON, CSV, and unreadable-input flows through the installed CLI. Update user documentation only from observed behavior.

## Prompt 9 — Packaging and benchmark evidence

> Execute Step 9. Add a deterministic fixture generator, keep generated bulk data ignored, build and validate distributions, install the wheel cleanly, and measure three representative 1 GB runs. Record hardware, software, correctness, wall time, and peak RSS. Profile before proposing any architecture change; do not claim the target if evidence is missing.

## Final release review prompt

> Review the implementation against every P0 story and Release Acceptance item in `PRD.md`, the Definition of Done in `STRATEGIC_PLAN.md`, and ADR-001 in `PROJECT_ARCHITECTURE.md`. Report a machine-readable pass/blocked verdict with command evidence, unresolved risks, and the explicit next action. Do not publish or deploy externally without separate authorization.
