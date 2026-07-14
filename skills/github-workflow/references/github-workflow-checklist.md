# GitHub Workflow — Checklist

Чеклист для связывания состояния проекта idea-to-deploy с работой в GitHub:
Issues, Pull Requests, CI (GitHub Actions), релизы, ревью-комментарии.

> **Explicit-invocation скилл** (`metadata.explicit_invocation: true`). Вызывается
> явно через `/github-workflow`, не авто-роутится — потому что несёт
> `external-write` (мутации в GitHub). Любая запись (push/merge/close/release) —
> только по явному намерению пользователя.

## Возможности

- Превратить узлы плана и блокеры (`LAUNCH_PLAN.md`, `BACKLOG.md`) в GitHub Issues.
- Посмотреть метаданные PR, ревью-комментарии, статус проверок через GitHub
  connector или `gh` CLI.
- Разобрать упавшие GitHub Actions ДО изменения кода.
- Подготовить ветку, changelog, release notes, summary для PR.
- Держать `.rubric-status` (гейт `/review`) и `STATE.json` в соответствии со
  статусом PR и CI.

## Процедура

1. **Определи цель** — репозиторий, ветку, issue, PR или check run.
2. **Прочитай локальный `git status`** до любых мутаций.
3. **Сначала GitHub connector**, `gh` CLI — когда покрытия коннектора не хватает.
4. **Свяжи находки с артефактами idea-to-deploy:**
   - issues → пункты плана / блокеры (`BACKLOG.md`, `LAUNCH_PLAN.md`)
   - CI-проверки → история верификации (`.rubric-status`, `/test` evidence)
   - ревью-комментарии → действия по починке
   - release notes → завершённые модули и принятые риски
5. **Перед завершением ветки** — запиши `BRANCH_FINISH.md` (шаблон в
   `docs/templates/.itd/`) c режимом (pr/merge/keep/discard) и свежей верификацией.
6. **Экспорт payload** (когда нужен файловый экспорт, а не live-синк) — в
   `.itd-integrations/github.json`.

## Форма вывода

```text
GITHUB TARGET:
ARTIFACTS UPDATED:
CHECK STATUS:
ACTION TAKEN:
BLOCKERS:
NEXT ACTION:
```

## Правила

- **Не** push/merge/close issues/resolve review threads/создание prod-релизов
  **без явного намерения** пользователя.
- **Не** прятать упавший CI за documentation-only статусом.
- Держи изменения worktree в рамках активного узла работы.
- **Не** помечать ветку завершённой без свежей верификации и `BRANCH_FINISH.md`,
  когда branch-finish в scope.
- Если GitHub недоступен — сформируй `.itd-integrations/github.json` и укажи, что
  live-синк не выполнялся.

## Self-validation (перед выводом)

- [ ] Локальный `git status` прочитан до мутаций.
- [ ] Использован connector/`gh`; находки связаны с артефактами idea-to-deploy.
- [ ] Упавший CI разобран честно (не спрятан).
- [ ] Деструктивные действия (push/merge/close/release) — только по явной просьбе.
- [ ] `BRANCH_FINISH.md` записан, если завершение ветки в scope.
