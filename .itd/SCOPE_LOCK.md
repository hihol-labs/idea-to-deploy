# Scope Lock — PRG-004 / release v1.100.1

## Current Task

Live native-Windows pre-push canary обнаружил release-blocker после PR #224:
content-addressed runtime не включал транзитивную exact-context цепочку:
`skills/review/scripts/itd_review_cache.py`, review skill и оба rubric-файла,
которые загружаются по абсолютным путям при revalidation exact-candidate
receipt. Source-tree doctor был GREEN, installed runtime последовательно
нашёл отсутствующие cache module и meta rubric и fail-closed вернул
`UNVERIFIED`, поэтому PR нельзя было разместить.

После закрытия PRG-003 CI PR #225 потребовал новый current-tree live evidence.
Bounded run показали второй release-blocker: Codex-модели читали
repository-local blueprint, но после command-safety отказов PowerShell ложно
объявляли workspace read-only; после первой prompt-починки native `apply_patch`
сам подтвердил внешний sandbox denial. Claude Skill fork терял product prompt.
PRG-004 разрешает только host-boundary инструкции и их preflight:

- `tests/fixtures/fixture-03-cli-tool/live-prompt.md`;
- `tests/run-live-model-benchmark.py` (только fail-closed prompt preflight);
- `tests/verify_live_model_benchmark.py`;
- generated `tests/fixtures/live-model-evidence/**` после реального run;
- `.itd/{SCOPE_LOCK.md,ACCEPTANCE_CONTRACT.json,IMPACT_GRAPH.json}`;
- `.itd-memory/{STATE.json,contracts/PRG-004.md,ROOT_CAUSE-PRG-004.md}`;
- `CHANGELOG.md`.

PRG-003 разрешает только корневое закрытие этого runtime inventory gap:

- `scripts/itd_install_runtime.py`;
- `tests/verify_itd_runtime_install.py`;
- `docs/CODEX_ADAPTER.md`, `docs/RELEASE_RUNBOOK.md`;
- `.itd/SCOPE_LOCK.md`, `.itd/ACCEPTANCE_CONTRACT.json`, механически
  регенерированный `.itd/IMPACT_GRAPH.json`;
- `.itd-memory/STATE.json`, `.itd-memory/contracts/PRG-003.md`,
  `.itd-memory/ROOT_CAUSE-PRG-003.md`;
- `CHANGELOG.md`.

Patch release также сохраняет уже проверенные канонические version surfaces:

- `.claude-plugin/{plugin,marketplace}.json`, `.codex-plugin/plugin.json`;
- `README.md`, `README.ru.md`, `CHANGELOG.md`;
- `docs/HARNESS_CONFORMANCE_REPORT.md`, `docs/HARNESS_DOCS_STATE.json`,
  `docs/api-reviewer/RELEASE_CANDIDATE_CONTRACT.json`;
- version canary `tests/verify_external_reviewer_release.py`;
- этот release scope.

## Forbidden Change Areas

- Никаких reviewer/gate semantics, receipt/keyring, hook logic, broker/App или
  version-parser изменений; generated evidence пишет только bounded runner.
- PRG-004 не меняет sandbox/approval flags, model routing, fixture product
  contract, snapshot oracle или pin policy; runner меняется только fail-closed
  preflight-проверкой этой директивы; generated evidence пишет только runner.
- Не расширять runtime inventory за пределы доказанного path-loaded набора
  exact-context review cache (module + skill + standard/meta rubrics).
- Не переписывать историю `v1.100.0`; новый раздел — только `v1.100.1`.
- Tag/release/rollout выполняются только после merge release PR и зелёного CI.

---

