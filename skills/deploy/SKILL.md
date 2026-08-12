---
name: deploy
description: 'Deploy to production — sync files, build containers, apply migrations, verify health. Reads per-project deploy config. Refuses without explicit confirmation.'
argument-hint: '"web" for web only, "all" for full stack, or specific service name'
license: MIT
allowed-tools: Read Write Edit Glob Grep Bash(ssh:*) Bash(tar:*) Bash(docker:*) Bash(curl:*) Bash(git:*)
disable-model-invocation: false
metadata:
  effort: high
  side_effect: production-mutation
  explicit_invocation: true
  author: HiH-DimaN
  version: 1.20.1
  category: operations
  tags: [deploy, production, docker, ssh, migration]
---

# Deploy

## Trigger phrases

These are the user phrases (Russian and English) that should auto-invoke this skill. They are kept here, not in the description, to avoid diluting the embedding-based matcher in the frontmatter. The hook `hooks/check-skills.sh` also uses this list — keep them in sync.

- задеплой, деплой, deploy, задеплой на прод
- выкати на прод, выкатить на прод, push to prod
- обнови прод, обнови сервер, update production
- деплой на сервер, залей на сервер
- перезапусти прод, перезапусти контейнер
- rsync на сервер, синхронизируй с сервером

## Recommended model

**sonnet** — Deploy is sequential execution of known steps, not architectural reasoning. Sonnet handles it well.

Set via `/model sonnet` before invoking this skill.

## Instructions

You are a production deployment operator. Your job is to safely deploy code changes to **the user's** production server. You follow a strict checklist, verify each step, and never skip healthchecks. **All server names, paths, and URLs come from per-project config** — no hardcoded targets belong to any specific project.

### Step 0: Pre-flight safety check

Before ANY deployment action:

1. **Check git status** — uncommitted changes? Warn the user.
2. **Check current branch** — deploying from non-main branch? Require explicit confirmation.
3. **Read deployment config** — resolve the following variables from the project (in priority order):
   - `DEPLOY_HOST` — SSH alias or host from `~/.ssh/config`, e.g. `myserver` or `user@host`
   - `DEPLOY_PATH` — remote project directory, e.g. `/opt/myapp`
   - `DEPLOY_COMPOSE` — path to the prod compose file, e.g. `docker/docker-compose.prod.yml`
   - `DEPLOY_ENV_FILE` — path to the env file, e.g. `.env`
   - `DEPLOY_SERVICE` — default service name to deploy, e.g. `web`
   - `HEALTHCHECK_URL` — URL that returns 200 when the app is healthy
   - `DB_CONTAINER` (optional) — container name for DB migrations, e.g. `docker-postgres-1`
   - `GATEWAY_RENDER_CMD` (optional) — command to regenerate gateway config if the project has one, e.g. `bash scripts/render-kong.sh`
   - `EXTRA_EXCLUDES` (optional) — space-separated list of additional paths to exclude from tar sync

   Discovery order:
   1. **`scripts/deploy-env.sh`** or **`scripts/deploy.sh`** in the project — bash-sourceable `export` statements. Preferred: predictable, version-controlled.
   2. **`CLAUDE.md` in project root** — a `## Deploy config` section with the variables listed as `KEY=value` or a fenced `sh` block with `export` statements.
   3. **Project memory** — files matching `reference_server*.md` or `reference_deploy*.md`.
   4. **None of the above** — **STOP** and ask the user for the missing values. Offer to write `scripts/deploy-env.sh` as a template they can commit. Do NOT invent defaults.

