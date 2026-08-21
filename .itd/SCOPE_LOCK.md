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
  head консервативно блокирует. По находке cross-vendor PUB2: heredoc
  КОНЕЧЕН — разрез стейтментов распознаёт делимитер и продолжается после
  терминатора (`cat <<EOF…EOF` + `pytest` больше не глотается). Оракул:
  `tests/verify_completion_signal_classes.py` (15 -> 61 проверки, RED-first —
  оба display-кейса воспроизведены на старом коде; 43 на закрытии A2,
  +8 в hd-раундах: двойной heredoc, отступленный псевдо-терминатор,
  here-string; +3 PUB4: делимитер — общее слово, не только [A-Za-z0-9_];
  +3 PUB5: quote-aware голова сегмента — кавычный VAR-префикс с пробелами;
  +4 PUB6: опции обёрток env/time не голова; формы делимитера \\EOF и
  кавычные с пробелом).
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
- **LPD002-A8 (процедура authority-снапшота)** — раздел в
  `docs/VERIFICATION_LOOP.md` + `scripts/itd_authority_check.py` (байт-паритет
  в обе стороны, DIVERGED/MISSING, exempt ключей) + сьют
  `tests/verify_authority_check.py` (20 проверок — 12 на закрытии; 5 деталей процедуры прибиты
  в доке по находке PUB2), зарегистрирован в run-all. Живой replay назвал 3
  разошедшихся модуля; снапшот LPD002-A8-62eea6bb-a1 перечеканен из
  origin/main. По находке PUB3 (high): `--repo` обязан быть git-чекаутом
  (`.git` dir или worktree-файл, иначе exit 2) — сфабрикованная директория
  со `skills/_shared` больше не проходит как авторитет сравнения; в доке
  явно сказано, что merged-main provenance даёт процедура чеканки +
  запуск проверки в каноническом чекауте, а не сам байт-паритет
  (сьют 17 -> 20; по PUB4 dummy-.git отбит: чекаут валидируется самим git rev-parse --show-toplevel, worktree-файл .git легитимен только настоящий). Вторая находка PUB3 (medium): бухгалтерия счётчика
  оракула A2 сведена к фактическому значению суммы во всех леджерах
  (контракт A2 / ACCEPTANCE / BACKLOG / CHANGELOG / этот файл); после
  PUB4/PUB5/PUB6-регрессий фактическое значение — 61, все места обновлены
  вместе.
- **A4, A6 — реклассификация без кода**: A4 опровергнут замером R6 (ноги
  пинят только `itd_free_reviewer_producer.py` + раннер + манифест; корень
  live-пина отложен решением владельца — memory
  `feedback_live_benchmark_pin_friction`); A6 — правило «стейдж только явным
  списком» фиксируется доктриной (helpers/BACKLOG), гейт не строится.
- Леджер по ходу: `.itd/ACCEPTANCE_CONTRACT.json` (критерии `LPD002-A*`),
  `.itd-memory/contracts/LPD002-A*.md`, `.itd-memory/STATE.json`, BACKLOG
  (галочки с evidence), `.itd/DECISIONS.md`, CHANGELOG `[Unreleased]`.

## Записанные улики в дифе — это НЕ авторский код кандидата

Файлы под `tests/fixtures/live-model-evidence/` — НАБЛЮДЕНИЕ за поведением
внешней модели, записанное дословно; кандидат их не пишет и не проектирует.
`runs/*/output/*.md` (CLAUDE.md, PRD и т.д.) — документы, СГЕНЕРИРОВАННЫЕ
моделью под тестом; их содержание (включая внутренние противоречия хендоффа
или заявления о валидации) судится snapshot-оракулом бенчмарка, а не ревью
кандидата — находка о них есть находка о модели, «исправление» = фальсификация
улики. `transcript.jsonl.gz` НА ДИСКЕ — настоящий gzip (магия `1f8b`,
`gzip -t` проходит, sha совпадает с `transcriptGzipSha256`); ревьюер видит
его ПРОЗРАЧНЫМ ПРЕДСТАВЛЕНИЕМ продюсера (декодированный JSONL в дифе — фича
S11 «model-visible means logged», а не текстовый файл с расширением .gz).

## PUB5 (cross-vendor, gpt-5.6-terra) — разбор находок

- РЕАЛЬНАЯ (medium, hooks/completion_lib.py): `_segment_head_token` резал по
  пробелам — `NOTE="test output pending" cat >> HANDOFF.md` давал голову
  `output` и display-подавление не срабатывало (RED воспроизведён). Закрыто
  quote-aware разбиением `_shell_words` + `_ASSIGNMENT_RE`; оракул 54 -> 57.
- ОПРОВЕРГНУТА (medium, run-report.json attemptCount=1 vs attempts=2):
  attempt 2 несёт `phase: "devils-advocate"` — фичей S3 (merge 2a8da71,
  PR #195) attemptCount НАМЕРЕННО считает только blueprint-попытки, а
  attempts[] дополнительно хранит фазовые записи для точного покрытия
  транскрипта (комментарий в рекордере, строки ~1257). Записанный артефакт
  НЕ правится (фальсификация улики); корень «артефакт не самоописателен»
  закрыт полем `attemptCountBasis` в рекордере для будущих записей.

## PUB6 (cross-vendor, gpt-5.6-terra) — разбор находок

Обе реальные (medium, hooks/completion_lib.py), закрыты корнем + 4 регрессии:
опции обёрток (`env -i`, `time -p`) не считаются головой сегмента; слово
heredoc-делимитера принимает формы `\\EOF` (экранирование) и кавычные с
пробелами (`'END MARK'`) — нераспознанный делимитер больше не превращает
хвост в display-поглощение. Оракул 57 -> 61.

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
