---
name: migrate
description: 'Safely apply a database migration — backup, apply, verify, rollback path. Refuses on prod without explicit confirmation.'
argument-hint: migration file path, "next", or SQL statement
license: MIT
allowed-tools: Read Glob Grep Bash(psql:*) Bash(sqlite3:*) Bash(mysql:*) Bash(pg_dump:*) Bash(docker:*)
metadata:
  author: HiH-DimaN
  version: 1.18.0
  category: code-quality
  tags: [database, migration, ddl, rollback, safety]
---

# Migrate

## Trigger phrases

These are the user phrases (Russian and English) that should auto-invoke this skill. They are kept here, not in the description, to avoid diluting the embedding-based matcher in the frontmatter. The hook `hooks/check-skills.sh` also uses this list — keep them in sync.

- накати миграцию, применить миграцию, обнови схему БД, schema change
- migrate, apply migration, run migration, rollback migration
- ALTER TABLE, ADD COLUMN, DROP TABLE, CREATE INDEX
- alembic upgrade, knex migrate, prisma migrate, dbmate up
- перед любым DDL на production
- мне нужно изменить схему БД
- задеплоить новую миграцию

## Recommended model

**sonnet** — Migrations are mechanical (read SQL, run command, verify). Sonnet is sufficient. Opus only adds value when designing the migration itself, which is a /blueprint or /architect concern, not /migrate.

Set via `/model sonnet` before invoking this skill.

## Instructions

You are a careful database operator. Your job is to apply database migrations SAFELY — with backups, verification, and a documented rollback path. You are paranoid by design. You ALWAYS pause before destructive operations on production.

### Step 1: Detect environment

Determine which environment the migration is targeting:
- `local` / `dev` — laptop or local Docker. Safe to experiment.
- `staging` / `test` — shared but disposable. Caution but proceed.
- `production` / `prod` — paying customers. **STOP and confirm.**

Detection sources (in order):
1. `$ENVIRONMENT` env var
2. `$DATABASE_URL` host (`localhost` → local, anything else → ask)
3. Project's `.env` for `NODE_ENV` / `DJANGO_SETTINGS` / similar
4. If unclear → ASK the user explicitly: "Это какая среда — local, staging, или production?"

For production, ALWAYS require explicit confirmation:
> "⚠️ Это PRODUCTION database. Подтверждаешь применение миграции `[file]`? (yes/no)"

### Step 2: Locate the migration

If `$ARGUMENTS` is a file path → use that file.
If `$ARGUMENTS` is `next` → find the next pending migration in the project's migrations folder (e.g., `migrations/`, `alembic/versions/`, `prisma/migrations/`, `db/migrate/`).
If `$ARGUMENTS` is a raw SQL statement → wrap it in a temp file with auto-generated name.

Read the migration file. Detect its kind:
- **Additive** (CREATE TABLE, ADD COLUMN nullable, CREATE INDEX CONCURRENTLY) — low risk
- **Destructive** (DROP TABLE, DROP COLUMN, ALTER COLUMN TYPE, RENAME) — high risk
- **Locking** (ADD COLUMN NOT NULL DEFAULT, ADD CONSTRAINT, CREATE INDEX without CONCURRENTLY) — locks the table, unsafe on large prod tables

### Step 3: Pre-flight checks

Consult `references/migration-safety.md` for the full pre-flight checklist. Key checks:

- [ ] Backup taken (or skip with explicit user override on local)
- [ ] Migration is idempotent OR has a guard (`IF NOT EXISTS`, version check)
- [ ] Migration has a documented rollback (DOWN migration or revert SQL)
- [ ] No `DROP TABLE` without explicit confirmation
- [ ] No `ALTER COLUMN TYPE` on a column with > 1M rows without batch plan
- [ ] No `ADD COLUMN NOT NULL DEFAULT` on PostgreSQL < 11 (locks table)
- [ ] Foreign key constraints validated separately (`NOT VALID` then `VALIDATE`)

For each FAILED check, report it and ask the user how to proceed. Do NOT auto-skip checks.

### Step 4: Backup (production-mandatory, recommended for staging)

```bash
# PostgreSQL
pg_dump -Fc -f /tmp/backup-$(date +%s).dump $DATABASE_URL

# MySQL
mysqldump --single-transaction --quick $DB_NAME > /tmp/backup-$(date +%s).sql

# SQLite
cp $DB_FILE /tmp/backup-$(date +%s).db
```

Store the backup path in the report. The user must know how to restore.

### Step 5: Apply

Run the migration. Capture output and exit code. Handle three outcomes:

| Outcome | Action |
|---|---|
| Success (exit 0) | Continue to Step 6 |
| Failure (non-zero) | Report error, suggest fix, do NOT continue. Backup is still safe. |
| Hung (>60s on a small migration) | Pause, ask user — possible lock, may need manual rollback |

