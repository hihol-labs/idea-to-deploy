# Claude Code Implementation Guide: Nginx Stream Analyzer

This guide turns `IMPLEMENTATION_PLAN.md` into bounded implementation prompts. Use one prompt per session or meaningful work block, preserve WIP=1, and require tests to run before accepting a step. The specifications are the source of truth; do not implement behavior that contradicts `PRD.md` or `PROJECT_ARCHITECTURE.md`.

## Global Guardrails

Include these requirements in every implementation session:

- Use Python 3.11, Click, Rich, and dataclasses; do not add a database, HTTP API, authentication, server, cloud dependency, Docker, or Kubernetes.
- Keep input streaming and single-process. Do not read a whole log into memory.
- Never emit raw log lines in diagnostics or send data over a network.
- Keep JSON and CSV free of ANSI styling and diagnostic prose.
- Preserve the complete exit-code contract `0/1/2/3/4`: 0 success, 1 unexpected internal error, 2 input open/read/decode error, 3 usage error or no valid records, and 4 unique-cardinality exhaustion.
- For code 4, emit no normal report; never relabel an incomplete exact result as successful.
- Add or update tests first where practical, run the focused suite, then run the complete suite before a commit.
- Do not publish, push, open a PR, or create an external release without explicit human confirmation.

## Prompt 1: Package Baseline

```text
Implement Step 1 from IMPLEMENTATION_PLAN.md only. Read PRD.md and PROJECT_ARCHITECTURE.md first. Create the Python 3.11 src-layout package, Click console entry point, test extras, and help/version smoke tests. Do not implement parsing or aggregation yet. Use apply_patch for edits. Run the exact focused verification commands from Step 1 and report their actual outcomes. Stop if installation or tests fail; do not commit or push.
```

Expected evidence: clean editable install, passing `tests/test_cli.py`, and captured help output.

## Prompt 2: Domain Contracts

```text
Implement Step 2 from IMPLEMENTATION_PLAN.md only. Define frozen dataclasses, validated run configuration, and typed operational/cardinality errors exactly as PROJECT_ARCHITECTURE.md specifies. Add boundary and immutability tests. Do not write the parser, reader, renderer, or CLI orchestration. Run focused tests and compileall, then the existing suite. Preserve exit meanings 0/1/2/3/4 for later CLI mapping.
```

Expected evidence: passing model/config tests and successful bytecode compilation.

## Prompt 3: Parser

```text
Implement Step 3 only. Start with hand-audited fixtures and failing parser tests for supported nginx combined format boundaries, then implement one compiled line parser. Parse only fields required by AccessRecord. Treat log contents as untrusted data and do not echo full invalid lines. Update README.md with the exact supported grammar. Run parser coverage and the full suite; show failures honestly.
```

Expected evidence: fixture expectations, focused parser test output, and coverage meeting the step threshold.

## Prompt 4: Streaming Reader

```text
Implement Step 4 only. Add buffered, incremental input from a path or caller-owned stdin with strict decode failures. Never open inputs for writing, never close stdin, and never use whole-file read methods. Add tests that make the read behavior and input-error taxonomy observable. Run the Step 4 commands and the complete suite.
```

Expected evidence: path/stdin parity at the reader boundary and tested input/decode failures.

## Prompt 5: Aggregation

```text
Implement Step 5 only. Add one-pass exact aggregation for top client IPs, top error URLs for statuses 400..599, all 24 hourly buckets, and exact unique User-Agent share. Use deterministic count-descending/key-ascending ranking. Calculate hourly percentage with 100 × hourly_request_count / total_valid_requests. Enforce configured distinct-key limits before exceeding them and raise the typed exhaustion error. Do not render output or wire Click. Add tests for boundaries, ties, zero denominator, and each exhaustion dimension; run focused coverage and the full suite.
```

Expected evidence: hand-calculated aggregates, deterministic tie tests, and explicit cap-boundary tests.

## Prompt 6: Renderers

```text
Implement Step 6 only. Render the same ReportSnapshot through Rich terminal tables, JSON schema version 1, and the normalized CSV schema in PROJECT_ARCHITECTURE.md. Escape or disable Rich markup for all log-derived fields. Use standard serializers, not string concatenation. Add tests for Unicode, commas, quotes, control content, deterministic order, and absence of ANSI sequences from JSON/CSV. Run the focused and complete suites.
```

Expected evidence: parseable JSON/CSV, terminal snapshots, and injection/ANSI regression tests.

## Prompt 7: CLI and Exit Codes

```text
Implement Step 7 only. Wire Click options, file/stdin selection, parser, aggregator, and renderer. Make --json and --csv mutually exclusive. Map every documented outcome to the complete 0/1/2/3/4 exit contract without tracebacks for expected failures. Code 4 must mean unique-cardinality exhaustion and must produce no normal stdout. Test every code in a subprocess plus file/stdin and stdout/stderr separation. Run the Step 7 commands and the full suite.
```

Expected evidence: subprocess results for 0, 1, 2, 3, and 4, plus valid JSON and CSV pipeline checks.

## Prompt 8: End-to-End Contracts

```text
Implement Step 8 only. Build end-to-end tests around one hand-calculated fixture and compare semantic values across terminal, JSON, and CSV outputs. Add dedicated exit-code and security tests, including untrusted terminal markup, CSV quoting, diagnostic redaction, and no unintended writes or network calls. Do not relax assertions to make tests pass. Run focused files and the complete coverage command.
```

Expected evidence: green cross-format acceptance tests and at least 90% product-module line coverage.

## Prompt 9: Performance Gate

```text
Implement Step 9 only. Add a deterministic benchmark corpus generator and a runner that records machine, Python version, input byte size and hash, elapsed time, and peak RSS. Generate a 1 GiB corpus in /tmp, never in Git. Measure the unmodified candidate first. If it misses 30 seconds, profile before proposing changes and keep optimization within the approved single-process architecture unless evidence requires an architecture decision. Run the full suite after any change. Do not claim the target without recorded measurement.
```

Expected evidence: reproducible benchmark metadata, elapsed time, peak RSS, and a full green test run.

## Prompt 10: Release Candidate

```text
Implement Step 10 only. Finalize user documentation, build sdist and wheel, install the wheel in a fresh Python 3.11 virtual environment, and run the documented JSON example plus the full test suite. Confirm README.md documents inputs, formats, privacy, limitations, and exit codes 0/1/2/3/4. Do not upload or publish any artifact and do not push without explicit human confirmation.
```

Expected evidence: green suite, successful build, clean-environment install, and working installed command.

## Session Completion Checklist

- [ ] Scope stayed within one implementation-plan step.
- [ ] New behavior has tests and the tests actually ran.
- [ ] Existing tests still pass.
- [ ] Any skipped command or unmet target is stated explicitly.
- [ ] No external action occurred without human confirmation.
- [ ] Decisions that change architecture or user-facing behavior are reflected in the source documents first.
- [ ] Context was saved through `/session-save` at the end of the meaningful work block.

