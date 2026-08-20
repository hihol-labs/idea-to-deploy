# Claude Code Implementation Guide: Nginx Stream Insights

## Purpose

Use this guide after the blueprint is approved to implement one
`IMPLEMENTATION_PLAN.md` step per session. The specification is the source of
truth; do not change behavior only in code. This guide contains prompts and
acceptance instructions, not product implementation.

## Non-Negotiable Contracts for Every Prompt

- Stack: Python 3.11, Click, Rich, dataclasses, `src/` packaging, pip wheel.
- Architecture: one local process, incremental stateless streaming, no
  database, HTTP API, authentication, server, cloud, Docker, or Kubernetes.
- Formats: Rich text default; `--json` and `--csv` are mutually exclusive and
  contain no ANSI sequences.
- Hourly distribution is a percentage using exactly
  `100 × hourly_request_count / total_valid_requests`.
- Exit codes are complete and immutable: `0` success/help/version; `1`
  I/O or unexpected runtime failure; `2` Click usage/option error; `3` zero
  valid records; `4` unique-cardinality exhaustion with no partial report.
- Treat log text as untrusted data: escape terminal markup, use standard JSON
  and CSV encoders, bound malformed samples, and never execute configuration.
- Preserve WIP=1. Run the step’s checks and repository verification loop before
  marking it complete. Record real evidence, not predicted outcomes.
- Do not create or claim `DEVILS_ADVOCATE_REVIEW.md`; that review belongs to a
  separate external session.

## Session Startup Prompt

```text
Read AGENTS.md, .itd/SCOPE_LOCK.md, .itd/VERIFICATION_CONTRACT.json,
STRATEGIC_PLAN.md, PROJECT_ARCHITECTURE.md, PRD.md,
IMPLEMENTATION_PLAN.md, and CLAUDE_CODE_GUIDE.md. Identify the single active
implementation step from project state. Restate its allowed files, acceptance
criteria, verification commands, and the public 0/1/2/3/4 exit-code mapping.
Do not edit until scope and evidence requirements are reconciled. Work on only
that step and keep product behavior aligned with the specifications.
```

## Step 1 Prompt: Package and CLI contracts

```text
Implement only IMPLEMENTATION_PLAN.md Step 1. Create the Python 3.11 src-layout
package, pip console entry point, typed public errors/exit constants, and Click
option skeleton. The command must expose file/stdin inputs, --json, --csv,
--color, --max-unique-user-agents, --encoding, --version, and --help. Enforce
mutual exclusions and positive limits through Click. Preserve codes 0 success,
1 I/O/runtime, 2 usage, 3 no valid records, and 4 exact-UA exhaustion even
where later steps still own behavior. Add and run only the tests and checks
listed for Step 1, then attach exact command results.
```

## Step 2 Prompt: Models and parser

```text
Implement only Step 2. Add the architecture's dataclasses and a compiled parser
for the exact nginx combined format. Parse timezone-aware timestamps, statuses,
IPv4/IPv6 text, normalized request paths, and User-Agent text. Treat malformed
or overlong lines as bounded diagnostics; escape samples and never render raw
markup. Add the specified fixtures and parser tests. Do not implement
aggregation or output. Run Step 2 verification and preserve the complete
0/1/2/3/4 exit contract at the CLI boundary.
```

## Step 3 Prompt: Input and aggregation

```text
Implement only Step 3. Stream files and stdin line by line and update exact IP,
4xx/5xx normalized-URL, 24-hour, and User-Agent aggregates. Do not load an
input file or all records into memory. Enforce the exact User-Agent ceiling
before retaining an excess value and raise the typed failure that maps only to
exit 4 with no report. Cover multiple files, stdin, I/O failures, malformed
records, and cardinality exhaustion. Run the listed Step 3 checks.
```

## Step 4 Prompt: Report construction

```text
Implement only Step 4. Convert aggregate state into immutable report
dataclasses. Rank by count descending then key ascending and truncate only at
report freeze time. Emit all hours 00-23 and compute every hourly percentage
with the literal formula 100 × hourly_request_count / total_valid_requests.
Compute exact UA percentage from valid request count. Add deterministic tests
for ties, top 10, rounding, and totals. Do not add a renderer. Run Step 4
verification and keep failure codes 0/1/2/3/4 unchanged.
```

## Step 5 Prompt: Rich renderer

```text
Implement only Step 5. Render the immutable report as four ordered Rich text
sections plus valid/malformed totals. Data belongs on stdout and warnings on
stderr. Escape every log-derived value. Honor color auto/always/never; auto
must not emit ANSI to a redirect. Add capture tests for layout, hostile markup,
and terminal behavior. Do not implement structured output. Run the Step 5
checks and preserve all five exit meanings.
```

## Step 6 Prompt: JSON and CSV renderers

```text
Implement only Step 6. Add versioned JSON and normalized CSV renderers exactly
as specified under PROJECT_ARCHITECTURE.md ## CLI Interface. Use standard
encoders, stable ordering, correct quoting, formula-injection protection, and
no ANSI output. Both formats must carry the same counts and percentage values
as text, including hourly values calculated as
100 × hourly_request_count / total_valid_requests. Add golden files and parse
them in tests. Run Step 6 verification; do not remap codes 0/1/2/3/4.
```

## Step 7 Prompt: End-to-end contract

```text
Implement only Step 7. Wire one CLI orchestration path from input through
parser, aggregator, report, and one renderer. Keep exception translation in
the CLI. Prove via subprocess-level tests: success is 0; missing/unreadable or
write/decode failure is 1; usage conflict is 2; zero valid records is 3; exact
unique-cardinality exhaustion is 4 and writes no partial stdout. Also prove
file/stdin and format equivalence, safe malformed-line success, and quiet
broken pipes. Run the full listed coverage command and record evidence.
```

## Step 8 Prompt: Performance and release

```text
Implement only Step 8. Add deterministic benchmark utilities, build the wheel,
install it into a fresh Python 3.11 environment, and run all golden flows. The
benchmark report must bind hardware, OS, Python version, fixture properties,
wall time, throughput, peak RSS, and three warm-cache runs for 1 GB. Acceptance
requires median time below 30 seconds. If it fails, profile first and make only
evidence-driven changes within scope. Re-run all tests, verify codes 0/1/2/3/4,
and update user docs with observed behavior rather than estimates.
```

## Review Prompt for Each Completed Step

```text
Freeze the exact staged candidate for the active step and run its declared
machine oracle. Check the diff against SCOPE_LOCK, PRD acceptance criteria,
architecture boundaries, security rules, deterministic formats, and the
complete exit-code matrix. Apply the risk-tier checker required by the Idea to
Deploy verification contract. Accept only a current adjudication receipt that
matches this exact candidate; otherwise leave the step in recovery with the
next concrete action recorded.
```

## Handoff Checklist

- [ ] Exactly one plan step is active or completed from current evidence.
- [ ] All listed commands were actually run and their results recorded.
- [ ] Specifications and tests agree on formulas, schemas, and `0/1/2/3/4`.
- [ ] No ignored/untracked input influenced acceptance unless explicitly hash-bound.
- [ ] State, scope, and next action are reconciled for a fresh session.
- [ ] Product source changes do not introduce excluded infrastructure.

