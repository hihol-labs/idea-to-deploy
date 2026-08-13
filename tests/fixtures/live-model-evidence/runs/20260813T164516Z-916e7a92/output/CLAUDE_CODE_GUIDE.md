# Claude Code Implementation Guide: nginx-top

## How to Use This Guide

Execute one prompt at a time in the order shown. Before each step, read `PROJECT_ARCHITECTURE.md`, `PRD.md`, and the matching section of `IMPLEMENTATION_PLAN.md`. Do not implement P1/P2 scope while any P0 acceptance criterion is failing. After each step, run the stated verification, record evidence, and update the status table in `CLAUDE.md`.

The invariant exit-code contract applies to every prompt and implementation change:

| Code | Required meaning |
|---:|---|
| `0` | Successful report, help, or version |
| `1` | Operational input/output failure |
| `2` | Usage or configuration error |
| `3` | Malformed-log threshold exceeded or no valid requests |
| `4` | Unique-cardinality exhaustion |

Never omit or remap code `4`. On exits `1`, `2`, `3`, or `4`, emit no partial report.

## Prompt 1: Package and CLI Skeleton

```text
Implement Step 1 from IMPLEMENTATION_PLAN.md only. Create pyproject.toml and the
src/nginx_top package with a Click entry point, all documented arguments/options,
version/help behavior, and typed errors. Do not implement parsing or renderers yet.
Use Python 3.11, Click, Rich, and standard-library dataclasses. Preserve the complete
exit mapping: 0 success/help/version, 1 operational I/O, 2 usage/configuration,
3 bad log data/no valid requests, 4 unique-cardinality exhaustion. Add and run the
specified CLI tests. Report changed files and command evidence; stop if verification fails.
```

## Prompt 2: Parser and Models

```text
Implement Step 2 from IMPLEMENTATION_PLAN.md only. Add frozen domain dataclasses and
a compiled bytes parser for the standard nginx combined format. Parse client IP,
request-target, status, timestamp hour, and User-Agent. Do not retain or echo full bad
lines. Add the exact parser fixtures and tests described in the plan. Parser failures
must feed exit 3 only through CLI threshold policy; do not disturb exits 0/1/2/4.
Run parser tests and coverage verification, then report evidence.
```

## Prompt 3: Streaming Aggregation

```text
Implement Step 3 from IMPLEMENTATION_PLAN.md only. Aggregate valid requests in one pass:
top-10 IPs, top-10 request-targets for statuses 400..599, all 24 hourly buckets, and
exact unique nonempty User-Agents. Compute each hourly percentage exactly as
100 × hourly_request_count / total_valid_requests. Enforce --max-unique before adding
a distinct retained key; exhaustion must emit no report and map to exit 4. Use stable
count-descending/key-ascending ordering. Add boundary and formula tests and run them.
```

## Prompt 4: Rich Terminal Output

```text
Implement Step 4 from IMPLEMENTATION_PLAN.md only. Build a Rich renderer from the frozen
Report model with summary, IP, error-URL, hourly, and unique-User-Agent sections. Auto-color
only for a TTY and honor explicit color options. Escape all log-derived markup and control
content. Do not alter aggregation or the 0/1/2/3/4 exit meanings; code 4 remains unique-
cardinality exhaustion. Add terminal golden, color, and injection tests and run them.
```

## Prompt 5: JSON and CSV Outputs

```text
Implement Step 5 from IMPLEMENTATION_PLAN.md only. Add JSON and CSV renderers matching the
schemas under PROJECT_ARCHITECTURE.md ## CLI Interface. Use standard-library encoders,
one trailing newline, no ANSI, and one long-form CSV header. Confirm all renderers consume
the same Report. Renderer write failures are exit 1; conflicting flags are exit 2;
parse-data failures are exit 3; unique-cardinality exhaustion is exit 4; success is 0.
Add schema, quoting, Unicode, and semantic-equivalence tests and run them.
```

## Prompt 6: End-to-End CLI

```text
Implement Step 6 from IMPLEMENTATION_PLAN.md only. Wire file and non-seekable stdin input
through parsing, aggregation, and the selected renderer. Enforce --max-parse-errors and
zero-valid-request behavior without partial output. Add table-driven integration evidence
for exit 0 success, exit 1 I/O, exit 2 usage/configuration, exit 3 parse threshold or empty
valid set, and exit 4 unique-cardinality exhaustion. Keep diagnostics on stderr and data
on stdout. Handle expected broken pipes without a traceback. Run all CLI tests.
```

## Prompt 7: Correctness and Package Gate

```text
Implement Step 7 from IMPLEMENTATION_PLAN.md only. Add renderer-neutral golden data,
cross-format edge cases, malicious log-text cases, and a clean-wheel install check.
Exercise all five exit codes 0/1/2/3/4 explicitly; verify code 4 means unique-cardinality
exhaustion and produces no partial output. Run the full test, coverage, build, pip check,
and source security commands. Fix only failures within this step's scope and report evidence.
```

## Prompt 8: Performance Evidence

```text
Implement Step 8 from IMPLEMENTATION_PLAN.md only. Create the deterministic benchmark
generator and CI-safe regression test, then generate a 1 GB local fixture outside version
control. Measure wall time and peak RSS on the named laptop, recording environment and
results in BENCHMARK.md. The acceptance target is under 30 seconds. Profile before changing
code; rerun correctness after any optimization. Preserve exact metrics, the literal hourly
formula 100 × hourly_request_count / total_valid_requests, and exits 0/1/2/3/4, especially
code 4 for unique-cardinality exhaustion. Do not claim the target without measured evidence.
```

## Prompt 9: Documentation and Release Handoff

```text
Implement Step 9 from IMPLEMENTATION_PLAN.md only. Reconcile README.md, CLAUDE.md, package
help, and actual behavior. Document file/stdin use, default Rich output, --json, --csv,
privacy, supported combined format, and the complete exits: 0 success, 1 operational I/O,
2 usage/configuration, 3 parse threshold/no valid requests, 4 unique-cardinality exhaustion.
Run the full tests and package checks, build distributions, and update the status table with
evidence. Do not publish, deploy, add services, or begin P1/P2 work.
```

## Review Prompt After Each Step

```text
Review only the current implementation-plan step against PRD P0 acceptance criteria and
PROJECT_ARCHITECTURE.md. Check streaming behavior, deterministic results, stdout/stderr
separation, unsafe rendering, and all exit mappings 0/1/2/3/4. Treat omission or remapping
of code 4 (unique-cardinality exhaustion) as blocking. Cite file locations and test evidence.
Do not broaden scope or implement fixes during review.
```

## Completion Gate

Do not call the MVP complete until the final checklist in `IMPLEMENTATION_PLAN.md` has current evidence, including clean installation, full tests, cross-renderer agreement, all five exit codes, and the measured 1 GB performance run. Planning documents are the source of truth: change `PRD.md` and `PROJECT_ARCHITECTURE.md` first if behavior must change.
