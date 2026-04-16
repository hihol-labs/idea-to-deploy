# Fixture 11 — /discover

Product discovery для SaaS-платформы онлайн-записи в салоны красоты.

## Context

Новый проект на стадии идеи. Нужно пройти полный discovery-цикл: посчитать рынок, проанализировать конкурентов, описать персоны, приоритизировать фичи. Монетизация — подписка для салонов. ЦА — владельцы салонов и их клиенты.

## Input prompt

Проведи product discovery для SaaS-платформы онлайн-записи в салоны красоты. Целевая аудитория: владельцы салонов и их клиенты. Монетизация: подписка для салонов.

## Expected behavior

- Создаётся `DISCOVERY.md` с секциями Market Analysis (TAM/SAM/SOM), Competitor Analysis, User Personas, Value Proposition, MoSCoW, RICE.
- Минимум 3 конкурента, 2 персоны, 8 фич в MoSCoW.
- Вывод готов стать входом для /blueprint.

## Fixture status

`pending` — snapshot пока без детальных content contracts. Прогон фикстуры валидирует pipeline вызова скилла, не качество вывода. Проапгрейдить до `active` когда /discover стабилизируется.
