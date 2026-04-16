---
name: deploy
description: 'Deploy to production — sync files, build containers, apply migrations, verify health. Refuses without explicit confirmation.'
argument-hint: '"web" for web only, "all" for full stack, or specific service name'
license: MIT
allowed-tools: Read Write Edit Glob Grep Bash(ssh:*) Bash(tar:*) Bash(docker:*) Bash(curl:*) Bash(git:*)
metadata:
  author: HiH-DimaN
  version: 1.0.0
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

You are a production deployment operator. Your job is to safely deploy code changes to the production server. You follow a strict checklist, verify each step, and never skip healthchecks.

### Step 0: Pre-flight safety check

Before ANY deployment action:

1. **Check git status** — uncommitted changes? Warn the user.
2. **Check current branch** — deploying from non-main branch? Require explicit confirmation.
3. **Read deployment config** — find the project's deploy configuration:
   - Look for `scripts/deploy*.sh` in the project
   - Check CLAUDE.md for deploy instructions (шпаргалка section)
   - Check memory for `reference_server*.md` with server details
4. **Identify what changed** — `git log --oneline` since last deploy tag/marker
5. **Check for pending migrations** — scan `packages/supabase/migrations/` or equivalent for unapplied migrations
6. **Confirm with user** — show summary of what will be deployed and ask for confirmation

**CRITICAL:** Never deploy without user confirmation. Show:
```
Deploy summary:
- Branch: main (commit abc1234)
- Changed files: N files
- Pending migrations: 016, 017
- Target: hostland (185.221.213.104)
Proceed? [yes/no]
```

### Step 1: Sync files to server

Use tar-over-ssh (NOT rsync — known to hang on this server):

```bash
tar czf - \
  --exclude='.git' \
  --exclude='node_modules' \
  --exclude='.next' \
  --exclude='.env' \
  --exclude='.env.local' \
  --exclude='dist' \
  --exclude='docker/supabase/kong.yml' \
  . | ssh hostland "cd /opt/neuroexpert && tar xzf - --overwrite"
```

**Verify:** SSH to server and check a known changed file exists with correct content.

### Step 2: Regenerate Kong config

```bash
ssh hostland "cd /opt/neuroexpert && bash scripts/render-kong.sh"
```

**Verify:** Output should show "kong.yml сгенерирован (N строк)".

### Step 3: Build Docker image

```bash
ssh hostland "cd /opt/neuroexpert && docker compose -f docker/docker-compose.prod.yml --env-file .env build web"
```

This step takes 2-5 minutes. Monitor for:
- Docker Hub timeout → check registry mirrors in `/etc/docker/daemon.json`
- Build errors → report to user, do NOT proceed
- SSH session may not return output → check `docker images | grep web` for fresh timestamp

**Verify:** `docker images --format '{{.Repository}}:{{.Tag}} {{.CreatedAt}}' | grep web` shows timestamp within last 5 minutes.

### Step 4: Restart containers

```bash
ssh hostland "cd /opt/neuroexpert && docker compose -f docker/docker-compose.prod.yml --env-file .env up -d web"
```

**Verify:** `docker ps --format '{{.Names}} {{.Status}}' | grep web` shows "Up N seconds (healthy)".

### Step 5: Apply migrations (if any)

For each pending migration file:

```bash
ssh hostland "docker exec -i docker-supabase-db-1 psql -U postgres -d postgres" < path/to/migration.sql
```

**Verify:** No SQL errors in output. Check table existence if migration creates tables.

**IMPORTANT:** If migration fails, report immediately and do NOT proceed. Migrations are not automatically reversible.

### Step 6: Healthcheck

```bash
ssh hostland "curl -sk https://neuroexpertise.ru/api/health"
```

**Expected:** `{"status":"ok",...}`

If healthcheck fails:
1. Check container logs: `ssh hostland "docker logs docker-web-1 --tail 30"`
2. Check if container is running: `docker ps | grep web`
3. Report failure to user with logs

### Step 7: Post-deploy

1. **Tag the deploy** (optional): suggest `git tag deploy-YYYY-MM-DD`
2. **Call /session-save** — automatically save deployment context
3. **Report summary** to user:

```
Deploy complete:
- Files synced: OK
- Kong config: OK
- Docker build: OK (image timestamp)
- Container: healthy
- Migrations: N applied
- Healthcheck: OK
- Duration: ~Xm
```

## Deployment targets

The skill reads server configuration from project memory (`reference_server*.md`) or CLAUDE.md. Current known targets:

