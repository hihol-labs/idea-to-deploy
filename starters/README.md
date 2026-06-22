# Starter Packs

Стартер-паки — машиночитаемые шаблоны проектов для idea-to-deploy. Каждый
`STARTER.json` объявляет:

- **productType** — тип продукта (`api_service`, `saas`, `messaging_bot`,
  `mini_app`, `landing_page`);
- **stackPreset** — пресет стека (`itd-default-stack-v1` и профили);
- **stack** — конкретные технологии;
- **folders** — ожидаемая структура каталогов;
- **commands** — как тестировать / запускать / собирать;
- **requiredArtifacts** — какие плановые артефакты idea-to-deploy должны
  существовать для этого типа продукта.

Стартер-слой делает генерацию повторяемой: `/kickstart` выбирает стартер, а не
изобретает каркас с нуля. `files/` — это заглушки-скелеты (health-роут, тест), от
которых отталкивается реализация.

## Стек по умолчанию

`itd-default-stack-v1` совпадает со стеком методологии: **Python / FastAPI /
Pydantic / PostgreSQL / Redis / MinIO S3** на бэкенде; **Vue / TypeScript / Vite
/ TailwindCSS** на фронте; **aiogram** для ботов; **Telegram Mini App SDK** для
mini-app; **Docker / Nginx / just** для эксплуатации. Это golden path, а не
жёсткий лок — отклонения валидны, когда `PROJECT_ARCHITECTURE.md` фиксирует
причину, риск и влияние на верификацию.

## Доступные стартеры

| Стартер | productType | Стек (кратко) |
|---|---|---|
| `api-fastapi` | `api_service` | FastAPI + PostgreSQL + pytest |
| `saas-fastapi-vue` | `saas` | FastAPI + Vue + Redis + MinIO |
| `bot-aiogram` | `messaging_bot` | aiogram + PostgreSQL/SQLite |
| `mini-app-vue` | `mini_app` | Vue + Telegram Mini App SDK + FastAPI |
| `landing-vite` | `landing_page` | Vite + Vue/HTML + TailwindCSS |

## Связь с golden-paths

`golden-paths/*.json` выбирают стартер по типу продукта и задают ожидаемые
артефакты и минимальные гейты. См. [`../golden-paths/README.md`](../golden-paths/README.md).

`requiredArtifacts` ссылаются на реальные артефакты idea-to-deploy: документы
планирования (`PRD.md`, `PROJECT_ARCHITECTURE.md`, `IMPLEMENTATION_PLAN.md`,
`STRATEGIC_PLAN.md`, `DISCOVERY.md`, `MARKET_BRIEF.md`, `LAUNCH_PLAN.md`) и
контракты `.itd/` (`DATA_POLICY.md`, `VERIFICATION_CONTRACT.json`).
