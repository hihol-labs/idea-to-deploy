# Scope Lock — сессия долгов LPD-002 (A1-A9), ветка fix/lpd002-debts

## Current Task

Решение владельца 2026-08-20: отдельная сессия закрывает девять долгов,
порождённых планом LPD-002 (BACKLOG «P1 — найдено в сессии R5 / при доставке
R6» + «P1 — дефекты маршрута R1»), и только затем стартует GENG-S02.
Прецедент формата — S9 (harness debts): юнит = долг/кластер долгов, WIP=1,
каждый коммит через полный Verification Loop (machine -> свежий чекер ->
adjudicate -> record). Тир: medium (правки гейтов ревью/completion).
Шаг 0 выполнен: снапшот телеметрии
`.itd-memory/telemetry-snapshots/2026-08-20-pre-debts/` (signals.jsonl был
ровно на пределе MAX_LEDGER_LINES=2000 — baseline GENG-S02 защищён).

## Юниты и зоны правок

- **LPD002-A2 (стейл-оценщик completion-гейта)** — `hooks/completion_lib.py`:
  (1) display/write-команды (каждый сегмент пайпа — display-инструмент:
  cat/grep/sed/tail/...) НЕ являются runtime-сигналом, каким бы L2-паттернам
  ни матчилась строка (замерено: heredoc `cat >> HANDOFF.md` и
  `grep ... tests/run-all.sh` классифицировались как test_run и вешали вечный
  FAILED); (2) идентичность «latest-на-команду» — нормализованная команда
  (`normalize_command_key`: display-хвосты пайпа и хвостовые редиректы
  отбрасываются; сплит quote-aware) — зелёный повтор `cmd | tail` вытесняет
  красный `cmd | grep`; (3) сигнал несёт `head` (короткий HEAD на момент
  прогона), красный от ЧУЖОГО HEAD — стейл и слой не блокирует; сигнал БЕЗ
  head консервативно блокирует. Оракул:
  `tests/verify_completion_signal_classes.py` (15 -> 43 проверок, RED-first —
  оба display-кейса воспроизведены на старом коде).
- **LPD002-A517 (кластер itd_review_evidence)** — `skills/_shared/
  itd_review_evidence.py`: A5 класс ledger-close принимает леджер-файлы,
  ОБЪЯВЛЕННЫЕ в STATE (не произвольный третий путь); A1 выбор критериев
  контракта — точная принадлежность юниту, не префикс `unitId + "-"`;
  A7 один проход `_staged_file_records` на `freeze_packet` (+ факт
  `stateBefore` из base-блоба STATE). Оракул:
  `tests/verify_review_evidence.py` (34 -> 43 проверки: 7×a5, 2×a1).
  Правка продюсера инвалидировала три подписанные efficacy-ноги — все три
  перечеканены живьём в этом юните (wsl + u12-cross-vendor на новом транспорте
  2e863156/0.146.0; windows через PowerShell/UNC, bc343ba4; verifier PASSED,
  hostParityVerified, cleanFalseBlockRate 0.0; ловушка: u12 требует
  `--maker-provider anthropic-subscription`, голое `anthropic` отвергается
  провенансом).
- **LPD002-A39 (маршрутные мелочи)** — `skills/_shared/itd_verification_loop.py`
  (чекер fail-closed при смене дерева кандидата между прогоном и чеканкой),
  `tests/run-all.sh` (красный сьют печатает свои строки FAIL, не только
  tail -6).
- **LPD002-A8 (процедура authority-снапшота)** — `docs/VERIFICATION_LOOP.md`
  или отдельный runbook-раздел + машинная проверка байт-паритета модулей
  снапшота с `skills/_shared/*` (скрипт + сьют).
- **A4, A6 — реклассификация без кода**: A4 опровергнут замером R6 (ноги
  пинят только `itd_free_reviewer_producer.py` + раннер + манифест; корень
  live-пина отложен решением владельца — memory
  `feedback_live_benchmark_pin_friction`); A6 — правило «стейдж только явным
  списком» фиксируется доктриной (helpers/BACKLOG), гейт не строится.
- Леджер по ходу: `.itd/ACCEPTANCE_CONTRACT.json` (критерии `LPD002-A*`),
  `.itd-memory/contracts/LPD002-A*.md`, `.itd-memory/STATE.json`, BACKLOG
  (галочки с evidence), `.itd/DECISIONS.md`, CHANGELOG `[Unreleased]`.

## Явно вне скоупа

- Корень live-benchmark пина (`METHODOLOGY_TREE_ROOTS`) — отложен владельцем.
- GENG (любая фаза) — только после этой сессии.
- Исторический замороженный пруф `tests/verify_operating_loops_release.py`
  (VERSION=1.94.0 захардкожен, в run-all НЕ зарегистрирован, красный на
  немодифицированном дереве — pre-existing, зафиксирован наблюдением).
- Скраббер, подписи, ключи, новые вендоры/транспорты.

## Принцип

Долг закрывается корнем с RED-first воспроизведением измеренного инцидента и
мутациями в обе стороны; «неактуальный» долг закрывается ЗАМЕРОМ, а не
галочкой. Один live re-record в конце ветки вместо перезаписи на каждый
коммит: промежуточные machine-квитанции не требуют live-оракула, он входит
только в publication claim.
