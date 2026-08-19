# Scope Lock — R3 (LPD-002): сетевые вызовы гейта переживают флейк и не создают дублей

## Current Task

`itd pr create` и `itd gate` в `scripts/itd.py`: bounded retry (<= 5 попыток,
экспоненциальная пауза 15 -> 30 с, потолок 30 с) на **транспортных** ошибках
GitHub (GraphQL/REST через `gh`, `git ls-remote` к origin); **никакого** ретрая
на 401/403/422 (права/валидация) и на любой неклассифицированной ошибке
(fail-closed: неизвестная ошибка не ретраится); перед созданием PR — проверка
существующего PR для ветки (идемпотентность, `gh pr create` никогда не зовётся
дважды на одну ветку); при исчерпании — typed `UNAVAILABLE` с подсказкой
«state may have applied; re-check with gh pr view». Третий пункт плана
`.itd-memory/LPD-002_UNIT_PLAN.json` (approved владельцем 2026-08-18), riskTier
**low** (`checkerMode machine_only`, `checkerRequired false`,
`minimumIndependentReviewers 0`), WIP=1. Pre-PR claim противоположным вендором
обязателен как всегда.

## Корень (измерен на живом маршруте, публикация R2 — сессия 2026-08-18-3)

1. `itd pr create` дважды вернул `{"reason": "GitHub PR lookup failed",
   "status": "UNAVAILABLE"}` на TLS-таймаутах к `api.github.com`. Первый вызов
   при этом УЖЕ выполнил пуш — удалённая ветка стояла на голове, PR не создан;
   код возврата об этом не говорил. `pr_view` (`scripts/itd.py:923`) поднимает
   `UNAVAILABLE` на любой ненулевой выход `gh pr view`, кроме точной строки
   «no pull requests found», и **выбрасывает stderr** — причина невидима.
2. Один из отказов пришёл как `{"reason": "command unavailable: git"}`
   (`run()`, `scripts/itd.py:170,177`): таймаут подпроцесса и отсутствие
   бинаря сообщаются ОДНОЙ строкой, хотя первое — сетевой `git ls-remote`
   к origin (TLS handshake завис), второе — локальный дефект окружения.
   Диагностика указывала на локальный git при сетевой причине.
3. Ручной обход, который сработал: повтор вызова 2-5 раз подряд. То есть
   поведение, которое R3 делает штатным, выполнялось руками
   (retro E5/P4: ручные повторы; E9/P8: тег релиза через `--target`).

Класс дефекта: **транспортный флейк судится как терминальный отказ**, а
повтор — ручной и без проверки «а не применилось ли уже».

## Candidate composition (allowed zones)

- `scripts/itd.py`:
  - закрытый словарь транспортных маркеров (`TRANSPORT_FAILURE_MARKERS`) и
    регулярка неретраибельных HTTP-статусов (`NON_RETRYABLE_HTTP_RE`:
    401/403/422); классификатор `transport_failure(exc)`: не-`UNAVAILABLE`
    -> нет; 401/403/422 -> нет (приоритет над любым маркером); маркер -> да;
    иначе -> нет (fail-closed);
  - драйвер `with_transport_retry(operation, label, ...)`: <= 5 попыток,
    паузы `min(30, 15 * 2**(n-1))` = 15, 30, 30, 30; после исчерпания —
    `UNAVAILABLE` с числом попыток, последней причиной и подсказкой
    `TRANSPORT_STATE_HINT`; любая неретраибельная ошибка пробрасывается как
    есть с первой попытки;
  - `gh_json` — обёртка над `gate.gh_json` с собственным runner'ом, который
    различает «gh не найден» (не транспорт) и «gh не ответил за 30 с»
    (транспорт), плюс retry; становится default `gh=` у
    `organization_repositories`, `current_pull_request`, `check_runs`,
    `wait_pull_candidate`, `wait_checks` и вызывается в `observe_enrollment`.
    Мутация `apply_ruleset --apply` (PUT/POST ruleset) НЕ ретраится:
    POST неидемпотентен, а идемпотентность здесь ничем не проверяется;
  - `run()`: таймаут подпроцесса сообщается честно —
    `<cmd> timed out after <N>s`, а не `command unavailable: <cmd>` (последнее
    остаётся только для OSError при запуске);
  - `pr_view`: причина несёт stderr `gh` (обрезанный до 1000 символов, как в
    `run()`/`gate.gh_json`), а не голое «lookup failed»;
  - `create_draft_pr`: `pr_view` и `remote_branch_head` (read-only) идут
    через retry; `gh pr create` — через `create_pull_request()`: перед
    КАЖДОЙ попыткой создания проверяется существующий PR ветки, при
    транспортной ошибке создания перед повтором снова проверяется PR (мог
    создаться на стороне GitHub), существующий PR возвращается без второго
    `create`. `git push` НЕ ретраится (мутация под pre-push гейтом; пустой
    повторный пуш гейт отвергает по построению) — его таймаут теперь честно
    назван.
