---
name: market-scan
description: 'Fresh public market and community signal scan for product discovery, validation, ICP, competitor, launch, and roadmap decisions. Pulls recent (~30-day) social/community signals via the last30days engine and normalizes them into artifacts. Distinct from /discover (full discovery phase).'
argument-hint: idea, problem, segment, competitor, audience, or launch question
license: MIT
allowed-tools: Read Write Edit Glob Grep Bash
context: fork
metadata:
  effort: high
  side_effect: local-write
  explicit_invocation: false
  author: HiH-DimaN
  version: 1.21.0
  category: research
  tags: [market, discovery, validation, last30days, social-signals]
---

# Market Scan

## Trigger phrases

- скан рынка, свежие сигналы рынка, что говорят о продукте
- проверь нишу, рыночные сигналы, сигналы сообщества
- market scan, scan the market, fresh market signals
- community signals, validate my idea, competitor signals

## Recommended model

**Opus** — синтез разнородных публичных сигналов, отделение доказательств от
допущений и adversarial discovery требуют глубокого рассуждения. Sonnet годится
для узкого скана одного источника.

## Instructions

Делай скан **свежих публичных** рыночных и комьюнити-сигналов перед
product/strategy-решением. Предпочтительный движок — `last30days`
(`mvanhorn/last30days-skill`), если установлен. Подробный чеклист — в
`references/market-scan-checklist.md`.

> **`/market-scan` ≠ `/discover`.** `/discover` — полноценная discovery-фаза
> (TAM/SAM/SOM, персоны, MoSCoW/RICE → `DISCOVERY.md`). `/market-scan` —
> точечный скан свежих публичных сигналов (что обсуждают/на что жалуются за
> последние ~30 дней) и нормализация их в артефакты. Если нужен весь discovery —
> это `/discover`.

### Step 1: Прочитай существующие артефакты

`DISCOVERY.md`, `MARKET_BRIEF.md`, `LAUNCH_PLAN.md`, `BACKLOG.md`,
`STRATEGIC_PLAN.md` — не дублируй уже собранное.

### Step 2: Сделай тему public-safe

Преврати запрос в публично-безопасную тему: убери секреты, приватные данные
клиентов, внутренние метрики, проприетарные сниппеты. Это критично — тема уходит
во внешний инструмент.

### Step 3: Запусти исследование

- Если `last30days` установлен — вызови его по теме, используй синтезированные
  доказательства.
- Если недоступен — пометь скан `BLOCKED_EXTERNAL_TOOL`, выпиши точную тему для
  повтора после установки. **Не выдумывай** соц./рыночные доказательства.

### Step 4: Нормализуй и зафиксируй impact

Не вставляй сырой вывод инструмента целиком. Обнови `MARKET_BRIEF.md` (свежие
сигналы, топ-жалобы, альтернативы, adversarial discovery, ссылки), при
необходимости — `BACKLOG.md` / `LAUNCH_PLAN.md`. **Дописывай датированные**
доказательства, не затирай прежнее (если пользователь не попросил переписать).

### Step 5: Вывод

```text
TOPIC:
FRESH SIGNALS:
TOP COMPLAINTS:
ALTERNATIVES:
ADVERSARIAL DISCOVERY:
CONFIDENCE:
ARTIFACT IMPACT:
NEXT VALIDATION STEP:
```

Свежая соц-активность — сигнал, а не доказательство. Превращай её в next
validation step, а не сразу в build scope.

## Examples

### Example 1: Скан ниши перед расширением scope
User: «Сделай скан рынка по нише AI-ассистента записи для барбершопов.»

Actions:
1. Читает `DISCOVERY.md`/`MARKET_BRIEF.md`, если есть.
2. Делает тему public-safe, вызывает `last30days`.
3. Выдаёт форму вывода с топ-жалобами и альтернативами; показывает негативные
   сигналы. Дописывает датированный блок в `MARKET_BRIEF.md`. Формулирует next
   validation step (например, 5 интервью с владельцами барбершопов).

### Example 2: Внешний инструмент недоступен (degraded)
User: «Проверь нишу X», но `last30days` не установлен.

Actions:
1. Не выдумывает сигналы.
2. Помечает скан `BLOCKED_EXTERNAL_TOOL`, выписывает точную тему для повтора.
3. Предлагает установить `last30days` или дать публичные ссылки вручную.

### Example 3: Сигналы конкурента перед стратегией
User: «Что говорят о конкуренте Y и его последнем релизе?»

Actions:
1. Public-safe тема по конкуренту.
2. Скан свежих сигналов: жалобы пользователей, преимущества, gaps.
3. Adversarial discovery — где конкурент сильнее нас; honest negative signals.

## Self-validation

Перед выводом убедись:
- [ ] Существующие артефакты прочитаны до исследования.
- [ ] Тема public-safe (нет секретов/приватных данных).
- [ ] `last30days` использован ИЛИ скан помечен `BLOCKED_EXTERNAL_TOOL` (без выдумок).
- [ ] Показаны негативные сигналы / преимущества конкурентов.
- [ ] Доказательства отделены от допущений; источники процитированы.
- [ ] В доки дописаны датированные находки, прежнее не затёрто.
- [ ] Есть next validation step.

## Troubleshooting

### Пользователь хочет полную discovery-фазу
Это `/discover`, не `/market-scan`. Скажи: «Для полной discovery (TAM/SAM/SOM,
персоны, приоритизация) используй `/discover`. `/market-scan` — точечный скан
свежих публичных сигналов.»

### `last30days` не установлен
Не выдумывай данные. Пометь `BLOCKED_EXTERNAL_TOOL`, дай точную тему и предложи
установку (`mvanhorn/last30days-skill`) или ручные публичные ссылки.

### Только поддерживающие сигналы, нет негатива
Это red flag предвзятого скана. Специально ищи топ-жалобы, преимущества
конкурентов и uncomfortable signals — иначе валидация ложно-оптимистична.

### Риск утечки во внешний инструмент
Никогда не отправляй секреты, приватные данные клиентов, нерелизнутые детали или
проприетарный код. Сначала обезличь тему.

## Rules

- **Только публичные источники.**
- **Не слать секреты/приватные данные** во внешние research-инструменты.
- **Не выдумывать** доказательства — при недоступности инструмента `BLOCKED_EXTERNAL_TOOL`.
- **Цитируй источники**; отделяй доказательства от допущений.
- **Показывай негатив** — преимущества конкурентов и неудобные сигналы.
- **Сигнал ≠ доказательство** — конвертируй в валидационный эксперимент.
- **Датированный append**, не затирание чужого исследования.
- **Match the user's language** для всего вывода.
