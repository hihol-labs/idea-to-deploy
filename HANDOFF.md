---
project: /home/hihol/projects/idea-to-deploy
stage: verification
from_role: active Codex implementation session
to_role: continuing Codex implementation session
reason: compact checkpoint during GPG-001 bugfix
branch: codex/harness-lifecycle-trust
head_commit: cec052df9fb7acdda30a84c331116afe4550e136
candidate_binding: external-git-write-tree-and-adjudication-receipt
---

# Handoff — GPG-001

> [!todo] Первое действие
> Вычисли exact staged tree и бесплатно повтори prepare-only и machine oracle.
> Terra report для tree `0c8dfeb2b671...` имеет `BLOCKED`; новый
> платный checker не запускать автоматически — только после отдельного явного
> согласия пользователя на ещё один расход. Коммит/push запрещены без current
> exact-candidate adjudication receipt.

## Текущее состояние

- Активная high-risk единица: `GPG-001` — глобальный fail-closed PR/API gate
  для Windows и WSL. Статус `in_progress`; WIP=1; завершение не заявлено.
- Ветка `codex/harness-lifecycle-trust`, Draft PR
  [#177](https://github.com/hihol-labs/idea-to-deploy/pull/177). `head_commit`
  выше — последний локальный commit перед staged split, не staged tree.
- Принятая до split bounded `.jsonl.gz` реализация сохранена в `cec052d` и на
  parked branch `codex/live-model-evidence-followup`; не откатывать и не
  публиковать её параллельно.
- Согласованный staged split убирает отдельный evidence-earned follow-up и
  сохраняет текущий bootstrap/control-plane slice в пределах 1.2 MB и 16
  review units. Generic binary остаётся `UNVERIFIED`; transparent review
  разрешён только явно объявленному `.jsonl.gz`.
- Paid Terra runs для `fb2b9a...` и `f65e559...` вернули `BLOCKED` (8 и 7
  findings). Run для `d66c9f...` остановился после call 5 как `UNVERIFIED` на
  чрезмерном same-path cross-segment запрете. Полный run `0c8dfeb...` выполнил
  17/17 calls и вернул `BLOCKED` с 8 findings; retry не разрешён и не запускается.
- Refute-pass по `0c8dfeb...` снял шесть findings: официально поддерживаемый
  GitHub API `2026-03-10`, local-only pre-push вне server trust boundary,
  compact-plan 80 KB, exact unit path binding, review-plan hash и уже полные
  provider/prompt/verdict bindings. Два воспроизводимых дефекта исправлены:
  произвольный абсолютный interpreter path и strict-prefix provider evidence.
  Live runner/image binding остаётся обязательным deployment prerequisite.
- Реальные/defense-in-depth follow-up закрыты RED→GREEN: strict `publicKey`,
  multiline scrub, non-shared machine clone, exact Compose allowlist, dynamic
  test-module registration и exact path binding для каждого diff unit;
  same-path cross-segment risks сверяет mandatory integration verdict.
  Synthetic credentials собираются runtime; tracked candidate scrub clean.
- После последних regressions broker 594, primitives 160 и cold-start GREEN.
  Нужно заново freeze tree,
  получить clean prepare-only, quick и оба machine receipts. Candidate не принят.

## Замороженные решения

- Обязательная проверка выполняется server-side dedicated GitHub App на exact
  GitHub test-merge SHA после Draft PR; local hooks/CLI — preflight, не trust
  boundary.
- API outage, zero balance, missing/stale provenance, incomplete pagination,
  redactions, oversized candidate и generic binary блокируют merge fail-closed.
- Sol-authored code проверяется fresh Terra как independent same-vendor review;
  Codex/Gemini CLI остаются advisory. Не называть это cross-vendor review.
- `.jsonl.gz` получает только declared bounded single-member transform: raw и
  logical hashes/bytes, streaming cap, strict UTF-8/JSONL, no NUL, secret scan,
  no candidate execution. Любой undeclared binary остаётся `UNVERIFIED`.
- Hierarchical review: direct до 80 KB, full diff до 1.2 MB, максимум 16 units
  плюс mandatory integration call; никакого truncation или повышения лимитов.
- Exact-candidate binding: staged tree, base, complete canonical diff/plan,
  per-unit byte ranges/hashes, provider request bundle и final adjudication.
- Reviewer credential принадлежит operator-managed secret boundary. Не читать,
  не печатать и не сохранять значение; DPAPI/KMS/secret-file — transport only.
- Установленный plugin cache не редактировать. Выпускать новую версию и
  устанавливать штатным plugin manager.

## Авторитетные входы

- `AGENTS.md`, `.itd-memory/STATE.json`, `.itd-memory/GOAL.json`.
- `ROOT_CAUSE.md`, `.itd/SCOPE_LOCK.md`, `.itd/FORBIDDEN_CHANGES.md`.
- `.itd-memory/session_2026-07-30.md` содержит полную хронологию старых trees.
- `.itd/ACCEPTANCE_CONTRACT.json` связывает portable девятичастную цель.
- Workflow: `skills/bugfix/SKILL.md`, затем shared Verification Loop и `/review`.
- Persistent `GOAL.json` относится к старому Practical Effectiveness goal
  (36/38; PE5-008/009 blocked). Не перезаписывать его без явного решения
  пользователя и не смешивать со статусом GPG-001.

## Команды проверки

```bash
sh skills/_shared/itd_py.sh --itd-isolated tests/verify_review_broker.py
sh skills/_shared/itd_py.sh --itd-isolated tests/verify_review_broker_primitives.py
sh skills/_shared/itd_py.sh --itd-isolated tests/verify_review_broker_policy.py
sh skills/_shared/itd_py.sh --itd-isolated tests/verify_api_reviewer.py
python3 tests/verify_machine_oracle.py
python3 tests/verify_review_broker_server.py
python3 tests/verify_review_broker_deployment.py
python3 tests/verify_host_adapters.py
bash tests/run-all.sh --quick
```

Acceptance evidence хранится вне tracked candidate. После freeze повторить
machine oracles для exact tree. Paid Terra checker — только после нового
явного разрешения пользователя; standalone `PASSED` без revalidated
adjudication receipt не принимает candidate.

## Блокеры и последовательность

1. Уложить compact handoff и защитные regressions в frozen 1.2 MB без
   удаления гарантий; получить clean prepare-only и machine receipts.
2. Получить отдельное согласие на один дополнительный платный Terra run.
3. При clean exact adjudication commit/push staged split и обновить Draft PR
   #177; при findings снова остановиться, не зацикливать платные проверки.
4. Текущий slice — bootstrap trust anchor. Он прямо не завершает GPG-001:
   live App/ruleset deployment, canaries, release и global install идут после
   принятия/merge bootstrap в последовательных units при WIP=1.
5. Для девяти пунктов далее нужны: подтверждённый inventory репозиториев,
   стабильный HTTPS broker host, GitHub org admin, dedicated GitHub App,
   production reviewer credential/KMS и бюджет, plan-dependent org ruleset
   либо per-repository protection, release/install ITD 1.95+, global
   Windows/WSL hooks, `itd gate doctor --all` и live negative canaries.

> [!warning]
> GitHub Organization `hihol-labs` ранее наблюдалась на Free; private org-wide
> rulesets могут требовать Team/Enterprise либо per-repository protection.
> Текущий slice не доказывает live runner policy, App ownership, HTTPS broker,
> ruleset enforcement или negative canaries. Не заявлять GPG-001 завершённой
> без этих live evidence и актуального exact-candidate adjudication receipt.
