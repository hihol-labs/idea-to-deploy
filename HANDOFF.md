---
project: /home/hihol/projects/idea-to-deploy
stage: implementation
from_role: completed Codex MEM-8 recovery session
to_role: continuing Codex GPG-001 implementation session
reason: MEM-8 repair committed and accepted; free reviewer producer is next
branch: codex/harness-lifecycle-trust
head_commit: 43e65b06aa32731da7b6725a9d0e37de0c42dc43
accepted_tree: 92fd0590a80d0234d829a13c5f572b28f6c7de4b
---

# Handoff — GPG-001

> [!todo] Первое действие
> Реализовать следующий bounded slice плана: free isolated fresh-model reviewer
> producer без inherited context, network, secrets или repository mutation;
> reviewer проверяет exact candidate до создания PR. После PASS создать Draft
> PR, добавить signed two-phase exact receipt и App-side live-coordinate
> revalidation mutations. Paid API, push и PR update запрещены до нового exact
> review/adjudication.

## Текущее состояние

- Активная единица `GPG-001`, high risk, `in_progress`, WIP=1.
- Ветка на `43e65b0`; MEM-8 repair committed локально. Draft PR #177 не
  обновлён; push не выполнялся.
- Коммит содержит broker/App/oracle/bootstrap slice и transparent review
  только для declared bounded `.jsonl.gz`; generic binary остаётся
  `UNVERIFIED`.
- Перед коммитом tree `f294c532...` прошёл free fresh `gpt-5.6-terra` full
  review и exact adjudication. После коммита обязательный новый `/review`
  сравнил весь parent→HEAD diff и нашёл пропущенную MEM-8 регрессию.
- Отдельный fresh refute подтвердил finding: удалены closed registry schema,
  validator, unknown-provider `abstain`, `/adopt` inventory, security MEM-8 и
  mutation test. `tests/run-all.sh --quick` при этом GREEN — именно поэтому
  нужно вернуть targeted sensor.
- RED воспроизведён в чистом `954a3b6`: parent sensor завершился exit 1 из-за
  отсутствующего `skills/_shared/itd_harness_controls.py`. Recovery overlay
  восстановил parent schema/validator/test byte-for-byte и registry/adopt/
  security/contract semantics.
- На pre-handoff staged tree `091db828...` GREEN: targeted tool-trust 13/13,
  operational cold-start all pass, meta-review `PASSED`, host adapters PASS,
  `bash tests/run-all.sh --quick` → `DONE fails:none`.
- Risk-budget general bucket достиг порога; новые product changes запрещены до
  успешного bound `/review`. Checker prompt подготовлен в ignored
  `.itd-memory/verification-loop/prompts/`; после этой tracked handoff-правки
  tree и имя prompt/report нужно обновить.
- Fresh review tree `b52779be...` завершился `BLOCKED`: подтвердил nested
  capability schema/validator mismatch, local unreviewed `allow`, отсутствие
  sensor в run-all/CI и неполное покрытие `/adopt` no-mutation wording. Все
  четыре finding закрыты regression-first; targeted all/integration и
  run-all drift уже GREEN, но новый exact tree ещё не заморожен и не принят.
- Re-review tree `8dbd29fb...` снял эти findings, но вернул один Important:
  stale `EXPECTED_DEMAND_SHA` в `verify_semantic_navigation.py`. RED
  воспроизведён, константа обновлена до фактического SHA tracked `DEMAND.json`,
  semantic-navigation/tool-trust/meta-review снова GREEN; нужен новый exact
  checker с нулевыми findings/unverified и adjudication.
- Final tree `92fd0590...` прошёл machine oracle, fresh full
  `gpt-5.6-terra` с `findings=[]`, `unverified=[]` и adjudication `PASSED`;
  exact tree сохранён commit `43e65b0`. MEM-8 blocker закрыт. Post-commit
  state/HANDOFF/AC16 reconciliation пока является новым uncommitted overlay и
  не входит в тот adjudicated commit.
- Plan из 9 пунктов обновлён: бесплатный isolated fresh-model reviewer —
  primary; paid Responses API — optional fallback только с отдельным согласием
  и бюджетом; App остаётся server-side authority.
- Единственное изменение исходного 9-point плана — транспорт reviewer:
  обязательную pre-PR проверку выполняет другая fresh AI model без inherited
  development context. Gate semantics, exact binding и App authority остаются.
- Global guarded push сейчас блокируется из-за отсутствующего
  `/home/hihol/.config/itd/gates.json`. Не обходить `--no-verify`.

## Авторитетные входы

1. `AGENTS.md`
2. `HANDOFF.md`
3. `.itd-memory/STATE.json`
4. `ROOT_CAUSE.md`
5. `.itd/SCOPE_LOCK.md`
6. `.itd/FORBIDDEN_CHANGES.md`
7. `.itd-memory/session_2026-08-01.md`
8. `.itd/GPG-001_NINE_POINT_PLAN.md`
9. `.itd/ACCEPTANCE_CONTRACT.json` AC15/AC16

Persistent `.itd-memory/GOAL.json` относится к старому Practical
Effectiveness goal (36/38, PE5-008/009 blocked). Не перезаписывать и не
смешивать его с GPG-001.

## Команды проверки

```bash
git diff --check
sh skills/_shared/itd_py.sh tests/verify_tool_trust_inventory.py
sh skills/_shared/itd_py.sh tests/verify_operational_cold_start.py
sh skills/_shared/itd_py.sh tests/meta_review.py --verbose
sh skills/_shared/itd_py.sh tests/verify_host_adapters.py
bash tests/run-all.sh --quick
```

После GREEN заморозить exact staged candidate, выполнить machine oracle,
fresh different-model checker и adjudication для `GPG-001:general-review`.
Только receipt с `findings=[]` и `unverified=[]` разблокирует commit.

## Последовательность после repair

1. Implement/test free isolated reviewer producer: no inherited context,
   secrets, network or mutation tools; host-observed model/session.
2. Sign two-phase exact receipt and revalidate live PR/base/head/check SHA in
   broker before App-owned Check publication.
3. Add same-session/inherited-context/forged/stale/unavailable canaries and
   prove no automatic paid dispatch.
4. Deploy App/ruleset serially, then canaries, release/install and doctor.

> [!warning]
> GPG-001 не завершена. Не заявлять completion без live App/ruleset/private
> repo evidence и актуального exact-candidate adjudication receipt. Не
> использовать ранее раскрытый ключ, не сохранять secrets и не редактировать
> installed plugin cache.
