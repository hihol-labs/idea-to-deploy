# BACKLOG — Harness-demo UX absorption

**Decision:** [ADR-004](docs/adr/ADR-004-harness-demo-ux-absorption.md)
**Last reviewed:** 2026-08-10
**Next review:** 2026-08-30

## P0 — Must do

- [ ] Freeze and mutation-test the absorption contract before behavior changes.
- [ ] Generate evidence-backed conditional context modules from `/adopt`.
- [ ] Freeze the captured-run schema and clean-temp replay before populating it.
- [ ] Add a PIV-lite brownfield façade by routing existing `/task`, `/test`, and
  `/review`; add no lifecycle skill.
- [ ] Publish one version-pinned, reproducible brownfield example run through the
  completed façade.

## P1 — дефекты маршрута, найденные при R1 (2026-08-18, вторая сессия)

- [ ] **Продюсер выбирает критерии контракта по префиксу `unitId + "-"`**
  (`skills/_shared/itd_review_evidence.py:142`). Юнит с id `R1` захватил
  исторический критерий `R1-SCRUB-1` и получил `UNVERIFIED: review evidence is
  not a closed object` — отказ формально правильный, но по чужой записи.
  Обошли переименованием юнита в `LPD002-R1`; корень (выбор по префиксу вместо
  явной принадлежности) остаётся.
- [ ] **Оценщик завершения приклеивает evidence к произвольной команде.**
  Красный L2-сигнал от прогона ДО перечеканки efficacy-ног остался в вердикте
  с evidence из текста heredoc (`cat > HANDOFF-R1.md`), и свежий зелёный
  `run-all --quick` его не перевесил -> коммит только через `COMPLETION_BYPASS`.
  Тот же класс, что P1 2026-08-18 (стейл FAILED-сигнал).
- [ ] **Чекер-субагент имеет доступ на запись к индексу.** В раунде 1 он выполнил
  `git stash` при живом закреплённом кандидате (дерево восстановил сам). Нужен
  read-only доступ к кандидату (`git show :<path>`), а не дисциплина промпта.
- [ ] **Правка любого файла в `skills/` инвалидирует три подписанные
  efficacy-ноги** -> обязательная живая перечеканка (~25 мин на юнит, из них
  Windows-нога через PowerShell/UNC). Замерено на R1; тот же класс, что
  live-benchmark пин.

## Отложено решением владельца (источник: retro 2026-08-18, план LPD-002)

- [ ] **M1 — мутация из конвенции в гейт** (LPD-001). Отложено: добавляет церемонию
  в маршрут, который по замеру 2026-08-18 съедал ~25% сессии; внешнего инцидента
  «мутацию не прогнали -> дефект прошёл» нет (4 вакуумных пина S10 поймала мутация
  по конвенции). Пересмотреть после LPD-002 по новым данным ретро.
- [ ] **M2 — бюджет церемонии на юнит** (LPD-001). Отложено: измеряет последствие M1;
  токены на мультисессионном юните не бюджетируются честно (леджер в /tmp, ротация 14 дней).
- [ ] **M4 — потолок поправок как warning** (LPD-001). Отложено: не сокращает ни один
  измеренный расход.
- [ ] P9 — false-block ревьюера 1/4 на clean-кейсах в первой ноге efficacy: недетерминизм
  внешней модели при адекватном пороге 0.1; фиксировать как метрику run1/run2, не «чинить».
- [ ] P10 — SKILL_BYPASS 27/сессию: все аннотации hard-gated класса (push/PR/release/sync
  и ретраи одной команды). Разделять «церемониальные» и «пропуски» в скане — только если
  владелец сочтёт метрику вводящей в заблуждение (иначе анти-Гудхарт).

## P1 — Found while closing S10-LEDGER / delivering S11 (2026-08-18)

- [ ] Ledger-close коммит (STATE `verified` + контракт) не проходит evidence-first
  продюсера ни с открытым followup («STATE и контракт расходятся»), ни с закрытым
  (`coverage_matrix = None` → «verified без покрытия классов»). Круг маршрута;
  обход владельца — ротация в delivery-коммите следующего юнита. HANDOFF-S10 §17.11.
- [ ] Продюсер классифицирует `Selected model is at capacity` (codex `turn.failed`)
  как UNVERIFIED «failed without proven transport unavailability»: маркер
  «at capacity» отсутствует в `CLI_UNAVAILABLE_MARKERS`; по смыслу это UNAVAILABLE
  (транзиент, лечится повтором). Диагностика доступна только обёрткой
  `run_bounded_process` — stderr/stdout транспорта при провале не сохраняются.
- [x] `tests/verify_independent_review_efficacy.py` требует host-input
  `.itd-memory/host-inputs/…sha256` (gitignored) → в изолированном machine-worktree
  не запускается (exit 1) даже с абсолютным путём; efficacy-oracle нельзя включить
  в машинную квитанцию. **Закрыто LPD-002 R4:** добавлена форма-значение
  `--expected-keyring-sha256 <hex>`, `.itd/VERIFICATION_CONTRACT.json` переведён
  на неё; сила авторизации названа в отчёте (`keyringAuthorization`).
