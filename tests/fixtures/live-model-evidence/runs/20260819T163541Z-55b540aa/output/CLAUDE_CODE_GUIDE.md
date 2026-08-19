# Claude Code Implementation Guide: Nginx Insight

## 1. How to Use This Guide

Run one prompt at a time in a fresh, evidence-aware implementation session. Before each prompt, read `CLAUDE.md`, `PRD.md`, `PROJECT_ARCHITECTURE.md`, and the matching step in `IMPLEMENTATION_PLAN.md`. Inspect existing work before editing, preserve WIP=1, and stop if the requested behavior conflicts with the specs.

This guide does not authorize database, authentication, HTTP API, server, cloud, Docker, Kubernetes, telemetry, or unrelated product work. Do not claim a step complete until its listed commands actually run successfully.

The complete public exit-code contract applies to every prompt:

- `0` = success.
- `1` = processing/data error.
- `2` = CLI usage error.
- `3` = input/output error.
- `4` = unique-cardinality exhaustion.

Never omit or remap code 4. Never silently approximate cardinality.

## 2. Prompt 1 — Package and Contract Skeleton

```text
Implement only STEP 1 from IMPLEMENTATION_PLAN.md.

Read CLAUDE.md, PRD.md, and PROJECT_ARCHITECTURE.md first. Create the Python 3.11 src-layout package, pyproject.toml, console entry point, typed dataclasses, Click option surface, and the initial help/version/usage tests. Keep domain logic out of cli.py. Do not implement the parser, aggregators, or renderers yet and do not add any server/persistence/container component.

Preserve the public 0/1/2/3/4 exit contract, with code 4 reserved for unique-cardinality exhaustion. Run exactly the STEP 1 verification commands and report actual results, changed files, and any unresolved issue. Do not advance to STEP 2.
```

## 3. Prompt 2 — Streaming Combined-Log Parser

```text
Implement only STEP 2 from IMPLEMENTATION_PLAN.md on top of the verified STEP 1 candidate.

Build parser.py and the sequential files/stdin iterator for the exact combined-log grammar and error behavior in PROJECT_ARCHITECTURE.md. Add focused fixtures and parser/CLI tests. Never retain all raw lines, never echo a malformed full line, and never turn a parse failure into an I/O failure. Default malformed lines are counted/skipped; --strict maps the first malformed line to code 1. CLI usage remains 2, I/O remains 3, and code 4 remains reserved for unique-cardinality exhaustion.

Run the STEP 2 verification commands plus the existing suite. Report evidence and stop; do not implement aggregation or output rendering.
```

## 4. Prompt 3 — Exact Streaming Metrics

```text
Implement only STEP 3 from IMPLEMENTATION_PLAN.md.

Create aggregate.py with the one-pass bounded state and exact metric semantics from PROJECT_ARCHITECTURE.md. Top lists are at most ten and have deterministic tie ordering. Generate all 24 hour buckets and calculate each percentage with the literal formula 100 × hourly_request_count / total_valid_requests. Calculate unique User-Agent share as a percentage, not a fraction. Enforce --max-unique independently for IPs, error URLs, and User-Agents; attempting a new key over the limit raises a typed cardinality error that will map to exit 4. Do not add approximation.

Add all specified boundary tests, run STEP 3 checks and the existing suite, and report actual evidence. Preserve codes 0/1/2/3/4 exactly. Do not start renderers.
```

## 5. Prompt 4 — CLI Orchestration and Exit Matrix

```text
Implement only STEP 4 from IMPLEMENTATION_PLAN.md.

Wire Click, input iteration, parsing, aggregation, and ReportSnapshot creation through thin cli.py orchestration. Implement one explicit exception-to-exit boundary. Prove the full subprocess matrix: 0 success, 1 processing/data error, 2 CLI usage error, 3 input/output error, and 4 unique-cardinality exhaustion. Code 4 must remain distinct. Ensure a machine-format failure leaves stdout empty and diagnostics go to stderr.

Run STEP 4 verification plus all prior tests. Report commands and real outputs succinctly, then stop before renderer work.
```

