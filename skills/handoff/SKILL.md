---
name: handoff
description: 'Write a compact HANDOFF.md context packet to transfer work from one session/agent to the next when there is no return path — compaction, delegation, AFK run, or recovery. Same format as the /session-save continuity document plus a transfer section. Distinct from /session-save (milestone save).'
argument-hint: project path plus handoff reason (compaction / delegation / AFK / recovery)
license: MIT
allowed-tools: Read Write Edit Glob Grep Bash
context: fork
metadata:
  effort: low
  side_effect: memory-write
  explicit_invocation: false
  author: HiH-DimaN
  version: 1.110.0
  category: workflow
  tags: [handoff, context, delegation, recovery, memory]
---

# Handoff

## Trigger phrases

- хендофф, сделай хендофф, передай контекст
- передача сессии, контекст для передачи, пакет контекста
- handoff, make a handoff, hand off
- transfer context, session handoff, context packet

## Recommended model

**Sonnet** — компактный пакет из уже принятых решений и состояния репозитория: структурированная суммаризация, а
не глубокое рассуждение. Haiku допустим для совсем коротких передач.

## Instructions

Передай **actionable** контекст следующему актору (сессии, роли, агенту, AFK-прогону), когда обратного пути нет.

> **`/handoff` ≠ `/session-save`.** `/session-save` — milestone save: документ темы для будущего «я».
> `/handoff` — пакет для **другого** актора перед его стартом. Веха завершена и следующего актора нет —
> это `/session-save`.

### Когда вызывать

- Планирующая сессия передает работу реализующей; работа уходит другому агенту, роли или AFK-прогону.
- Долгая сессия вот-вот компактится или рестартует; восстановление после неоднозначного гейта.
- **Порог контекста — 60%.** Задача по оценке больше 60% окна — заложи передачу с начала (durable-артефакты по
  ходу); израсходовано ~60% и конца не видно — пиши пакет **сейчас**: после авто-компакции писать его уже не из чего.

### Step 1: Собери состояние (только чтение)

- `git log --oneline -10` и `git status --short` — что закоммичено, есть ли WIP.
- Документ темы `.itd-memory/continuity/<тема>.md` (если есть) и durable-артефакты: `STATE.json`, `GOAL.json`,
  `.itd/SCOPE_LOCK.md`, `.itd/FORBIDDEN_CHANGES.md`, `.itd/DECISIONS.md`, `BACKLOG.md` — что есть.
- Есть `.itd-memory/GOAL.json` — строку состояния цели дает **репортер харнеса**, не пересказ (цифры не меняй):

  ```bash
  GT="skills/goal/scripts"; [ -f "$GT/itd_goal_report.py" ] || GT="$HOME/.claude/skills/goal/scripts"
  SHD="skills/_shared"; [ -f "$SHD/itd_py.sh" ] || SHD="$HOME/.claude/skills/_shared"
  sh "$SHD/itd_py.sh" "$GT/itd_goal_report.py" --goal .itd-memory/GOAL.json
  ```

### Step 2: Обнови документ темы

Тот же документ и тот же формат, что у `/session-save` (frontmatter `topic/status/updated/branch/unit`, затем
«Следующее действие», «Состояние», «Решения», «Проверки», «Блокеры»): перезапиши
`.itd-memory/continuity/<тема>.md`. Текущее состояние живет в одном месте, пакет его не подменяет.

### Step 3: Напиши `HANDOFF.md`

`HANDOFF.md` в корне проекта = содержимое документа темы + раздел передачи:

```markdown
## Передача
- From → To: <роль или сессия> → <роль, сессия или агент>
- Причина: компакция | делегирование | AFK | восстановление | релиз
- Входы: [[STATE]], [[BUILD_PLAN]], `.itd/SCOPE_LOCK.md` — что прочитать, чтобы продолжить
- Зоны записи: <что можно менять>; запреты: <что трогать нельзя>
- Проверка: `<команды, которые подтверждают, что все работает>`

> [!warning] <риски: что может пойти не так>
```

Следующее действие в пакете — то же `> [!todo]`, что в документе: одна точная команда или шаг, с которого свежий
актор начинает «с холода». Финальные решения — без пересказа обсуждения; ссылки на durable-артефакты
(`[[STATE]]`), а не на историю чата; секреты — именем переменной, не значением.

### Где живёт пакет

`HANDOFF.md` — локальный пакет рабочего дерева, а не запись истории. Файл внутри коммита не может записать ревью
этого же коммита, поэтому закоммиченный пакет всегда на шаг отстаёт от своего кандидата, и независимое ревью
находит в нём устаревший чекпоинт. Правило:

- пакет не входит в отревьюенный дифф: не перечисляй его в Allowed Change Areas SCOPE_LOCK и не добавляй в коммит,
  даже через `git add -f`;
- в проекте, где пакет ещё отслеживается, предложи владельцу строку `/HANDOFF.md` в `.gitignore` и
  `git rm --cached HANDOFF.md` (локальный файл остаётся); если владелец отказался — не стейдж правки пакета
  (`git restore --staged HANDOFF.md`, без `git commit -a`);
