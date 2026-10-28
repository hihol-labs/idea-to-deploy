---
name: session-save
description: 'Save session continuity — one document per workstream with the next action, current state, decisions, check results and blockers; history is appended separately. Runs at milestones and before irreversible steps; a parallel session cannot overwrite the same document.'
argument-hint: optional — topic slug or note; --close for verified session exit; --sync / --push-memory (ITD repository only)
license: MIT
allowed-tools: Read Write Edit Bash Glob Grep
metadata:
  effort: low
  side_effect: memory-write
  explicit_invocation: false
  author: HiH-DimaN
  version: 1.110.0
  category: workflow
  tags: [session, memory, context, persistence, continuity, parallel-sessions]
---

# Session Save

## Trigger phrases

These are the user phrases (Russian and English) that should auto-invoke this skill. They are kept here, not in the description, to avoid diluting the embedding-based matcher in the frontmatter. The hook `hooks/check-skills.sh` also uses this list — keep them in sync.

- сохрани контекст, сохрани сессию, запомни что делали
- итоги сессии, конец сессии, закончили работу
- на сегодня всё, заканчиваем работу
- save session, save context, end of session
- wrap up session, session summary
- любой сигнал завершения сессии

## Когда сохранять

Без явного запроса — на вехах и перед необратимым, а не после каждого подшага: веха (фича или фикс закоммичены и
тесты зелёные; юнит `/goal` verified; решение, меняющее план), шаг перед необратимым или внешним действием (деплой,
миграция, push/PR, удаление, отправка наружу) как точка возврата, конец сессии или просьба пользователя; ~60%
контекста при невидимом конце работы — `/handoff`. Не после каждого коммита, правки или прогона.

## Recommended model

**sonnet** — прочитать git и прежний документ, записать короткий файл. Глубокого анализа нет.

## Instructions

### Документ продолжения

Один документ на поток работы: `.itd-memory/continuity/<тема>.md`. Тема — короткий kebab-slug задачи
(`basler-oos`, `itd-plan`); ветка фичи — хорошая тема. Параллельные сессии ведут разные темы и друг другу не
мешают. Документ хранит только текущее и **перезаписывается целиком** при каждом сохранении. История — отдельно,
дозаписью в `.itd-memory/HISTORY.md`; в документе она не повторяется и с ним не конкурирует.

Формат (тот же у `/handoff`; разделы в этом порядке, документ не длиннее 60 строк):

```markdown
---
topic: <тема>
status: open
updated: <YYYY-MM-DDTHH:MMZ>
branch: <ветка> @ <короткий sha>
unit: <id юнита (статус)> | n/a
---

## Следующее действие
> [!todo] <один точный шаг: можно начать без догадок>

## Состояние
- <что верно сейчас: закоммичено, запушено, выкачено; что в процессе>

## Решения
- <решение> — <почему>

## Проверки
- `<команда>` -> <результат с числами>, <когда>

## Блокеры
- нет | <блокер> -> <кто или что снимает>
```
`status: done` — тема закрыта: следующее действие «нет», pre-flight ее больше не показывает.

### Step 1: Собери состояние

```bash
git status --short; git log --oneline -5; git branch --show-current
ls -t .itd-memory/continuity/ 2>/dev/null | head -5
```

Документ темы уже есть — прочитай его (Read) и обновляй, а не пиши с нуля. Нет `.itd-memory/` — создай
каноническую папку (канон на каждом хосте; приватная память хоста `~/.claude/projects/<hash>/memory/` не источник
и не цель, успех не зависит от этого private path):

```bash
git rev-parse --show-toplevel >/dev/null 2>&1 && MEM_DIR="$(git rev-parse --show-toplevel)/.itd-memory" || MEM_DIR="$PWD/.itd-memory"
mkdir -p "$MEM_DIR/continuity"
```

### Step 2: Запиши документ

Запиши `.itd-memory/continuity/<тема>.md` целиком по формату (Write; в Codex — apply_patch или shell). Конкретика
(«JWT refresh с ротацией, 8 тестов», а не «работал над auth»); решения — с «почему»; проверки — только прогоны этой
сессии, с числами, не прогнанное так и названо; секреты — именем переменной, не значением. Хук state-guard
отклоняет Write поверх документа, который другая сессия меняла меньше 10 минут назад: прочитай его и слей свое
Edit'ом или возьми другую тему.

### Step 3: Дозапиши историю

```bash
cat >> .itd-memory/HISTORY.md <<'EOF'

## <YYYY-MM-DD HH:MMZ> <тема> - <что сделано, одна строка>
- <коммиты/PR, решения, итог проверок: 1-4 строки>
EOF
```

Без следующих шагов: они только в документе. HISTORY.md только дописывается и при сохранении не перечитывается.

### Step 4: Durable-решения — в журнал

Есть `.itd/` и durable-решение (выбор подхода, отвергнутая альтернатива, договоренность, осознанный trade-off) —
допиши в конец `.itd/DECISIONS.md` запись `## YYYY-MM-DD: <решение>` (Почему / Отвергнуто / Ограничение / Ссылки);
отмена — новая запись со ссылкой. Ход работ туда не идет; нет durable-решений — шаг пропускается.

### Step 5: Сообщи пользователю

Путь документа, следующее действие, блокеры — одной-тремя строками.

### Флаг `--close`: явное закрытие сессии