4. **Identify what changed** — `git log --oneline` since last deploy tag/marker (`git tag --list 'deploy-*' | tail -1`).
5. **Check for pending migrations** — scan `packages/supabase/migrations/`, `migrations/`, `db/migrations/`, or whichever directory the project uses. If the project has no migrations dir, skip this check and note it in the summary.
5b. **Pre-deploy independent review gate (U16)** — before ANY
   mutating step (Steps 1–5), run the risk-tiered gate:

   ```bash
   # ONLY the installed copy — never a gate script shipped inside the deploy
   # candidate (candidate-controlled gate code must not gate itself). The
   # anchor comes from the OS account database, NOT from $HOME: a launch
   # with a relocated HOME must not be able to substitute the gate itself
   # (route findings r53/r55). On hosts without getent, use the installed
   # launcher path verified by /doctor.
   ITD_HOME="$(getent passwd "$(id -u)" | cut -d: -f6)"
   G="$ITD_HOME/.claude/skills/deploy/scripts/itd_predeploy_gate.py"
   # For a GATED class add both flags (r60: this fence is paste-executable,
   # so the optional flags live in this comment, not in bracket notation):
   #   --receipt <path-to-the-fresh-adjudication-receipt>
   #   --emit-deploy-input .itd-memory/deploy-input.tar
   sh "$ITD_HOME/.claude/skills/_shared/itd_py.sh" "$G" check --root "$(git rev-parse --show-toplevel)"
   ```

   For a **gated** class `--emit-deploy-input` is REQUIRED: the gate itself
   produces the deployable artifact (`git archive --format=tar HEAD`) and
   prints its `deployInputSha256`. Steps 1–5 must ship **that artifact**;
   an rsync/tar of the working directory is not the reviewed candidate and
   silently carries ignored, unreviewed files (route finding r30).

   Exit 0 — proceed; exit 2 prints one typed JSON line (WHY + FIX) and the
   deploy MUST stop before any mutating step. **Enforcement is mechanical**:
   `hooks/check-predeploy-gate.sh` (PreToolUse, Bash matcher) is a
   **shipment-scoped receipt gate** (ADR-008, 2026-08-12): for a gated
   candidate it denies a recognized deploy transport — `ssh`, `scp`, `rsync`,
   `docker` push, `podman`, `kubectl`, `helm`, `tar`, `curl`, `wget`, `nc`,
   `aws`, `rclone`, `terraform`, `pulumi`, `flyctl`, `vercel`, `kamal`, … —
   or a statically opaque command that could hide one (command/process
   substitution outside single quotes, `eval`/`source`/`xargs`, `case`/
   `select`, unlexable text) until this gate has recorded a pass bound to the
   exact current candidate digest, so skipping this item does not skip the
   gate. A **valid current pass then allows the reviewed deploy regardless of
   shipment form** — the r53–r89 review rounds proved that statically parsing
   a Turing-complete shell to prove a command "ships only the reviewed
   artifact" is undecidable, so the gate stopped analysing the form.
   **Ordinary local code execution** (interpreters, build/test/task runners
   like `bash deploy.sh` / `python deploy.py` / `make deploy`, path-qualified
   or custom executables) and **local file operations** are **out of scope**
   — allowed, and covered by `/careful`, the completion gate and human deploy
   review, not this hook. Read-only inspection (`docker ps`, `kubectl get`,
   …) and routine candidates are never blocked. Shipping the exact
   `--emit-deploy-input` artifact (above) remains the correct practice even
   though the gate no longer mechanically enforces the transport's shape.
   **Stated boundary (route finding r73, same-principal TOCTOU):** the gate
   binds the deploy-input digest at check time, but a *separate concurrent
   process running as the same user* could replace the artifact file between
   the gate's validation and the transport's own `open()`. A PreToolUse hook
   cannot hold that file descriptor through an external `rsync`/`scp`, so this
   race is out of scope — it is the same same-principal limit already stated
   for the pass-record key (r51/r53): the gate is not a defense against an
   attacker who already has concurrent code execution as the user. Risk signals are
   read from **opt-in project declarations**, not objectively derived: the
   `itd-domain: data-sensitive` / `itd-domain: monetary` markers in the
   project's `CLAUDE.md`, `ITD_DEPLOY_MONETARY` in the deploy environment,
   and a recursive auto-scan of a **fixed list** of migration directories
   (`migrations`, `db/migrations`, `packages/supabase/migrations`) — a
   genuinely data-sensitive project that declares no marker and keeps
   migrations elsewhere (`alembic/versions`, `prisma/migrations`, …) is
   classified routine and passes unreviewed; broader auto-detection is a
   queued BACKLOG follow-up. ANY populated
   migration directory from that list classifies the candidate irreversible (strict
   presence-based; local `deploy-*` tags are a forgeable marker and never
   downgrade the class — an authenticated deployed-state attestation is a
   queued BACKLOG follow-up). Explicit `--data-sensitive` /
   `--monetary` / `--migrations-dir` flags can only ESCALATE a signal (e.g.
   with the dir found in item 5) — they never suppress one the project
   itself declares. Semantics (fail-closed): a data-sensitive,
   irreversible or monetary candidate requires a clean
   worktree (the deployed content must be the exact reviewed HEAD) and a
   fresh Verification Loop adjudication receipt bound to that candidate —
   missing/stale/invalid blocks. Receipt and override validation run against
   the INSTALLED methodology (fixed trust anchor `~/.claude`; deliberately
   not configurable from the CLI), never against validator code shipped
   inside the deploy candidate. The
   criterion's only bypass class — the audited
   `HUMAN_OVERRIDE_NO_INDEPENDENT_REVIEW` record — must carry a recorded
   reason AND a signature; `mint-override` records are unsigned today, so
   the gate refuses every override for every gated class (strict fail-closed
   branch; the signed override channel is a queued BACKLOG follow-up), and
   an override is never PASSED and never review evidence. A routine
   candidate passes without a receipt — the gate is risk-tiered, not
   unconditional. **Deployment-input constraint for gated classes:** the
   receipt covers tracked committed content only — locally changed IGNORED
   artifacts are outside it (`git status` cannot see them). For a
   data-sensitive/irreversible/monetary deploy, Step 1 MUST ship the artifact
   the gate itself emitted — the gate produces it with `git archive HEAD`, so
   it is exactly the tracked committed content of the reviewed candidate.
   Never a working-directory tar that could include ignored build/deploy
   artifacts, and never a fresh ad-hoc archive of the working tree. **This is
   required deploy procedure, not hook enforcement:** under ADR-008 a valid
   current pass authorizes the reviewed deploy regardless of the transport's
   shape, so the hook will NOT deny an ad-hoc archive after a clean gate run —
   shipping the emitted artifact is on the operator, and skipping it silently
   ships unreviewed ignored files. Ship it, for example, as
   `cat .itd-memory/deploy-input.tar | ssh $DEPLOY_HOST "tar -x -C $DEPLOY_PATH"`
   or `scp .itd-memory/deploy-input.tar $DEPLOY_HOST:$DEPLOY_PATH/`.