- [x] `tests/run-independent-review-efficacy.py`: `--max-transport-attempts` принимает
  только 1 (иначе `retry bound is invalid`) — флаг вводит в заблуждение; чекпоинт
  удаляется при успехе, повторный запуск с тем же путём стартует с нуля.
  **Закрыто LPD-002 R4:** флаг удалён (граница — константа
  `TRANSPORT_ATTEMPT_BOUND = 1`, исполнение `.itd/DECISIONS.md:214/:447`),
  чекпоинт сохраняется как `<path>.done`.
- [x] `itd_unit_log.py activate` не пишет `riskTier` (нет флага) — правится руками в STATE.
  **Закрыто LPD-002 R4:** `--risk-tier low|medium|high|unknown` обязателен и
  пишется в `STATE.currentUnit`.

## P1 — Found while closing S10-LEDGER (2026-08-16)

- [ ] `hooks/completion-signals.sh` помечает ЗЕЛЁНЫЙ прогон как `FAILED`: строка
  `24 passed, 0 failed` матчится по подстроке `failed` без разбора числа. За одну
  сессию сработало 6 раз на зелёных прогонах — шум, обесценивающий сигнал слоя L2.
  Воспроизведение: любой тест этого репо, печатающий `N passed, 0 failed`.
- [ ] `scripts/itd_metrics.py` и `skills/retro/scripts/itd_retro_scan.py` держали
  ДВЕ копии семантики VCR (комментарий в retro_scan прямо это фиксировал). Копии
  сведены в `skills/_shared/itd_unit_lifecycle.py` — проверить, нет ли третьего
  потребителя unit-событий, который остался на старой семантике.

- [ ] **Идентификатор claim'а рассогласован между продюсером и review-cache.**
  `itd_review_cache.py:329` валидирует квитанцию против `review_claim_id()` =
  `"<unit>:general-review"`, а Verification Loop выпускает квитанции с голым
  `unitId`. `machine` и `checker` под claim-id проходят, но `adjudicate` падает
  (`mandatory route receipt binds another machine receipt`). Цена — лишний ЖИВОЙ
  прогон ревьюера только ради согласования имени. Измерено на S10-LEDGER
  2026-08-17; в `HANDOFF-RELEASE-1.97.0.md` тот же дефект описан неточно.
- [ ] `checker` требует отчёт, промпт, phase-one-квитанцию И keyring продюсера
  внутри `.itd-memory/verification-loop/`; каждый внешний путь отдаётся
  отдельным `UNVERIFIED`, по одному за прогон.
- [ ] Продюсер отдаёт два неразличимых `UNVERIFIED`: исчерпание квоты (решение
  владельца) и обрыв event stream (просто ретрай). За S10 обрыв случился дважды.

## P0 — Deferred out of the bounded-process/resumability slice (GPG-004)

Each item was found while accepting that slice and deliberately left out of it, so
the slice stays one reviewable change. None of them is a known-broken invariant.

- [ ] Reviewer independence policy unit: cross-vendor `{Claude, Codex}` with an
  honestly labeled `same-vendor-different-model` fallback and a
  `HUMAN_OVERRIDE_NO_INDEPENDENT_REVIEW` class. Starts with `.itd/SCOPE_LOCK.md`,
  `ACCEPTANCE_CONTRACT.json` and ADR-007, then narrows the ladder already written in
  `refs/itd-backup/gpg004-candidate`. Blocks the two items below.
- [ ] Restore the reviewer-cardinality structural cases (`low-reviewer`,
  `high-quorum`) in `tests/verify_independent_review_efficacy.py` together with the
  `minimumIndependentReviewers` contract they assert. They were removed from the
  ported matcher because that contract belongs to the policy unit.
- [ ] `run_codex_review` in `skills/_shared/itd_free_reviewer_producer.py` is a
  God-function: 145 lines after S8-U3, already 107 before it (general-review
  finding, 2026-08-14). Transport setup, event-stream classification, provenance
  and report parsing all live in one body, which is why every change to it needs
  a full-file read. Deliberately not refactored inside a narrowly-scoped
  classification fix - a behaviour-preserving split is its own unit.
- [x] Codex error-item classification (A19): the candidate's `run_codex_review`
  handles a reviewer error item that the slice's HEAD-derived version does not.
  Not observed to fail on codex 0.146.0 during acceptance, so it stays a separate
  bounded fix rather than a silent slice extension. CLOSED by S8-U3: an error
  ITEM now routes to the same typed CLI-failure path as a `turn.failed` EVENT
  instead of being counted as a tool call (which reported the transport's own
  failure as the reviewer breaking isolation); the code-mode-disabled advisory
  is recognized by prefix as the denylist working rather than a failure; and the
  tool-call refusal names the observed item types, so an unknown item type from
  a newer CLI can be told apart from a real tool call. Covered by five new cases
  in `tests/verify_free_reviewer_producer.py` (153 -> 158 checks). One narrowing
  beyond the reviewed GPG-004 port: the advisory must be a single line, so an
  unbounded trailing suffix cannot smuggle a second line past the prefix match.