- получатель в другом чекауте (worktree, свежий клон, облачный или AFK-агент) не видит локальный пакет: передай
  путь или содержимое явно в промпт или задачу, не коммитом;
- durable-решения — в `.itd/DECISIONS.md`, текущее состояние — в документе темы; пакет на них ссылается.

### Step 4: Обнови срез состояния

`.itd-memory/STATE.json` (канон для Claude Code и Codex; схема `docs/templates/itd-memory/STATE.json`) — текущий
узел, статус, ссылка на `HANDOFF.md`. Долгая цель `/goal` — статусы юнитов в `.itd-memory/GOAL.json`, чтобы
получатель продолжил с первого не-verified юнита. Glance-вью — инструментом из установки (best-effort; INSTALL-OWNED-1,
интерпретатор выбирает `itd_py.sh`):

```bash
T="skills/_shared"; for d in "$HOME/.claude/skills/_shared" "${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT:-/nonexistent}}/skills/_shared"; do [ -f "$d/itd_tool.sh" ] && T="$d"; done
[ "$T" = skills/_shared ] && C=$(ls -d "$HOME"/.codex/plugins/cache/*/idea-to-deploy/*/skills/_shared 2>/dev/null | awk -F/ '{print $(NF-2), $0}' | sort -k1,1V | tail -1 | cut -d" " -f2-) && [ -f "${C:-/}/itd_tool.sh" ] && T="$C"
sh "$T/itd_tool.sh" itd_progress.py 2>/dev/null || true  # win-ok: itd_py.sh выбирает интерпретатор сам
```

Нет установки или интерпретатора — шаг тихо пропускается. Публикация в Obsidian-vault — `/obsidian-export`.

## Examples

### Example 1: Передача перед компакцией (planning → implementation)
User: «Сделай хендофф: сессия компактится. Передай контекст по auth.»

Actions:
1. `git log`/`git status` — login/register закоммичены, refresh — WIP (red-тест).
2. Обновляет `continuity/auth-refresh.md`: следующее действие `> [!todo]` запусти red-тест refresh, затем
   реализуй эндпоинт; проверки — `pytest tests/test_auth.py` 12 passed, 1 failed (red); решения — python-jose, Redis.
3. `HANDOFF.md` = документ + «Передача»: From planner → To implementer, причина — компакция, входы `[[STATE]]`,
   `[[BUILD_PLAN]]`, зоны записи `src/auth/**`, `> [!warning]` нужен `STRIPE_KEY` от заказчика. Секретов нет.

### Example 2: Делегирование агенту на AFK-прогон
User: «Передай контекст агенту, он продолжит ночью.»

Actions:
1. Пакет самодостаточен — без опоры на этот чат; все входы перечислены.
2. Агент работает в другом чекауте — путь или текст `HANDOFF.md` идет прямо в его задачу.
3. Первое действие однозначно — свежий агент начинает «с холода».

### Example 3: Восстановление после проваленного гейта
User: «`/review` упал, передай контекст на восстановление.»

Actions:
1. В «Проверках» — какой гейт упал и почему (цитата вердикта, не пересказ).
2. В «Блокерах» — что чинить; в следующем действии — конкретный фикс-шаг; зоны записи — затронутые файлы.

## Self-validation

- [ ] Документ темы обновлен; `HANDOFF.md` = документ + «Передача» (From → To, причина, входы, зоны записи и
      запреты, команды проверки, `> [!warning]` риски).
- [ ] Следующее действие — одна конкретная команда или шаг в `> [!todo]`.
- [ ] Нет секретов; ссылки на durable-артефакты (`[[STATE]]`), а не на историю чата.
- [ ] `STATE.json` обновлен; `GOAL.json` актуален, если ведется `/goal`.

## Troubleshooting

### Пользователь на самом деле хочет сохранить веху
Следующего актора нет, а работа завершена — это `/session-save`. Скажи: «Похоже на завершение вехи — используй
`/session-save`. `/handoff` нужен для передачи перед стартом следующего актора.»

### Нет durable-артефактов
Собери состояние из git-истории и кода, опиши явно и пометь отсутствующие артефакты. Не выдумывай решений.

### Слишком длинный пакет
Документ темы не длиннее 60 строк; «Передача» — 5-8 строк. Детали — ссылками на артефакты, не копипастой.

### Риск утечки секретов
Никогда не вставляй ключи, токены, пароли: имя переменной и где ее взять («нужен `STRIPE_KEY` от заказчика»).

## Rules

- **Не храни секреты** в `HANDOFF.md`.
- **Тот же формат**, что документ темы `/session-save`, плюс «Передача»; текущее состояние — в документе темы.
- **Только финальные решения** — без пересказа обсуждения.
- **Durable-ссылки, не чат** — `[[STATE]]`, а не «как обсуждали выше».
- **Первое действие однозначно** — одна команда или шаг.
- **`/handoff` для передачи, `/session-save` для вехи** — не путай.
- **Match the user's language** для всего вывода.
