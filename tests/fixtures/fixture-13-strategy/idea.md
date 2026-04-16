# Fixture 13 — /strategy

Стратегический репланинг существующего SaaS, не дотянувшего до целевого MRR.

## Context

Проект NeuroExpert: текущий MRR 50K ₽, цель была 200K ₽ к Q2. Ключевая проблема — низкая конверсия trial→paid (8% вместо 25%). 5 потоков выручки, но доминирует один. Нужно пересобрать LAUNCH_PLAN.md с новыми блоками работы и ADR по pivot-решениям.

## Input prompt

Пересмотри стратегию проекта NeuroExpert. Текущий MRR 50K ₽, цель была 200K ₽ к Q2. Основная проблема: низкая конверсия trial→paid (8% вместо 25%). Есть 5 потоков выручки, доминирует один. Нужен launch plan с новыми блоками работы.

## Expected behavior

- Создаётся `LAUNCH_PLAN.md` с секциями Situation Analysis, Gap, Root Cause, Option A, Option B, ADR, Block, Acceptance criteria.
- Минимум 2 опции с trade-offs, минимум 3 измерения gap-анализа.
- В явном виде зафиксировано pivot-решение (ADR).

## Fixture status

`pending` — snapshot без детальных content contracts. Прогон валидирует pipeline /strategy, не качество стратегических выводов. Upgrade до `active` в будущих версиях.
