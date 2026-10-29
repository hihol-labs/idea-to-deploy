# Test - strict route

Read this file when Step 0 of `SKILL.md` chose the strict route: the project declares `itd-route: strict` or
`itd-domain: data-sensitive`, the arguments contain `--strict`, or the task falls in a strict class of the global
rules. Run Step 5.5 below after Step 5 of `SKILL.md` and before its Step 6; on the minimal path it does not run.

### Step 5.5: Refute pass — mutation-check each new test before you trust it as coverage (v1.60.0 — Ось 2, agentic engineering)

The refute pass from `/review` Step 2.6, applied to the test verify fleet. Here
the "finding" is a new test's implicit claim «this asserts real behavior». A
test that passes on BOTH the correct and the broken code is vacuous coverage — a
green that proves nothing and lies to every later reader. This pass adversarially
challenges that claim before the suite's green is trusted.

For each **behavior-asserting** test just written (not trivial getters /
formatting / snapshot-only tests), run a **fresh** mutation check: break the code
path the test claims to cover — invert a condition, drop a guard, return a wrong
constant (or dispatch `Agent(subagent_type: "test-generator", …)` with a refute
prompt to attempt it) — and confirm the test now **FAILS**. A test that stays
green under the mutation is **refuted as meaningful coverage**. This is the
red→green TDD gate (`SKILL.md` Step 5) run in reverse: green→red-under-mutation. **Default
to `refuted: true` under uncertainty** — if you cannot make the test fail by
breaking what it supposedly checks, treat its coverage claim as unproven.

- Refuted (survives the mutation) → the test is vacuous: fix it (tighten the
  assertion) or drop it; do not count it as coverage.
- Confirmed (fails under mutation) → real coverage, keep it.
- **Trivial / non-behavioral tests are NOT mutation-checked** — the cost is not
  justified.
- **Record the mutation run (COMPLETION-SUPERSEDE-1).** The red of a mutation run
  is expected, but the completion gate sees a failed test. Launch the oracle
  through the runner with a record — `ITD_RUN_RECORD=1 sh skills/_shared/itd_py.sh
  <oracle> [args]`, one recorded run per Bash call with nothing else printing in
  it, the oracle's summary line kept in the output (`| tail -3`, not `| tail -1`
  or `| cut`) — and after reverting the
  mutation run the same oracle the same way from the project root: the later
  green record supersedes the red one (`docs/completion-gate.md`). A red without
  a record, or without that final green run, still blocks the commit.
- **Unique mutation marker (TEST-RULES-1).** The marker - the exact text a
  mutation replaces - must occur **exactly once** in the mutated file. With a
  repeated marker the mutant lands on the first copy, which may not be the code
  path the test covers, or is refused: the run then proves nothing either way
  (STOPRULE-STUB-1: the same type check sat in a second function and the
  mutant did not apply). The mutation helper checks `text.count(marker) == 1`
  **before applying** the mutant and refuses otherwise; widen the marker with
  the surrounding lines until it is unique.
- **Fixtures with non-ASCII or invisible characters (TEST-RULES-1).** The
  file-write tool decodes escape sequences: `\u00a0` typed into it lands in
  the file as the character itself, and an invisible one (U+00A0, U+3164, curly
  quotes) then disappears from every diff and review. Write such a fixture as
  escape sequences by a script (a Bash heredoc running Python that writes
  `"\u00a0"`, not the raw character), then read the written bytes back
  with Python (`repr()` of the line shows a backslash sequence, not the
  character; `text.count(chr(0xa0)) == 0`) before trusting it.

**Invariant:** the refute pass can only REMOVE vacuous tests from the trusted
coverage set; it never fabricates a passing test and never reports mutation
evidence it did not actually run. When a real mutation run is impractical
(env-specific, flaky), state that exception explicitly rather than silently
claiming the coverage is proven — same honesty rule as the TDD gate of `SKILL.md` Step 5.
