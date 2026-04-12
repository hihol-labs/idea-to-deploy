# Git Isolation Pattern (GSD-inspired)

## Принцип

Каждый milestone (фаза /kickstart, /autopilot) работает в изолированной git-ветке.
По завершении — squash merge в основную ветку. Это даёт чистую историю и лёгкий rollback.

## Реализация в /kickstart

### Phase 1 (Planning) — основная ветка
Работаем прямо в текущей ветке. Документы не опасны.

### Phase 2 (Code Generation) — изолированная ветка
```bash
# Создаём ветку для кодогенерации
git checkout -b feat/<project>-codegen

# ... генерация кода ...

# Коммитим по частям (sequential slice commits)
git add src/models/
git commit -m "feat: add data models"

git add src/api/
git commit -m "feat: add API endpoints"

git add src/services/
git commit -m "feat: add business logic"
```

### Phase 3 (Tests) — та же ветка
```bash
git add tests/
git commit -m "test: add unit and integration tests"
```

### Phase 4 (Deploy) — та же ветка
```bash
git add docker-compose.yml Dockerfile nginx.conf
git commit -m "infra: add deployment configuration"
```

### Merge — squash в основную ветку
```bash
git checkout main  # или исходная ветка
git merge --squash feat/<project>-codegen
git commit -m "feat: complete <project> — code + tests + deploy"
```

## Когда использовать worktree вместо ветки

Worktree полезен когда нужно параллельно работать в двух контекстах:
- Основной код в одном worktree
- Эксперимент / spike в другом

```bash
git worktree add ../<project>-spike feat/<project>-spike
# Работаем в ../<project>-spike
# По завершении:
git worktree remove ../<project>-spike
```

## Правила

1. **Никогда не коммитить напрямую в main** — всегда через feature branch
2. **Sequential commits** — один коммит на один логический юнит (модели отдельно, API отдельно)
3. **Squash merge** — для чистой истории (один коммит = один milestone)
4. **Rollback** — `git revert <squash-commit>` откатывает весь milestone
