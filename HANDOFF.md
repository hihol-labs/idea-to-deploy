---
project: idea-to-deploy
stage: "Release v1.96.0 (юнит GPG-004 verified и в main) — release-PR + tag + rollout"
roles: "сессия 2026-08-09 (release started) → следующая сессия-реализатор"
---

# HANDOFF — release v1.96.0 + rollout WSL/Windows

**Дата:** 2026-08-09 · **Ветка:** `chore/release-v1.96.0` от `main@126a1f0` (PR #184 merged, юнит GPG-004 verified). Risk `high` (release-цепочка), WIP=1.

## 1. Состояние

- **GPG-004 закрыт verified и целиком в main** (merge-commit `126a1f0`, Gate 1 + windows-verify success). Локальный main синхронизирован ff-only до `126a1f0`.
- **Release-коммит подготовлен (не закоммичен, если дерево грязное — доделай)**: бамп 1.95.1 → 1.96.0 в `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json`, `README.md`, `README.ru.md`, `docs/HARNESS_DOCS_STATE.json`, `docs/api-reviewer/RELEASE_CANDIDATE_CONTRACT.json`, `docs/HARNESS_CONFORMANCE_REPORT.md` (+прозаический абзац v1.96.0), `docs/HARNESS_ENGINEERING_MAP.md`; заголовок `## [1.96.0] - 2026-08-09` в CHANGELOG (контент уже был в Unreleased). Live-model evidence свежий (прогон 20260809T204934Z в main) — refresh НЕ нужен.

## 2. Осталось (порядок фиксирован)

1. `bash tests/run-all.sh` зелёный → коммит `chore: release v1.96.0` (единый, включая этот HANDOFF).
2. **Свежая committed-head цепочка на release-коммите**: machine-квитанция (15 оракулов — состав как в `push-f2d9a2b/GPG-004-machine-pushchain.json`: adjudication-channel(+gate), copilot-reviewer, free-reviewer-producer, gate-profile-doctor, gate-registry-isolation/profiles, host-adapter, independent-review-efficacy (keyring-пин `.itd-memory/host-inputs/GPG-003_REVIEW_EFFICACY_KEYRING.sha256`), mandatory-keyless-review, push-gate-adjudicated, reviewer-provider-freshness, verification-loop-commit-bridge, reviewer-independence-policy, live-model-evidence-replay), `--candidate-mode committed-head --risk-tier high`.
3. Checker: cross-vendor маршрут из снапшота `~/.cache/itd-gpg004-producer/a6/`, ключ `~/.cache/itd-review-authority/GPG004-U8-1ed4cb5a-a1/producer-ed25519.key` (key-id `gpg004-u8-producer-20260808`), codex-sha `2e863156…6e04`, proxy-sha `01ba4719…546b`. Находки → диспозиции пишет ЧЕЛОВЕК (ADR-007), затем `check --require-mandatory-route --accept-adjudicated-route`.
4. Registry: guarded `register-profile` на release-HEAD → `itd pr create` (--maker-vendor/--maker-model/--maker-session; probe-драйвер при мигающей сети; ретраи только typed exit 3).
5. CI зелёный → merge (авторизован заданием сессии) → tag `v1.96.0` + gh release notes.
6. Rollout: `bash scripts/sync-to-active.sh` (WSL) + `CLAUDE_HOME=/mnt/c/Users/<user>/.claude bash scripts/sync-to-active.sh` (Windows), hash-верификация по прецеденту v1.94/v1.95; манифест `~/.claude/.claude-plugin/plugin.json` копировать ВРУЧНУЮ (sync-gap в BACKLOG). Затем `/session-save`.

## 3. Ссылки

- Kickoff: `.itd-memory/session_2026-08-09_19.md`; runbook: `docs/RELEASE_RUNBOOK.md`.
- Прецедент цепочки: `.itd-memory/verification-loop/receipts/push-f2d9a2b/`, `push-a3aa462/`; прецедент release-диффа: коммит `1422c94` (v1.95.1).
- CLI: `python3 skills/_shared/itd_verification_loop.py {machine,checker,adjudicate,check}`; `python3 scripts/itd.py pr create`; producer `skills/_shared/itd_free_reviewer_producer.py review`.

## 4. Запреты

`--no-verify`/env-обходы/прямой push (только `itd pr create`); пересэмпл маршрута (ретрай только typed exit 3); ручная правка `~/.config/itd/gates.json`; ветку `codex/gpg-004-reviewer-independence` и `refs/itd-backup/gpg004-pre-rebase` не удалять до конца release-цикла; следующие юниты (U6/U16/U17/GENG) — только после rollout.
