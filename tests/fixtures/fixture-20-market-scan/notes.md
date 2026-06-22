# Manual verification — fixture 20 (/market-scan)

`/market-scan` scans **fresh public** market and community signals (preferred
engine: `last30days`) and normalizes them into artifacts + a structured stdout
summary. This fixture regressionally fixes the public-safe contract, the
no-fabrication / BLOCKED_EXTERNAL_TOOL fallback, the dated-append rule, and the
`/market-scan` vs `/discover` distinction.

## Fixture status

`pending` — **deferred**, same bucket as `fixture-15-advisor` (depends on an
external research tool + stdout). For now: manual checklist below. The stub
satisfies `check-skill-completeness.sh`.

## /market-scan — Scenario A: niche signal scan (happy path)

User pastes the prompt from `idea.md`: scan the "AI booking assistant for
barbershops" niche — current chatter, complaints, alternatives, public only.

### Public-safe topic
- [ ] Topic sent to the external tool contains NO secrets / private customer
      data / unreleased product details / proprietary code
- [ ] Existing artifacts (`DISCOVERY.md` / `MARKET_BRIEF.md`) read BEFORE researching

### External tool handling
- [ ] If `last30days` is installed — it is invoked and its synthesized evidence used
- [ ] If `last30days` is unavailable — scan is marked `BLOCKED_EXTERNAL_TOOL`
      with the exact topic to rerun, and NO social/market evidence is fabricated

### Output shape (stdout)
- [ ] Contains TOPIC, FRESH SIGNALS, TOP COMPLAINTS, ALTERNATIVES,
      ADVERSARIAL DISCOVERY, CONFIDENCE, ARTIFACT IMPACT, NEXT VALIDATION STEP
- [ ] Surfaces negative signals / competitor advantages, not only supportive evidence
- [ ] Verified evidence separated from assumptions; source links cited when available

### Artifact writes
- [ ] `MARKET_BRIEF.md` updated with a DATED append (prior research NOT overwritten)
- [ ] Raw last30days output is NOT pasted wholesale
- [ ] Signals converted into a NEXT VALIDATION STEP (not directly into build scope)

## /market-scan — Scenario B: external tool missing (degraded mode)

`last30days` not installed.

- [ ] Scan status = `BLOCKED_EXTERNAL_TOOL`
- [ ] Exact research topic listed for rerun after installation
- [ ] NO fabricated signals, complaints, or alternatives

## /market-scan — Scenario C: confused with /discover

User says: «сделай discovery с персонами и TAM/SAM/SOM».

- [ ] Skill redirects: «Это полная discovery-фаза — используй `/discover`.
      `/market-scan` — точечный скан свежих публичных сигналов.»

## Cross-reference with `check-skill-completeness.sh`

1. ✅ `skills/market-scan/references/` exists (market-scan-checklist.md)
2. ✅ `hooks/check-skills.sh` contains trigger phrases for `/market-scan`
3. ✅ `tests/fixtures/fixture-20-market-scan/` exists with `idea.md`, `notes.md`,
   `expected-files.txt`, `expected-snapshot.json`

## Run manually

1. `cd tests/fixtures/fixture-20-market-scan/`
2. `mkdir -p output && cd output`
3. Start Claude Code on Opus, paste `idea.md` content, invoke `/market-scan`
4. Verify the checklist above against the transcript and any written artifacts
5. `cd .. && python3 ../../verify_snapshot.py .` — expected: `⏸️ fixture-20-market-scan: PENDING`

## Failures (fill in if any)

(empty unless the fixture fails — especially any fabricated evidence when the
external tool is unavailable, or a secret leaked into an external query)
