# Checker prompt — <UNIT-ID> <targeted|full>

Fill the placeholders, hand the whole file to a fresh checker session, and store
it verbatim under `.itd-memory/verification-loop/prompts/` (see
[docs/VERIFICATION_LOOP.md](../VERIFICATION_LOOP.md)).

Independently verify exact <staged|committed> tree `<TREE-SHA256>`.

Scope of the candidate:

- Claim: <one sentence — what the candidate asserts>
- Files: <paths that may legitimately change>
- Machine evidence already produced: <oracle id = command, exit code>
- Out of scope: <what this candidate deliberately does not touch>

Verify independently — do not trust the summary above:

1. Read the diff of the exact tree named above.
2. Re-run the named oracles yourself; a green summary is not evidence.
3. Report every finding with file, line, why it is wrong, and how it fails.
4. Report anything you could not verify under `unverified` instead of guessing.

## Required last line of your report

Finish the report with this fenced JSON block and nothing after it. The verdict
is a token from a closed set, not free prose:

`PASSED` · `PASSED_WITH_WARNINGS` · `BLOCKED` · `UNVERIFIED` · `FAILED`

Anything outside that set is not a verdict. In particular `PASS`, `OK`,
`APPROVED`, `LGTM` and a bare prose sentence are rejected by
`skills/_shared/itd_verification_loop.py` (`ALLOWED_VERDICTS`), the receipt is
recorded as `UNVERIFIED`, and the whole review has to be run again:

```json
{"verdict": "PASS", "findings": [], "unverified": []}
```

That block above is the **rejected** form — it is here so the exact mistake is
visible. Copy the block below instead, replacing the verdict token with the one
you actually reached and filling the two lists:

```json
{"verdict": "PASSED", "findings": [], "unverified": []}
```
