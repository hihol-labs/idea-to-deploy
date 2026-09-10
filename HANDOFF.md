# HANDOFF — REL-1.104.0 закрыт owner-маршрутом; следующий юнит BROKER-ISOLATION

Дата: 2026-09-10. Ветка `chore/ledger-close-1.104.0` от `main` 4d19a16, коммит `0a1673a`
(строка `verification_failed` вчерашнего ОТК) плюс этот ledger-close.

## Состояние цели
`REL-1.104.0` — **verified** (43 из 48 юнитов). `currentUnitId` пуст, WIP свободен.
Открыты: `BROKER-ISOLATION` (следующий), `RSI-DEBT-2`, `RSI-DEBT-3` — pending;
`PE5-008` и `PE5-009` — blocked до реального внешнего adoption/outcome evidence.

## Как именно закрыт REL-1.104.0
Owner-маршрут, решение владельца 2026-09-10 (см. `.itd/DECISIONS.md`, запись
«REL-1.104.0 closes through the owner route»). Что есть и чего нет:

- **Есть.** Харнес прогнал sealed `verificationCommand` на хосте, и все его ноги зелёные —
  единственная строка отказа была `UNVERIFIED REL-1.104.0 — full checker receipt is missing`.
  Релиз `v1.104.0` опубликован (PR #276 -> `df95089`), раскатка доказана `INSTALLED.json`
  из канареек `native-Linux-a3` и `native-Windows-a6` на дереве `dee8abbf`.
- **Нет.** Квитанции независимого ревьюера. Продюсер исполняет оракул в изолированном
  staged-кандидате, где `verify_review_broker` красный (BACKLOG P1 2026-09-10, шесть заходов).
- Событие перехода в `events.jsonl` несёт `actor: human-owner`, а не `harness` — owner-маршрут
  отличается от машинной верификации по одному полю.

## Следующий юнит: BROKER-ISOLATION (перед RSI-DEBT-2)
Критерий: `tests/verify_review_broker.py` проходит внутри изолированного staged-кандидата под
зеркалом, а не только отдельно и не только на хосте; новый оракул
`tests/verify_isolated_candidate_mirror.py` материализует изолированный кандидат, гоняет
`bash tests/run-all.sh --quick` внутри него и требует, чтобы последняя строка была ровно
sealed-строкой; зависимость `free_review_phase` от порядка зеркала либо объявляется входом,
либо снимается. RED-first: до фикса новый оракул красный на том же кандидате.

Замеры, с которых начинать (полностью — BACKLOG P1 2026-09-10):

| где | как | последняя строка |
| --- | --- | --- |
| хост | зеркало | `DONE fails: verify_reviewer_provider_freshness` |
| изолированный кандидат | зеркало | `... verify_reviewer_provider_freshness verify_review_broker` |
| изолированный кандидат | сьют отдельно | `{"checks": 741, "status": "PASSED"}` (дважды) |
| хост | сьют отдельно | PASSED |

Падает `free receipt reaches broker success` в `tests/verify_review_broker.py:2816`.
Опровергнуто замером: host-owned файлы `.itd` (все шесть), расположение TMPDIR, дрейф runtime.

## Рабочие инструменты этого цикла (git-ignored, переиспользуемы)
- `.itd-memory/verification-loop/REL-1.104.0-run-machine-close2.py` — машинная квитанция: весь
  sealed-оракул ОДНИМ `oracle=`-раном (иначе `receipt_binds_command` не свяжет claim), два
  declared input, предпусковая очистка байт-кода runtime, проверка чистоты дерева.
- `.itd-memory/verification-loop/REL-1.104.0-canary-close.py` — перенос кандидата на Windows без
  push (временный коммит -> `git bundle` через именованный ref -> fetch/read-tree/checkout-index),
  канарейка и копирование квитанций обратно.
- `.itd-memory/verification-loop/REL-1.104.0-owner-close.py` — owner-route переход, с dry-run.
- `.itd-memory/verification-loop/REL-1.104.0-probe-close1/probe_legs.py` — разбор оракула по
  ногам в изолированном клоне; для BROKER-ISOLATION это готовый стенд.

## Ловушки маршрута (измерены сегодня)
- Любая правка дерева обесценивает нативные канарейки: `--installed-proof` привязан к точному
  кандидату. Порядок один: заморозить пакет -> канарейки -> ОТК -> переход -> коммит.
- Изолированный кандидат должен лежать ВНЕ репозитория (иначе краснеет
  `verify_host_neutral_memory`) и на пути, доверенном Windows-git по UNC (иначе Windows-половина
  реплея падает на «detected dubious ownership»). Рабочий путь: `~/.cache/itd-isolated-tmp`,
  он зарегистрирован в глобальном `safe.directory` на Windows.
- Оба установленных runtime (WSL и Windows) накапливают `__pycache__`, когда оракул через них
  проходит; следующий `validate_runtime` называет это дрейфом инвентаря. Чистить перед прогоном.
- В изолированном `--shared`-клоне нет GitHub-remote: нога релиза работает только с `GH_REPO`.
- Зеркало в изоляции требует declared input `GPG-003_REVIEW_EFFICACY_KEYRING.sha256`, иначе
  кончается на `blocked: verify_independent_review_efficacy`.
- `git bundle` не принимает голый sha как tip — нужен именованный ref.
- Скретчпад сессии Claude Code стирается при рестарте; долгоживущее — только в `.itd-memory/`.
- Windows-копия `C:\itd-src\idea-to-deploy` стоит на кандидате `0a1673a`+`dee8abbf`; stash
  «pre-1.104.0 local modifications» на месте, не трогать.

## Что осталось по этому PR
`itd gate register-profile` под itd 1.104.0 (repository `hihol-labs/idea-to-deploy`, checkout
`/home/hihol/projects/idea-to-deploy`, owner-type organization, local-submission / local-review,
unit REL-1.104.0, risk high, keyring sha `1fa8afec…b0744`) -> `doctor` LOCAL_REVIEWED ->
`itd pr create --timeout 3600` -> `gh pr ready` -> CI -> merge.
