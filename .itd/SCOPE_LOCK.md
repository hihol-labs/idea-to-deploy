# SCOPE_LOCK — STOPRULE-2 (открыт 2026-09-03)

## Предмет
Правило остановки ревью `scripts/itd_stop_rule.py` получает право РЕШАТЬ
остановку: на терминалах решения владельца (`REDESIGN_OR_DISCARD`,
`SURFACE_TREADMILL`) оно само составляет черновик диспозиций ADR-007 по
BLOCKED-квитанции чекера (`--emit-dispositions <receipt> --out <file>`), а
человек заполняет класс и основание каждой строки и подписывает одной закрытой
фразой. Статус политики `advisory` -> `decides-with-human-confirmation`
(1.1.0 -> 1.2.0). Форма утверждена владельцем 2026-09-03: «правило составляет,
человек подписывает»; гейтом правило не становится.

## Замер ДО правки (2026-09-03)
- STOPRULE-1 (PR #255): R7 доставлен, но маршрут ADR-007 ручной — владелец
  составлял диспозиции сам (`.itd-memory/stop-rule/draft_dispositions.py`,
  untracked-черновик), правило лишь называло терминал.
- На одном дереве `d2ff7ed7` r26 = PASS, pub1 = BLOCKED (4 реальные находки):
  вердикт независимого ревьюера на одном кандидате — случайная величина, поэтому
  остановку должна решать машина по окну серии, а человек — подтверждать.
- PILOT-P02 заморожен на r73 (2 открытые находки r58, кандидат —
  `.itd-memory/PILOT-P02-frozen-candidate.patch`); по реплею правило остановило
  бы серию на r14.

## Разрез
1. **Код**: `emit_dispositions()` + CLI `--emit-dispositions/--out`; черновик =
   по одной строке на уникальную находку и пункт unverified (дайджест —
   `itd_verification_loop.finding_digest`), точная фраза подписи
   `CONFIRMATION_TEMPLATE` с sha256 квитанции, класс/основание/подписант —
   плейсхолдер `ЗАПОЛНИТЬ`; отказ на терминале продолжения, на не-BLOCKED
   вердикте, на пустой квитанции. FIX-текст R7 называет маршрут.
2. **Политика 1.2.0**: `status`, `statusNote`, блок `humanConfirmation`
   (terminals, placeholder) — заморожены загрузчиком.
3. **Оракул**: +16 проверок (черновик, валидатор маршрута принимает
   заполненный и отвергает незаполненный, отказы, CLI exit 0/2); мутации 10/10.
4. **Документация**: `docs/VERIFICATION_LOOP.md` — статус, команда, R7 в порядке
   применения (там его не было — дрейф со STOPRULE-1 закрыт здесь).
5. **Закрытие PILOT-P02** этим маршрутом — ПОСЛЕ публикации кода: свежая ветка
   от main, замороженный патч по существу (13 файлов), заход продюсера,
   `--emit-dispositions`, заполнение и подпись ВЛАДЕЛЬЦЕМ, adjudicated-маршрут,
   PR. Без подписи владельца P02 не закрывается.

## Вне скоупа
- Вшивание вызова правила в цикл продюсера после каждого BLOCKED (BACKLOG).
- Фикстура LPD-003-3 для R7; вырождение ключа `(file, category)`.
- Продюсер и чекер не меняются; маршрут `--accept-adjudicated-route` /
  `adjudicate --dispositions` уже существует и не переделывается. В
  `validate_human_adjudication` — ТОЛЬКО отказ на плейсхолдере черновика
  (поправка c1, см. allowlist); схема блока, классы и фраза подписи прежние.
- Установленный runtime: правило — скрипт репозитория.

## Файлы (allowlist)
- `.itd/STOP_RULE_POLICY.json` (1.1.0 -> 1.2.0)
- `scripts/itd_stop_rule.py`, `tests/verify_stop_rule.py`
- `skills/_shared/itd_verification_loop.py` — ТОЛЬКО константа `DRAFT_PLACEHOLDER`
  и отказ `validate_human_adjudication` на плейсхолдере в confirmedBy /
  rationale / evidence (поправка скоупа по находке чекера c1: гарантия
  «валидатор не принимает плейсхолдер» держалась только на `class`).
- `docs/VERIFICATION_LOOP.md`
- `.itd/ACCEPTANCE_CONTRACT.json`, `.itd/SCOPE_LOCK.md`, `.itd/DECISIONS.md`,
  `.itd/IMPACT_GRAPH.json`, `BACKLOG.md`
- `.itd-memory/STATE.json`, `.itd-memory/events.jsonl`,
  `.itd-memory/contracts/STOPRULE-2.md`

## Статус 2026-09-04 — ЗАКРЫТ
PR #257 merged `6d38631` (дерево `082de5ad`). Публикация — adjudicated-маршрут: правило
остановило собственную серию (r3-r5, один ключ `scripts/itd_stop_rule.py::correctness`)
на r4, составило диспозицию r5, владелец подписал `accepted-trade-off`, квитанция
`ADJUDICATED`. Пункт 5 разреза (закрытие PILOT-P02) — следующим юнитом
PILOT-P02-CLOSE: WIP=1 и собственный контракт приёмки P02.