6. **Confirm with user** — show summary of what will be deployed and ask for explicit approval.

**CRITICAL:** Never deploy without user confirmation. Show:
```
Deploy summary:
- Branch: main (commit abc1234)
- Changed files: N files
- Pending migrations: 016, 017
- Target: $DEPLOY_HOST ($DEPLOY_PATH)
- Service: $DEPLOY_SERVICE
- Healthcheck: $HEALTHCHECK_URL
Proceed? [yes/no]
```

### Step 1: Sync files to server

Use tar-over-ssh (more reliable than rsync on slow/exotic links):

```bash
tar czf - \
  --exclude='.git' \
  --exclude='node_modules' \
  --exclude='.next' \
  --exclude='.env' \
  --exclude='.env.local' \
  --exclude='dist' \
  $EXTRA_EXCLUDES \
  . | ssh $DEPLOY_HOST "cd $DEPLOY_PATH && tar xzf - --overwrite"
```

If the project's `deploy-env.sh` defines `EXTRA_EXCLUDES`, append them (e.g., a rendered-on-server config like `docker/supabase/kong.yml` that should not be overwritten by local content).

**Verify:** SSH to server and check a known changed file exists with correct content.

### Step 2: Regenerate gateway / reverse-proxy config (optional)

Skip this step if the project doesn't define `GATEWAY_RENDER_CMD`. Otherwise:

```bash
ssh $DEPLOY_HOST "cd $DEPLOY_PATH && $GATEWAY_RENDER_CMD"
```

**Verify:** command exits 0 and (if the command echoes a summary) the summary looks sensible.

### Step 3: Build Docker image

```bash
ssh $DEPLOY_HOST "cd $DEPLOY_PATH && docker compose -f $DEPLOY_COMPOSE --env-file $DEPLOY_ENV_FILE build $DEPLOY_SERVICE"
```

This step typically takes 2-5 minutes. Monitor for:
- Docker Hub timeout → check registry mirrors in `/etc/docker/daemon.json` (particularly relevant in jurisdictions where Docker Hub is throttled)
- Build errors → report to user, do NOT proceed
- SSH session may not return output for long-running builds → separately check `docker images | grep $DEPLOY_SERVICE` for fresh timestamp

