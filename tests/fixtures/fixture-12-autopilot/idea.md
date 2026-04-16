# Fixture 12 — /autopilot

Полный автопилот-пайплайн для простого Telegram-бота.

## Context

Проверка сквозного запуска всех фаз методологии без ручного вмешательства: discover → blueprint → kickstart → review → test, с чекпойнтами между фазами. Стек фиксирован, чтобы исключить вариативность по технологиям.

## Input prompt

Автопилот: создай Telegram-бот для записи к парикмахеру. Стек: Python + aiogram + PostgreSQL. Целевая аудитория: парикмахеры-одиночки.

## Expected behavior

- Проходят все 5 фаз (discover, blueprint, kickstart, review, test).
- Созданы DISCOVERY.md, STRATEGIC_PLAN.md, ARCHITECTURE.md, PRD.md, IMPLEMENTATION_PLAN.md, README.md.
- Минимум 1 /session-save между фазами.
- /review даёт оценку не ниже 8/10.

## Fixture status

`pending` — snapshot без content contracts. Прогон валидирует только orchestration pipeline, не качество отдельных артефактов. Upgrade до `active` после стабилизации /autopilot.
