# Оценка эффективности ITD и соответствия Harness Engineering

> **Результат: 5,0/5,0.** Текущий пакет — idea-to-deploy **v1.91.1**.
> Исполняемая evidence-база обновлена на текущем content-pinned tree
> 2026-07-18. v1.91.1 меняет публичное позиционирование и надёжность
> live-benchmark transport/evidence, но не production contracts, hooks, skills
> или adapter semantics. Оценка действительна только пока проходят
> замороженный evaluator, freshness-проверки и полный regression suite.

## Метод оценки

Пять принципов Harness Engineering оцениваются по бинарной шкале: каждая ось
H1–H5 даёт ровно 1 балл, только если все её независимые evidence-команды
завершаются с кодом 0. Итог 5/5 невозможен при missing, stale, skipped,
self-referential или failing evidence. Рубрика заморожена до реализации в
[`HARNESS_CONFORMANCE_CONTRACT.json`](HARNESS_CONFORMANCE_CONTRACT.json) и
защищена SHA-256
`8f0f5d3bb7beff0c20b39ce5405a770de20d21e4cbb67162a8115f116366ef3e`.
Narrative-документы не могут выставить себе оценку.

## Результаты

| Ось | Балл | Почему результат обоснован | Проверяемое evidence |
|---|:---:|---|---|
| **H1 — ограничение поведения** | **1,0/1,0** | Риск управляет уровнем доверия: high-risk действия закрываются fail-closed, а low-risk путь остаётся неблокирующим. Все 11 computational hard gates зарегистрированы и дают эквивалентное deny/block-поведение через Claude Code и Codex. | `verify_graduated_trust.py`; `verify_all_hard_gate_host_parity.py`; `verify_redteam_multihost.py` |
| **H2 — сохранение контекста** | **1,0/1,0** | Каноническая память находится в project-local `.itd-memory`, а не в приватном состоянии одного хоста. Новая сессия восстанавливает активный unit, evidence, blockers и next action; adversarial state cases закрываются fail-closed. | `verify_host_neutral_memory.py`; `verify_fresh_session_resume.py`; `verify_state_hardening.py` |
| **H3 — защита от преждевременного завершения** | **1,0/1,0** | В strict/high-risk режиме commit исходного кода и explicit close запрещены без валидных runtime signals. Low/medium no-signal остаётся калиброванным advisory, а human bypass требует причины и сохраняет аудит. | `verify_strict_completion_policy.py`; `verify_completion_gate.py`; `verify_completion_policy_calibration.py`; `verify_session_hygiene_quality.py` |
| **H4 — верификация тестированием** | **1,0/1,0** | Structural и behavioural тесты проверяют реальные allow/deny и pass/fail ветви. Дополнительно выполнен настоящий post-freeze live-model benchmark с независимым snapshot oracle; отсутствие credential даёт UNVERIFIED, а не ложный PASS. | `verify_harness_map_fixtures.py`; `verify_review_evalset.py`; `verify_live_model_benchmark.py`; content-pinned `tests/fixtures/live-model-evidence/latest.json` |
| **H5 — наблюдаемость** | **1,0/1,0** | Trace связывает intent с outcome; estimated и host-observed tokens разведены и имеют provenance. Фиксированный control corpus измеряет FP/FN, а версия, инвентарь, taxonomy и документы проверяются на drift и freshness. | `verify_execution_trace_outcome.py`; `verify_observed_token_telemetry.py`; `verify_signal_attribution.py`; `verify_control_quality.py`; `verify_harness_docs_freshness.py` |
| **Итого** | **5,0/5,0** | Все пять осей обязаны одновременно пройти замороженный fail-closed evaluator. | `python3 tests/verify_harness_conformance.py --axis all` |

## Анализ эффективности

ITD эффективна как engineering harness, потому что покрывает полный замкнутый
контур, а не отдельные prompt-рекомендации:

1. **До действия** — risk-tier policy и computational gates ограничивают
   опасные переходы.
2. **Во время длинной работы** — WIP=1, контракты и durable state удерживают
   одну проверяемую единицу и позволяют resume без памяти транскрипта.
3. **На границе завершения** — статус `done` выводится из evidence, а не из
   уверенности модели.
4. **После действия** — behavioural tests, независимый live-model oracle и
   traces замыкают feedback loop.
5. **На уровне самой методологии** — quality/freshness checks обнаруживают
   расхождение заявлений, регистрации хостов и фактического поведения.

Практическая сила архитектуры — разделение **11 hard gates** и **18 soft
hooks**. Computational-инварианты могут блокировать, а семантические или
наблюдательные механизмы остаются advisory. Это снижает риск одновременно
двух типов ошибок: пропуска опасного действия и чрезмерной блокировки обычной
работы.

## Ограничения вывода

- 5/5 означает соответствие замороженной H1–H5 рубрике, а не доказанный рост
  бизнес-ROI, throughput команды или качества любого прикладного продукта.
- Live-model evidence имеет срок 30 дней; после него H4 и общий score обязаны
  стать непройденными до нового запуска.
- Нулевые FP/FN относятся к фиксированному corpus из 16 контрольных случаев,
  а не ко всем возможным командам и проектам.
- Soft hooks улучшают обратную связь, но намеренно не являются security
  boundary. Гарантии строятся только на перечисленных computational gates и
  fail-closed evidence.

Подробное соответствие механизмов принципам и исторический контекст находятся
в [`HARNESS_ENGINEERING_MAP.md`](HARNESS_ENGINEERING_MAP.md). Машиночитаемое
состояние документации — в [`HARNESS_DOCS_STATE.json`](HARNESS_DOCS_STATE.json).
