# Fixture 02: Telegram bot — appointment booking

## User says

> Нужен Telegram-бот для записи на стрижку в одну парикмахерскую. Клиент пишет боту, выбирает мастера и время, бот сохраняет запись и отправляет напоминание за час. Админ-парикмахер видит все записи в отдельной команде /admin. Один мастер ведёт расписание сам через бота.

## Why this fixture exists

Tests **Lite mode** (`/blueprint --lite` or auto-Lite on Sonnet). Exercises:
- Single bot service (no separate web frontend)
- Minimal database (1 service)
- aiogram or grammY conventions
- Cron-based reminders
- Simple admin role (just one extra command)

## Expected complexity

- 2–3 database tables (`masters`, `appointments`, optionally `clients`)
- No HTTP API (Telegram Bot API only)
- 4–6 implementation steps in Lite mode
- Single deployable container
