---
name: mcp-docs
description: 'Fresh library and framework documentation lookup through MCP documentation providers such as Context7. Read-only — resolves a library ID, asks a narrow implementation question, records source + decision. Use when implementation depends on current APIs, SDK behavior, framework conventions, setup, or migration details.'
argument-hint: library, framework, API, version, error, or implementation question
license: MIT
allowed-tools: Read Glob Grep
context: fork
metadata:
  effort: medium
  side_effect: read-only
  explicit_invocation: false
  author: HiH-DimaN
  version: 1.21.0
  category: research
  tags: [mcp, context7, documentation, libraries, read-only]
---

# MCP Docs

## Trigger phrases

- актуальная документация, проверь доки библиотеки, свежие доки
- документация по библиотеке, актуальный api, context7
- mcp docs, check the docs, library documentation
- current api docs, look up docs, fetch documentation

## Recommended model

**Sonnet** — резолв library ID + узкий запрос к докам и фиксация решения. Это
точечный lookup, не глубокое рассуждение; Opus избыточен. Haiku допустим для
совсем простых проверок версии.

## Instructions

Используй этот скилл, когда устаревшее или угаданное знание библиотеки может
повлиять на реализацию. Подробный чеклист — в `references/mcp-docs-checklist.md`.

> Read-only по дизайну: скилл читает внешние доки и возвращает выжимку в stdout
> или в рабочие заметки/план/ревью. **Файлы проекта он не меняет.**

### Primary source: MCP (Context7)

1. **Резолвни library ID** для пакета/фреймворка/платформы.
2. **Задай узкий вопрос** под конкретную задачу реализации.
3. **Зафиксируй** source library ID и решение в заметках/плане/ревью-отчёте.

Если MCP-документация недоступна — fallback на официальную документацию проекта,
с явной пометкой, что MCP-источник был недоступен.

### Использовать ПЕРЕД

- Добавлением/апгрейдом зависимостей.
- Интеграцией против SDK, auth-провайдеров, платёжных API, деплой-платформ,
  UI-фреймворков, ORM, очередей, browser API.
- Починкой сбоев от version drift.
- Выбором фреймворк-специфичных конвенций в `/bugfix`, `/refactor`, `/infra`,
  `/deploy`, `/deps-audit`, `/harden`.

### Вывод

```text
DOC SOURCE:
VERSION OR LIBRARY ID:
DECISION:
IMPLEMENTATION IMPACT:
FOLLOW-UP RISK:
```

## Examples

### Example 1: Свежие доки SDK перед интеграцией
User: «Как сейчас инициализируется клиент в новой мажорной версии SDK?»

Actions:
1. Резолвит library ID, задаёт узкий вопрос про инициализацию в новой версии.
2. Возвращает форму вывода: DOC SOURCE (Context7), VERSION/LIBRARY ID, DECISION
   (новый паттерн init), IMPLEMENTATION IMPACT, FOLLOW-UP RISK (deprecated старый API).
3. Фиксирует источник и решение в заметках. Файлы не пишет.

### Example 2: MCP недоступен (fallback)
User: «Проверь доки библиотеки X», но Context7 недоступен.

Actions:
1. Fallback на официальную документацию проекта.
2. Явно помечает: «MCP-источник был недоступен, использована официальная дока».
3. Тот же output shape, с пометкой источника.

### Example 3: Конфликт доков и конвенции репо
User: «Доки советуют паттерн A, но у нас везде B — что делать?»

Actions:
1. Объясняет конфликт A vs B.
2. Предпочитает конвенцию репозитория (B), если она не сломана/не deprecated.
3. Если B deprecated — рекомендует миграцию на A с указанием follow-up risk.

## Self-validation

Перед выводом убедись:
- [ ] Library ID резолвнут (или указано: MCP недоступен → fallback).
- [ ] Запрос узкий, под конкретную задачу.
- [ ] Source library ID + решение зафиксированы в заметках/плане/ревью.
- [ ] Секреты/проприетарный код не отправлены наружу.
- [ ] Конфликт «доки vs конвенция репо» (если есть) разобран.
- [ ] Файлы проекта не изменены.

## Troubleshooting

### MCP/Context7 недоступен
Fallback на официальную документацию проекта и явно укажи, что MCP был
недоступен. Не угадывай API по памяти.

### Доки конфликтуют с конвенциями репозитория
Объясни конфликт, предпочти конвенцию репо — если она не сломана и не deprecated.
Если deprecated — предложи миграцию с пометкой follow-up risk.

### Крошечный локальный фикс, поведение уже доказано
Не блокируй фикс ради lookup, если поведение API уже подтверждено тестами или
кодом. `/mcp-docs` — для случаев реального риска version drift.

### Запрос слишком широкий
Сузь до конкретного вопроса задачи — широкий дамп доков шумит и тратит контекст.

## Rules

- **Read-only** — не меняет файлы проекта.
- **Не слать секреты/проприетарный код/креды** в инструменты документации.
- **Узкие запросы** — ровно под задачу.
- **Официальные/высокорепутационные источники** в приоритете.
- **Конвенция репо важнее доков**, если она не сломана/не deprecated.
- **Не блокируй мелкие фиксы**, если поведение API уже доказано тестами/кодом.
- **Match the user's language** для всего вывода.