- [ ] Explain one unreproduced `UNVERIFIED` reviewer failure seen on the first WSL
  efficacy attempt (`high-export-capacity`, no unavailability marker in the CLI
  output). The case passed on every later attempt and the suppressed CLI detail was
  not captured, so the cause is currently unknown rather than diagnosed.
- [x] Strict POSIX descendant containment in `run_bounded_process` (route finding,
  2026-08-09): cleanup kills the call's process group, so a descendant that
  re-calls `setsid()` escapes and is not reaped; Windows is already strict via the
  Job Object. CLOSED by S7-U3 with a PPID-walk reap (pre-kill /proc snapshot,
  then SIGKILL of the group escapees) and a test that actually daemonizes.
- [ ] Residual of the containment fix above (S7-U3, 2026-08-13): (a) a double-fork
  orphan already reparented to init before cleanup is invisible to a PPID walk;
  (b) the walk is /proc-only, so on a POSIX host without it (macOS) containment
  degrades to the plain killpg it always was — the reap test skips there rather
  than claiming coverage; (c) a snapshotted PID reused by an unrelated process
  before the kill would be signalled by mistake (the window killpg always had,
  now spread over the escapee list). Closing (a)-(c) properly means cgroup or
  PID-namespace containment — a separate bounded design, not a patch.
- [ ] Ложноположительный класс у gpt-5.6-sol на чистом коде (S7, 2026-08-14):
  в раунде-1 ре-минта обе same-vendor ноги независимо заблокировали чистый
  кейс `clean-bounded-reconciled-export` с находкой severity high вида
  «`chunk.push` берётся из `Array.prototype`, достижимого для атакующего».
  Раунд-2 на том же промпте (promptSha256 совпадает) прошёл чисто, поэтому это
  дисперсия, а не устойчивый дефект — но класс стоит отслеживать: при пороге
  maximumCleanFalseBlockRate 0.1 одного такого срабатывания на 4 чистых кейса
  хватает, чтобы покраснел весь гейт. Артефакты раунда-1:
  `.itd-memory/efficacy-evidence/s7-round1/`.
- [ ] Harden the run-all host-pin boundary (route finding F4, 2026-08-09): the
  efficacy keyring pin path is chosen by candidate code (`tests/run-all.sh`) and
  only existence-checked. The strict receipt path already passes it as a declared
  host input; move the convenience path to a host-owned location outside the
  checkout (env var or absolute host path) so candidate code cannot select the pin.
- [ ] `quick-regression.trustedVerifierPaths` in `docs/VERIFICATION_CONTRACT.json`
  is a stale roster (S8-U1, 2026-08-14): it enumerates 55 verifiers while
  `run-all.sh` CORE now carries ~70, so verifiers added since (efficacy,
  `verify_sync_manifest`, `verify_free_reviewer_producer`, …) are executed by the
  aggregator without being declared. The trusted-path check only binds the
  dispatcher and its script, so nothing is red today — but the list reads as a
  complete dependency declaration and is not one. Either regenerate it from CORE
  and police the equality, or stop presenting it as the full roster.
- [ ] Git-ignored debris makes tracked-namespace trusted paths fail the
  clean-HEAD check (S8-U1, 2026-08-14): `v2_verifier_error` runs
  `git status --ignored=matching` over each `trustedVerifierPaths` entry, and the
  `.itd/VERIFICATION_CONTRACT.json` entries that name the whole `tests` namespace
  therefore report `trusted verifier differs from clean HEAD` whenever
  `tests/__pycache__/`, `tests/helpers/__pycache__/` or
  `tests/fixtures/*/output/` exist — which is after any local test run. Same
  class as the H4 tree-pin item below. Decide once: either the clean-HEAD check
  ignores what Git ignores, or the namespace entries are replaced by file lists.
- [ ] A closed `activeFollowup` still pins the independent-review coverage matrix
  (S8, 2026-08-14). `evidence_first_policy` in `skills/_shared/itd_review_evidence.py`
  activates the matrix on the mere presence of `reviewPolicy` and never reads
  `status`/`closedAt`, while `coverage_matrix` then takes the active unit from
  `activeFollowup.unitId` rather than from `.itd-memory/STATE.json`. A followup
  marked `status: verified, closedAt: …` therefore keeps binding every later
  candidate to a unit that is finished: two S8 route attempts failed with
  `active unit and machine evidence differ` before the field was re-declared
  (a third, earlier attempt failed for an unrelated reason — `staged machine
  candidate diff is empty`, because the producer reads `git diff --cached` and
  the candidate was already committed).
  Either honour the closed status (fall back to no matrix, or to STATE's active
  unit) or refuse a closed followup loudly instead of silently pinning it.
