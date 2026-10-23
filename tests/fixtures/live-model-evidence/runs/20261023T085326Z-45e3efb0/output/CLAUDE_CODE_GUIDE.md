# Claude Code Implementation Guide: nginx-top

This guide turns `IMPLEMENTATION_PLAN.md` into bounded implementation prompts. Use one prompt at a time, keep WIP at one step, and do not continue when its checks are red. The durable specification is `PRD.md`; architectural choices and CLI schemas come from `PROJECT_ARCHITECTURE.md`.

## Global Contract for Every Step

Preserve the complete exit-code contract in every change:

- `0` — successful complete analysis, including empty valid input.
- `1` — input/output operational failure.
- `2` — CLI usage or option validation error.
- `3` — malformed input in `--strict` mode.
- `4` — unique-cardinality exhaustion.

Never omit or remap code 4. Never render a partial JSON/CSV result after a fatal error. Keep stdout for result data and stderr for diagnostics. Do not add authentication, a database, HTTP API, server, cloud component, Docker requirement, or Kubernetes. Use Python 3.11, Click, Rich, and dataclasses. Write tests with each behavior and run them before claiming the step is complete.

## Prompt 1: Package Skeleton and CLI Contract

```text
Implement only STEP 1 from IMPLEMENTATION_PLAN.md.

Read PROJECT_ARCHITECTURE.md sections “System Components,” “CLI Interface,” and
“Packaging and Deployment,” plus PRD.md FR-011. Create pyproject.toml,
src/nginx_top/__init__.py, src/nginx_top/errors.py, src/nginx_top/cli.py, and
tests/integration/test_cli_contract.py. Use the src layout and a console script
named nginx-top. Implement Click help/version and option validation, but do not
implement parsing, aggregation, or renderers yet.

Model the complete 0/1/2/3/4 exit contract from the start: success, I/O,
usage, strict malformed input, and unique-cardinality exhaustion. In this step,
exercise help/version and usage error 2. Keep the remaining typed errors ready
for later steps without pretending their paths are implemented.

Run:
python3.11 -m pip install -e '.[dev]'
python3.11 -m pytest tests/integration/test_cli_contract.py -q
nginx-top --help

Report changed files and actual command results. Stop if a check fails.
```

## Prompt 2: Domain Models and Parser

```text
Implement only STEP 2 from IMPLEMENTATION_PLAN.md.

Read PROJECT_ARCHITECTURE.md “Data Model and Streaming State” and “Supported
Input Contract,” and PRD.md FR-001/FR-002. Create the specified frozen/slots
dataclasses, combined-format parser, synthetic fixtures, and parser tests. Parse
only client IP, timezone-aware timestamp, request target, numeric status, and
User-Agent. Treat log contents as untrusted data and never put a full malformed
record in diagnostics.

Do not add renderer or aggregation behavior. Preserve the 0/1/2/3/4 contract;
parser strict failure will ultimately map to 3 and cardinality exhaustion to 4.

Run:
python3.11 -m pytest tests/unit/test_parser.py -q
python3.11 -m mypy src/nginx_top/models.py src/nginx_top/parser.py

Report changed files and actual results. Stop on failure.
```

## Prompt 3: Streaming Input and Core Metrics

```text
Implement only STEP 3 from IMPLEMENTATION_PLAN.md.

Read the processing flow, state invariants, and performance sections of
PROJECT_ARCHITECTURE.md, plus PRD.md FR-003 through FR-005. Implement sequential
file/stdin iteration and one-pass aggregation for top IPs, top 4xx/5xx URLs,
and all 24 hourly buckets. Do not retain raw lines or records after aggregation.
Use deterministic ordering: count descending, key ascending.

Hourly percentages must use exactly:
100 × hourly_request_count / total_valid_requests
They are percentages, not unscaled fractions. Empty valid input yields zero.

Preserve all exit meanings 0/1/2/3/4, including 4 for unique-cardinality
exhaustion even though the cardinality feature arrives in the next step.

Run the step-specific tests and the coverage command listed in
IMPLEMENTATION_PLAN.md. Report observed results; stop on failure.
```

## Prompt 4: User-Agent Cardinality

