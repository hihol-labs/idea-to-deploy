# Fixture 14 notes

## Why this fixture exists

Фиксирует, что /migrate-prod генерирует полный runbook миграции с dual-run и rollback, а не только DB-часть (это домен /migrate).

## Known limitations

- Fixture is `status: pending` — verify_snapshot.py авто-пассит без content-валидации.
- Корректность конкретных команд (rsync, pg_dump, Cloudflare API) не верифицируется на реальных хостах.
- Нет mock SSH-таргета — только текстовый план.

## Run manually

1. `cd tests/fixtures/fixture-14-migrate-prod/`
2. `mkdir -p output && cd output`
3. Start Claude Code session, paste idea.md content, invoke /migrate-prod.
4. After it finishes: `cd .. && python3 ../../verify_snapshot.py .`