- [ ] The recorded live H4 run contradicts itself (independent review, S8,
  2026-08-14). In the committed run `20260814T163339Z-1e1ab055` the final
  structural validation command exits 1 while the next agent message asserts
  every required check passed. The reviewer raised a second, similar defect
  (generated `CLAUDE.md` redefining exit code 3 against the PRD of the same
  session) against a LATER re-record that exists only in a throwaway review
  worktree and was never committed — recorded here as an observation, not as a
  repository artifact, because citing an artifact the repo does not contain is
  itself a defect (that miscitation was the reviewer's own finding). The
  benchmark exists to measure exactly this, and no run was re-shot to look
  better. Open question worth its own unit: should
  `verify_live_model_benchmark.py` fail an internally self-contradictory run
  rather than accepting the snapshot oracle's PASS?
- [ ] `bash tests/run-all.sh` can report a FALSE red when the unit ledger is
  written concurrently (S8, 2026-08-14): a run that overlapped an
  `itd_unit_log activate` write to `.itd-memory/STATE.json` reported
  `DONE fails: verify_harness_map_fixtures`, while the same verifier standalone
  gave `39 passed, 0 failed` and an immediate clean re-run of the whole suite
  gave `DONE fails:none`. Harness-state readers should either snapshot the
  ledger or the suite should refuse to start while a ledger write is in flight;
  a red that disappears on re-run teaches operators to ignore reds.
- [ ] A16 keeps costing whole runs: the isolated benchmark invocation drops with
  a typed `OpenAI reviewer event stream transport is unavailable` (exit 3) far
  more often than a flat `codex exec` does. Fresh data, S8 re-mint 2026-08-14:
  the `wsl` leg went clean first try, `u12-cross-vendor` needed three attempts
  and `windows` two, all on that same typed exit, on the same transport within
  the same hour. Two of those failures hit the FIRST case, so no checkpoint
  existed and the whole leg restarted from zero - the checkpoint only helps once
  a verdict has been produced. Worth either a bounded typed-exit-3 retry inside
  the runner, or a checkpoint written before the first case.
- [ ] `prepare_adopted_project` in `tests/run-live-model-benchmark.py` copies the
  same `METHODOLOGY_TREE_ROOTS` into the isolated benchmark project through
  `shutil.ignore_patterns`, which excludes `__pycache__`/`*.pyc` by name and is
  not Git-ignore aware (general-review finding, S8-U2, 2026-08-14). Same debris
  class the tree pin just closed, different surface: harness output under a tree
  root is handed to the live model as if it were methodology. Deliberately left
  out of S8-U2's scope rather than widened into it.
- [x] Make the methodology tree pin ignore harness debris. `methodology_tree_sha256`
  in `tests/verify_live_model_benchmark.py` skips `__pycache__` and `.pyc` but not
  Git-ignored harness output such as `.claude/`. A stray 800-byte trace file under
  `skills/_shared/.claude/traces/` silently entered the H4 tree pin, and the mismatch
  only surfaced later in the isolated staged candidate as three failing checks. The
  pin should either exclude the same paths Git ignores or fail loudly at run time.
  CLOSED by S8-U2 with both: one batched `git check-ignore -z --stdin` in the
  verifier AND in the producer (`tests/run-live-model-benchmark.py`, which writes
  the pin the verifier re-computes), and a `RuntimeError` when Git cannot answer.
  Covered by `tests/verify_tree_pin_debris.py` (14 checks: H4 debris reproduction,
  non-vacuity via a non-ignored probe, producer/verifier agreement, and loud failure
  on all three ways Git can fail to answer - missing executable, fatal exit code,
  timeout - for both implementations). The digest is unchanged on today's tree - every ignored file
  under the roots is already `__pycache__`/`*.pyc`.
- [x] Exclude `__pycache__`/`*.pyc` bytecode from the `sync-to-active.sh` drift
  scan (found closing U6, 2026-08-10): the only reported skill drift on a fully
  synced install was `skills/_shared/__pycache__` — pure noise that makes a
  clean parity check read as "~1 updated". CLOSED by S7-U4 (`diff -rq -x
  __pycache__ -x '*.pyc'`), covered by `tests/verify_sync_manifest.py`.
- [x] Whitespace-split secrets evade the scrubber detectors (R1 review
  finding, 2026-08-10, pre-existing): closed INSIDE the R1 slice after the
  independent route showed R1 widens the exposure (the accidental
  any-redaction block previously caught the composite case) —
  `contains_high_confidence_secret` now also checks per-line
  whitespace-collapsed variants (detection only; line-scoped so entropy
  checks never see the document fused into one token). Remaining open tail:
  secrets split ACROSS lines, and entropy detection on collapsed text, stay
  undetected by design — document-scoped collapse would fire on everything;
  revisit only with a bounded design.
- [ ] Signed HUMAN_OVERRIDE channel (U16 cross-vendor route finding r17,
  2026-08-10): `itd_verification_loop.py mint-override` records carry no
  cryptographic signature, so the pre-deploy gate refuses ALL override records
  (an unsigned record is forgeable). Add an authenticated minting channel
  (host-owned signing key + verification against the installed trust anchor),
  then re-enable the data-sensitive-only bypass in `itd_predeploy_gate.py`.
- [ ] Authenticated deployed-state attestation (U16 route findings r23/r25,
  2026-08-10): local `deploy-*` tags are forgeable, so the pre-deploy gate
  classifies ANY populated migration directory as irreversible (strict
  presence-based) and migration-bearing projects have no routine path. Add an
  attested "deployed up to X" marker (e.g. signed by the same host-owned
  authority as the override channel) to restore a sound routine path.
- [ ] Broaden pre-deploy risk auto-detection (U16 review finding, 2026-08-10):
  classification is opt-in — a project with no `itd-domain:` marker whose
  migrations live outside the fixed list (`migrations`, `db/migrations`,
  `packages/supabase/migrations`) is classified routine and deploys
  unreviewed. Add the common tool layouts (`alembic/versions`,
  `prisma/migrations`, `app/migrations`, …) and payment/PII import
  heuristics as defense-in-depth.
- [x] Mechanical pre-deploy enforcement (U16 review finding + route finding
  r32, 2026-08-10): closed inside U16 — `hooks/check-predeploy-gate.sh`
  (PreToolUse, Bash matcher) denies content-shipping commands for a gated
  candidate until the gate records a pass bound to the exact candidate
  digest. Follow-up CLOSED 2026-08-11 (route finding r51): the gate-pass
  record is authenticated by an HMAC keyed by a host-owned secret outside every
  checkout (`~/.config/itd/deploy-gate.key`), so a hand-written record is not a
  pass. The signed OVERRIDE channel above stays open — different channel.

## P0 — Deferred out of GPG-004 push-gate/adjudication execution (2026-08-09)

Found while executing the ADR-007 channel, the push-gate slice and the route
adjudication; each was deliberately kept out of those bounded slices.

- [ ] Completion gate: `runtime_evidence_status` (`hooks/completion-gate.sh`)
  reduces the session's L2/L3 signals as one outcome set — a single
  ambiguous/unknown signal or any earlier `fail` poisons the session verdict
  permanently, because there is no latest-signal-per-command reduction; a later
  green rerun of the same command cannot supersede an earlier red or unknown one.
- [ ] Completion gate: `rerun_strict_verification` (`hooks/completion-gate.sh`)
  reads `spec.command`, but the shipped `.itd/VERIFICATION_CONTRACT.json` v2
  schema declares `commands[].argv` — every strict rerun fails closed as
  "verification command is empty", so the strict boundary is structurally
  impassable on argv contracts. Support the argv shape (shell-free) while
  keeping fail-closed semantics for missing/ambiguous commands.
- [x] Live-model benchmark fixture hardening — the Devil's Advocate defect is
  CLOSED under S3 (2026-08-13): headless transports cannot spawn Claude-native
  subagents (claude -p 401 account review; codex has no subagent mechanism),
  so the runner now executes the real `agents/devils-advocate.md` definition
  in a harness-orchestrated SECOND fresh session (definition embedded verbatim
  in the phase prompt; artifact newly created, Debate-Protocol-validated,
  hash-bound; complete-workspace immutability proven; replay verifier enforces
  it fail-closed under --require-evidence). Re-recorded run
  20260813T090330Z-64df7624, full replay 107/107. `/blueprint`'s interactive
  Devil's Advocate stays as designed. Residual honest tail (recorded-run
  provenance polish: fail-open self-validation visible in the old transcript;
  originating user request now pinned only via live-prompt sourcePins) stays
  below.
