# Task contract — ROUTE-DEBTS-FOLLOWUP-A13 (high)

## Scope
Четыре находки Sol-a13, отложенные решением владельца 2026-09-07 (BACKLOG P1).
Поверхность заморожена: ровно эти четыре места и их регрессии, ничего сверх.

1. `skills/task/scripts/itd_unit_log.py` — `state_write_lock` открывает
   `.STATE.write.lock` по имени пути (`Path.open("a+b")`), то есть через ссылку;
   перевести на общий anchored no-follow примитив с требованием обычного файла
   с единственной жёсткой ссылкой (и владельцем на POSIX).
2. `tests/verify_independent_review_efficacy.py` —
   `validate_current_result_archive_binding` читает текущий вид
   `results/*.json` через `read_bytes()`; перевести на anchored no-follow
   ридер.
3. `skills/_shared/itd_safe_atomic_windows.py` — приватная проверка смотрит
   только `links == 1`; добавить сверку владельца объекта с владельцем
   процесса (паритет с правилом `st_uid` на POSIX).
4. `skills/_shared/itd_review_evidence.py` — `active_criteria` молча
   игнорирует явную строку с совпадающим `unitId` и нестроковым `id` и
   откатывается на legacy-подбор по префиксу; сделать fail-closed.

## Verification standards
- **RED-first обязателен для каждой из четырёх**: регрессия падает на текущих
  байтах и зеленеет после правки; наблюдённый переход, а не утверждение.
- Единственный источник DoD — поле `criterion` юнита `ROUTE-DEBTS-FOLLOWUP-A13`
  в `.itd-memory/GOAL.json`. Здесь оно намеренно не пересказывается.
- Verification: `sh skills/_shared/itd_py.sh tests/verify_route_debts.py` и
  `... --host-metadata` (verificationCommand юнита), плюс `bash tests/run-all.sh
  --quick`, где единственный допустимый красный — предшествующий кандидату
  `verify_reviewer_provider_freshness`.
- Пункт 3 исполняется НАТИВНО на Windows (адаптер не грузится на POSIX): на
  POSIX проба печатает SKIP с названной причиной, доказательство даёт нативный
  прогон и `windows-verify` в CI.

## Exclusions
- Никаких новых мест (surface treadmill): находка вне этих четырёх идёт в
  BACKLOG, а не в кандидата.
- Не трогать live-model evidence, efficacy history, кампанию Q6, гейты,
  провайдерские маршруты, релиз и раскатку.
- Правка `skills/**` по построению сдвигает пин live-model бенчмарка: перепин
  делается ОДИН раз на финальном дереве, отдельным шагом, до публикации.
