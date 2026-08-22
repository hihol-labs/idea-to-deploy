# Task Contract — GENG-S04B

## Scope
ТОЛЬКО D2: pre-flight входы `command_checker` валидируются пакетно — один
`LoopError` со всеми WHY+FIX (одиночное нарушение сохраняет исторический
текст); каждый вход независим (report-путь, prompt-путь, разбор отчёта,
phase-one, keyring, route-evidence). RED-first тесты + регрессии PUB1/PUB2.

D1 (мост claim-id) ВЫБРОШЕН по хард-стопу владельца 2026-08-22 после двух
находок high в четырёх раундах ревью; `validate_route_machine_binding`
восстановлена байт-в-байт из `214ee2e`.

## Verification Standards
- Оба инцидента воспроизведены RED на до-фиксовом коде;
- негативные мутации D1: чужой candidateDigest / несвязанное имя /
  FAILED bound / security<->general кросс — 100% reject;
- targeted-замыкание IMPACT_GRAPH по двум модулям зелёное;
- финальный полный tests/run-all.sh один раз (micro-path);
- VL medium: machine + targeted checker + adjudicate, check rc=0.

## Exclusions
Продюсер/брокер/хуки; изменение текстов существующих LoopError; любые
GENG-фазы. Ослабление fail-closed — запрещено.
