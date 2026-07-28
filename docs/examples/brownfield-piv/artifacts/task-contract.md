# Task Contract: BF-017

## Scope

- Correct the basis-point denominator in `src/invoice.py`.
- Preserve the public function and integer-cent behavior.

## Verification

- Before the patch, the focused `unittest` command must fail.
- After the patch, the same command must pass.
- The staged candidate must equal the receipt-bound Git tree.

## Exclusions

- No dependency, API, rounding-policy, persistence, or deployment change.
- No external adoption or business-outcome claim.
