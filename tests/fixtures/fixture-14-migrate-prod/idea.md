# Fixture 14 — /migrate-prod

Миграция 2 production-сервисов с Beget VDS на Hostland VDS.

## Context

Существующие сервисы (Telegram-бот на aiogram + FastAPI backend с PostgreSQL и Minio) работают на старом Beget VDS (Ubuntu 20.04) и должны переехать на новый Hostland VDS (Ubuntu 22.04, Docker, Coolify). DNS управляется через Cloudflare. Нужен план с dual-run периодом и rollback path.

## Input prompt

Перенеси 2 проекта (Telegram-бот на aiogram + FastAPI backend с PostgreSQL и Minio) с Beget VDS (Ubuntu 20.04) на новый Hostland VDS (Ubuntu 22.04, Docker, Coolify). DNS через Cloudflare. Нужен план с dual-run периодом и rollback.

## Expected behavior

- Создаётся `MIGRATION_PLAN.md` с секциями Source Inventory, Target Setup, Data Migration, DNS Strategy, Dual-Run, Cut-Over, Rollback Plan, Decommission.
- Описаны оба сервиса (min 2).
- Явный DNS cut-over план через Cloudflare и rollback-шаги.

## Fixture status

`pending` — snapshot без детальных content contracts. Прогон валидирует pipeline /migrate-prod. Upgrade до `active` когда скилл стабилизируется.
