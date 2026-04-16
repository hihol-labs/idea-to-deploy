---
name: migrate-prod
description: 'Migrate running production services between hosts — inventory, setup, data migration, dual-run, DNS cut-over, rollback plan. For DB-only migrations use /migrate instead.'
argument-hint: source host, target host, or "plan only"
license: MIT
allowed-tools: Read Write Edit Glob Grep Bash(ssh:*) Bash(scp:*) Bash(rsync:*) Bash(docker:*) Bash(pg_dump:*) Bash(dig:*) Bash(curl:*)
metadata:
  author: HiH-DimaN
  version: 1.19.0
  category: operations
  tags: [migration, production, infrastructure, dns, rollback, dual-run]
---

# Migrate-Prod

## Trigger phrases

- мигрируй сервер, перенеси сервер, перенос prod, миграция prod
- перенос сайта на другой сервер, переезд сервера, переезд VDS
- с одного сервера на другой, переезд на новый сервер
- migrate prod, migrate server, server migration
- move to new server/host/VDS/VPS
- перенос инфраструктуры, infrastructure migration
- dual-run, cut-over DNS

## Recommended model

**opus** — Production migrations are high-risk operations requiring careful sequencing, risk assessment, and rollback planning. Opus reasoning is essential.

## Instructions

### Step 0: Confirm production scope

**STOP and confirm with the user:**
> "Это PRODUCTION миграция. Сервисы будут затронуты. Подтверждаешь? (yes/no)"
> "Есть ли maintenance window или миграция должна быть zero-downtime?"

Gather:
- Source host (IP, provider, OS)
- Target host (IP, provider, OS)
- List of services to migrate
- DNS provider (Cloudflare, Route53, etc.)
- Acceptable downtime window

### Step 1: Source inventory

Catalog everything running on the source:

```bash
# Docker containers
ssh source "docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}\t{{.Status}}'"

# Volumes
ssh source "docker volume ls"

# Databases
ssh source "docker exec -i db psql -U postgres -c '\l'"

# Disk usage
ssh source "df -h && du -sh /var/lib/docker/volumes/*"

# Cron jobs
ssh source "crontab -l 2>/dev/null; ls /etc/cron.d/ 2>/dev/null"

# SSL certificates
ssh source "ls -la /etc/letsencrypt/live/ 2>/dev/null"

# Environment files
ssh source "find /opt /srv /home -name '.env' -o -name 'docker-compose*.yml' 2>/dev/null"
```

Document in `MIGRATION_PLAN.md`:
```markdown
## Source Inventory
| Service | Image | Ports | Data Volumes | Size |
|---|---|---|---|---|
| app | myapp:latest | 8000 | app_data (2.1G) | — |
| db | postgres:15 | 5432 | pg_data (4.3G) | — |
| minio | minio/minio | 9000,9001 | minio_data (12G) | — |
```

### Step 2: Target setup

Prepare the target host:

1. **OS hardening** — unattended-upgrades, fail2ban, SSH key-only
2. **Docker + Compose** — install and verify
3. **Reverse proxy** — Traefik/Nginx/Coolify setup
4. **Firewall** — allow only needed ports (22, 80, 443, app-specific)
5. **Monitoring** — at minimum: `docker stats` + uptime check
6. **SSL** — certbot or Cloudflare origin certificates

Do NOT switch DNS yet. Verify target is accessible via IP.

### Step 3: Data migration

**Order matters:** databases first, then object storage, then uploads.

```bash
# PostgreSQL
ssh source "pg_dump -Fc dbname" | ssh target "pg_restore -d dbname"

# Minio / S3 objects
rsync -avz --progress source:/path/to/minio/data/ target:/path/to/minio/data/

# File uploads
rsync -avz --progress source:/path/to/uploads/ target:/path/to/uploads/

# Docker volumes (generic)
ssh source "docker run --rm -v volname:/data -v /tmp:/backup alpine tar czf /backup/vol.tar.gz /data"
scp source:/tmp/vol.tar.gz target:/tmp/
ssh target "docker run --rm -v volname:/data -v /tmp:/backup alpine tar xzf /backup/vol.tar.gz -C /"
```

### Step 4: Deploy services on target

1. Copy `docker-compose.yml` and `.env` files
2. Adjust for target differences (paths, IPs, ports)
3. `docker compose up -d`
4. Verify each service:
   - Health check endpoint responds
   - Database has expected data
   - Object storage accessible
   - Telegram bot webhook (if applicable) — update to target IP temporarily

### Step 5: Dual-run period (24-48h recommended)

Both source and target running simultaneously:
- Source: continues serving production traffic via DNS
- Target: ready but not receiving external traffic
- Test target via direct IP access or `/etc/hosts` override

