---
project: idea-to-deploy
stage: "GPG-004 / юнит лестницы (reviewer independence), коммит-лестница — fix-round после BLOCKED-ревью"
roles: "сессия 2026-08-09 (PC-S3 выполнен, лестница в fix-round) → следующая сессия-реализатор"
---

# HANDOFF — GPG-004 ladder remainder: коммит-лестница, fix-round

**Дата:** 2026-08-09 · **Ветка:** `codex/gpg-003-unified-keyless-review` · **HEAD:** `0dd58bd` (== origin == PR #183, зелёный). Индекс держит комбинированный кандидат PC-S2+PC-S3. Risk `high`, WIP=1.

## 1. Состояние (актуальное, НЕ инструкция перегонять принятое)

- **PC-S3 выполнен целиком**: батч продюсера (закрытый класс {anthropic, openai}, cross-vendor маршрут для anthropic-maker'ов, flagged same-vendor fallback), прошивка `independenceLevel`/`routeIndependence`/`mint-override`, PC1..PC5 — passed в `.itd/ACCEPTANCE_CONTRACT.json`.
- **Три подписанные ноги отчеканены и ВАЛИДНЫ** (перегонять ЗАПРЕЩЕНО, кроме случая изменения байтов продюсера/раннера): `results/wsl.json` (same-vendor), `results/u12-cross-vendor-wsl.json` (cross-vendor, U12), `results/windows.json` (stable codex 0.146.0, `C:\Users\Public\itd-transport\`). Efficacy-verify: PASSED, `hostParityVerified: true`, U12 записан честно (обе ноги: criticalHigh 1.0 / medium 1.0 / cleanFalseBlock 0.0).
- **Лестница**: первый независимый маршрут (a5-снапшот, anthropic-maker → openai-reviewer, cross-vendor) вернул **BLOCKED, 12 находок** (6 различных). Пользователь выбрал fix-and-rerun: освежены STATE/HANDOFF (наход. A/B), закрыта v3-лазейка label'а (E), same-vendor label теперь несёт typed cross-vendor unavailability через `authorize_same_vendor_fallback` (C). Находки D (нет исполняемого cross-vendor транспорта для openai-maker — документированный optional-статус anthropic-транспорта, AC10) и F (exact-equality кворума — сознательное восстановление, DECISIONS) — кандидаты refuted-by-evidence, если всплывут снова.

## 2. Осталось (порядок фиксирован)

1. Фокусные сьюты после фиксов C/E → зелёные.
2. **Перегон трёх ног** (producer-байты изменились fix-round'ом): wsl → u12 → windows (драйвер `win-leg2`-рецепт, stable 0.146.0), затем efficacy-verify до `hostParityVerified: true`.
3. `run-all --quick && run-all` зелёные → `git add -A` → новый staged tree.
4. Две machine-квитанции (bare `GPG-004` для маршрута + `GPG-004:general-review` для claim), 14 оракулов, `--input` keyring-пин.
5. Свежий маршрут из НОВОГО снапшота продюсера (a6) — anthropic-maker, ретраи только typed exit 3.
6. PASSED → checker → adjudicate → коммит; находки → диспозиции пишет ЧЕЛОВЕК (ADR-007).
7. После коммита: follow-up «pin clean live evidence state» (skills/ жгут H4), пуш/PR только по явной команде, затем /goal-проход юнита.

## 3. Ссылки

- Квитанции лестницы: `.itd-memory/verification-loop/receipts/9def38638c70b461/` (machine ×2 PASSED на дереве 9def3863… — устареют с новым tree; route-report BLOCKED — вход fix-round'а).
- Durable-решения: `.itd/DECISIONS.md` (2026-08-09: граница PC-S2/PC-S3; broker-фикстура; typed fallback evidence).
- Скоуп/критерии: `.itd/SCOPE_LOCK.md`, `.itd/ACCEPTANCE_CONTRACT.json`.
- Ключ маршрута: `~/.cache/itd-review-authority/GPG004-U8-1ed4cb5a-a1/producer-ed25519.key`, key-id `gpg004-u8-producer-20260808`.

## 4. Запреты

`--no-verify`/env-обходы/прямой push; пересэмпл маршрута (ретрай только typed exit 3); перегон валидных ног без изменения producer/runner байтов; ручная правка `~/.config/itd/gates.json`; U6/U16/U17 — вне юнита.
