---
project: /home/hihol/projects/idea-to-deploy
stage: handoff
from_role: release-operator
to_role: next-session
reason: post-release continuity
unit: GPG-001
status: verified
---

# GPG-001 handoff — v1.95.0 опубликована и установлена

> [!todo] Первое действие
> На `main` после merge post-release reconciliation запусти `python3 scripts/itd.py gate doctor --repository hihol-labs/idea-to-deploy` и подтверди `LOCAL_REVIEWED`; не открывай GPG-001 заново без нового явно выбранного follow-up.

## 1. From → To и причина передачи

- From: release/operator session, завершившая review, merge и dual-host rollout.
- To: следующая рабочая сессия Idea to Deploy.
- Причина: post-release handoff после завершения high-risk юнита.

## 2. Текущее состояние

- `GPG-001` завершён для выбранного профиля
  `local-submission` + `local-review`; claim `PROTECTED` не делается.
- PR #177 смержен squash-коммитом `234752828d463821814020bebf2cc3dc40399beb`.
- Release PR #178 смержен squash-коммитом
  `8c2bb1b0689ce68282a3ef10a2edc6143a097f8f`.
- В `CHANGELOG.md` опубликована версия 1.95.0 от 2026-08-02. GitHub tag и
  GitHub Release не создавались: текущий `docs/RELEASE_RUNBOOK.md` их не
  требует.
- WSL и Windows Claude sync показывают zero drift. WSL и Windows Codex
  показывают `idea-to-deploy@personal` installed/enabled 1.95.0; пять
  load-bearing файлов byte-identical источнику релиза.
- WSL registry подтвердил `LOCAL_REVIEWED` на release candidate; после
  любого нового exact candidate receipt закономерно устаревает и должен
  быть обновлён после exact review/commit. Временная Windows registry-запись удалена:
  Windows-native validator на UNC checkout не уложился в фиксированный
  30-секундный timeout; глобальный Windows pre-push остаётся fail-closed.
- Основной checkout перед этим handoff был clean на `origin/main`.

## 3. Финальные решения

- Независимым остаётся reviewer; maker, maintainer и deployer могут совпадать.
- Базовый переносимый профиль — `local-submission/local-review`. Он не требует
  GitHub App и административных прав на чужой репозиторий.
- App-owned check и `PROTECTED` — отдельное opt-in усиление, а не условие
  завершения базовой методологии.
- Merge/deploy выполняет владелец целевого проекта; reviewer не получает этих
  прав.
- Ruleset `main` сохраняет pull-request/deletion/non-fast-forward/thread
  protections и требует `Gate 1 — meta-review rubric`; недоступный
  `ITD external review gate` удалён по явному подтверждению пользователя.
- Установленные Codex cache вручную не редактируются: релиз развёрнут через
  personal marketplace source и `codex plugin add`, создав cache `1.95.0`.

## 4. Требуемые входы

- `AGENTS.md`, этот `HANDOFF.md`, [[STATE]].
- `.itd/GPG-001_NINE_POINT_PLAN.md`, `.itd/ACCEPTANCE_CONTRACT.json`,
  `.itd/VERIFICATION_CONTRACT.json`, `.itd/GPG-001_COMPLETION_EVIDENCE.json`.
- `skills/_shared/GATE_DEPLOYMENT_PROFILES.json`,
  `docs/RELEASE_RUNBOOK.md`, `docs/CODEX_ADAPTER.md`.

## 5. Зоны записи и запреты

- Следующую работу начинать новым WIP=1 юнитом или явно одобренным follow-up.
- Не выдавать `LOCAL_REVIEWED` за `PROTECTED`.
- Не возвращать stale required check `ITD external review gate`, пока реально
  не развёрнут и не enrolled App/broker.
- Не редактировать `~/.codex/plugins/cache/**` напрямую и не хранить ключи,
  токены или приватные App credentials в репозитории.
- При release сначала merge/publish exact candidate, затем устанавливать из
  merge SHA.

## 6. Команды проверки

```bash
git status --short --branch
git log -3 --oneline --decorate
python3 scripts/itd.py gate doctor --repository hihol-labs/idea-to-deploy
bash tests/run-all.sh --quick
bash scripts/sync-to-active.sh --check
CLAUDE_HOME=/mnt/c/Users/Дмитрий/.claude bash scripts/sync-to-active.sh --check
codex plugin list | grep idea-to-deploy
```

На Windows дополнительно:

```powershell
codex plugin list | Select-String idea-to-deploy
```

## 7. Блокеры и риски

> [!warning]
> Блокеров GPG-001 нет. Опциональный follow-up: сделать timeout Windows-native local-adjudication validator пропорциональным скорости UNC checkout либо документировать native-Windows checkout requirement. До этого Windows registry для данного UNC checkout не регистрировать.

- В локальном `.git/config` обнаружены legacy branch remote URL с credential
  material. Значение не использовать и не переносить в артефакты; credential
  следует отдельно отозвать/ротировать и очистить конфиг с явным разрешением.
- Долгая цель [[GOAL]] остаётся active: 36/38 verified; PE5-008/009 blocked
  внешним outcome evidence и не закрываются этим релизом.

## 8. Evidence

- Release staged tree: `aee9ee16c45974d0d822675d4912ed27f5505c45`.
- Independent fresh-model review: `PASSED`, findings 0, unverified 0.
- Clone-durable evidence index: `.itd/GPG-001_COMPLETION_EVIDENCE.json`.
- Tracked implementation adjudication:
  `.itd-memory/verification-loop/receipts/360a8d71643b981a/GPG-001-live-evidence-adjudication-a1.json`.
- Tracked release adjudication:
  `.itd-memory/verification-loop/GPG-001-release-1.95.0-adjudication.json`;
  canonical receipt SHA-256
  `97fff7101de985ccf3a4bb23b85e6daa54ce039619d2c2ba84e9665897127cb2`.
- GitHub Actions PR #178: meta-review success, windows-verify success.
- Installed-cache smoke: release oracle 14 criteria / 5 mutation guards PASS;
  host adapters PASS with 28 shared registrations and 11 hard gates.
- Recoverable marketplace-source backups:
  `/home/hihol/.codex/plugin-backups/idea-to-deploy-source-before-1.95.0-20260802`
  and
  `C:\Users\Дмитрий\.codex\plugin-backups\idea-to-deploy-source-before-1.95.0-20260802`.

## 9. Следующее действие после cold start

После merge reconciliation и проверки `LOCAL_REVIEWED` выбрать новый
юнит по прямому запросу пользователя. UNC-timeout считать отдельным bugfix,
а не незавершённой частью GPG-001.
