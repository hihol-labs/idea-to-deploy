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

## Review transport follow-up: one oversized JSONL event

The complete, sanitized successful transcript contains 59 JSONL events. Event
15 (`item.completed`, `command_execution`) occupies 126130 UTF-8 bytes on one
line. The canonical planner accepts at most 80000 bytes per review unit and
only splits complete lines, so it returns `UNVERIFIED` before model dispatch.
The exact committed-head machine receipt for `cf6aba4` passes all six legs;
this failure is in review transport, not the live evidence or product oracle.

The bounded repair is broker-side representation, not a producer or partition
change. A declared `.jsonl.gz` with an oversized raw/serialized record selects
the lossless `gzip-jsonl-utf8-chunks-v2` view. A header binds the original source
digest, bytes and line count; 4096-byte UTF-8-safe fragment rows bind source
offsets and reconstruct the original JSONL exactly. Original gzip bytes and
all existing ceilings stay unchanged. The original source is scanned before
projection so fragment boundaries cannot conceal secrets. The producer and
ordinary complete-line partition remain byte-identical to the accepted base.

Regression coverage must include raw-over-bound, Unicode/escape-heavy and
encoded-only oversized records, exact reassembly and serialized request limits.
The existing producer end-to-end fixture reviews every view range and final
integration, retaining its tamper, malformed-data and negative-verdict guards.
The rejected local `a153348` experiment changed the producer itself and was
correctly refused by efficacy replay because signed diagnostics bind its exact
source digest. The final representation-only approach preserves that digest
and the frozen reports instead of re-signing or weakening their applicability.
The owner explicitly authorized a temporary, independently reviewed authority
snapshot for this repair; do not mutate the global installed producer or use
unreviewed candidate code as its own review authority.

## Review context: closed history was sent as active acceptance

With no active follow-up, the producer's generic projection included all 293
historical criteria and the closed-followup archive. This exceeded the reviewer
prompt bound even after the diff itself fit its units. The owner-approved
`CLOSE-DEBT-1-LIVE` follow-up now declares three current criteria and their
`quick`/`live` oracle coverage. The existing projection selects those criteria
while hashing the complete unchanged history; no criterion is deleted and no
prompt or review limit is raised.
