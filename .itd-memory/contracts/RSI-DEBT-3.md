# Task contract — RSI-DEBT-3 (low)

## Scope
1. `itd_goal_verify.py`: для `verificationCommand` вида `A && B` evidence
   юнита - одна строка на каждую верхнеуровневую команду в форме
   `<command>: exit <code>, stdout sha256 <16 hex>, <last line>`; терминальное
   событие повторяет ту же сводку; одиночная команда сохраняет прежнюю форму
   и прежний обрез в 200 символов.
2. Сплиттер моделирует ровно одну форму - цепочку `&&` верхнего уровня с
   учётом кавычек; любой другой оператор верхнего уровня (включая неэкранированный
   `#` и завершающий `\`) - ОТКАЗ и legacy-форма, не догадка; единственный `&`
   вне `&&` - дублирование дескриптора `>&`/`<&` (`2>&1`).
3. Цепочка исполняется в ОДНОМ шелле с покомандным захватом вывода и статуса;
   `&&` короткое замыкание сохранено; команда, которую шелл начал и не
   завершил, записывается с кодом выхода шелла и юнит не верифицируется.
4. Записи: `.itd/RSI-DEBT-3_ROOT_CAUSE.md` (причина, разрешение, таблица
   мутаций, отчёт ревьюера, объявленные пределы), строки приёмки
   `RSI-DEBT-3-1..3`; `.itd/IMPACT_GRAPH.json` перегенерирован механически
   (оракул `verify_verification_profiles` требует свежую карту после правки
   `tests/verify_goal_tools.py`).

## Verification standards
- RED-first: 5 красных проверок на байтах `e97fc7c` (72/5) до единой правки
  кода; первая зелёная точка 80/0; итог 83/0 после трёх проверок, добавленных
  по дырам, найденным вопросом ревьюера (`#`, `2>&1`) и объявленному пределу
  (завершающий `\`) - они доказаны мутацией, не RED-first, и записаны так.
- Запечатанная команда: `sh skills/_shared/itd_py.sh tests/verify_goal_tools.py
  && sh skills/_shared/itd_py.sh tests/verify_goal_bounded_autonomy.py` -
  83/0 и 42/0, exit 0.
- Мутации: 12/12 летальны в одноразовом worktree (M1-M9, M11-M13), одна
  мутация - одна гарантия, после прогона worktree и живое дерево идентичны.
  M10 выжила как мёртвая избыточность и удалена, не оставлена прозой; M4 в
  первом варианте тоже выжила и вскрыла настоящий дефект (недописанный статус
  наследовал ноль предыдущей ноги -> ложный verified), закрытый фикстурой
  `A && exit 3` и мутацией M9.
- Зеркало: кандидат `DONE fails: verify_verification_profiles
  verify_reviewer_provider_freshness verify_ledger_reconciliation
  verify_mandatory_keyless_review`; чистый `e97fc7c` в отдельном worktree
  `DONE fails: verify_reviewer_provider_freshness verify_ledger_reconciliation
  verify_mandatory_keyless_review blocked: verify_independent_review_efficacy`.
  Разность = `verify_verification_profiles` = дрейф карты IMPACT_GRAPH от
  правки теста; закрыт перегенерацией (`FRESH`). Финальное зеркало кандидата:
  `DONE fails: verify_reviewer_provider_freshness verify_ledger_reconciliation
  verify_mandatory_keyless_review` - ровно набор чистого `main`.
- Независимое ревью: субагент code-reviewer по юниту целиком vs `main` -
  PASSED, 2 minor, 4 unverified (три захода из-за лимита ходов). Кросс-вендорный
  продюсер по юниту целиком - как evidence; на low-risk его PASS к гейту не
  привязывается (записанный долг P1). Дельта-режим не засчитывается.
- Host parity: `.resolve()` на корне захвата виден только ноге windows-verify.
