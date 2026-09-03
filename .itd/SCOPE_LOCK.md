# SCOPE_LOCK — STOPRULE-1 (открыт 2026-09-03)

## Предмет
Второй критерий стоп-правила ревью `scripts/itd_stop_rule.py` — R7
`SURFACE_TREADMILL`: серия находит дефекты только в коде, который сама же и
добавила (поток стабилен, поверхность растёт с каждой правкой). Пробел назван
в BACKLOG после LPD-003-3 (r15-r35) и подтверждён второй раз серией PILOT-P02
(r1-r73). Правило остаётся advisory; терминал R7 — терминал решения владельца.

## Замер ДО правки (2026-09-03)
- Правило в маршрут ревью не вшито и по ходу серии P02 не запускалось.
- Реплей восстановленной записи P02 (18 вердиктов с содержанием из транскрипта,
  18 деревьев кандидатов из машинных квитанций, живых в объектной базе):
  R1 взводит `REDESIGN_OR_DISCARD` на **r14** (ключ
  `tests/verify_blind_protocol.py::test-coverage`, впервые r10) — за 56 заходов
  до остановки владельцем на r70.
- Доля засчитанных находок на добавленной поверхности: r6 1/4 -> r10 4/6 ->
  r41..r65 100% (кроме r51 2/3) -> r70 0/1 (опровергнута владельцем).
- Улики серии (промпты, JSON-отчёты, логи) лежали во временном каталоге сессии
  и утрачены при продолжении сессии; уцелели stdout обёртки в транскрипте и
  машинные квитанции. Поэтому раунды P02 — класса `narrative`, а не `report`.

## Разрез (утверждён владельцем 2026-09-03: «правило составляет, человек подписывает»)
1. **STOPRULE-1 (этот юнит)** — критерий R7 в политике и `decide()`, улика
   поверхности (проекция `git diff -U0`, sha256, пересчёт по живым деревьям),
   парсер иерархических отчётов, `line` у находок, kind `reviewed-tree`,
   фикстура PILOT-P02 (narrative + машинная поверхность), синтетический позитив
   R7, контроли R6/S04b/LPD003-1 без смены терминала, мутации.
2. **STOPRULE-2 (следующая сессия)** — `--emit-dispositions`: при терминале
   решения владельца правило составляет файл диспозиций ADR-007 по каждой
   находке чекера, человек подписывает одной закрытой фразой; статус политики
   `advisory` -> `decides-with-human-confirmation`; закрытие PILOT-P02 этим
   маршрутом (кандидат заморожен в `.itd-memory/PILOT-P02-frozen-candidate.patch`,
   дерево `4cd424d4`).

## Прецедент (решение внутри юнита)
`SURFACE_TREADMILL` стоит ПОСЛЕ `REDESIGN_OR_DISCARD`/`RECURRENCE_UNCONFIRMED`
и ПЕРЕД `ROUTE_REPAIR`. Повтор одного ключа на добавленной поверхности бывает
и дефектом формы (S04b: блок пре-флайта чинили на месте, и он ломался снова) —
treadmill не имеет права перекрывать REDESIGN; хвостовой срыв транспорта не
обнуляет содержание окна вердиктов.

## Вне скоупа
- Фикстура LPD-003-3 для R7: деревья её раундов не восстановимы, а пометки «на
  добавленной поверхности» по памяти были бы выдумкой на уровне находок —
  отклонение от одобренного плана, записано в BACKLOG как follow-up.
- Продюсер, чекер, `validate_adjudication` — не меняются (маршрут ADR-007 для
  BLOCKED уже существует: `checker --accept-adjudicated-route`,
  `adjudicate --dispositions`).
- Установленный runtime: правило — скрипт репозитория, не устанавливается.

## Файлы (allowlist)
- `.itd/STOP_RULE_POLICY.json` (1.0.0 -> 1.1.0)
- `scripts/itd_stop_rule.py`
- `tests/verify_stop_rule.py`
- `tests/references/stop-rule/pilot-p02.json`
- `tests/references/stop-rule/evidence/PILOT-P02-r*.surface` (18),
  `tests/references/stop-rule/evidence/PILOT-P02-transcript-findings.json`
- `.itd/ACCEPTANCE_CONTRACT.json`, `.itd/SCOPE_LOCK.md`, `.itd/DECISIONS.md`,
  `.itd/IMPACT_GRAPH.json`, `BACKLOG.md`
- `.itd-memory/STATE.json`, `.itd-memory/events.jsonl`,
  `.itd-memory/contracts/STOPRULE-1.md`

## Статус 2026-09-03 — ЗАКРЫТ
PR #255 merged `ae95ca1` (дерево `23b71493`). Публикация: продюсер pub2 — чистый PASS (gpt-5.6-sol, committed-head), adjudication PASSED, CI Gate 1 + windows-verify pass. Юнит verified в STATE; остаток класса — STOPRULE-2 (BACKLOG).