```text
Implement only STEP 4 from IMPLEMENTATION_PLAN.md.

Read PROJECT_ARCHITECTURE.md data model/resource design/exit codes and PRD.md
FR-006/FR-007. Add exact distinct User-Agent tracking with the configured
positive ceiling. Compute:
100 × unique_user_agent_count / total_valid_requests
with 0.0 for empty valid input. Accept exactly the limit; the next distinct
value must abort before rendering any partial report.

Map unique-cardinality exhaustion to exit code 4 and no other code. Preserve
the rest of the complete contract: 0 success, 1 I/O, 2 usage, 3 strict malformed,
4 cardinality exhaustion. Add unit and CLI integration coverage for the exact
boundary and stdout-empty fatal case.

Run every STEP 4 verification command. Report real output and stop on failure.
```

## Prompt 5: Rich Text Output

```text
Implement only STEP 5 from IMPLEMENTATION_PLAN.md.

Read PROJECT_ARCHITECTURE.md output and security sections and PRD.md FR-008.
Implement the renderer interface and default Rich report with four metric
sections plus diagnostics. Make meaning independent of color, honor color
selection, and ensure log-derived strings cannot become Rich markup or terminal
instructions. Keep stdout/stderr separate.

Do not alter metric math or the 0/1/2/3/4 mapping; code 4 continues to mean
unique-cardinality exhaustion. Add snapshot/behavior tests and run all STEP 5
verification commands. Report actual results and stop on failure.
```

## Prompt 6: JSON and CSV Output

```text
Implement only STEP 6 from IMPLEMENTATION_PLAN.md.

Read PROJECT_ARCHITECTURE.md “CLI Interface” and “Output Schema Examples,” and
PRD.md FR-009/FR-010. Implement stable JSON and long-form CSV serializers over
the same AnalysisResult. Use standard-library serializers, numeric JSON values,
the exact CSV header metric,rank,key,count,percentage, deterministic ordering,
and the documented spreadsheet formula neutralization. Structured output must
never contain ANSI or Rich markup.

Keep --json and --csv mutually exclusive with exit 2. Preserve 0/1/2/3/4;
code 4 is unique-cardinality exhaustion and cannot emit partial structured data.
Run all STEP 6 verification commands and report actual results.
```

## Prompt 7: Failure Semantics and Quality Gate

```text
Implement only STEP 7 from IMPLEMENTATION_PLAN.md.

Reconcile the complete behavior against PRD.md P0 acceptance criteria and
PROJECT_ARCHITECTURE.md error handling. Complete exception boundaries and add
integration evidence for every code: 0 success, 1 I/O failure, 2 usage error,
3 malformed strict input, 4 unique-cardinality exhaustion. Ensure every fatal
path writes a concise diagnostic to stderr and never emits partial JSON/CSV.

Add invariant tests for cross-renderer equivalence and percentages. Configure
Ruff, mypy, pytest, and at least 90% line coverage. Run the exact lint, typing,
and test commands from STEP 7. Do not claim completion if any gate is red.
```

## Prompt 8: Benchmark and Release Readiness

```text
Implement only STEP 8 from IMPLEMENTATION_PLAN.md.

Read STRATEGIC_PLAN.md Definition of Done, PROJECT_ARCHITECTURE.md performance
and packaging sections, and README.md. Add a deterministic synthetic-log
generator and opt-in benchmark harness. Do not commit a 1 GB artifact. Record
platform, Python, CPU, bytes, lines, wall time, and peak RSS from an actual run.
Build wheel/sdist and smoke-test the built wheel in a clean Python 3.11 venv.

Re-check the complete 0/1/2/3/4 contract in the installed artifact, including
exit 4 for unique-cardinality exhaustion. Do not infer the <30-second result;
report it only from the measured command. Run the full test/static/package and
benchmark commands in STEP 8 and report their actual outcomes.
```

## Final Implementation Review Prompt

```text
Review the completed implementation against PRD.md and PROJECT_ARCHITECTURE.md
without changing scope. Verify parser edge cases, deterministic rankings, the
literal hourly formula 100 × hourly_request_count / total_valid_requests,
User-Agent share, stdout/stderr isolation, all three output formats, privacy
controls, and all five exit codes 0/1/2/3/4. Code 4 must mean only
unique-cardinality exhaustion. Run Ruff, mypy, the full pytest coverage gate,
wheel build/install smoke tests, and the documented benchmark. Report failures
as failures and identify any acceptance criterion lacking executed evidence.
```

