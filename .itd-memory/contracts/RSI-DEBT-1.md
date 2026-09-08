# Task contract — RSI-DEBT-1 (medium)

## Scope
Скраббер секретов ревью (`skills/_shared/itd_external_reviewer.py`, `SECRET_PATTERNS`
и `scrub()`) редактирует значение любого присваивания с именем на
`password|passwd|api_key|secret|token`, включая обычный код вида
`token = self.w.HANDLE()`. Наблюдено живьём: Sol-fa2 по ROUTE-DEBTS-FOLLOWUP-A13
выдал ложную high-находку «NameError на `token = [REDACTED]`» против кода, который
зелёный нативно. Задача: редактировать только значения, похожие на литерал
(строка в кавычках, непрерывный непрозрачный ран), оставляя выражения-вызовы
и прочие не-литералы нетронутыми; настоящие ключи корпуса
`tests/verify_scrubber_precision.py` редактируются как прежде.

## Verification standards
- RED-first на обеих формах: до правки вызов-выражение редактируется (RED),
  после - нет (GREEN); каждый реальный секрет корпуса редактируется до и после.
- Летальность мутацией: ослабление правила, пропускающее литерал, и правило,
  снова режущее вызов, - обе мутации роняют оракул.
- Единственный источник DoD - поле `criterion` юнита `RSI-DEBT-1` в
  `.itd-memory/GOAL.json`; здесь оно не пересказывается.
- Verification: `sh skills/_shared/itd_py.sh tests/verify_scrubber_precision.py &&
  sh skills/_shared/itd_py.sh tests/verify_free_reviewer_producer.py`
  (verificationCommand юнита); плюс `bash tests/run-all.sh --quick`, где
  единственный допустимый красный - предшествующий `verify_reviewer_provider_freshness`.
- Маршрут (решение владельца 2026-09-08, вариант а): код -> `/test` ->
  **`/review`-субагент** (пополняет популяцию слепого протокола) -> машинная
  квитанция -> cross-vendor продюсер -> адъюдикация -> коммит.

## Exclusions
- Не ослаблять редактирование настоящих секретов; не добавлять новые классы
  секретов и новые правила сверх двух assignment-shaped.
- Никаких новых мест (surface treadmill): находка вне скоупа - в BACKLOG.
- Правка `skills/**` сдвигает пин live-model бенчмарка: один перепин на
  финальном дереве, отдельным коммитом, до публикации.