На feature-ветке сначала запиши в «Состояние» режим ветки: PR | merge | keep | discard (`docs/templates/BRANCH_FINISH.md`;
по умолчанию keep, discard — только по явному подтверждению). Затем граница **`itd_hygiene.py close`** из установки
(INSTALL-OWNED-1); контракт — свой у проекта или `docs/` репо методологии (`skills/_shared/itd_contract_dir.py`):

```bash
T="skills/_shared"; for d in "$HOME/.claude/skills/_shared" "${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT:-/nonexistent}}/skills/_shared"; do [ -f "$d/itd_tool.sh" ] && T="$d"; done
[ "$T" = skills/_shared ] && C=$(ls -d "$HOME"/.codex/plugins/cache/*/idea-to-deploy/*/skills/_shared 2>/dev/null | awk -F/ '{print $(NF-2), $0}' | sort -k1,1V | tail -1 | cut -d" " -f2-) && [ -f "${C:-/}/itd_tool.sh" ] && T="$C"
CONTRACT="$(sh "$T/itd_py.sh" "$T/itd_contract_dir.py" SESSION_EXIT_CONTRACT.json)/SESSION_EXIT_CONTRACT.json"
sh "$T/itd_tool.sh" itd_hygiene.py close --root . --contract "$CONTRACT"
```

Исключение — только с непустой причиной от пользователя (`--close COMPLETION_BYPASS: <причина>` ->
`--completion-bypass-reason "<причина>"`; runner пишет его в `.itd-memory/events.jsonl`). Exit 0 — вся конъюнкция
контракта зеленая; любой сбой: **документ сохранен, сессия НЕ закрыта**, строки WHY+FIX — в «Блокеры».

### Флаги `--sync` и `--push-memory`: только репо ITD

Только по явному флагу от пользователя и только в репо методологии: верхнеуровневое `name` разобранного
`.claude-plugin/plugin.json` корня репо — `idea-to-deploy` (`itd_contract_dir.py` печатает `docs`); иначе ничего.
Строку `--sync` или блок `--push-memory` (бэкап в приватный `~/.claude/methodology-memory/`) запускай после первых
четырех строк:

```bash
R="$(git rev-parse --show-toplevel)"
T="skills/_shared"; for d in "$HOME/.claude/skills/_shared" "${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT:-/nonexistent}}/skills/_shared"; do [ -f "$d/itd_tool.sh" ] && T="$d"; done
[ "$T" = skills/_shared ] && C=$(ls -d "$HOME"/.codex/plugins/cache/*/idea-to-deploy/*/skills/_shared 2>/dev/null | awk -F/ '{print $(NF-2), $0}' | sort -k1,1V | tail -1 | cut -d" " -f2-) && [ -f "${C:-/}/itd_tool.sh" ] && T="$C"
ITD="$(sh "$T/itd_py.sh" "$T/itd_contract_dir.py" --root "$R")"
[ "$ITD" = docs ] && (cd "$R" && bash scripts/sync-to-active.sh)  # --sync
MM="$HOME/.claude/methodology-memory"  # --push-memory
if [ "$ITD" = docs ] && [ -d "$MM/.git" ]; then
  git -C "$MM" add -A
  git -C "$MM" diff --cached --quiet || git -C "$MM" commit -q -m "memory: session checkpoint $(date +%F)"
  git -C "$MM" push -q origin HEAD || echo "memory push failed - the commit stays local"
fi
```

Сбой сети не блокирует сохранение. Старые `session_*.md` и `MEMORY.md` — история только для чтения (хуки
показывают их, пока нет `continuity/`); `.active-session.lock` ведет хук state-guard. Их скилл не пишет.

## Examples

### Example 1: веха в продуктовом проекте
Фикс basler oos слит (PR #527, c0010c95), тесты 42/0. Один Bash (git + `continuity/`), Read и Write
`continuity/basler-oos.md` («Следующее действие: выкатить c0010c95 на бой», «Проверки: pytest tests/basler 42
passed»), дозапись HISTORY.md. DECISIONS не трогается — durable-решений не было.

### Example 2: перед необратимым шагом
Перед `/deploy`: в «Состоянии» — уходящий коммит, в «Следующем действии» — проверка health после деплоя. Точка
возврата зафиксирована до деплоя, а не после.

## Rules

1. Один документ на тему, перезапись целиком; история — только дозапись в HISTORY.md.
2. Следующее действие — одна строка, исполнимая без догадок; закрытая тема — `status: done`.
3. Числа проверок — только из прогонов этой сессии.
4. Сохранять на вехах и перед необратимым, не после каждого подшага.
5. `--sync` и `--push-memory` — только в репо ITD и только по явному флагу пользователя.
6. Секреты не пишутся.

## Self-validation

- [ ] Документ темы по формату: frontmatter и пять разделов по порядку, не длиннее 60 строк.
- [ ] Следующее действие — одна строка; блокеры — «нет» или с тем, кто снимает.
- [ ] HISTORY.md дописан, без следующих шагов.
- [ ] С `--close`: `itd_hygiene.py close` вернул 0, иначе сессия явно названа открытой.

## Troubleshooting

### Write отклонен: параллельная сессия
Ту же тему меняла другая сессия меньше 10 минут назад: прочитай документ и слей свое Edit'ом или возьми другую тему.
Write после двух отказов пройдет с предупреждением — только если чужое состояние уже учтено.

### Нет git или документ больше 60 строк
Без git — документ в `./.itd-memory/continuity/`, в «Состоянии» сказано, что данных git нет. Длинный документ
содержит историю: перенеси сделанное в HISTORY.md.
