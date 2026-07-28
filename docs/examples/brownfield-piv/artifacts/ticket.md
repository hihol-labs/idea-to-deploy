# BF-017 — invoice tax is multiplied by 100

## Observed failure

For a subtotal of 10,000 cents and a tax rate of 825 basis points, the existing
function returns 92,500 cents. The expected total is 10,825 cents.

## Acceptance

- Interpret 825 basis points as 8.25 percent.
- Preserve integer-cent arithmetic.
- The focused standard-library regression test passes.
