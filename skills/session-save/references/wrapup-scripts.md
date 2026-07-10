# Wrap-up скрипты `/session-save` (Steps 4.6 / 4.7b / 4.9)

Исполняемые блоки, вынесенные из SKILL.md (progressive disclosure, v1.73.0):
правила шагов живут в SKILL.md, точные команды — здесь. Читай секцию перед
выполнением соответствующего шага.

## §4.6 Cost snapshot — чтение леджера cost-tracker

```bash
tmpd="$(python3 -c 'import tempfile;print(tempfile.gettempdir())' 2>/dev/null || echo /tmp)"
ledger="$(ls -1t /tmp/claude-cost-${CLAUDE_SESSION_ID:-*}.json "$tmpd"/claude-cost-${CLAUDE_SESSION_ID:-*}.json 2>/dev/null | head -1)"
if [ -n "$ledger" ] && [ -f "$ledger" ]; then
  echo "— Cost snapshot —"; cat "$ledger"
else
  echo "cost ledger not found (cost-tracker.sh inactive this session)"
fi
```

Есть леджер → добавь в session-файл строку **`## Стоимость сессии`**
(токены + blended USD + был ли достигнут soft/hard ceiling; если доступен
`ctx-stats` — его context-savings на той же строке). Нет леджера → мягкий
no-op, `/session-save` не блокируется.

## §4.7b Methodology-memory auto-push

```bash
MM="$HOME/.claude/methodology-memory"
if [ -d "$MM/.git" ]; then
  git -C "$MM" add -A
  git -C "$MM" diff --cached --quiet || \
    git -C "$MM" commit -q -m "memory: session checkpoint $(date +%F)"
  if git -C "$MM" remote get-url origin >/dev/null 2>&1; then
    git -C "$MM" push -q origin HEAD || echo "memory push failed (offline?) — commit is local, will push next time"
  fi
fi
```

Best-effort: сетевой/auth-сбой НИКОГДА не блокирует `/session-save` — одна
строка отчёта и дальше (локальный коммит состояние уже сохранил). Scope guard:
в этом репо живут только заметки методологии; секретные ЗНАЧЕНИЯ в память не
писать (имена env-переменных — можно); remote остаётся приватным. Нет репо /
remote → тихий no-op.

## §4.9 Skill-coverage self-audit — сбор входов

```bash
tmpd="$(python3 -c 'import tempfile;print(tempfile.gettempdir())' 2>/dev/null || echo /tmp)"
ledger="$(ls -1t /tmp/claude-skill-ledger-*.jsonl "$tmpd"/claude-skill-ledger-*.jsonl 2>/dev/null | head -1)"
echo "— SKILL_BYPASS за сессию —"
if [ -n "$ledger" ]; then echo "записей: $(wc -l < "$ledger")"; tail -n 20 "$ledger"; else echo "нет"; fi
echo "— sentinel'ы скиллов (свежие/этой сессии) —"
for s in review test migrate security-audit; do
  if ls /tmp/claude-$s-done-* "$tmpd"/claude-$s-done-* >/dev/null 2>&1; then echo "  $s: есть"; else echo "  $s: НЕТ"; fi
done
```

Интерпретация результатов и risk-матрица (миграция → /migrate+/test;
payments/auth/secrets → /security-audit; multi-file коммит → /review; новые
source-файлы → /test) — в SKILL.md Step 4.9.