- [ ] Live-model benchmark provenance polish (residual of the closed item
  above): assert absence of fail-open self-validation in the retained
  transcript and record the originating request as a first-class field.
- [x] Sync-manifest gap: `scripts/sync-to-active.sh` verifies that
  `.claude-plugin/plugin.json` exists but never syncs it, so the installed
  manifest `~/.claude/.claude-plugin/plugin.json` is aligned manually today.
  CLOSED by S7-U4: the manifest is synced (add + content-drift paths, dry-run
  aware) and policed by `scripts/verify-sync-to-active.sh`, with
  `tests/verify_sync_manifest.py` as the behavioral oracle.
- [x] Bounded-process transport hardening (route-adjudication accepted
  trade-offs): reject NaN/inf timeout values before deadline arithmetic and
  harden relative-cwd handling in the Windows wrapper. CLOSED by S7-U1
  (`math.isfinite` guard) and S7-U2 (`wrapper_plan_cwd` anchors a relative cwd
  at the caller before the temp-dir hop). POSIX descendant containment closed
  separately by S7-U3; the run-all host-pin boundary stays open above.
- [x] `itd pr create` fails on an already-pushed branch (S7 finish, 2026-08-14):
  a first attempt timed out AFTER its push succeeded, and every retry then died
  in the pre-push hook — a no-op push produces an empty update stream which the
  hook treats as invalid ("pre-push update stream is empty or invalid"). The
  no-op case should be recognized as already-synced and skip to PR creation.
  CLOSED by S9-U4-PRCREATE: `remote_branch_head` resolves the remote head with
  `git ls-remote` and the absent-PR path skips the push when it already equals
  local `HEAD`; `parse_updates` stays fail-closed on an empty stream.
