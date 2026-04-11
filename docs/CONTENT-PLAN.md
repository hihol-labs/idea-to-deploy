# Контент-план продвижения idea-to-deploy

> Дата создания: 2026-04-09
> Цель: максимальный охват в dev-сообществе → GitHub stars → личный бренд → монетизация через экспертизу

---

## Часть 0: Размещение в маркетплейсах (приоритет №1)

Это не контент, а дистрибуция — даёт установки без усилий на контент.

### 0.1. Anthropic Official Directory (claude-plugins-official)

| Параметр | Значение |
|---|---|
| **Что** | Подача заявки в официальный каталог Anthropic |
| **Как** | Форма подачи: [clau.de/plugin-directory-submission](https://clau.de/plugin-directory-submission) или через Console: `platform.claude.com/plugins/submit` |
| **Требования** | Валидный `.claude-plugin/marketplace.json`, качество кода, безопасность |
| **Бейдж** | После ревью возможен статус "Anthropic Verified" |
| **Приоритет** | КРИТИЧЕСКИЙ — это главный канал обнаружения плагинов |
| **Срок** | Подать в течение 1 недели |

**Действия:**
1. Проверить/создать `.claude-plugin/marketplace.json` по [официальной схеме](https://github.com/anthropics/claude-plugins-official)
2. Заполнить форму подачи
3. Подготовить описание на английском (marketplace — англоязычный)
4. После одобрения — упомянуть бейдж во всех материалах

### 0.2. Community Marketplaces

| Маркетплейс | URL | Как попасть |
|---|---|---|
| **Claude Marketplaces** | [claudemarketplaces.com](https://claudemarketplaces.com/) | Автоматический crawler — нужен валидный `marketplace.json` |
| **Claude Plugin Hub** | [claudepluginhub.com](https://www.claudepluginhub.com) | Подача через сайт |
| **Claude Plugins Registry** | [claude-plugins.dev](https://claude-plugins.dev/) | Индексация публичных плагинов |
| **Build with Claude** | [buildwithclaude.com](https://buildwithclaude.com/) | Подача через форму |
| **AI Tool Marketplace** | [aitmpl.com/plugins](https://www.aitmpl.com/plugins/) | Каталог плагинов |
| **awesome-claude-plugins** | [GitHub](https://github.com/quemsah/awesome-claude-plugins) | PR в репозиторий |

**Действия:**
1. Подать во все 6 маркетплейсов в течение 2 недель
2. Отслеживать статус и количество установок

---

## Часть 1: Каналы продвижения

### 1.1. GitHub (базовый канал)

| Параметр | Значение |
|---|---|
| **Тип контента** | README, releases, discussions, issues, wiki |
| **Частота** | Релиз каждые 1-2 недели, discussions — по мере поступления |
| **Цель** | Звёзды, форки, контрибьюторы |
| **KPI** | 100 stars за 1 месяц, 500 за 3 месяца |

**Действия:**
- [ ] Добавить GIF-демо в README (самое важное для конверсии)
- [ ] Настроить GitHub Topics: `claude-code`, `ai-coding`, `developer-tools`, `claude-plugin`, `methodology`
- [ ] Создать Discussion-категории: Show & Tell, Ideas, Q&A
- [ ] Добавить "Star History" бейдж
- [ ] Публиковать Release Notes с подробным описанием каждой фичи

---

### 1.2. Twitter/X (основной канал роста)

| Параметр | Значение |
|---|---|
| **Тип контента** | Треды, короткие видео, мемы, цитаты, скриншоты |
| **Частота** | 4-5 постов в неделю |
| **Хештеги** | #ClaudeCode #AI #DevTools #OpenSource #CodingWithAI |
| **Цель** | Аудитория 1000+ подписчиков за 3 месяца |

**Формат постов:**
1. **Треды (2 в неделю)** — обучающие, с демо и скриншотами
2. **Короткие посты (2-3 в неделю)** — tips, цитаты, мемы про AI-кодинг
3. **Видео-скринкасты (1 в неделю)** — 30-60 сек демо одного скилла

---

### 1.3. Dev.to (длинный контент, англоязычный)

| Параметр | Значение |
|---|---|
| **Тип контента** | Технические статьи, туториалы, кейсы |
| **Частота** | 1 статья в неделю |
| **Теги** | #showdev, #ai, #productivity, #claude |
| **Цель** | Топ постов недели, стабильный трафик на GitHub |

---

### 1.4. Habr (русскоязычная аудитория)

| Параметр | Значение |
|---|---|
| **Тип контента** | Глубокие технические статьи, кейсы, обзоры |
| **Частота** | 2 статьи в месяц |
| **Хабы** | Программирование, Open Source, AI, DevOps |
| **Цель** | Рейтинг 10+, попадание в "Лучшее" |

---

### 1.5. Reddit

| Параметр | Значение |
|---|---|
| **Сабреддиты** | r/ClaudeAI, r/SideProject, r/webdev, r/programming, r/MachineLearning, r/LocalLLaMA |
| **Тип контента** | Showcase-посты, ответы на вопросы, "I built this" |
| **Частота** | 2-3 поста в месяц + ежедневные комментарии |
| **Цель** | Трафик + SEO (Reddit индексируется Google) |

---

### 1.6. Hacker News

| Параметр | Значение |
|---|---|
| **Тип контента** | "Show HN" посты |
| **Частота** | 2-3 раза за весь период (нельзя спамить) |
| **Цель** | Один пост на главной = 5000-10000 визитов за сутки |

---

### 1.7. YouTube

| Параметр | Значение |
|---|---|
| **Тип контента** | Скринкасты, туториалы, обзоры, демо |
| **Частота** | 1 видео в 2 недели |
| **Длительность** | 5-15 мин для туториалов, 1-3 мин для shorts |
| **Цель** | Evergreen-контент, поиск по "Claude Code tutorial" |

---

### 1.8. LinkedIn

| Параметр | Значение |
|---|---|
| **Тип контента** | Посты о продуктивности, AI в разработке, истории создания |
| **Частота** | 2-3 поста в неделю |
| **Цель** | B2B-аудитория, CTOs, тимлиды → консалтинг |

---

### 1.9. Product Hunt

| Параметр | Значение |
|---|---|
| **Тип контента** | Запуск продукта |
| **Частота** | 1 запуск (тщательно подготовленный) |
| **Категория** | [AI Coding Agents](https://www.producthunt.com/categories/ai-coding-agents), Developer Tools |
| **Цель** | Топ-5 дня → массовый трафик |

---

### 1.10. Telegram

| Параметр | Значение |
|---|---|
| **Тип контента** | Канал с tips, новостями, обсуждениями |
| **Частота** | 3-4 поста в неделю |
| **Цель** | Русскоязычное комьюнити, лояльная аудитория |

---

### 1.11. Discord

| Параметр | Значение |
|---|---|
| **Тип контента** | Канал в Claude Code / AI-разработка серверах + свой сервер |
| **Частота** | Ежедневное присутствие |
| **Цель** | Комьюнити, фидбек, контрибьюторы |

---

## Часть 2: Контент-план по неделям (первые 8 недель)

### Неделя 1: Запуск

| # | Канал | Тип | Заголовок | Описание |
|---|---|---|---|---|
| 1 | GitHub | README | **Обновление README с GIF-демо** | Записать терминальное демо `/kickstart` → готовый проект за 1 команду |
| 2 | Anthropic | Форма | **Подача в Official Directory** | marketplace.json + описание + скриншоты |
| 3 | Twitter/X | Тред | **"I built a methodology that turns Claude Code into a senior developer"** | 7-10 твитов: проблема → решение → демо → ссылка. Тегнуть @AnthropicAI |
| 4 | Reddit | Пост | **"[Show] idea-to-deploy: 17 skills that turn Claude Code into a professional dev pipeline"** | r/ClaudeAI + r/SideProject |
| 5 | Community | Формы | **Подача во все community-маркетплейсы** | claudemarketplaces, pluginhub, и т.д. |

### Неделя 2: Обучающий контент

| # | Канал | Тип | Заголовок | Описание |
|---|---|---|---|---|
| 6 | Dev.to | Статья | **"How I made Claude Code 10x more reliable with a plugin methodology"** | Проблема хаотичной генерации → pipeline → результаты. Тег #showdev |
| 7 | Twitter/X | Тред | **"5 things Claude Code does WRONG without instructions (and how to fix them)"** | Конкретные примеры: пропускает тесты, ломает код, не документирует |
| 8 | YouTube | Видео | **"Claude Code + idea-to-deploy: Full Demo (Idea to Deploy in 15 min)"** | Скринкаст: от идеи до работающего проекта |
| 9 | LinkedIn | Пост | **"Почему AI-ассистенты без методологии — это строитель без чертежа"** | Бизнес-угол: стоимость ошибок vs стоимость процесса |
| 10 | Habr | Статья | **"Как я заставил Claude Code работать по методологии: 17 скиллов от идеи до продакшена"** | Глубокий технический разбор с примерами кода |

### Неделя 3: Social proof

| # | Канал | Тип | Заголовок | Описание |
|---|---|---|---|---|
| 11 | Twitter/X | Тред | **"From 0 to 500 lines of tested code in 10 minutes with Claude Code"** | Реальный кейс: что было → `/kickstart` → результат |
| 12 | Dev.to | Статья | **"Building a Full-Stack App with Claude Code in 30 Minutes (Step-by-Step)"** | Пошаговый туториал с idea-to-deploy |
| 13 | Reddit | Пост | **"I've been using Claude Code with a strict methodology for 2 months. Here's what changed."** | r/programming — личный опыт |
| 14 | Telegram | Пост | **"Запустил методологию для Claude Code — делюсь результатами"** | Анонс канала + ссылка на GitHub |
| 15 | Twitter/X | Видео | **30-сек скринкаст: `/bugfix` находит и чинит баг** | Вау-эффект, короткий формат |

### Неделя 4: Углубление

| # | Канал | Тип | Заголовок | Описание |
|---|---|---|---|---|
| 16 | Habr | Статья | **"Open Source как маркетинг: зачем я отдал бесплатно инструмент, который экономит часы"** | Meta-статья: стратегия продвижения через open source |
| 17 | YouTube | Видео | **"5 Claude Code Skills Every Developer Needs"** | Обзор топ-5 скиллов: kickstart, bugfix, test, review, session-save |
| 18 | Dev.to | Статья | **"Why Your AI Coding Assistant Needs a Methodology, Not Just Prompts"** | Философская статья: prompts vs pipeline |
| 19 | Twitter/X | Тред | **"The secret to making AI write GOOD code: treat it like a junior developer"** | Аналогия: онбординг джуна = настройка AI |
| 20 | LinkedIn | Пост | **"AI заменит разработчиков? Нет. Но разработчик с AI-методологией заменит того, кто без неё"** | Провокационный тезис → раскрытие |

### Неделя 5: Show HN + Product Hunt подготовка

| # | Канал | Тип | Заголовок | Описание |
|---|---|---|---|---|
| 21 | HN | Show HN | **"Show HN: idea-to-deploy – 17-skill methodology plugin for Claude Code"** | Краткое описание + ссылка. Быть готовым отвечать 24 часа |
| 22 | Twitter/X | Тред | **"We hit [X] GitHub stars in 4 weeks. Here's exactly what we did"** | Прозрачность процесса продвижения |
| 23 | Dev.to | Статья | **"How to Build Your Own Claude Code Plugin: A Complete Guide"** | Туториал по созданию плагинов — привлекает контрибьюторов |
| 24 | YouTube | Видео | **"Creating a Claude Code Plugin from Scratch"** | Видео-версия туториала |
| 25 | Telegram | Серия | **"Скилл недели: /review — как автоматизировать code review"** | Еженедельная рубрика |

### Неделя 6: Product Hunt Launch

| # | Канал | Тип | Заголовок | Описание |
|---|---|---|---|---|
| 26 | Product Hunt | Запуск | **"idea-to-deploy — Turn Claude Code into a senior developer with 17 skills"** | Подготовить: логотип, скриншоты, GIF, первый комментарий maker'а |
| 27 | Twitter/X | Пост | **"We're live on Product Hunt! 🚀"** | Кросс-промо, просьба поддержать |
| 28 | LinkedIn | Пост | **"Запустились на Product Hunt"** | Кросс-промо для B2B аудитории |
| 29 | Reddit | Пост | **"Just launched on Product Hunt: idea-to-deploy"** | r/SideProject |
| 30 | Telegram | Пост | **"Мы на Product Hunt — поддержите!"** | Мобилизация русскоязычного комьюнити |

### Неделя 7: Экспертный контент

| # | Канал | Тип | Заголовок | Описание |
|---|---|---|---|---|
| 31 | Habr | Статья | **"Архитектура Claude Code плагина: как устроены скиллы, агенты и хуки"** | Технический deep-dive для продвинутых |
| 32 | Dev.to | Статья | **"AI-Driven Development: A Methodology That Actually Works"** | Обобщающая статья о подходе |
| 33 | Twitter/X | Тред | **"Unpopular opinion: AI coding assistants without guardrails are more dangerous than helpful"** | Провокация → раскрытие → решение |
| 34 | YouTube | Видео | **"Claude Code vs Cursor vs Copilot: Why methodology matters more than the tool"** | Сравнительный обзор — привлекает трафик по запросам |
| 35 | LinkedIn | Пост | **"3 урока, которые я вынес, создавая open source инструмент для AI-разработки"** | Личная история |

### Неделя 8: Комьюнити и масштабирование

| # | Канал | Тип | Заголовок | Описание |
|---|---|---|---|---|
| 36 | Discord | Сервер | **Запуск Discord-сервера idea-to-deploy** | Каналы: general, showcase, feature-requests, contributing |
| 37 | Dev.to | Статья | **"Contributing to idea-to-deploy: How to Write Your First Claude Code Skill"** | Привлечение контрибьюторов |
| 38 | Twitter/X | Тред | **"Open call: help us build the best Claude Code plugin"** | Призыв к участию |
| 39 | Habr | Статья | **"Результаты 2 месяцев: как open source проект набрал [X] звёзд"** | Ретроспектива с цифрами |
| 40 | YouTube | Видео | **"What's Next for idea-to-deploy: Roadmap 2026"** | Дорожная карта → вовлечение |

---

## Часть 3: Контент по каждому скиллу (длинный хвост)

Каждый из 18 скиллов = отдельная единица контента. Формат: Twitter тред + Dev.to статья + YouTube short.

| Скилл | Twitter-тред | Dev.to статья | YouTube short |
|---|---|---|---|
| `/project` | "One command to start any project right" | "Smart Project Router: How /project Picks the Right Workflow" | 60 сек демо |
| `/kickstart` | "Idea to deployed app in one command" | "From Idea to Production with /kickstart" | Полный цикл за 60 сек |
| `/blueprint` | "Plan before you code: /blueprint generates 6 docs" | "Project Planning with AI: The /blueprint Approach" | Генерация 6 документов |
| `/guide` | "Turn docs into step-by-step Claude prompts" | "Auto-generating Claude Code Guides" | Демо guide |
| `/bugfix` | "AI debugger that actually finds root causes" | "Systematic Debugging with Claude Code" | Баг → фикс за 30 сек |
| `/test` | "100% test coverage in 2 minutes" | "AI-Generated Tests That Actually Catch Bugs" | Генерация тестов |
| `/review` | "Automated code review: 24 checks in seconds" | "Building a Code Review Pipeline with AI" | Review результат |
| `/refactor` | "Refactor without breaking: AI knows the context" | "Safe Refactoring with Claude Code" | Before/after |
| `/explain` | "Understand any codebase in minutes" | "Code Explanation with ASCII Diagrams" | Объяснение сложного кода |
| `/doc` | "Documentation that writes itself" | "AI-Powered Documentation Generation" | README за 30 сек |
| `/perf` | "Find bottlenecks AI style" | "Performance Analysis with Claude Code" | Профилирование |
| `/security-audit` | "Security audit in 60 seconds" | "Automated Security Auditing" | Находка уязвимости |
| `/deps-audit` | "Are your dependencies safe?" | "Dependency Auditing with AI" | Проверка зависимостей |
| `/harden` | "Production hardening checklist" | "Hardening Your App for Production" | Чеклист |
| `/infra` | "Infrastructure as Code, generated" | "AI-Generated Infrastructure" | Terraform/Docker |
| `/migrate` | "Safe database migrations" | "Database Migrations Without Fear" | Миграция |
| `/session-save` | "Never lose context between sessions" | "Session Persistence for AI Development" | Сохранение контекста |

---

## Часть 4: Сводная таблица каналов

| Канал | Язык | Частота | Тип контента | Приоритет |
|---|---|---|---|---|
| **Anthropic Marketplace** | EN | Разовая подача | Листинг плагина | P0 |
| **Community Marketplaces (6шт)** | EN | Разовая подача | Листинги | P0 |
| **GitHub** | EN/RU | Постоянно | README, Releases, Discussions | P0 |
| **Twitter/X** | EN | 4-5/неделю | Треды, видео, скриншоты | P1 |
| **Dev.to** | EN | 1/неделю | Статьи, туториалы | P1 |
| **Habr** | RU | 2/месяц | Глубокие статьи | P1 |
| **Reddit** | EN | 2-3/месяц | Showcase, обсуждения | P1 |
| **YouTube** | EN | 1/2 недели | Скринкасты, туториалы | P2 |
| **LinkedIn** | RU/EN | 2-3/неделю | Бизнес-посты | P2 |
| **Hacker News** | EN | 2-3 за 8 нед. | Show HN | P2 |
| **Product Hunt** | EN | 1 запуск | Product launch | P2 |
| **Telegram** | RU | 3-4/неделю | Tips, новости | P2 |
| **Discord** | EN/RU | Ежедневно | Комьюнити | P3 |

---

## Часть 5: Метрики успеха

| Метрика | 1 месяц | 3 месяца | 6 месяцев |
|---|---|---|---|
| GitHub Stars | 100 | 500 | 2000 |
| GitHub Forks | 15 | 50 | 200 |
| Twitter подписчики | 200 | 1000 | 3000 |
| Dev.to подписчики | 50 | 300 | 1000 |
| Установки плагина | 50 | 300 | 1500 |
| Контрибьюторы | 3 | 10 | 25 |
| Habr рейтинг | +10 | +30 | +50 |

---

## Часть 6: Подготовительные активности (до начала продвижения)

### Обязательно до старта:
1. **GIF/видео-демо** — записать 3 скринкаста (kickstart, bugfix, review)
2. **marketplace.json** — подготовить и подать в Anthropic
3. **Логотип** — создать для Product Hunt и соцсетей
4. **Twitter/X аккаунт** — создать или подготовить профиль
5. **Open Graph изображения** — для каждой статьи
6. **Контрибьюторский гайд** — CONTRIBUTING.md уже есть, проверить актуальность

### Инструменты для контента:
- **Скринкасты**: asciinema (терминал) + OBS (экран)
- **GIF**: gifski или ScreenToGif
- **Изображения**: Canva (у тебя есть доступ)
- **Планирование постов**: Buffer или Typefully (для Twitter тредов)

---

## Часть 7: Долгосрочная монетизация (после 500+ stars)

1. **GitHub Sponsors** — подключить, когда есть аудитория
2. **Консалтинг** — "Настрою AI-методологию для вашей команды" ($150-300/час)
3. **Курс** — "AI-Driven Development Masterclass" (платный, Udemy/Stepik)
4. **Enterprise-версия** — приватные скиллы + интеграции + поддержка
5. **Выступления** — конференции (TeamLead Conf, HolyJS, PyCon) = авторитет + контакты