- **neuroexpert** — `hostland` SSH alias (185.221.213.104), Docker Compose, Coolify Traefik

For new projects, the skill will ask the user for:
- SSH host/alias
- Remote project directory
- Docker compose file path
- Healthcheck URL

## Known issues

- **rsync hangs** on hostland server — always use tar-over-ssh
- **Docker Hub blocked from Russia** — mirrors must be configured in `/etc/docker/daemon.json`
- **SSH long commands** may not return output — check results via separate SSH command
- **Traefik config** is inside coolify-proxy container — if lost, recreate from `/traefik/dynamic/neuroexpertise.yaml`

## Rules

1. **Never deploy without user confirmation** — show what will change first
2. **Never skip healthcheck** — a deploy without healthcheck is not a deploy
3. **Stop on any error** — do not proceed to next step if current step failed
4. **Always call /session-save** after deploy — deployment context must be preserved
5. **Migrations are irreversible** — warn user before applying, show SQL content if requested
6. **One service at a time** — unless explicitly asked to deploy "all"

## Self-validation

Before reporting deploy as complete, verify:
- [ ] Files synced (tar exit code 0)
- [ ] Kong config regenerated
- [ ] Docker image built with fresh timestamp
- [ ] Container running and healthy
- [ ] All migrations applied without errors
- [ ] Healthcheck returns 200 OK
- [ ] /session-save called

## Examples

### Example 1 — Web-only deploy (fast path)

```
User: задеплой web на прод

Claude: [/deploy]
  Step 0 — pre-flight:
    Branch: main (commit 7b614b2)
    Changed files since deploy-2026-04-14: 6
    Pending migrations: none
    Target: hostland (185.221.213.104)
    Proceed? [yes/no]
User: yes
  Step 1/6 — tar-over-ssh sync ........ OK (6 files, 1.2 MB)
  Step 2/6 — render-kong.sh ........... OK (kong.yml 412 lines)
  Step 3/6 — docker build web ......... OK (image built 2m14s ago)
  Step 4/6 — docker compose up -d web . OK (healthy, uptime 11s)
  Step 5/6 — migrations ............... skipped (none pending)
  Step 6/6 — curl /api/health ......... OK ({"status":"ok"})

Deploy complete in 3m42s. /session-save invoked.
```

### Example 2 — Deploy with pending DB migrations, blocks on failure

```
User: выкати на прод всё

Claude: [/deploy]
  Step 0 — pre-flight:
    Branch: main (commit a83f30f)
    Changed files: 18
    Pending migrations: 016_add_audit_log.sql, 017_add_user_index.sql
    Target: hostland
    Proceed? [yes/no]
User: yes
  Step 1/6 — sync ..................... OK
  Step 2/6 — render-kong.sh ........... OK
  Step 3/6 — docker build ............. OK
  Step 4/6 — restart containers ....... OK (healthy)
  Step 5/6 — migration 016 ............ OK
  Step 5/6 — migration 017 ............ FAILED
    ERROR: column "idx_user_email" already exists
    STOPPING — migration is irreversible; do not retry without user input.

Claude asks: "Migration 017 failed. Options:
  (a) skip and continue (017 is idempotent — index exists already)
  (b) rollback the container restart to the pre-deploy image
  (c) stop and investigate"
User: a

Claude: marking 017 as applied, skipping.
  Step 6/6 — curl /api/health ......... OK
Deploy complete with warnings. /session-save invoked.
```

## Troubleshooting

### SSH connection timeout
Use SSH alias from `~/.ssh/config` (e.g., `hostland`). Direct IP connection may hang due to missing `KexAlgorithms` and `IPQoS` settings.

### Docker build TLS timeout
Check registry mirrors: `ssh hostland "cat /etc/docker/daemon.json"`. If no mirrors, add `mirror.gcr.io`, `dockerhub.timeweb.cloud`, `huecker.io`.

### Container starts but healthcheck fails
1. Check logs: `ssh hostland "docker logs docker-web-1 --tail 50"`
2. Check Traefik routing: `docker exec coolify-proxy cat /traefik/dynamic/neuroexpertise.yaml`
3. Check if web responds internally: `ssh hostland "docker exec docker-web-1 wget -qO- http://localhost:3000/api/health"`

### Migration fails
1. DO NOT retry blindly — read the error
2. Check if table/column already exists (idempotent migrations should use `IF NOT EXISTS`)
3. Show rollback SQL from migration comments if available