- [ ] Unexplained nondeterminism in the isolated machine oracle's quick
  aggregator (S9-U4, 2026-08-15): on the identical staged tree `962f862c` with
  the same declared host input, three runs were green and one had
  `bash tests/run-all.sh --quick` exit 1. Red receipt
  `.itd-memory/verification-loop/receipts/a1770aa1284c11fa/S9-U4-PRCREATE-general-review-machine-fe28e0ca6cf6c519.json`,
  green `1c9a2c1ea68e118c` and `40bc24b82d532974`. Receipts retain hashes only,
  so the failing suite name is unknown. Manual reproduction in a
  `git clone --shared` + `read-tree` isolation only ever showed the
  deterministic `verify_independent_review_efficacy (host-owned efficacy
  keyring pin is not provisioned)`, which points at a race in declared-input
  provisioning. Worth retaining a bounded stdout tail (or the failing suite
  name) in the receipt so this is diagnosable without re-running.
- [ ] The completion-signal classifier recognizes failure text but not success
  text (S9-U3, 2026-08-15): `outcome_from`
  (`hooks/completion_lib.py:361-378`) resolves an outcome from an exit code, an
  echoed `EXIT: N`, then `FAIL_TEXT_RE`, then `PASS_TEXT_RE`. This host does not
  supply a structural exit code and a `| tail` masks `$?`, so a verifier
  printing `{"checks": 75, "status": "PASSED"}` is recorded as `unknown` while
  the same verifier's `AssertionError` is recorded as `fail`. The ledger can
  therefore go red and never green again for the same command, and a checker's
  deliberate mutation run blocks the commit until the operator knows to re-run
  with `; echo "EXIT: $?"`. Asymmetric by construction: worth teaching
  `PASS_TEXT_RE` the project's own verifier JSON, or having the runner echo the
  code.
- [x] `itd_unit_log.py activate` does not record the unit's `riskTier`
  (S9-U4, 2026-08-15; **closed by LPD-002 R4** — `--risk-tier` is required at
  activation and written to `STATE.currentUnit`): `skills/task/scripts/itd_unit_log.py:116` writes
  `currentUnit` as `{id, goal, status, startedAt}` only, so
  `detected_risk_tier` in `skills/review/scripts/itd_review_cache.py:250-266`
  falls through to `unknown` and the commit gate then refuses a review receipt
  minted at the unit's real tier. Worked around here by writing `riskTier`
  into `.itd-memory/STATE.json` by hand; the writer is the thing to fix. It
  lives under `skills/`, so fixing it burns the live-evidence pin and does not
  belong inside a `scripts/`-scoped unit.
- [ ] The `pr_view` GitHub lookup still runs BEFORE the push, so a lookup
  outage is a full transport failure (split out of the item above by S9-U4).
  Push-first ordering would decouple them, but it was deliberately NOT taken:
  the pre-push draft check is what rejects a ready (non-draft) PR before any
  push happens, and with an unknown draft state failing closed is correct.
  A safe decoupling needs a different mechanism, not a reordering.
- [ ] gh CLI GraphQL transport fails with TLS handshake timeout from this WSL
  environment while plain REST via curl/urllib works (S7 finish, 2026-08-14):
  `gh pr create/list` and `gh api` die on api.github.com GraphQL; the S7 PR was
  created, un-drafted and merged over REST as a workaround. Diagnose the gh
  HTTP client difference (proxy/IPv6/http2?) or teach the itd transport a REST
  fallback for lookup/create.
- [ ] Pre-existing ledger drift: `GOAL-2026-07-06-axis*` / `PE5-015` unit
  ledgers drifted from current evidence before GPG-004 started. Reconcile the
  ledgers honestly — no synthetic evidence backfill.
- [x] Surface the reviewer-independence label in the local-review profile
  doctor: `validate_local_adjudication` already receives `routeIndependence`
  in the check stdout, but its `str | None` route-label contract (stubbed by
  the doctor regression suite) keeps the doctor entry at
  `routeEvidence`-only. Extend the callable contract and the doctor suite
  together in one bounded change.
  CLOSED by S9-U2-DOCTOR: the contract is now `dict[str, str] | None` carrying
  `routeEvidence` and, when the check printed a member of the closed
  independence class, `routeIndependence`; `profile_doctor_entry` surfaces both
  without lifting the claim. The class is read lazily from
  `itd_reviewer_independence.py` rather than copied, and an unavailable policy
  module reports an empty class so the label is dropped, never trusted.
