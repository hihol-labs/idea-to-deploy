# Starter Packs

Стартер-паки — машиночитаемые шаблоны проектов для idea-to-deploy. Каждый
`STARTER.json` объявляет:

- **productType** — тип продукта (`api_service`, `saas`, `messaging_bot`,
  `mini_app`, `landing_page`);
- **stackPreset** — пресет стека (`itd-default-stack-v1` и профили);
- **stack** — конкретные технологии;
- **folders** — ожидаемая структура каталогов;
- **commands** — как поднять окружение / тестировать / запускать / собирать;
- **requiredArtifacts** — какие плановые артефакты idea-to-deploy должны
  существовать для этого типа продукта.

Стартер-слой делает генерацию повторяемой: `/kickstart` выбирает стартер, а не
изобретает каркас с нуля. `files/` — это заглушки-скелеты (health-роут, тест), от
которых отталкивается реализация.

## Env-boot норма: `commands.bootstrap` (v1.40.0, обязательно)

Каждый `STARTER.json` **обязан** объявлять `commands.bootstrap` — одну команду,
поднимающую окружение с холода (чистый клон → установленные зависимости). Это
порт «запускаемого окружения» из исследования Anthropic по long-running агентам:
свежая сессия должна суметь запустить проект, зная только содержимое репо.

Правила:

- `bootstrap` идемпотентен и не требует интерактива;
- `/kickstart` Phase 3 обязан оставить команду рабочей — Initialization
  Acceptance Checklist требует её успешный прогон с чистого клона;
- если проект вводит свой эквивалент (`make setup`, `just bootstrap`) —
  синхронизируй `commands.bootstrap` с ним, а не дублируй логику;
- отдельного механизма env-boot в методологии нет сознательно: норма живёт в
  стартерах, проверка — в чеклисте `/kickstart`.

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
