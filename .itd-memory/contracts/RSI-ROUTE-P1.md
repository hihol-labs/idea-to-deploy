# Task contract — RSI-ROUTE-P1 (medium)

## Scope
`skills/_shared/itd_free_reviewer_producer.py::_transparent_review_representation` (ветка,
когда в staged-кандидате есть объявленный transparent-файл `.jsonl.gz`) возвращает
`diff_text` после `scrub()`, а по-файловые `chunks` режет из сырых байтов, поэтому при
любой редактируемой строке `"".join(chunks) != diff_text` и
`itd_review_broker._review_units` отказывает: «hierarchical review unit coverage is
invalid» (UNVERIFIED, exit 4) до вызова модели. Наблюдено живьём: RSI-DEBT-1 cp1 на
ветке с re-pin (первое расхождение - критерий юнита в GOAL.json). Задача: резать chunks
из того же скраббленного текста, что возвращается (как это уже делает
`_raw_review_file_chunks` для обычной ветки), и закрепить равенство тестом.

## Verification standards
- RED-first: запечатанная фикстура (один `.jsonl.gz` + одна редактируемая строка) на
  до-фиксовых байтах отвергается с точной причиной, на кандидате партиционируется.
- Мутация «chunks из сырых байтов» роняет оракул; обычная ветка и все пины скраббера
  не меняются (`verify_scrubber_precision` зелёный без правок).
- Единственный источник DoD - поле `criterion` юнита `RSI-ROUTE-P1` в
  `.itd-memory/GOAL.json`; здесь оно не пересказывается.
- Verification: `sh skills/_shared/itd_py.sh tests/verify_free_reviewer_producer.py &&
  sh skills/_shared/itd_py.sh tests/verify_scrubber_precision.py`; плюс
  `bash tests/run-all.sh --quick`, где единственный допустимый красный -
  `verify_reviewer_provider_freshness`.
- Маршрут: код -> `/test` -> `/review`-субагент (финал с прозой `Verdict:`) ->
  машинная квитанция -> cross-vendor продюсер (установленный 1.103.1: в staged-диффе
  НЕ должно быть `.jsonl.gz` вместе с редактируемой строкой) -> адъюдикация -> коммит ->
  re-pin отдельным коммитом -> публикация.

## Exclusions
- Не трогать `itd_external_reviewer.py` и `itd_review_broker.py`; не ослаблять отказ по
  sensitive material; никаких новых мест (surface treadmill) - находка вне скоупа в BACKLOG.
- Релиз и раскатка - следующий юнит REL-1.104.0.
