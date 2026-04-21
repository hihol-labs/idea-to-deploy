# Manual verification — fixture 16 (/deploy)

`/deploy` is a live-ops deployment skill. It SSH-syncs files, rebuilds Docker images, applies migrations, and verifies healthcheck on a real production host. This fixture documents the expected step-by-step behaviour; it cannot be run automatically in CI without an ephemeral test target.

`/deploy` is flagged `disable-model-invocation: true` in its SKILL.md — it runs only on explicit user request, never auto-triggered.

## Fixture status

`pending` — **deferred**, same bucket as `fixture-10-task` / `fixture-15-advisor` (stdout-based + live-ops output that verify_snapshot.py's Phase 1 schema cannot validate). The stub satisfies `check-skill-completeness.sh` and anchors future regression work.

**Do NOT run this fixture against the user's real production host.** Use a throwaway VPS with the same config layout as production.

## /deploy — Scenario A: happy-path deploy, safe test target

Prerequisites before starting:
- Safe target VPS accessible via SSH (not the real prod host)
- `scripts/deploy-env.sh` in the project with: `DEPLOY_HOST`, `DEPLOY_PATH`, `DEPLOY_COMPOSE`, `DEPLOY_ENV_FILE`, `DEPLOY_SERVICE`, `HEALTHCHECK_URL`
- Git working tree clean or at least staged changes intended to ship
- User knows the current deployed commit (`git tag --list 'deploy-*' | tail -1`)

### Step 0 — Pre-flight safety check
- [ ] Skill checks `git status` — warns if uncommitted changes
- [ ] Skill checks current branch — requires explicit confirmation if not `main`
- [ ] Skill resolves deploy variables from `scripts/deploy-env.sh` (priority 1). If absent, checks CLAUDE.md `## Deploy config` section (priority 2), then project memory (priority 3). If none found — **STOPS** and asks user
- [ ] Skill identifies changed files via `git log --oneline` since last `deploy-*` tag
- [ ] Skill scans migrations dir (if any) and lists pending migration numbers
- [ ] Skill shows deploy summary (branch, commit, changed files count, pending migrations, target host, service, healthcheck URL) and asks **"Proceed? [yes/no]"**
- [ ] Skill does NOT proceed without explicit "yes"

### Step 1 — Sync files (tar-over-ssh)
- [ ] Skill uses tar-over-ssh, not rsync (more reliable on slow/exotic links)
- [ ] Excludes `.git`, `node_modules`, `.next`, `.env`, `.env.local`, `dist` by default
- [ ] Appends `$EXTRA_EXCLUDES` from deploy-env if defined (common: rendered-on-server gateway configs)
- [ ] Verifies sync by SSH-cat of a known changed file

### Step 2 — Regenerate gateway config (optional)
- [ ] If `GATEWAY_RENDER_CMD` defined — runs it on the target
- [ ] If undefined — skips this step, notes it in the summary

### Step 3 — Docker build
- [ ] Runs `docker compose build $DEPLOY_SERVICE` (or equivalent) on target
- [ ] On build failure: stops, reports the failing step, does NOT proceed to restart

### Step 4 — Container restart
- [ ] `docker compose up -d $DEPLOY_SERVICE` on target
- [ ] Verifies containers are `Up` before proceeding (docker ps | grep ...)

### Step 5 — Apply pending migrations
- [ ] If project has pending migrations AND `DB_CONTAINER` defined — applies them sequentially
- [ ] Each migration reports success/failure individually
- [ ] Failure halts — does NOT auto-rollback (that's /migrate-prod domain), reports state for manual review

### Step 6 — Healthcheck
- [ ] `curl $HEALTHCHECK_URL` expects HTTP 200
- [ ] Retries up to 3 times with 5s backoff (app might still be starting)
- [ ] On persistent failure: reports last response, exits with non-zero

### Step 7 — Tag and optionally push
- [ ] Creates local git tag `deploy-$(date +%Y-%m-%d-%H%M%S)`
- [ ] Does NOT push tag automatically — asks user
- [ ] Final summary: «Deployed commit X to $DEPLOY_HOST, service $DEPLOY_SERVICE, healthcheck green»

### Post-deploy
- [ ] Skill invokes `/session-save` automatically (per the skill's contract: always `/session-save` after deploy)
- [ ] Session save includes deploy summary so future sessions have context

## /deploy — Scenario B: missing deploy config (edge case)

No `scripts/deploy-env.sh`, no CLAUDE.md `## Deploy config` section, no memory reference.

- [ ] Skill does NOT invent defaults — STOPS and asks the user for the missing values
- [ ] Skill offers to write `scripts/deploy-env.sh` as a template the user can commit
- [ ] Waits for the user to fill values; does NOT proceed with partial/placeholder config

## /deploy — Scenario C: healthcheck fails

Build succeeds, containers restart, but curl returns 502 repeatedly.

- [ ] Skill retries 3 times with 5s backoff
- [ ] On persistent failure: reports the last response body + HTTP code + `docker logs $DEPLOY_SERVICE --tail 20` on target
- [ ] Does NOT auto-rollback — /deploy is forward-only, rollback is user's explicit decision via /migrate-prod or manual git revert + redeploy
- [ ] Exits non-zero

## /deploy — Scenario D: guard rails (what /deploy MUST NOT do)

- [ ] Does NOT deploy without explicit user "yes" in Step 0
- [ ] Does NOT deploy from a dirty working tree without explicit confirmation
- [ ] Does NOT deploy from non-main branch without explicit confirmation
- [ ] Does NOT skip the healthcheck even if user says "пропусти проверку"
- [ ] Does NOT run on Haiku — Sonnet required
- [ ] Does NOT auto-push the deploy tag to the remote

## Cross-reference with `check-skill-completeness.sh`

`/deploy` satisfies the three Quality Gate 2 requirements:

1. ✅ `skills/deploy/references/` exists (deploy-checklist, env-vars-reference)
2. ✅ `hooks/check-skills.sh` contains trigger phrases for `/deploy`
3. ✅ `tests/fixtures/fixture-16-deploy/` exists with `idea.md`, `notes.md`, `expected-files.txt`, `expected-snapshot.json`

## Why active validation is deferred

`verify_snapshot.py` validates files in a local output dir. `/deploy`'s side effects are:
- Remote (on SSH target) — files, containers, DB state
- Ephemeral (container restarts, healthcheck responses)
- Environmental (git tags, session-save marker)

Building an automated harness for this would require:
- An ephemeral test target VPS in CI (cost + setup complexity)
- OR a mocked SSH surface with predictable return codes (fragile, maintenance burden)
- OR a contract-testing approach with recorded fixtures from a golden run (schema drift risk)

None of the above are justified for a solo-maintainer plugin at current adoption phase. Deferred to v1.16.0 candidate list, alongside `fixture-10-task` / `fixture-15-advisor` stdout-snapshot scheme.

Until then: the manual checklist above is the contract. Run it against a throwaway VPS before each methodology release that touches `skills/deploy/`.

## Run manually (against a safe test target)

1. Set up a throwaway VPS: clean Ubuntu, Docker + Compose, SSH key from your workstation, a minimal project with a healthcheck endpoint
2. Add `scripts/deploy-env.sh` to a test clone pointing at the throwaway VPS
3. `cd tests/fixtures/fixture-16-deploy/`
4. `mkdir -p output && cd output`
5. Copy your test clone's files into `output/` OR cd into the test clone directly
6. Start Claude Code on Sonnet, paste `idea.md`, invoke `/deploy`
7. Answer "yes" at Step 0
8. Go through Scenario A checklist during and after the run
9. Tear down the VPS afterwards (or reuse for next deploy regression)

## Failures (fill in if any)

(empty unless the fixture fails — leave space for documenting regressions, especially deploys that succeeded despite broken healthcheck, or deploys from dirty trees without confirmation)