- [x] Completion-ledger writer schema: agent-delegation telemetry rows are
  written without the `producer` field, so the strict completion evaluation
  fails to parse the ledger (observed 2026-08-09, signals.jsonl line 270,
  audited COMPLETION_BYPASS). Fix the writer and make the evaluator skip
  layer-0 telemetry rows instead of failing closed on them.
  CLOSED by S9-U3-LEDGER: `record-agent-skill.sh` stamps its own provenance
  `itd-record-agent-skill`; both strict evaluators (`hooks/completion-gate.sh`
  and the explicit-close path in `docs/templates/itd/itd_hygiene.py`) exempt
  layer-0 delegation accounting from provenance and runtime-field checks while
  the policy has not declared layer 0 a runtime layer. Layer 2 keeps failing
  closed on a missing or foreign producer.
- [ ] Harden `reviewer_independence_level`: require the shared family to be a
  member of the closed independence class before labeling a same-family pair
  (currently unreachable through minting because the reviewer provider is
  pinned to openai-subscription — reviewer finding, adjudicated
  refuted-by-evidence on 2026-08-09).

## P1 — Should do

- [ ] Build project-aware incremental diagnostics with latency/noise telemetry and a
  default-off policy.
- [ ] Decide promotion only after at least 30 labeled A/B emissions.
- [ ] Build the fresh-session worktree/resource-isolation pilot kit.
- [ ] Run three serial, user-authorized brownfield units in named project roots with
  isolated mutable resources and exact-candidate receipts.
- [x] Narrow the residual-credential detector's assignment false positive
  (U16, 2026-08-11) — **closed under S6-SCRUBBER (2026-08-13)**: the detector
  now captures the assigned VALUE and skips a value that is purely one code
  expression (call, subscript, shell interpolation; trailing prose backticks
  stripped) — a token-named variable assigned from `tokens[position]` and
  prose quoting that line no longer refuse a route, while every exclusion
  carries a true-positive antipair
  (`tests/verify_scrubber_precision.py`, RED-first). The free-reviewer
  producer now runs all three detectors on the SCRUBBED text, matching the
  broker and build_candidate routes and its own "redaction is not a finding"
  contract; the unneutralisable gap (scrub stops at `#`, detector does not)
  is pinned fail-closed. Signed efficacy legs re-minted on the new producer
  bytes.
- [x] Investigate machine-oracle interference between two heavy commands in
  one isolated candidate (U16, 2026-08-11) — **root-caused and pinned under S2
  (2026-08-12)**: the shared state is the HOST, not temp paths or ordering.
  Receipts a45/a46/a47 prove the commands ran serially, each in a fresh
  isolated checkout; the reds are transient fork-level `EAGAIN` failures under
  user-wide process/memory pressure (parallel-session windows), and the
  per-run hit probability scales with subprocess count — measured ≈4429 git
  spawns for `run-all.sh --quick` vs ≈328 for the U16 verifier (~13.5×), which
  explains "verifier green 3/3, quick red" exactly. Natural reproduction,
  receipt analysis, and the fix/pin live in
  `tests/ROOT_CAUSE-s2-oracle-nondeterminism.md`. Promoting the quick suite
  back into the U16 oracle (SCOPE_LOCK criterion 4) stays blocked by the
  unrelated deterministic efficacy-pin red (live-pin friction, see S6).
  Historical record below: minting a receipt with both
  `verify_predeploy_independent_review` AND `run-all.sh --quick` produced a red
  verdict three times at the SAME tree, alternating which command failed
  (quick red / verifier green, then verifier red twice). The verifier run alone
  in the same oracle was green 3/3, and both commands were green outside it.
  U16's accepted exact-candidate oracle was therefore narrowed to the single
  verifier command `python3 tests/verify_predeploy_independent_review.py`
  (deterministic; it self-proves its own CORE registration) — see the scope
  lock's "Machine-oracle shape" and the acceptance contract's U16 `oracleIds`.
  The full `run-all.sh --quick` still runs in pre-commit/CI; it is simply no
  longer this unit's oracle. What remains for S2 is the interference itself: a
  machine oracle that can go red for reasons that are not the candidate is a
  trust problem for every future multi-command unit; find the shared state
  (temp paths, process limits, or ordering) and pin it. (The residual
  `gate_pass_is_current` flake inside the verifier was root-caused and fixed
  under S1, but NOT as first hypothesised: instrumenting every return-False
  branch showed the failing branch was the freshness check with a NEGATIVE age
  — the wall clock stepping backward on WSL2 / NTP, not a racy-clean
  `worktree_clean`. The speculative `git update-index --refresh` change was
  therefore REVERTED; the real fix is a bounded negative clock-skew tolerance
  in the age check. See the scope lock's "S1-flake root cause and fix". This
  S2 item is the broader full-suite interference, not that sub-check.)