## 6. Prompt 5 — Safe Rich Renderer

```text
Implement only STEP 5 from IMPLEMENTATION_PLAN.md.

Create the renderer boundary and Rich terminal renderer for summary, top IPs, top error URLs, all 24 hourly counts/percentages, and unique User-Agent count/share. Escape untrusted Rich markup. Implement auto color and --color/--no-color without affecting machine formats. Add and review deterministic no-color golden tests, empty-state behavior, long-value behavior, and rounding cases.

Do not change parser/metric semantics or the complete 0/1/2/3/4 mapping (4 means unique-cardinality exhaustion). Run STEP 5 and regression checks; report evidence and stop.
```

## 7. Prompt 6 — Stable JSON and CSV

```text
Implement only STEP 6 from IMPLEMENTATION_PLAN.md.

Create JSON schema-version-1 and fixed-header long-form CSV renderers exactly as specified under PROJECT_ARCHITECTURE.md ## CLI Interface. Use standard encoders, deterministic ordering, newline termination, no ANSI/progress on stdout, and CSV spreadsheet-formula neutralization. Build complete golden fixtures and validate the schemas through subprocesses. --json plus --csv is usage code 2; output I/O failure is code 3.

Preserve every exit: 0 success, 1 processing/data, 2 usage, 3 I/O, 4 unique-cardinality exhaustion. Run STEP 6 verification and the complete suite. Report evidence and stop.
```

## 8. Prompt 7 — Performance and Robustness

```text
Implement only STEP 7 from IMPLEMENTATION_PLAN.md.

Add a deterministic benchmark-data generator and CI-safe performance test. First run and record correctness plus a baseline profile. Generate the representative 1 GB fixture outside the repository, warm once, measure three runs on the documented laptop, and report median wall time and peak RSS. Optimize only measured hot paths and rerun golden/correctness tests after every change. Exercise hostile terminal/CSV values, privacy-safe diagnostics, and exhaustion of each unique collection.

Do not introduce multiprocessing, a database, server, persistence, approximation, or a new architecture without a spec change. Preserve 0/1/2/3/4; code 4 remains unique-cardinality exhaustion. Do not invent benchmark results if the environment cannot run them—mark the step unverified instead. Stop after STEP 7.
```

## 9. Prompt 8 — Release Candidate

```text
Implement only STEP 8 from IMPLEMENTATION_PLAN.md after STEPS 1–7 have current evidence.

Complete user documentation, Python ignore rules, owner-approved open-source license metadata, wheel/sdist creation, and fresh-venv wheel installation. Cross-check --help, README, PRD.md, and PROJECT_ARCHITECTURE.md for the same command/options/formulas/schemas. Verify all tests, Ruff, mypy, distribution checks, and the already recorded performance acceptance. Confirm 0/1/2/3/4 everywhere, where code 4 means unique-cardinality exhaustion.

Do not publish a package, create a remote release, or perform any external side effect unless separately authorized. Report the exact commands actually run and remaining blockers. Completion requires real evidence, not a prose assertion.
```

## 10. Review Checklist for Every Step

- [ ] Only the current implementation-plan step changed.
- [ ] Required specs were read before editing and changed first if behavior intentionally changed.
- [ ] No raw-log accumulation or hidden persistence was added.
- [ ] No authentication, database, HTTP API, server, cloud, Docker, or Kubernetes was added.
- [ ] Machine stdout remains deterministic and diagnostic-free.
- [ ] Exit codes are exactly `0/1/2/3/4`; code 4 means unique-cardinality exhaustion.
- [ ] New behavior has focused tests and the full prior suite still passes.
- [ ] Verification results are actual and current; skipped checks are labeled unverified.
- [ ] Session state and next action are recorded according to `CLAUDE.md`.

## 11. Handoff Format

End each implementation session with:

```text
Step: <N and name>
Status: verified | blocked | unverified
Changed: <files>
Evidence: <commands and observed pass/fail>
Contract check: 0/1/2/3/4 preserved; code 4 = unique-cardinality exhaustion
Blockers: <none or concrete issue>
Next action: <one bounded action>
```
