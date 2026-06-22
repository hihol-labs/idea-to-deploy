# Data Policy

## Real Data

- Define data that must come from real sources.

## Synthetic Data

- Define where mock, demo, seed, fixture, or generated data is allowed.

## Production Rules

- Synthetic data must not be presented as real production data.
- If a real source is unavailable, return an explicit unavailable/degraded status or use an approved transparent fallback (see `FALLBACK_POLICY.md`).

## Evidence Required

- Define logs, tests, source metadata, timestamps, provider IDs, database fields, or API response evidence required for real data paths.
