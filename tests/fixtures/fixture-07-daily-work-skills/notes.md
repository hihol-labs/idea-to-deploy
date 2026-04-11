# Manual verification — fixture 07 (shared: /bugfix, /refactor, /perf, /security-audit, /migrate)

This fixture intentionally covers five daily-work skills in one place. Each skill targets the same `app/api/users.py` file or the `migrations/20260408_add_users_email_index.sql` file, looking for different kinds of problems.

## /bugfix

Scenario: the user reports `AttributeError: 'NoneType' object has no attribute 'orders'` when calling `GET /users/999/orders`.

- [ ] `/bugfix` reads the stack trace and isolates the cause: user 999 does not exist, the `user` variable is `None` because the SQL returned no rows
- [ ] Suggests fix: add `if user is None: raise HTTPException(status_code=404)` before the loop
- [ ] Writes a regression test (`tests/test_users.py::test_get_orders_404`)
- [ ] Report format: `debug-report.md` with sections: Symptom, Root cause, Fix, Regression test

## /refactor

Scenario: the user says "refactor `process_checkout`, too long".

- [ ] `/refactor` identifies the long-parameter-list smell (7 params) → Introduce Parameter Object
- [ ] Identifies the conditional ladder → Replace Conditional with Polymorphism OR Extract Method
- [ ] Preserves behavior (suggests running the test suite after each step)
- [ ] Report format: `refactor-diff.patch` with the before/after diff and a note about what smell was addressed

## /perf

Scenario: the user says "эндпоинт /users/{id}/orders тормозит".

- [ ] `/perf` identifies the N+1 query pattern (loop over `user.orders` with a separate `SELECT` per item)
- [ ] Suggests `selectinload` / `joinedload` / `LEFT JOIN` fix depending on the ORM
- [ ] Estimates the improvement (e.g., "from 1 + N queries to 1 query; for 100 orders, 100x fewer round-trips")
- [ ] Report format: `perf-report.md` with: Bottleneck, Fix, Before/after metric estimate

## /security-audit

Scenario: the user says "проверь безопасность users.py перед выкаткой".

- [ ] `/security-audit` flags the hardcoded `ADMIN_TOKEN = "sk-live-..."` → Tier 1 (SECRET-1)
- [ ] Flags the SQL string concatenation `f"SELECT * FROM users WHERE id = {user_id}"` → Tier 1 (INJECT-1)
- [ ] Suggests fixes per finding: move token to env, use parameterized query
- [ ] Does NOT apply fixes (read-only by design)
- [ ] Report format: `security-audit-report.md` matching the format in `skills/security-audit/references/security-checklist.md`
- [ ] Final status: BLOCKED (at least one Critical)

## /migrate

Scenario: the user says "накати миграцию `migrations/20260408_add_users_email_index.sql` на prod".

- [ ] `/migrate` detects environment as `prod` and STOPS, requires explicit confirmation
- [ ] Reads the migration file, detects `CREATE INDEX` without `CONCURRENTLY`
- [ ] Refuses to apply: explains that CREATE INDEX without CONCURRENTLY locks the table on prod
- [ ] Suggests the safe variant: `CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_email ON users(email);`
- [ ] Reports the rollback path: `DROP INDEX CONCURRENTLY IF EXISTS idx_users_email;`
- [ ] Report format: `migrate-report.md` with backup path, applied status, rollback command

## Failures (fill in if any)