- `tests/verify_itd_cli.py` — RED-first проверки классификатора, драйвера,
  идемпотентности создания и **двух обязательных канареек**: ретрай на 403
  -> падает; двойной вызов `create` при существующем PR -> падает.
  oracleId `guarded-pr-cli-regression`; `tests/verify_gate_control.py` — регрессия
  (`gate-control-regression`), сам модуль не меняется.
- `docs/RELEASE_RUNBOOK.md` — конвейер п.5 (merge/PR больше не «ретраить
  циклом» руками — retry штатный, при `UNAVAILABLE` проверять факт через
  `gh pr view`/`gh api .../pulls?head=`), плюс E9: тег релиза только через
  `gh release create --target $(git rev-parse <merge-sha>)`; «Грабли» —
  запись о закрытом классе.
- `.itd/ACCEPTANCE_CONTRACT.json` — критерии `LPD002-R3-*`, ротация
  `activeFollowup` `LPD002-R2` -> `LPD002-R3` (riskTier low, 0 reviewers);
  `.itd-memory/STATE.json` — `currentUnit LPD002-R3` (`riskTier: low`
  вручную — у `activate` нет флага, это пункт R4);
  `.itd-memory/contracts/LPD002-R3.md`; `.itd-memory/LPD-002_UNIT_PLAN.json`
  — статус пункта R3.
- С delivery-коммитом R3 едут отметки закрытия R2 в `STATE.json` и
  `LPD-002_UNIT_PLAN.json` (отдельный ledger-close коммит не проходит
  evidence-first продюсера — HANDOFF-S10 §17.11, решение владельца; тот же
  шаблон, что R1 -> R2).

## Явно вне скоупа

- `skills/_shared/itd_gate_control.py` (`gh_json`, `GateError`) — не
  трогается: retry живёт в CLI над ним, ошибки классифицируются по
  `reason`, а не по новым полям исключения. Это же держит live-evidence пин
  (`skills/`, `hooks/` не меняются -> перечеканка не нужна, проверить
  `verify_live_model_benchmark.py --require-evidence`).
- Ретрай мутаций без проверки идемпотентности (`git push`, ruleset POST).
- Retry-политика внутри `wait_pull_candidate`/`wait_checks` (их poll по
  «GitHub is still computing the test merge» остаётся как есть; retry
  добавляется только на уровне `gh_json`, который они зовут).
- Пункты R4-R6 плана — каждый отдельной сессией, WIP=1.

## Принцип

Retry — **сужение** класса «терминальный отказ», а не расширение доверия:
ретраится только доказанно транспортное (закрытый словарь), права/валидация
и всё неизвестное — нет; ни одна мутация не повторяется без проверки, что
она не применилась; исчерпание не притворяется успехом и говорит, что
именно перепроверить.
