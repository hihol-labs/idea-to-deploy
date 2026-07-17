# /review — runner, report-файл и восстановление вердикта (справочник)

Вынесено из SKILL.md (progressive disclosure, v1.73.0): в SKILL.md — правила,
здесь — обоснования, история отказов и детали контрактов. Читать при отладке
runner'а/ревьюеров, не при каждом ревью.

## §0 Fork-thrash: почему при большом CLAUDE.md форк не годится (v1.24.0)

Скилл объявлен `context: fork`. Форк наследует **копию текущего разговора**,
включая корневой `CLAUDE.md` проекта. Когда тот большой (тяжело-онбордженные
репо: эмпирически **> ~12 KB**, или в сессии уже был autocompact-churn), форк
стартует у потолка контекста и **autocompact-трэшится до смерти**, не выдав
вердикта. Каверза: Step 0 читается уже ВНУТРИ форка — форк уже существует;
диспатч Agent-tool из форка возможен, поэтому размер-чек и переключение на
Agent-диспатч делаются ПЕРВЫМ действием, до загрузки любого контекста.

Это частный случай общего правила **stall-resilience**: на ЛЮБОЙ затык
субагента (watchdog timeout, autocompact death, пустой возврат) свежий узкий
агент — АВТОМАТИЧЕСКИЙ фолбэк, не ручной вопрос «resume or retry?». См.
`skills/_shared/helpers.md` §9.

## §0-report Контракт report-файла (v1.72.0 — root cause 2026-07-09)

Три длинных (9–15 мин) ревью-прогона за один день были убиты харнесом
mid-stream и отрапортованы «completed» с пустым финалом — готовый отчёт жил
только в транскрипте. Правило: файл на диске делает работу невыгораемой —
**file = contract, final message = transport**.

- Путь — предпочтительно ВНЕ git-дерева review-цели (scratchpad/tempdir;
  `claude-review-<slug>.md`); если внутри дерева — добавь/посоветуй
  `claude-review-*.md` в `.gitignore` цели и удали файл после принятия вердикта.
- Требование агенту: писать findings в файл ИНКРЕМЕНТАЛЬНО по ходу ревью
  (контракт — «Report file» в `agents/code-reviewer.md`), вердикт + ```json-блок
  кладутся в файл ДО финального сообщения.
- При обрыве/пустом финале: **сначала прочитай report-файл** (полный файл на
  диске = результат, ничего переспрашивать не надо), потом Step 2.7 re-ping, и
  только затем fresh narrow (helpers §9, finish-line class).

## §2.7 Belt and suspenders: история и слои защиты вердикта (v1.60.0)

Исторический отказ: субагент возвращался без вердикта (нарратив процесса,
повисшее «далее проверю…», autocompact-смерть), и человек вручную пинговал
«выдай итог одним сообщением» — драг №1, ×4 за одну сессию. Step 2.7 делает
восстановление **механическим и caller-side** — кондуктор ре-пингует сам.

Почему детекция — по ОТСУТСТВИЮ маркера, а не по регексу прозы: единственный
надёжный вопрос — «есть ли маркер вердикта» (```json-блок канонический; голые
слова PASSED/BLOCKED — сознательная толерантность, чтобы валидный вердикт с
поломанным JSON-фенсингом не зациклил re-ping; полноту JSON-блока отдельно
enforce'ит `verdict-contract.sh`, двойного гейта нет). Регекс-угадывание
нарратив-опенера — работа subagent-side хука, никогда не caller'а; расширять
нарратив-регекс строго менее надёжно, чем проверять наличие маркера.

**Empty return = тот же класс (v1.72.0):** длинный диспатч, вернувшийся
«completed» с ПУСТЫМ финалом — мислейбл харнеса для mid-stream kill,
finish-line interruption class (helpers §9; root cause 2026-07-09, 3/3
восстановлены одним ре-пингом). Перед пингом читай report-файл из диспатча.

Слои: caller-side Step 2.7 — *ремень*; два SubagentStop-хука — *подтяжки*,
ловят дефект на границе субагента, до кондуктора: `hooks/narration-final.sh`
блокирует стоп с повисшим нарратив-опенером без маркера (возвращая субагенту
resume-инструкцию), `hooks/verdict-contract.sh` блокирует прозаический вердикт
без machine-readable ```json-блока. Если харнес уронит SubagentStop-хуки
(vendor/version switch — best-effort invariant), подтяжки тихо исчезают, но
задокументированный caller-side ремень всё равно восстанавливает вердикт; слои
деградируют независимо, никогда — в ложный green.

## §5 Exact-context review cache и risk-budget

- `Skill` не обязан проходить через host-specific `PreToolUse`, поэтому
  финальный Step 5 вызывает model-neutral producer
  `skills/review/scripts/itd_review_cache.py` явно, после принятия независимого
  вердикта caller'ом. Generic `SubagentStop` не несёт аутентифицированный тип
  workflow: `verdict-contract.sh` проверяет JSON и пишет только non-gating
  findings ledger, но не может создать cache evidence.
- Ключ кэша не имеет wildcard-полей: resolved repository, base commit,
  staged tree, binary diff hash, hashes scope/acceptance contracts,
  applicable rubric, methodology version и active risk tier. Любое
  расхождение закрывает commit gate.
- Только accepted status открывает gate. `BLOCKED`, `UNVERIFIED` и
  malformed/empty warnings записываются fail-closed и не могут
  переиспользовать старый pass.
- Risk-budget разделён на `general_score` и `security_score`.
  Успешный ordinary review гасит только general bucket,
  security audit — только security bucket. После gate в threshold
  входит только новый delta.
