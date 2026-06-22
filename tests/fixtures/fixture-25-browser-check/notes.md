# Manual verification — fixture 25 (/browser-check)

`/browser-check` runs a **local browser smoke-test** (default: the Playwright
harness in `skills/browser-check/playwright/`) against a local URL. This fixture
regressionally fixes the temp-scripts-outside-project rule, the BLOCKED-on-broken-
render contract, the real-interaction-over-screenshots rule, and the
fixes-route-through-/bugfix guard.

## Fixture status

`pending` — **deferred**, same bucket as `fixture-15-advisor` (live dev server +
Playwright + stdout). For now: manual checklist below. The stub satisfies
`check-skill-completeness.sh`.

## Harness note

The skill ships a Playwright harness at `skills/browser-check/playwright/`
(`run.js`, `package.json`, `lib/helpers.js`). `$SKILL_DIR` resolves to the
directory containing `SKILL.md`. Setup (needs network + user approval):
`npm run setup` from `$SKILL_DIR/playwright`.

## /browser-check — Scenario A: smoke-test login flow (happy path)

User pastes the prompt from `idea.md`: after frontend changes, verify the login
form + navigation; smoke test the UI on localhost.

### Target resolution
- [ ] URL supplied → used directly
- [ ] localhost, no URL → `node $SKILL_DIR/playwright/run.js --detect`
- [ ] multiple servers detected → asks which to verify

### Script handling
- [ ] Task-specific script written OUTSIDE the project (`/tmp/itd-browser-check-*.js`)
- [ ] Script run via `node $SKILL_DIR/playwright/run.js <script>`
- [ ] Temp script NOT committed

### Checks
- [ ] First render checked (blank screen, broken layout, overlap, missing assets, console errors)
- [ ] Critical path exercised by real interaction (navigation, login form, loading/error states)
- [ ] Not relying on screenshots alone when forms/nav are clickable

### Result + routing
- [ ] RESULT is honest (PASSED / PASSED_WITH_WARNINGS / BLOCKED)
- [ ] Broken first render / blank shell / unusable nav / inaccessible primary flow → BLOCKED
- [ ] Fixes routed through `/bugfix` (no production-impacting changes from the check)

### Output shape (stdout)
- [ ] BROWSER TARGET / ENGINE / FLOW CHECKED / RESULT / EVIDENCE / SCREENSHOTS /
      CONSOLE OR NETWORK ISSUES / ISSUES / NEXT ACTION

## /browser-check — Scenario B: Playwright unavailable (fallback)

Harness dependency missing.

- [ ] Offers `npm run setup` from `$SKILL_DIR/playwright` (after user approval, needs network)
- [ ] Or falls back to in-app browser / Browser Use / manual, stating the engine

## /browser-check — Scenario C: broken first render

App shell is blank after the change.

- [ ] RESULT = BLOCKED (before deploy)
- [ ] Issue described; fix routed through `/bugfix`, not patched from the check

## Cross-reference with `check-skill-completeness.sh`

1. ✅ `skills/browser-check/references/` exists (browser-check-checklist.md)
2. ✅ `hooks/check-skills.sh` contains trigger phrases for `/browser-check`
3. ✅ `tests/fixtures/fixture-25-browser-check/` exists with `idea.md`,
   `notes.md`, `expected-files.txt`, `expected-snapshot.json`

## Run manually

1. `cd tests/fixtures/fixture-25-browser-check/`
2. `mkdir -p output && cd output`
3. Start a dev server, then start Claude Code, paste `idea.md`, invoke `/browser-check`
4. Verify the checklist above; confirm no temp script was committed
5. `cd .. && python3 ../../verify_snapshot.py .` — expected: `⏸️ fixture-25-browser-check: PENDING`

## Failures (fill in if any)

(empty unless the fixture fails — especially a committed temp Playwright script,
a production-impacting change made from the check, or a broken render not marked BLOCKED)