**Verify:** `docker images --format '{{.Repository}}:{{.Tag}} {{.CreatedAt}}' | grep $DEPLOY_SERVICE` shows timestamp within the last 5 minutes.

### Step 4: Restart containers

```bash
ssh $DEPLOY_HOST "cd $DEPLOY_PATH && docker compose -f $DEPLOY_COMPOSE --env-file $DEPLOY_ENV_FILE up -d $DEPLOY_SERVICE"
```

**Verify:** `docker ps --format '{{.Names}} {{.Status}}' | grep $DEPLOY_SERVICE` shows "Up N seconds (healthy)".

### Step 5: Apply migrations (if any)

Skip this step if `DB_CONTAINER` is not set OR the project has no pending migrations. Otherwise, for each pending migration file:

```bash
ssh $DEPLOY_HOST "docker exec -i $DB_CONTAINER psql -U postgres -d postgres" < path/to/migration.sql
```

Adapt the `psql`/`mysql`/etc command to whichever DB the project uses — resolve from `DEPLOY_COMPOSE`.

**Verify:** No SQL errors in output. Check table existence if migration creates tables.

**IMPORTANT:** If migration fails, report immediately and do NOT proceed. Migrations are not automatically reversible.

### Step 6: Healthcheck

```bash
ssh $DEPLOY_HOST "curl -sk $HEALTHCHECK_URL"
```

(Or run `curl` from the local side if the healthcheck URL is public.)

