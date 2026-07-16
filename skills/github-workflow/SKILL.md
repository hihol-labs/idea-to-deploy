---
name: github-workflow
description: 'GitHub Issues, Pull Request, CI, release, and code-review workflow for idea-to-deploy projects. Inspects PR/CI/review state, debugs failing GitHub Actions before code changes, prepares branches/changelogs/release notes, and keeps project artifacts aligned with PR/CI status. Explicit-invocation, external-write.'
argument-hint: issue, pull request, branch, check run, release, or GitHub repo
license: MIT
allowed-tools: Read Write Edit Glob Grep Bash(gh:*) Bash(git:*)
disable-model-invocation: false
metadata:
  effort: medium
  side_effect: external-write
  explicit_invocation: true
  author: HiH-DimaN
  version: 1.21.0
  category: integration
  tags: [github, pull-request, ci, release, integration]
---

# GitHub Workflow

## Trigger phrases

- создай issue, открой pull request, оформи pr
- github issue, github actions упал, gh workflow
- create github issue, open pull request, ci is failing
- release notes, pr summary, review comments

## Recommended model

**Sonnet** — это структурированная работа с `gh`/git и связывание находок с
артефактами проекта; глубокое рассуждение не требуется. Opus оправдан только для
разбора нетривиального падения CI с кросс-слойной причиной.

## Instructions

Используй этот скилл, когда состояние idea-to-deploy нужно связать с работой в
GitHub. Подробный чеклист — в `references/github-workflow-checklist.md`.

> **Explicit-invocation** (`metadata.explicit_invocation: true`; Codex policy
> `allow_implicit_invocation: false`). Вызывается явно
> через `/github-workflow`. Несёт `external-write` — любые мутации в GitHub
> (push/merge/close/resolve/release) выполняются **только по явному намерению**
> пользователя.

### Capabilities

- Превратить пункты плана и блокеры (`LAUNCH_PLAN.md`, `BACKLOG.md`) в GitHub Issues.
- Посмотреть метаданные PR, ревью-комментарии, статус проверок через GitHub
  connector или `gh`.
- Разобрать упавшие GitHub Actions ДО изменения кода.
- Подготовить ветку, changelog, release notes, summary для PR.
- Держать `.rubric-status` (гейт `/review`) и `STATE.json` в соответствии с PR/CI.

### Procedure

1. Определи цель: репозиторий, ветку, issue, PR или check run.
2. Прочитай локальный `git status` ДО любых мутаций.
3. Сначала используй GitHub connector; `gh` — когда покрытия коннектора не хватает.
4. Свяжи находки с артефактами idea-to-deploy:
   - issues → пункты плана/блокеры (`BACKLOG.md`, `LAUNCH_PLAN.md`)
   - CI-проверки → история верификации (`.rubric-status`, `/test` evidence)
   - ревью-комментарии → действия по починке
   - release notes → завершённые модули и принятые риски
5. Перед завершением ветки — запиши `BRANCH_FINISH.md` (шаблон в
   `docs/templates/.itd/`) c режимом (pr/merge/keep/discard) и свежей верификацией.
6. Когда нужен файловый экспорт — `.itd-integrations/github.json`.

### Output

```text
GITHUB TARGET:
ARTIFACTS UPDATED:
CHECK STATUS:
ACTION TAKEN:
BLOCKERS:
NEXT ACTION:
```

## Examples

### Example 1: Упавший CI на PR
User: «/github-workflow: на PR упал GitHub Actions, разбери до правок кода.»

Actions:
1. Читает локальный `git status`, затем статус проверок через `gh`/connector.
2. Находит root cause падения (не прячет за documentation-only статусом).
3. Связывает: CI → `.rubric-status`, ревью-комментарии → repair actions.
4. Готовит summary для PR, ничего не мержит. Выдаёт форму вывода.

### Example 2: План → GitHub Issues
User: «/github-workflow: заведи issues по блокерам из BACKLOG.md.»

Actions:
1. Читает `BACKLOG.md`, выбирает блокеры.
2. Создаёт issues (по явному намерению), мапит их обратно на пункты плана.
3. Фиксирует связь issue↔узел в `BACKLOG.md`.

### Example 3: Завершение ветки с release notes
User: «/github-workflow: ветка готова, подготовь release notes.»

Actions:
1. Требует свежую верификацию (тесты/`.rubric-status`) перед finish.
2. Пишет `BRANCH_FINISH.md` (mode pr/merge/keep/discard).
3. Готовит release notes: завершённые модули + принятые риски. Merge/release —
   только по явной команде.

## Self-validation

Перед выводом убедись:
- [ ] Локальный `git status` прочитан до мутаций.
- [ ] Использован connector/`gh`; находки связаны с артефактами idea-to-deploy.
- [ ] Упавший CI разобран честно (не спрятан за docs-only статусом).
- [ ] push/merge/close/resolve/release — только по явному намерению.
- [ ] `BRANCH_FINISH.md` записан, если завершение ветки в scope.
- [ ] При недоступности GitHub — `.itd-integrations/github.json` + пометка.

## Troubleshooting

### GitHub недоступен (нет connector и `gh`)
Сформируй `.itd-integrations/github.json` и явно укажи, что live-синк не
выполнялся. Не выдумывай статус CI.

### Пользователь просит «просто смержи»
Подтверди намерение явно перед merge — это external-write. Покажи, что CI зелёный
и верификация свежая, прежде чем выполнять.

### Упавший CI хочется обойти документацией
Запрещено. Падение CI — это реальный блокер; разбери root cause, не прячь за
documentation-only статусом.

### Изменения worktree выходят за активный узел
Сузь scope до активного узла работы; не смешивай несвязанные правки в одной ветке/PR.

## Rules

- **Explicit-invocation** — вызывается явно; не авто-роутится.
- **Никаких push/merge/close/resolve/release без явного намерения.**
- **Не прятать упавший CI** за documentation-only статусом.
- **Read `git status` до мутаций.**
- **Не завершать ветку** без свежей верификации и `BRANCH_FINISH.md`.
- **GitHub недоступен** → `.itd-integrations/github.json` + пометка.
- **Match the user's language** для всего вывода.
