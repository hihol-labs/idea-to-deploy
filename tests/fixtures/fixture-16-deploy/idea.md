# Fixture 16 — /deploy

Deploy pipeline для существующего проекта на живой production-хост.

## Context

/deploy последовательно выполняет: sync файлов на сервер → регенерацию kong config → docker build → restart контейнеров → прогон миграций → healthcheck. Требует SSH-доступ к реальному или ephemeral таргету. Для fixture-окружения это stub — полноценный прогон отложен до появления dedicated тест-хоста или mock SSH.

## Input prompt

Задеплой текущую ветку на прод. Убедись, что миграции применились и healthcheck зелёный.

## Expected behavior

- Запрашивает явное подтверждение (refuse without explicit confirmation).
- Проходит шаги: sync → kong config → docker build → restart → migrations → healthcheck.
- При провале любого шага — останавливается и репортит состояние без отката (скилл не rollback-ориентирован, это зона /migrate-prod).

## Fixture status

`pending` — stub. Полноценная валидация требует ephemeral SSH-хоста или mock surface. Сейчас фикстура нужна только чтобы удовлетворить `check-skill-completeness.sh` и якорить будущую регрессионную работу.
