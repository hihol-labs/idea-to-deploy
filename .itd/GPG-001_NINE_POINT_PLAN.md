# GPG-001 — согласованный план из 9 пунктов

Статус базового GPG-001: `verified` для выбранного профиля
`local-submission` + `local-review`. После выявленного false-pass review
уточнённый план 9/9 открыт как WIP=1 `GPG-003` и остаётся `in_progress` до
completion evidence и подтверждённого dual-host rollout.
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
Inventory также хранит активный risk tier, обязательные generic impact classes
и capability/evidence profile; неизвестный impact считается непокрытым.

## 2. Независимая authority и GitHub App/broker

В `local-submission` authority — exact signed independent receipt до PR. В
server-enforced профилях dedicated least-privilege GitHub App остаётся
единственной publisher authority и никогда не merge/deploy authority. Broker
становится reviewer-transport-neutral: получает durable
independent-review evidence от допустимого изолированного producer,
перепроверяет live base/head/test-merge SHA, exact tree/diff и signer, после
чего публикует App-owned Check Run. Валидный бесплатный receipt не должен
автоматически запускать платный provider.
Broker проверяет закрытый evidence-coverage graph и полный host union. Для
medium/high/unknown достаточно одной phase-one v2 identity свежего reviewer,
строго противоположного maker в паре Sol/Terra; никакой clean verdict не удаляет
machine evidence, findings или unverified contours.

## 3. Независимый reviewer без обязательного платного API

Обязателен fresh different-model/different-session review, но не обязательный
Responses API call. Primary route — сильная установленная модель в новом
контексте, без истории разработки, secrets, network и mutation tools. Producer
получает только scrubbed exact candidate, выдаёт structured verdict и
host-observed model/session provenance. Receipt двухфазный: сначала связывает
base/head/tree/diff/prompt/report, затем App после live revalidation добавляет
PR/check SHA и публикует результат.

Anthropic, GitHub Copilot, Antigravity и paid Responses API остаются только
отдельно вызываемыми optional transports. Они не являются автоматическим
fallback, quorum или prerequisite выбранного `LOCAL_REVIEWED` route.
Недоступность обязательного opposite-GPT reviewer даёт `UNAVAILABLE` и
блокирует публикацию данного candidate, но не другие проекты.

Evidence-first предшествует мнению модели: каждый активный acceptance criterion
связан с exact-tree oracle IDs и generic impact classes. Isolated machine oracle
служит read-only explorer, а sealed host adjudicator объединяет unit,
integration и reviewer evidence. Для medium/high/unknown нужен один чистый
fresh opposite-GPT report; missing evidence всегда `UNVERIFIED`.

## 4. Release и установка ITD

Выпустить следующую версию ITD только после принятия кандидата. В release
включить free-review producer/adapter, broker-side receipt validation,
Windows/WSL parity и документацию. Установленный plugin cache не редактировать:
только publish + штатная установка новой версии.
Release дополнительно блокируется, если frozen efficacy corpus не достигает
100% critical/high и missing-evidence detection, 100% finding retention, 90%
medium detection, ≤10% clean false blocks и dual-host parity.

## 5. Machine oracle и bounded diff

Machine oracle выполняется из protected pinned source на exact candidate.
Иерархические пределы сохраняются: direct до 80 KB, full diff до 1.2 MB,
не более 16 review units с обязательной integration проверкой, без truncation.
Только явно объявленный bounded single-member `.jsonl.gz` допускает
transparent logical review; любой generic binary остаётся `UNVERIFIED`.
Machine contract должен содержать impact-driven domain oracles: bounded output,
reconciliation, numerical stability, generated-artifact freshness, scale,
performance и другие объявленные классы. Hash успешного общего test suite не
заменяет отсутствующий oracle конкретного риска.

## 6. Ruleset и merge gate

`app-check` требует App-owned external-review check доступным владельцу
репозитория механизмом, но не заявляет protected workflow authority.
`organization-workflow` дополнительно требует protected machine-oracle check
на policy-selected SHA для `pull_request` и `merge_group`. Local status,
same-name check, stale receipt, admin prose или standalone `PASSED` не
удовлетворяют server gate. Merge и deploy выполняют maintainer/deployer
конкретного проекта; эти роли могут совпадать с maker.
Merge также требует `evidence gaps=[]`, clean checkout/generation/typecheck по
контракту, repository hygiene, Ready (не Draft) и текущие live coordinates.

## 7. Secrets и стоимость

Primary free route не требует OpenAI API key. Ранее раскрытый ключ не
использовать, не читать и не сохранять. Если платный fallback когда-либо будет
явно включён, credential принадлежит broker/KMS/service account boundary,
доступен только credential-free worker boundary и ограничен отдельным
consent/budget. Candidate code никогда не исполняется рядом с secrets.
Reviewer не получает произвольный shell/production access. Исследование идёт
через allowlisted read-only machine oracles в disposable exact checkout;
внешние данные предварительно sanitised и hash-bound.

## 8. Windows/WSL preflight и Draft PR

Глобальные hooks/CLI блокируют protected-branch push, незарегистрированный
repo, stale/foreign receipts и обход guarded Draft PR flow. Перед PR локально
готовится бесплатный independent receipt; после PR broker перепривязывает его
к live coordinates. Hooks улучшают UX, но не являются security boundary.
Preflight проверяет freshness generated artifacts, clean regeneration/typecheck,
отсутствие внутренних review-файлов в candidate и безопасное отключение hooks
в live-model harness без trust bypass.

## 9. Doctor, canaries и rollout

Profile-aware doctor проверяет registry, App/ruleset/workflow drift,
free-producer availability, model/session separation, isolation, signer и
receipt freshness и не завышает protection claim. Negative canaries обязаны доказать блокировку forged/stale
receipt, inherited-context/same-session reviewer, generic binary, reviewer
unavailable, missing oracle и unbound integration identity. Затем — serial
adoption, release/install и live evidence выбранных профилей при WIP=1.
Canaries дополнительно измеряют blocker recall, missing-evidence detection,
finding retention и false-block rate; каждый escaped blocker становится
sanitised generic fixture. Метрики обязаны совпасть на WSL и Windows.

## Текущая граница

Базовая реализация девяти пунктов, выпущенная GPG-001/GPG-002, остаётся
действующей. Уточнение GPG-003 пока не закрыто. Для его закрытия нужны:

1. evidence-first coverage для всех активных критериев;
2. non-erasable host adjudication и один fresh opposite-GPT reviewer;
3. frozen efficacy thresholds на WSL и native Windows;
4. свежий exact-candidate machine receipt и route-bound adjudication;
5. Ready PR #183, зелёный CI и merge;
6. patch release, штатная установка и проверка на обоих hosts;
7. `.itd/GPG-003_COMPLETION_EVIDENCE.json`, связывающий все эти факты.

Исторически подтверждённая базовая граница:

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