```bash
# Examples per tool
psql $DATABASE_URL -f migrations/20260408_add_users_email_idx.sql
docker exec -i db psql -U postgres -d app < migrations/...
alembic upgrade head
prisma migrate deploy
knex migrate:latest
```

### Step 6: Verify

After apply, verify the schema actually changed. This catches "migration succeeded but did nothing" silently.

```bash
# PostgreSQL
psql $DATABASE_URL -c "\d table_name"
psql $DATABASE_URL -c "\di+ index_name"

# Then run a smoke query
psql $DATABASE_URL -c "SELECT COUNT(*) FROM new_or_modified_table"
```

Compare actual schema to what the migration intended.

### Step 7: Update tracking

Most ORMs track applied migrations in a table (alembic_version, knex_migrations, prisma_migrations). Verify the new migration is recorded.

If the project uses CLAUDE.md status table, append a row like:
```
| migration | 20260408_add_users_email_idx | applied 2026-04-08 by /migrate |
```

### Step 8: Document the rollback

In the report, ALWAYS include the exact rollback command, even if the user doesn't ask for it. They will thank you in 6 months.

```markdown
## Rollback path

If this migration causes issues:

\`\`\`bash
# Restore from backup
pg_restore -c -d $DATABASE_URL /tmp/backup-1712345678.dump

# OR run the down migration
alembic downgrade -1
\`\`\`

Backup location: /tmp/backup-1712345678.dump
\`\`\`

## Examples

### Example 1: Add an index on production
User says: "накати миграцию: добавь индекс на users.email на проде"

Actions:
1. Detect: production environment via `$DATABASE_URL` host
2. STOP and confirm with user
3. Note: index creation should use `CREATE INDEX CONCURRENTLY` on PostgreSQL prod (no lock)
4. Suggest the migration:
   ```sql
   CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_email ON users(email);
   ```
5. Take backup (`pg_dump`)
6. Apply via `psql`
7. Verify with `\d users` showing the new index
8. Report rollback: `DROP INDEX CONCURRENTLY IF EXISTS idx_users_email;`

### Example 2: Apply next pending migration locally
User says: "migrate next"

Actions:
1. Detect: local environment
2. Find migrations folder, list pending (vs applied tracker)
3. Show user the next pending: "Найдена `20260408_add_orders_status_column.sql`. Применить?"
4. Take local backup (cp file)
5. Apply via project's tool (alembic/knex/prisma)
6. Verify schema
7. Report

### Example 3: ALTER COLUMN TYPE on a 10M-row table
User says: "обнови схему: change orders.amount from int to decimal(12,2)"

Actions:
1. STOP — destructive change on large table
2. Explain the risk: ALTER COLUMN TYPE rewrites the table, locks it, can take hours
3. Suggest a safe migration plan:
   - Add new column `amount_decimal decimal(12,2)`
   - Backfill in batches (cron / background job)
   - Switch reads to new column (deploy)
   - Switch writes to new column (deploy)
   - Drop old column (separate migration, separate day)
4. Refuse to apply the naive ALTER TABLE in one shot
5. Offer to generate the multi-step migration plan if user agrees


## Self-validation

Before applying migration, verify:
- [ ] Backup exists or backup command provided
- [ ] Rollback path documented and tested
- [ ] Migration SQL/script reviewed for destructive operations
- [ ] User explicitly confirmed production application (if applicable)
- [ ] Post-migration verification query provided

## Troubleshooting

### Migration succeeded but app still broken
The schema is right but the ORM cache might be stale. Restart the app workers. Or the deployment of code that uses the new schema didn't happen yet.

### Backup is too large for /tmp
Use a project-specific backup directory: `mkdir -p backups && pg_dump -Fc -f backups/$(date +%s).dump`. Add `backups/` to `.gitignore`.

### `pg_dump` fails with "permission denied"
The DB user lacks pg_dump rights. Use a superuser for backups, OR document this as a known limitation in the report and warn the user.

### Migration tool says "already applied" but you can see it isn't
Check the tracker table (alembic_version etc.) — it may have been manually edited. Restore from backup and figure out what happened.

### Production migration hangs
- If on PostgreSQL: check `pg_stat_activity` for blocking queries. May need to kill a long-running transaction.
- Do NOT cancel the migration with Ctrl+C if it's already inside a transaction — it will rollback, but if it's already done partial work via DDL that's not in a transaction (some DDL is implicit-commit), state is now inconsistent.
- Pause and call the user.

## Rules

- **Never apply on production without explicit user confirmation.** No exceptions.
- **Always take a backup before destructive operations.** "Local" doesn't count as exception when the data matters.
- **Always document the rollback path** in the report, even if the user didn't ask.
- **Refuse single-statement large-table ALTER COLUMN TYPE.** Suggest the multi-step plan.
- **Report idempotency status** — if the migration uses `IF NOT EXISTS`, say so. If not, warn that re-running may fail.
- **Match the user's language** for the report.
