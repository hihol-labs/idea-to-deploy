# ROOT CAUSE — S2: недетерминизм machine-оракула и флейк session_hygiene

**Дата:** 2026-08-12 · **Юнит:** S2 (PLAN-CLOSEOUT-2026-08-11) · **Статус:** причины запинены

Закрывает два пункта BACKLOG «P0» от 2026-08-11: (A) full-suite интерференция
machine-оракула U16; (B) одноразовый флейк `verify_session_hygiene_quality`
(«close rejects dirty git state»).

## Summary (одно предложение на причину)

- **Общий корень (A и B):** транзиентный отказ спавна субпроцесса на хосте
  (fork → `EAGAIN`/`BlockingIOError [Errno 11]` при давлении на общий
  user-wide пул процессов/памяти WSL2 в окна параллельных сессий), помноженный
  на количество спавнов в проверяемом контуре.
- **B конкретно:** незащищённый `subprocess.run` в `git()`
  (`docs/templates/itd/itd_hygiene.py`) превращал такой отказ в необработанный
  крэш `close` — rc=1 при **пустом stdout**, что тест читал как неверный
  вердикт гейта («working tree is dirty» отсутствует), а не как сбой хоста.

## Evidence

1. **Квитанции оракула** (`.itd-memory/verification-loop/receipts/u16-staged/`):
   a45/a46/a47 — одно и то же дерево `862d3416823e`, вердикты FAILED с
   чередованием красной команды (a45: quick rc=1/верифаер rc=0; a46 и a47 —
   наоборот), затем a48 PASSED на том же дереве. Команды выполнялись
   **последовательно**, каждая в **свежем** изолированном checkout
   (`isolated-staged-tree`, отдельный `tempfile.TemporaryDirectory`) — это
   исключает гипотезы «общие temp-пути» и «порядок команд» из BACKLOG.
   Общее у команд — только хост (user-wide пул процессов, память, планировщик).
2. **Красные распределены по разным тестам** (a17 верифаер, a19 quick, a30
   meta_review+quick, a56/a60/a71/a80 quick, a87 верифаер=gate_pass_is_current,
   закрыт в S1) — единого «виновного теста» нет; это систем­ный хостовый класс.
3. **Натуральное воспроизведение:** под ограничением RLIMIT_NPROC c fork-churn
   оба контура падают именно `BlockingIOError: [Errno 11] Resource temporarily
   unavailable` в `subprocess.run` (fork). 40/40 прогонов
   `itd_hygiene.py close` под давлением дали rc=1 + **пустой stdout** +
   traceback в stderr — точная сигнатура зафиксированного флейка
   «FAIL close rejects dirty git state: » (детали в чеке — из stdout, он пуст).
4. **Масштабирование вероятности по числу спавнов** (git-спавны, замер шимом):
   `run-all.sh --quick` ≈ **4429**, `verify_predeploy_independent_review.py`
   ≈ **328** (~13,5×; поверх ещё python-спавны). Отсюда наблюдавшаяся
   асимметрия: верифаер-в-изоляции «зелёный 3/3», quick-suite в тех же окнах
   краснеет многократно. Решение r77 (оракул U16 = верифаер-only) было
   направленно верным.
5. **Не связано с S2:** `verify_independent_review_efficacy` красный и на
   чистом main `b5fd588` («wsl semantic result binding is foreign») — это
   известный live-pin friction (memory: feedback_live_benchmark_pin_friction,
   root-cause отложен решением пользователя; прецедент merge #189 с красным
   Gate 1). Он детерминированный, а не флейк, и в объём S2 не входит.

## Fix

- `docs/templates/itd/itd_hygiene.py::git()` — bounded retry (3 попытки с
  backoff) на spawn-level `OSError` (fork не состоялся ⇒ ретрай безопасен для
  любой git-команды; `FileNotFoundError` не ретраится) и итоговая деградация в
  синтетический `CompletedProcess(rc=127)` — каждый вызывающий уходит в свой
  структурный fail-closed diagnose вместо крэша с пустым stdout.
- Сопутствующая дыра, найденная при фиксе: `cleanup_manifest` разрешал
  удаление при **отсутствии доказательства** tracked (любой сбой git читался
  как «untracked»). Теперь удаление требует **позитивного** доказательства
  untracked (`ls-files --error-unmatch` rc=1); rc∉{0,1} — fail-closed ошибка
  «tracking state could not be proven».

## Regression test (пин)

`tests/verify_session_hygiene_quality.py::test_close_survives_spawn_pressure`
(POSIX): RLIMIT_NPROC=1 в дочернем процессе close ⇒ каждый внутренний спавн
детерминированно падает EAGAIN; ассерты — rc=1, stdout непустой и структурный,
в stderr нет Traceback. На коде до фикса тест красный с точной сигнатурой
флейка (rc=1, stdout='', Traceback) — проверено stash-прогоном.

## Residual / follow-ups (вне объёма S2)

- Промоушен quick-suite обратно в exact-candidate оракул U16 (SCOPE_LOCK
  criterion 4 amendment «promote после S2») — политическое решение; сейчас
  блокирован независимым детерминированным красным efficacy-пина (см. п. 5) —
  это S6/live-pin friction, не флейк.
- Хостовый транзиент неустраним из репо; смягчение для остальных ~60
  verify-тестов (общий retry-хелпер спавна) — кандидат в backlog, если класс
  снова проявится вне close-контура.
