# Design Provenance — fixture (fully sourced)

## Claim: PostgreSQL with PG Vector is the primary store
- Source: user-requirement
- Reference: project CLAUDE.md stack section

## Claim: p95 latency budget is 300ms for the search endpoint
- Source: measured-evidence
- Reference: load test run 2026-08-01, report attached to PRD

## Claim: Telegram Mini App SDK requires HTTPS-only callbacks
- Source: external-doc
- Reference: https://core.telegram.org/bots/webapps

## Claim: traffic will stay under 50 rps for the first quarter
- Source: model-assumption
- Reference: refutable by week-2 analytics; revisit at 30 rps sustained