- [x] Chase the `verify_session_hygiene_quality` flake seen once during U16
  (2026-08-11) — **root-caused, fixed and pinned under S2 (2026-08-12)**: not
  temp dir reuse or host git state. The unguarded `subprocess.run` in
  `itd_hygiene.py::git()` turned a transient fork `EAGAIN` (host process
  pressure) into an uncaught crash of `close` — rc=1 with EMPTY stdout — which
  the suite misread as a wrong gate verdict (the check needs "working tree is
  dirty" in stdout). Reproduced 40/40 under RLIMIT_NPROC pressure with the
  exact recorded signature. Fix: bounded spawn retry + structured rc=127
  degradation in `git()`, plus a fail-closed positive-proof guard in
  `cleanup_manifest` (a git failure no longer reads as "untracked"). Pinned by
  `test_close_survives_spawn_pressure` (red on pre-fix code via stash run).
  Details: `tests/ROOT_CAUSE-s2-oracle-nondeterminism.md`.

## P1 — GENG: Graph Contract Layer (ADR-009, accepted 2026-08-10)

Decision record: [ADR-009](docs/adr/ADR-009-graph-contract-layer.md). Program
GENG-000…GENG-010 (variant B, approved 2026-08-07; full unit text enters the
repo as a /goal ledger at GENG-000 start). Ordered after the queued GPG
follow-ups (U6/U16/U17); no GENG code before GENG-000 is started as a unit.

- [ ] GENG-000 Harness Readiness Freeze — first GENG unit via /goal; imports
  the program text from the originating sessions into the unit ledger.
- [ ] GENG-003 carries the amended exit criterion: content-addressed node
  receipts with downstream-only invalidation; final integration oracle always
  over the single exact candidate (ADR-009, amendment 3).
- [ ] GENG-004 (Codex Shadow Mode) is entry-gated on a dedicated Codex
  isolated-transport stability check (repeated clean passes; U8's adjudicated
  closure does not itself certify stability — transport root cause unknown);
  serial fallback stays first-class until then (ADR-009, amendment 2).

## P2 — Conditional

- [x] Run a frozen multi-language demand gate.
- [x] Only if activated, add provider-neutral semantic navigation with explicit
  coverage, confidence, and honest fallback.

## Icebox / rejected

- Ralph or any ITD-owned scheduler/runtime.
- Agent-written `DONE.txt` as completion evidence.
- `git add -A`, `--no-verify`, or `--dangerously-skip-permissions` as methodology
  defaults.
- Markdown plans/reports as canonical state.
- A bundled Python-only code-navigation MCP.
- New `plan`, `implement`, `validate`, or `review` lifecycle skills duplicating the
  current pipeline.

## P1 — Recorded in S8 publication route (2026-08-15)

- [ ] The mandatory route grades generated benchmark output as if the candidate
  proposed it. On the S8 re-record candidate the free reviewer returned three
  high findings against `output/PRD.md` and `output/PROJECT_ARCHITECTURE.md`
  inside `tests/fixtures/live-model-evidence/runs/**` — documents the
  model-under-test wrote, which the maker must not edit. Closed for S8 by
  declaring the reviewable properties in `.itd/SCOPE_LOCK.md`; the durable fix
  is for the packet builder to mark recorded-evidence paths as observations so
  the reviewer scores integrity/freshness/hygiene instead of content.
- [ ] The same review claimed the transcript had an unmatched in-progress item
  and no `turn.completed`, and read a sandbox `git status` exit 128 as a
  provenance failure. Both are machine-refutable on the artifact (0 unmatched,
  two `turn.completed`, the failure is inside the disposable adopted project).
  Worth a cheap transcript-shape summary in the packet so the reviewer does not
  have to infer structure from a gzip blob.

## P0 — S9: the route must accept a committed-head candidate

- [x] `itd_free_reviewer_producer.py review` reads `git diff --cached` only, so
  a candidate that is already committed cannot be routed: publication needs the
  LAST commit of the branch reviewed, and re-staging it re-introduces the
  dirty-state problem this repo hit twice (2026-08-14 whole-branch attempt,
  2026-08-15 ledger commit). Teach the producer a `--candidate-mode
  committed-head` that binds parent->HEAD with the same exact tree/diff the
  machine receipt uses, mirroring `itd_verification_loop`. User decision
  2026-08-15: this is unit S9; until then a closed followup (S8-POLICY) keeps
  the matrix from blocking later commits.
  CLOSED by S9-U1-COMMITTED-HEAD: `freeze_packet` takes a `candidate_mode`, and
  `review --candidate-mode committed-head` resolves the parent from
  `git rev-list --parents -n 1 HEAD`, rejects anything that is not a
  single-parent commit, and requires the index to equal `HEAD^{tree}` — so the
  existing `git diff --cached <parent>` yields exactly `parent..HEAD` and the
  exact-candidate math is unchanged. `staged` stays the default; the clean-tree
  requirement is not relaxed. Proven equivalent: the packet frozen from an index
  and the packet frozen from the commit of that same index agree on tree,
  diffSha256, parentCommit and baseCommit.