**Expected:** HTTP 200 with a body indicating health (commonly `{"status":"ok"}` or similar — check the project's actual healthcheck contract).

If healthcheck fails:
1. Check container logs: `ssh $DEPLOY_HOST "docker logs <container-name> --tail 30"`
2. Check if container is running: `docker ps | grep $DEPLOY_SERVICE`
3. Report failure to user with logs

### Step 7: Post-deploy

1. **Tag the deploy** (optional): suggest `git tag deploy-YYYY-MM-DD`
2. **Call /session-save** — automatically save deployment context
3. **Report summary** to user:

```
Deploy complete:
- Files synced: OK
- Gateway config: OK (or skipped)
- Docker build: OK (image timestamp)
- Container: healthy
- Migrations: N applied (or skipped)
- Healthcheck: OK
- Duration: ~Xm
```

## Deployment config — how users configure `/deploy` for their project

For `/deploy` to work on a new project, the user needs ONE of the following in the project:

**Option A: `scripts/deploy-env.sh`** (recommended — bash-sourceable, version-controlled):

```bash
#!/usr/bin/env bash
# Deploy target for /deploy skill — used by idea-to-deploy methodology.
export DEPLOY_HOST="myserver"           # ~/.ssh/config alias
export DEPLOY_PATH="/opt/myapp"
export DEPLOY_COMPOSE="docker/docker-compose.prod.yml"
export DEPLOY_ENV_FILE=".env"
export DEPLOY_SERVICE="web"
export HEALTHCHECK_URL="https://myapp.example.com/api/health"
export DB_CONTAINER="docker-postgres-1"      # optional, only for migrations
export GATEWAY_RENDER_CMD=""                 # optional: e.g., "bash scripts/render-kong.sh"
export EXTRA_EXCLUDES=""                     # optional: space-separated extra tar excludes
```

**Option B: `## Deploy config` section in project `CLAUDE.md`** — same variables as above, inside a fenced `sh` block.

**Option C: Project continuity file** — `.itd-memory/reference_deploy.md` with
an `export` block. Host-private memory may mirror it, but is never the only
copy.

If none of the above is present, `/deploy` will **ask the user** for each value and offer to write `scripts/deploy-env.sh` as a template.

## Known issues

- **rsync may hang** on some providers with aggressive TCP tuning — always use tar-over-ssh (Step 1 already does this).
- **Docker Hub throttling/blocks** in some jurisdictions — mirrors must be configured in `/etc/docker/daemon.json` on the target host. Common mirrors: `mirror.gcr.io`, `dockerhub.timeweb.cloud`, `huecker.io`.
- **SSH long-running commands** may not return output until the command finishes. Verify side effects out-of-band (separate SSH with `docker images`/`docker ps`).
- **Reverse-proxy config lost after container recreate** — if the project uses Traefik/Caddy/Nginx in a separate container, export the dynamic config file BEFORE container recreation and re-apply after. This is project-specific and belongs in `GATEWAY_RENDER_CMD` or a post-deploy script.

## Rules

1. **Never deploy without user confirmation** — show what will change first
2. **Never skip healthcheck** — a deploy without healthcheck is not a deploy
3. **Stop on any error** — do not proceed to next step if current step failed
4. **Always call /session-save** after deploy — deployment context must be preserved
5. **Migrations are irreversible** — warn user before applying, show SQL content if requested
6. **One service at a time** — unless explicitly asked to deploy "all"
7. **No hardcoded project-specific values** — all host/path/URL come from config; if config missing, ask the user

## Self-validation

Before reporting deploy as complete, verify:
- [ ] Files synced (tar exit code 0)
- [ ] Gateway/proxy config regenerated (if applicable)
- [ ] Docker image built with fresh timestamp
- [ ] Container running and healthy
- [ ] All migrations applied without errors
- [ ] Healthcheck returns 200 OK
- [ ] /session-save called

## Examples

### Example 1 — Web-only deploy (fast path)

The project has a `scripts/deploy-env.sh` with `DEPLOY_HOST=myserver`, `DEPLOY_PATH=/opt/myapp`, etc.

```
User: задеплой web на прод

Claude: [/deploy]
  Step 0 — pre-flight:
    Sourcing scripts/deploy-env.sh ...... OK
    Branch: main (commit 7b614b2)
    Changed files since deploy-2026-04-14: 6
    Pending migrations: none
    Target: myserver (/opt/myapp)
    Service: web
    Healthcheck: https://myapp.example.com/api/health
    Proceed? [yes/no]
User: yes
  Step 1/6 — tar-over-ssh sync ........ OK (6 files, 1.2 MB)
  Step 2/6 — gateway render ........... skipped (no GATEWAY_RENDER_CMD)
  Step 3/6 — docker build web ......... OK (image built 2m14s ago)
  Step 4/6 — docker compose up -d web . OK (healthy, uptime 11s)
  Step 5/6 — migrations ............... skipped (none pending)
  Step 6/6 — curl /api/health ......... OK (HTTP 200)

Deploy complete in 3m42s. /session-save invoked.
```

### Example 2 — First deploy, config missing

```
User: задеплой на прод

Claude: [/deploy]
  Step 0 — pre-flight:
    Looking for scripts/deploy-env.sh ... not found
    Looking for ## Deploy config in CLAUDE.md ... not found
    Looking for memory reference_deploy.md ... not found
    
  I need deploy configuration to proceed. Let me ask you for the
  values, and I'll offer to save them as scripts/deploy-env.sh so
  you don't have to re-enter them next time.
  
  1. What's your SSH host or alias? (e.g., `myserver` from ~/.ssh/config)
User: myserver
  2. Remote project directory? (e.g., `/opt/myapp`)
User: /opt/shop
  3. Healthcheck URL that returns 200 when healthy?
User: https://shop.example.com/health
  [...4 more questions...]
  
  Shall I save these as scripts/deploy-env.sh? [yes/no]
User: yes
  Wrote scripts/deploy-env.sh. Add it to git and commit.
  
  Now proceeding with deploy... [continues as Example 1]
```

## Troubleshooting

### SSH connection timeout
Use SSH alias from `~/.ssh/config` as `DEPLOY_HOST`. Direct IP connection may hang on hosts that lack `KexAlgorithms` / `IPQoS` negotiation; aliases pre-configure these.

### Docker build TLS timeout
Check registry mirrors: `ssh $DEPLOY_HOST "cat /etc/docker/daemon.json"`. If no mirrors, the target host has no fallback when Docker Hub is slow/blocked. Add mirrors like `mirror.gcr.io`, `dockerhub.timeweb.cloud`, `huecker.io` (region-dependent).

### Container starts but healthcheck fails
1. Check logs: `ssh $DEPLOY_HOST "docker logs <container-name> --tail 50"`
2. Check internal connectivity: `ssh $DEPLOY_HOST "docker exec <container-name> wget -qO- http://localhost:PORT/health"`
3. Check reverse-proxy routing: `docker exec <proxy-container> cat /path/to/config`

### Migration fails
1. DO NOT retry blindly — read the error
2. Check if table/column already exists (idempotent migrations should use `IF NOT EXISTS`)
3. Show rollback SQL from migration comments if available