Checklist during dual-run:
- [ ] All services healthy on target
- [ ] DB data matches (row count comparison)
- [ ] File uploads accessible
- [ ] API endpoints respond correctly
- [ ] Telegram bots respond (if using proxy/webhook)
- [ ] SSL certificates valid
- [ ] Monitoring alerts configured

### Step 6: DNS cut-over

**This is the point of no return for users.** Prepare rollback BEFORE switching.

```bash
# Lower TTL 24h before cut-over (if not already low)
# Cloudflare: set to 60s, wait for old TTL to expire

# Switch A/AAAA records to target IP
# Verify propagation
dig +short domain.com @8.8.8.8
dig +short domain.com @1.1.1.1

# Monitor for errors in first 30 minutes
ssh target "docker logs -f --since 5m app"
```

### Step 7: Rollback plan

Document BEFORE cut-over:

```markdown
## Rollback Plan

If critical issues after DNS switch:

1. **Immediate (DNS):** Switch A records back to source IP
   - Cloudflare: <60s propagation
   - Standard DNS: up to old TTL (lower beforehand!)

2. **Data sync back** (if target accumulated new data):
   ```bash
   ssh target "pg_dump -Fc dbname" | ssh source "pg_restore -c -d dbname"
   rsync target:/uploads/ source:/uploads/
   ```

3. **Telegram bots:** Update webhook URL back to source

Source server stays running for 7 days post-cutover as safety net.
```

### Step 8: Post-migration cleanup

After 7 days of stable operation on target:

- [ ] Final data comparison (source vs target)
- [ ] Decommission source: stop services, NOT delete data
- [ ] Archive source data (backup to S3/local)
- [ ] Cancel source hosting after 30 days
- [ ] Update all documentation with new IPs/hosts
- [ ] Rotate any secrets that were copied (DB passwords, API keys)
- [ ] Remove source from monitoring


## Examples

### Example 1: Migrate 3 projects from Beget to Hostland
User: "Перенеси 3 проекта с Beget VDS на Hostland VDS"

Actions:
1. Confirm: production, 3 services, zero-downtime preferred
2. Inventory: 3 Docker Compose stacks, 2 PostgreSQL DBs, 1 Minio
3. Setup Hostland: Ubuntu 22.04, Docker, Coolify, Cloudflare SSL
4. Data: pg_dump all DBs, rsync Minio buckets and uploads
5. Deploy all 3 stacks on target, verify via IP
6. Dual-run 48h, test Telegram bot webhooks
7. DNS cut-over via Cloudflare (60s TTL)
8. Keep Beget running 7 days, then decommission


### Example 2: Migrate single Telegram bot to new VPS
User: "Перенеси Telegram-бот с Beget на Hetzner VPS"

Actions:
1. Confirm: single service, Telegram bot on aiogram
2. Inventory: 1 Docker Compose stack, SQLite DB, no object storage
3. Setup Hetzner: Ubuntu 22.04, Docker, Nginx reverse proxy
4. Data: scp SQLite file + uploads directory
5. Deploy on target, test bot via direct IP webhook
6. Update Telegram webhook to new domain
7. Keep Beget running 7 days as safety net


## Self-validation

Before executing migration steps, verify:
- [ ] Source inventory complete (all services, volumes, data sizes documented)
- [ ] Target setup verified (Docker, SSL, firewall, monitoring)
- [ ] Rollback plan documented with exact commands
- [ ] Data migration tested on non-critical service first
- [ ] DNS TTL lowered 24h before cut-over
- [ ] User explicitly confirmed production migration
- [ ] Secret rotation planned for post-migration


## Troubleshooting

### SSH connection to source/target fails
Check: firewall rules, SSH key permissions (600), correct user. Try `ssh -vvv` for debug output. If behind VPN, ensure routing is correct.

### Docker volumes too large to rsync
Use `docker save` for images and incremental `rsync --partial` for volumes. For very large datasets (>50GB), consider shipping a physical disk or using the provider's migration tools.

### DNS propagation is slow
Lower TTL to 60s at least 24h before migration. Use `dig @8.8.8.8` and `dig @1.1.1.1` to check propagation. Cloudflare proxied records propagate in <60s.

### Telegram bot stops responding after migration
Update webhook URL to new server IP/domain. Check that the bot token is correct in `.env`. Verify outbound HTTPS access from the target server (some providers block port 443 outbound by default).

### Database dump/restore fails with version mismatch
Source and target PostgreSQL versions must be compatible. If upgrading (e.g., 14→16), use `pg_dump` from the TARGET version against the SOURCE database.


## Rules

- **Never switch DNS without a tested rollback plan.** No exceptions.
- **Never delete source data within 7 days of cut-over.**
- **Always do data migration in order:** databases → object storage → files.
- **Always verify target services via IP before DNS switch.**
- **Dual-run period is mandatory** — minimum 24h for production services.
- **Rotate secrets after migration** — copied credentials are a security risk.
- **Match the user's language** for MIGRATION_PLAN.md and all reports.
