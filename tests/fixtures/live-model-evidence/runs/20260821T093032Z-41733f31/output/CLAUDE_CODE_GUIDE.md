# Claude Code Implementation Guide: Nginx Stream Insights

Use this guide after the documentation-only blueprint is accepted. Start a
fresh implementation session for one numbered prompt at a time. Before each
step, read `CLAUDE.md`, `PROJECT_ARCHITECTURE.md`, `PRD.md`, and the matching
section of `IMPLEMENTATION_PLAN.md`; preserve WIP=1 and attach the verification
evidence before marking the step complete.

## Non-Negotiable Contract

- Python 3.11, Click, Rich, dataclasses, a `src/` layout, and pip installation.
- One local process; no database, HTTP API, authentication, server, cloud,
  Docker, or Kubernetes.
- Hourly percentage is exactly
  `100 × hourly_request_count / total_valid_requests`.
- The complete exit-code contract is `0/1/2/3/4`:

| Code | Meaning |
|---:|---|
| `0` | Successful report/help/version |
| `1` | Input/output operating error |
| `2` | Usage or invalid option combination |
| `3` | No valid records in finite input |
| `4` | Unique-cardinality exhaustion |

Never omit or remap code 4. Never present an approximate User-Agent count as
the exact result. Do not implement product behavior that is not specified;
update the PRD and architecture first when a behavior must change.

## Prompt 1: Package and quality foundation

```text
Implement only Step 1 of IMPLEMENTATION_PLAN.md. Create the Python 3.11
pyproject, src package, Click help/version scaffold, and quality-tool
configuration. Do not implement parsing or aggregation yet. Preserve the
CLI and complete 0/1/2/3/4 exit-code contract for later steps, with code 4
reserved for unique-cardinality exhaustion. Run every Step 1 verification
command, report evidence, reconcile project state, and stop.
```

## Prompt 2: Models, errors, and fixtures

```text
Implement only Step 2 of IMPLEMENTATION_PLAN.md. Define the dataclasses and
typed error boundaries specified by PROJECT_ARCHITECTURE.md, including error
categories that will map to exit codes 1, 3, and 4. Add the exact fixture
corpus and model tests; do not add parser or CLI feature behavior. Preserve
all meanings in 0/1/2/3/4. Run Step 2 verification, record evidence, and stop.
```

## Prompt 3: Streaming input and parser

```text
Implement only Step 3 of IMPLEMENTATION_PLAN.md. Build lazy finite file/stdin
reading and the conventional nginx combined-format parser. Treat invalid UTF-8
and invalid grammar as malformed lines without retaining or echoing raw input.
Do not add renderers or follow mode. Keep operating errors compatible with exit
1 and preserve the full 0/1/2/3/4 contract, where 4 is unique-cardinality
exhaustion. Run Step 3 verification, record evidence, and stop.
```

## Prompt 4: Exact aggregation

```text
Implement only Step 4 of IMPLEMENTATION_PLAN.md. Produce exact IP and 4xx/5xx
URL counters, 24 hourly counts, and exact non-empty User-Agent cardinality.
Use the literal formula 100 × hourly_request_count / total_valid_requests.
Enforce the configured UA limit before inserting limit+1 and raise the typed
failure for exit 4; do not approximate. Preserve exit codes 0/1/2/3/4. Run all
Step 4 tests including the limit boundary, record evidence, and stop.
```

## Prompt 5: Shared-report renderers

```text
Implement only Step 5 of IMPLEMENTATION_PLAN.md. Add Rich terminal, schema-v1
JSON, and five-column RFC 4180 CSV renderers that consume only the shared
Report dataclass. Emit all 24 hours and never put ANSI in JSON/CSV. Do not
recompute metrics in a renderer. Preserve the exact 0/1/2/3/4 exit contract,
including code 4 for unique-cardinality exhaustion. Run Step 5 verification,
record evidence, and stop.
```

## Prompt 6: Finite-stream CLI integration

```text
Implement only Step 6 of IMPLEMENTATION_PLAN.md. Wire finite file/stdin input,
all P0 options, aggregation, and renderers. Test stdout/stderr separation and
every exit code: 0 success, 1 I/O operating error, 2 usage error, 3 no valid
finite-input records, 4 unique-cardinality exhaustion. On code 4, emit no
complete machine report and never approximate. Run all Step 6 verification
commands, record evidence, reconcile state, and stop.
```

## Prompt 7: Follow mode

```text
Implement only Step 7 of IMPLEMENTATION_PLAN.md. Add non-busy-spin complete-line
follow behavior for named regular files and reject stdin follow as exit 2.
Preserve finite behavior, output contracts, and all codes 0/1/2/3/4; code 4
continues to mean unique-cardinality exhaustion while following. Test controlled
termination without changing the application-code table. Run verification,
record evidence, and stop.
```

## Prompt 8: Acceptance and performance evidence

```text
Implement only Step 8 of IMPLEMENTATION_PLAN.md. Add contract tests, a
deterministic benchmark-log generator, and the benchmark evidence template.
Test the hourly formula, stable rankings, privacy rules, schema semantics, and
all exits 0/1/2/3/4 with 4 meaning unique-cardinality exhaustion. Generate but
do not commit the 1 GB fixture. Run the full quality suite and recorded time
command on the exact candidate, save evidence, reconcile state, and stop.
```

## Prompt 9: Release handoff

```text
Implement only Step 9 of IMPLEMENTATION_PLAN.md. Align README with observed
behavior, add license/changelog decisions, build distributions, and install the
wheel in a clean Python 3.11 environment. Exercise terminal, JSON, CSV, and the
complete 0/1/2/3/4 contract; code 4 must remain unique-cardinality exhaustion.
Do not publish externally and do not add services or infrastructure. Run all
Step 9 checks, record evidence, reconcile the final state, and stop.
```

## Completion Handoff

After each prompt, report changed files, actual commands and outcomes, any
unverified acceptance criterion, and the next single step. A prose assertion
is not a substitute for current verification evidence. At the end of a session
or meaningful block, follow the session-save rule in `CLAUDE.md`.

