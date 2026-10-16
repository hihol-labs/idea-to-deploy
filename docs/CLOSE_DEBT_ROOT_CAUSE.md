# Root Cause: CLOSE-DEBT-1

Recorded: 2026-10-16

## Summary

The signal producer legitimately writes `outcome: unknown` with empty evidence,
but strict commit and explicit-close validation rejected that row before considering
observed green runs in the same session. The closure contract also ran the quick
suite twice and gave its verification leg only 300 seconds.

## Reproduction

Place a producer-attributed L2 `unknown` row with empty evidence beside a valid
L2 `pass` in the current session, then invoke the strict commit gate or explicit
close. Before the fix both reject the empty evidence.

## Evidence

The local ledger parsed as 2000 JSON objects with no malformed lines. All 236
runtime rows with empty evidence had outcome `unknown`. These observations do not
justify changing historical outcomes or assigning provenance to older rows.

## Fix Hypothesis

Validate the structure and producer of unknown signals, then exclude them from
runtime proof. Retain failure blocking, require nonempty evidence for pass/fail,
and deny unknown-only closure. Run quick once with a 1200-second limit; use the
installed-runtime inventory oracle as the separate startup smoke (180 seconds).
Set the repository's quality freshness window to 120 days without changing its
recorded review dates or the default template for other projects.

## Regression Test

`tests/verify_strict_completion_policy.py` exercises unknown with pass, unknown
alone, pass without evidence, L3 unknown with L2 pass, and unknown with fail at
both commit and explicit-close boundaries. `tests/verify_session_hygiene_quality.py`
checks the bounded smoke and the single quick verification leg.

## Constraints

Preserve the signal ledger as observed history. Do not convert unknown to pass,
discard failures, relax producer validation, or hide the release's known-red
`verify_independent_review_efficacy` result. Formal closure still requires the
repository's current candidate receipt and a clean working tree.

## Efficacy replay: named function on an adjacent blank line

The signed WSL report correctly names `displayedClosing`, the omitted `fx_other`
type and the 1494440 TRY reconciliation error, but anchors that finding at line 6,
the blank line immediately after the function's closing brace at line 5. The
matcher accepts the fault range (2-4), declaration (1) and closing brace (5),
but has no rule for this explicitly named, adjacent blank-line anchor.

The bounded repair accepts that blank line only when the summary names the
exact containing function as a complete identifier. The existing file, severity
floor, fault-specific term, immediate-function structure and nested-function
guards remain mandatory. Nonblank neighboring statements, distant blank lines,
other function names and identifier substrings remain rejected. Frozen case
definitions, signed reports, thresholds and immutable history remain unchanged.

The added regression in `verify_function_anchor_matching` reproduces the miss
before the repair and tests the positive anchor and negative boundaries.

## PR #366 CI follow-up: stale live benchmark evidence

Gate 1 ran `verify_live_model_benchmark.py --require-evidence --max-age-days 30`
and reported 151 passed / 3 failed: the live run still bound the methodology
tree from before the `itd_hygiene.py` repair. The quick suite had run this
verifier without `--require-evidence`, so explicit close did not replay the
strict evidence checks required by CI.

The canonical live runner produced a real PASS at
`20261016T193843Z-faa5f07d` using native WSL Codex 0.161.0. Its blueprint and
separate Devil's Advocate phases both exited zero; the independent snapshot
oracle and strict archived replay passed (154 passed / 0 failed). No source
pins, immutable reports, runner behavior or oracle thresholds were rewritten.
Earlier transport failures remain recoverable in ignored local diagnostics.

The close verification contract now declares the same strict, 30-day evidence
replay as CI as a separate bounded 180-second leg. A focused regression fails
when that leg is absent and checks its argv, dependency bindings and parser.
This closes the local-close/CI coverage gap without duplicating quick or
relaxing live evidence requirements.