## Previous verified scope — LPD-002 debts (A1-A9)

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
  `tests/verify_completion_signal_classes.py` (15 -> 83 проверки, RED-first —
  оба display-кейса воспроизведены на старом коде; 43 на закрытии A2,
  +8 в hd-раундах: двойной heredoc, отступленный псевдо-терминатор,
  here-string; +3 PUB4: делимитер — общее слово, не только [A-Za-z0-9_];
  +3 PUB5: quote-aware голова сегмента — кавычный VAR-префикс с пробелами;
  +4 PUB6: опции обёрток env/time не голова; формы делимитера \\EOF и
  кавычные с пробелом; +4 PUB7: system ( с пробелом — исполнение;
  операнды опций env -u/-C/-S и time -f/-o; +2 envelope: неуверенный
  разбор never-display; +3 env-r1: top-level escape, $'...', висящая
  кавычка; +2 env-r2: операторы стейтментов в строке
  открытия heredoc -> uncertain; +3 env-r3: $(...) и backticks ->
  uncertain, слова без головы -> не display; +2 env-r4: подстановка
  процесса <(...)/>(...) -> uncertain, обычные редиректы display;
  env-r5: sed/awk исключены из display-набора — интерпретаторы с
  неперечислимыми exec-диалектами, проверки объединены; +2 env-r6:
  длинные опции display-инструментов -> не display, голый -- безопасен;
  +5 PUB8B: одиночный & -> uncertain при сохранении 2>&1/>&2/&>file,
  стейл-фильтр HEAD до выбора latest-на-команду).
- **LPD002-A517 (кластер itd_review_evidence)** — `skills/_shared/
  itd_review_evidence.py`: A5 класс ledger-close принимает леджер-файлы,
  ОБЪЯВЛЕННЫЕ в STATE (не произвольный третий путь); A1 выбор критериев
  контракта — точная принадлежность юниту, не префикс `unitId + "-"`;
  A7 один проход `_staged_file_records` на `freeze_packet` (+ факт
  `stateBefore` из base-блоба STATE). Оракул:
  `tests/verify_review_evidence.py` (7×a5, 2×a1 + усиление a1 по PUB8B;
  фактический счёт — 50 PASS-строк прогона: 43 в заявке A517 считались по
  top-level `check(`-вызовам, часть проверок печатается из циклов).
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
  PUB4/PUB5/PUB6/PUB7/envelope/PUB8B-регрессий фактическое значение — 83,
  все места обновлены вместе.
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

## PUB7 (cross-vendor, gpt-5.6-terra) — разбор находок

- РЕАЛЬНАЯ (high, completion_lib): `_EXEC_MARKER_RE` матчил только литеральный
  `system(` — awk допускает пробел перед скобкой; `system\\s*\\(` + регрессия.
- РЕАЛЬНАЯ (medium, completion_lib): опции обёрток с отдельным аргументом
  (`env -u CI`, `time -f '%E'`) делали операнд головой сегмента — операнд
  теперь пропускается (env -u/-C/-S, time -f/-o) + 3 регрессии. Оракул 61->65.
- ЛОЖНАЯ (medium, itd_review_evidence «extra-леджер без проверки M»):
  `modifiedPaths` — это строки со статусом M у продюсера
  (itd_free_reviewer_producer.py:913), а политика требует
  `set(modified) == changed` (itd_review_evidence.py:212) — added/deleted/
  type-changed extra-строка меняет равенство и класс отклоняется; оракул уже
  прибивает ровно этот сценарий проверкой `a5-extra-file-must-be-a-modification`
  (tests/verify_review_evidence.py:459). Код не менялся.

## Envelope display-подавления (структурная граница, после PUB7)

Шесть PUB-раундов подряд находили edge-кейсы рукописного разбора shell —
поверхность неограничена. Структурное закрытие класса: display-подавление
работает на ЯВНО ограниченном подмножестве shell (пайпы, &&/||/;/NL,
heredoc с распознанным словом-делимитером и найденным терминатором,
here-string, кавычки/экранирование, обёртки env/command/nohup/time с их
опциями). ВСЁ вне подмножества — `_UncertainShellParse` -> команда НЕ
display, сигналы сохраняются. Асимметрия отказа задекларирована: худший
случай неуверенного разбора — ложный КРАСНЫЙ (снимается чистым перезапуском
команды), никогда не ложное зелёное (подавление реального сигнала).
Находка «конструкция X не разбирается» отныне опровергается этой границей,
если X вне подмножества и падает в never-display; находкой остаётся только
(а) конструкция ВНУТРИ подмножества, разобранная неверно, или (б) путь, где
неуверенный разбор всё же даёт display/подавление. Первый же чекер
envelope-r1 нашёл ровно (а): идиома `'...'\\''...'` и `$'...'`
рассинхронизировали сканер (top-level `\\` не понимался) — escape вне
кавычек теперь в подмножестве, `$'...'`/`$"..."` и незакрытая кавычка —
uncertain (никогда не display). env-r2 нашёл (б): `cat <<EOF && pytest`
— хвост строки открытия heredoc поглощался; операторы стейтментов в этой
строке теперь uncertain. env-r3 нашёл ещё (а): RESULT=$(pytest ...)
— подстановка команды и пустая голова сегмента; $(...) и `...`
теперь uncertain, слова-без-головы — не display. env-r4: подстановка
процесса <(...)/>(...) — uncertain. env-r5: exec-диалекты sed/awk
(голый e, print|"cmd", getline, не-GNU) неперечислимы — sed/awk выведены
из display-набора целиком; цена — обычные sed -n/awk-печать больше не
подавляются (возможен ложный красный, снимается перезапуском без sed/awk),
ложное зелёное через них исключено. env-r6: argv-исполнители через
длинные опции (sort --compress-program, rg --pre; не-GNU варианты
неперечислимы) — любой токен `--...` кроме голого `--` снимает
display-гарантию; цена — grep --line-buffered и т.п. не подавляются.

## PUB8B (cross-vendor, gpt-5.6-terra) — разбор находок

- РЕАЛЬНАЯ (high, completion_lib): разрез знал `&&`, но не одиночный `&` —
  `cat HANDOFF.md & pytest` целиком считался display и глотал прогон
  переднего плана. Закрыто: одиночный `&` -> uncertain (никогда не display);
  дублирование дескриптора (`2>&1`, `>&2`, `<&3`) и `&>file` остаются
  редиректами внутри сегмента. RED воспроизведён, 2 регрессии.
- РЕАЛЬНАЯ (medium, completion_lib): стейл-фильтр по HEAD стоял ПОСЛЕ
  выбора latest-на-команду, поэтому чужой прогон вытеснял действующий
  красный своей команды, а затем сам отфильтровывался -> слой `unknown`
  вместо `fail`. Закрыто переносом фильтра до выбора; 3 регрессии
  (чужой не вытесняет; свой зелёный вытесняет; только чужие -> unknown).
- РЕАЛЬНАЯ (medium, ACCEPTANCE): критерий LPD002-A2-1 всё ещё перечислял
  sed/awk среди display-инструментов вопреки env-r5. Текст критерия
  приведён к поведению (sed/awk исключены, diff/comm — verification,
  длинные опции и выход за envelope снимают гарантию).
- ЛОЖНАЯ (medium, tests/verify_review_evidence.py «a1-фикстура наследует
  unitId=R1»): базовая фикстура поля `unitId` НЕ несёт (acceptance_fixture
  задаёт его только в activeFollowup), поэтому `foreign` исключается
  правилом «явный набор побеждает префикс» (itd_review_evidence.py:275-287),
  а не игнорированием данных. Проверка усилена отдельным сценарием, где
  чужой критерий несёт ЯВНЫЙ чужой unitId и всё равно исключён при
  совпадении префикса. Побочно измерено и сведено: сьют печатает 50
  PASS-строк, а леджер заявлял 43 (считались top-level check()-вызовы).

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
