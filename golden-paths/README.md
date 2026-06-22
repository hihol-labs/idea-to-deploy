# Golden Paths

Golden paths задают ожидаемое поведение idea-to-deploy по категориям продукта.
Они намеренно машиночитаемы, чтобы валидаторы (и будущие проверки) могли
сравнивать сгенерированные проекты с ожидаемыми маршрутом, стартером, артефактами
и гейтами.

Каждый `*.json` объявляет:

- **id** — идентификатор сценария;
- **prompt** — типичный запрос пользователя (на естественном языке);
- **productType** — тип продукта;
- **starter** — выбираемый стартер-пак (см. [`../starters/`](../starters/));
- **route** — ожидаемая цепочка скиллов (например `/project -> /kickstart`);
- **requiredArtifacts** — артефакты idea-to-deploy, которые должны появиться;
- **minimumGates** — минимальный набор гейтов качества.

## Маппинг гейтов на скиллы

Имена в `minimumGates` — это абстрактные гейты, каждый реализуется скиллом:

| Гейт | Скилл |
|---|---|
| `strategy` | `/strategy` (или `/discover` + `/blueprint`) |
| `architecture` | `/blueprint` → `PROJECT_ARCHITECTURE.md` |
| `tests` | `/test` |
| `review` | `/review` (фиксируется в `.rubric-status`) |
| `security` | `/security-audit` |
| `dependencies` | `/deps-audit` |
| `hardening` | `/harden` |

## Доступные golden paths

| id | productType | starter | route |
|---|---|---|---|
| `api-service-booking` | `api_service` | `api-fastapi` | `/project -> /kickstart` |
| `saas-subscriptions` | `saas` | `saas-fastapi-vue` | `/project -> /kickstart` |
| `messaging-bot-sales` | `messaging_bot` | `bot-aiogram` | `/project -> /kickstart` |
| `mini-app-loyalty` | `mini_app` | `mini-app-vue` | `/project -> /kickstart` |
| `landing-leadgen` | `landing_page` | `landing-vite` | `/project -> /kickstart` |

## Связь с route-snapshots

Golden paths дополняют trigger/route-проверки методологии:

- trigger-проверки (`hooks/check-skills.sh` + `tests/verify_triggers.py`)
  доказывают маршрутизацию по естественному языку;
- golden paths доказывают выбор стартера по типу продукта, требуемые артефакты и
  минимальные гейты.

Источник истины по артефактам — реальные выходы скиллов idea-to-deploy
(`/discover`, `/blueprint`, `/market-scan`) и контракты `.itd/`.
