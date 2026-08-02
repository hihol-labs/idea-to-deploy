# GPG-001 — согласованный план из 9 пунктов

Статус: `verified` для выбранного профиля
`local-submission` + `local-review`, WIP=1 закрыт 2026-08-02.
Статус опирается на exact-candidate receipts, GitHub checks, merge и
release/install evidence из `.itd/GPG-001_COMPLETION_EVIDENCE.json`; он не
является заявлением `PROTECTED`.

## Инварианты ролей и профилей

План остаётся универсальным и не привязан к конкретному maintainer или
репозиторию. Роли `maker`, `maintainer` и `deployer` могут выполняться одним
человеком. Только `independentReviewer` обязан отличаться от maker точного
candidate. Reviewer App публикует verdict/check, но не получает права merge
или deploy.

Развёртывание выбирается отдельно: `local-submission` без GitHub App,
`self-hosted-app` с App пользователя/организации и `managed-app` с общей
public App сервиса. Уровень защиты также отдельный: `local-review`,
`app-check` или `organization-workflow`. Только последний при полном live
doctor/canary evidence может называться `PROTECTED`.

## Нулевое условие перед следующим пунктом

Сначала восстановить удалённый коммитом `954a3b6` контроль MEM-8: закрытый
реестр prompt-bearing tools/MCP, schema + validator, `allow|ask|abstain`,
fail-closed default для неизвестного provider, read-only inventory в `/adopt`,
security-audit check и mutation tests. Восстановление делается bounded repair
поверх текущей ветки, без rollback принятого GPG bootstrap. Пока RED→GREEN и
новый bound `/review` не пройдены, commit/push/PR update запрещены.

Условие выполнено: MEM-8 восстановлен, mutation coverage и свежие
general/security reviews пройдены до merge PR #177.

## 1. Inventory контролируемых репозиториев

Собрать и поддерживать allowlist GitHub accounts/repositories, явно связывая
repository identity, visibility, default/protected branches, adoption state,
deployment/protection profile и ожидаемые checks. Неизвестный или
незарегистрированный repo блокируется fail-closed в server-enforced профилях.

## 2. Независимая authority и GitHub App/broker

В `local-submission` authority — exact signed independent receipt до PR. В
server-enforced профилях dedicated least-privilege GitHub App остаётся
единственной publisher authority и никогда не merge/deploy authority. Broker
становится reviewer-transport-neutral: получает durable
independent-review evidence от допустимого изолированного producer,
перепроверяет live base/head/test-merge SHA, exact tree/diff и signer, после
чего публикует App-owned Check Run. Валидный бесплатный receipt не должен
автоматически запускать платный provider.

## 3. Независимый reviewer без обязательного платного API

Обязателен fresh different-model/different-session review, но не обязательный
Responses API call. Primary route — сильная установленная модель в новом
контексте, без истории разработки, secrets, network и mutation tools. Producer
получает только scrubbed exact candidate, выдаёт structured verdict и
host-observed model/session provenance. Receipt двухфазный: сначала связывает
base/head/tree/diff/prompt/report, затем App после live revalidation добавляет
PR/check SHA и публикует результат.

Generic CLI/OAuth reviewer остаётся advisory, пока нет enforceable sandbox,
identity/session telemetry и signer. Paid Responses API — только optional
availability fallback после отдельного явного согласия и бюджета; никогда не
запускается автоматически. Недоступность бесплатного reviewer даёт
`UNAVAILABLE` и блокирует merge.

## 4. Release и установка ITD

Выпустить следующую версию ITD только после принятия кандидата. В release
включить free-review producer/adapter, broker-side receipt validation,
Windows/WSL parity и документацию. Установленный plugin cache не редактировать:
только publish + штатная установка новой версии.

## 5. Machine oracle и bounded diff

Machine oracle выполняется из protected pinned source на exact candidate.
Иерархические пределы сохраняются: direct до 80 KB, full diff до 1.2 MB,
не более 16 review units с обязательной integration проверкой, без truncation.
Только явно объявленный bounded single-member `.jsonl.gz` допускает
transparent logical review; любой generic binary остаётся `UNVERIFIED`.

## 6. Ruleset и merge gate

`app-check` требует App-owned external-review check доступным владельцу
репозитория механизмом, но не заявляет protected workflow authority.
`organization-workflow` дополнительно требует protected machine-oracle check
на policy-selected SHA для `pull_request` и `merge_group`. Local status,
same-name check, stale receipt, admin prose или standalone `PASSED` не
удовлетворяют server gate. Merge и deploy выполняют maintainer/deployer
конкретного проекта; эти роли могут совпадать с maker.

## 7. Secrets и стоимость

Primary free route не требует OpenAI API key. Ранее раскрытый ключ не
использовать, не читать и не сохранять. Если платный fallback когда-либо будет
явно включён, credential принадлежит broker/KMS/service account boundary,
доступен только credential-free worker boundary и ограничен отдельным
consent/budget. Candidate code никогда не исполняется рядом с secrets.

## 8. Windows/WSL preflight и Draft PR

Глобальные hooks/CLI блокируют protected-branch push, незарегистрированный
repo, stale/foreign receipts и обход guarded Draft PR flow. Перед PR локально
готовится бесплатный independent receipt; после PR broker перепривязывает его
к live coordinates. Hooks улучшают UX, но не являются security boundary.

## 9. Doctor, canaries и rollout

Profile-aware doctor проверяет registry, App/ruleset/workflow drift,
free-producer availability, model/session separation, isolation, signer и
receipt freshness и не завышает protection claim. Negative canaries обязаны доказать блокировку forged/stale
receipt, inherited-context/same-session reviewer, generic binary, reviewer
unavailable, missing oracle и unbound integration identity. Затем — serial
adoption, release/install и live evidence выбранных профилей при WIP=1.

## Текущая граница

Все девять пунктов реализованы для базового переносимого профиля:

1. profile registry и fail-closed inventory выпущены;
2. transport-neutral broker/App authority реализованы и протестированы;
3. free isolated fresh-model reviewer и exact receipts приняты;
4. PR #177 смержен, v1.95.0 выпущена PR #178 и установлена на
   Windows/WSL для Codex и Claude;
5. exact machine oracle, bounded diff и binary fail-closed guards приняты;
6. guarded local-review flow и репозиторный ruleset использованы при
   merge; App-owned check остаётся условием только App-профиля;
7. free-primary route не использует API key, paid fallback не включался;
8. Windows/WSL hooks, guarded Draft PR и committed-head bridge выпущены;
9. WSL doctor до post-release reconciliation подтвердил `LOCAL_REVIEWED`,
   canaries и dual-host release smoke пройдены.

`self-hosted-app`, `managed-app` и `organization-workflow/PROTECTED` сохранены
как opt-in профили. Их live enrollment и protected canaries не нужны для
завершения `local-review` и не заявляются как выполненные. Windows
native doctor для UNC checkout остаётся отдельным timeout bugfix, а не
частью уже выпущенной методологии.
