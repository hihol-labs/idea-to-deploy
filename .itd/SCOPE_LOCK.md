# ROUTE-REPAIR-2

**Публикация закрытия леджера (2026-09-14) - отдельный кандидат этого же юнита.**
Код-кандидат смержен как `dee34a3` через PR #289, Gate 1 и windows-verify зелёные,
`--no-verify` не применялся ни разу за юнит. Переход в леджере уже сделан ХАРНЕСОМ:
`itd_goal_verify --candidate-mode committed-head` вернул `VERIFIED` с
`actor: harness` и `verifiedAt 2026-09-13T21:21:55Z`, 47/50. Это первый машинный
close после ДВУХ подряд закрытий маршрутом владельца (RSI-DEBT-2 2026-09-12,
ROUTE-REPAIR-1 2026-09-12); маршрутом владельца закрыты три из четырёх
предшествующих юнитов, но не подряд - между REL-1.104.0 и RSI-DEBT-2 стоит
машинный close BROKER-ISOLATION 2026-09-11. Формулировка «three units in a row»
в смерженном код-кандидате и близкая формулировка «ВПЕРВЫЕ за четыре юнита»
в описании `session_2026-09-14.md` не совпадают с журналом событий; принятое
evidence не переписывается, расхождение записано в BACKLOG. Этот кандидат
публикует уже записанный переход и то, что маршрут стоил.

Allowed для кандидата закрытия ровно пять путей: `.itd-memory/GOAL.json`,
`.itd-memory/STATE.json`, `.itd-memory/events.jsonl` (все три уже записаны
харнесом и агентом не редактируются), `BACKLOG.md` (новые записи и поправки к
двум существующим) и этот файл. `.itd/ACCEPTANCE_CONTRACT.json` НЕ трогается:
строки `ROUTE-REPAIR-2-1..4` внесены код-кандидатом и стоят `passed`, а
`activeFollowup` был закрыт ещё на ROUTE-REPAIR-1, поэтому открывать и тут же
закрывать followup ради формы значило бы подгонять запись под класс.

Forbidden дополнительно к списку ниже: редактировать `verified`, `evidence` или
`verifiedAt` руками; переписывать запечатанный критерий RSI-DEBT-3; активировать
RSI-DEBT-3 до мержа этого кандидата (WIP=1).


Current unit ROUTE-REPAIR-2, medium risk, activated by the harness on 2026-09-13. Owner-approved queue (2026-09-12, superseding the 2026-09-08 order): ROUTE-REPAIR-1 (done, merged 2d50a12) -> ROUTE-REPAIR-2 -> ROUTE-REPAIR-3 (the metric sees the route) -> RSI-DEBT-3. One plan item is one session.

One measured root, three places. The binding a consumer expects is fixed, while the only honest receipt the lifecycle can produce at that point does not match it, so the route either refuses valid evidence or accepts evidence that attests to nothing.

First place, measured mechanically on the clean merged head 1a31fea: `candidate_context(repo, "low", "staged")` returns `diffHash e3b0c44298fc...`, which is the sha256 of the empty string, while `committed-head` on the same tree returns `0d121610aa7c...`. A staged receipt minted after a merge therefore does not fail - it succeeds and binds an EMPTY candidate. Second place: `itd_goal_verify.validate_verification_receipt` calls `validate_adjudication` with the default staged mode and has no way to say committed-head, so the post-merge transition has no honest route at all. Three units in a row were closed by the owner rather than the harness: REL-1.104.0, RSI-DEBT-2, ROUTE-REPAIR-1, against 3 owner-route rows in 15 verified unit events overall. Third place: `itd_review_cache.validate_review_receipt` validates against claim id `<UNIT>:general-review` while receipts were minted under the bare unit id. This one is NOT a code defect - a live probe on 2026-09-13 minted a machine receipt and an adjudication under `ROUTE-REPAIR-2:general-review` and `validate_adjudication` accepted the chain under exactly the claim id the cache builds, and `v2_primary_unit` supports the suffix by construction. The defect is narrower than it was first written here and is corrected by measurement: the route DOES name the claim id, in `docs/VERIFICATION_LOOP.md` inside the `CLAIM_ID is G-00X for /goal` comment of the canonical producer sequence (cited by content, because this candidate inserts lines above it and any line number recorded here would be stale the moment it lands - independent review caught exactly that). What it did not say is the consequence - that every link of the chain must carry the same id, that `itd_review_cache` is the consumer that refuses otherwise, and what its refusal looks like - so the discovery was paid for once per session even though the code always supported it.

Allowed: the empty-candidate refusal in `skills/_shared/itd_verification_loop.py`; an explicit candidate mode in `skills/goal/scripts/itd_goal_verify.py` with a clean-worktree and single-parent precondition; the route documentation that names the `<UNIT>:general-review` claim chain; RED-first additions to `tests/verify_verification_loop.py` and `tests/verify_goal_tools.py`; canonical unit ledgers and the acceptance rows of this unit; the BACKLOG records named below. Pin outcomes are measured, not assumed.

Required: both legs of the sealed verificationCommand exit 0 - `tests/verify_goal_tools.py` and `tests/verify_verification_loop.py`. RED-first is observed on the pre-fix bytes for the same candidate before the fix is accepted. Each of the three guarantees is killed by its own mutation, and the mutation table is recorded with its measured outcomes rather than asserted. EVERY mutation in the table is re-measured in ONE run after the last edit, against the baseline it is quoted with, because this candidate already produced a table that its own next commit invalidated. The requirement names no count on purpose: an earlier wording fixed it at eleven, the set grew to sixteen as findings were closed, and the frozen number went stale exactly the way the quoted totals did - independent review caught that too. The table is authoritative for its own size; the mutations are enumerated in the acceptance evidence of the criterion each one defends. The full mirror's ACTUAL last line is recorded with every red suite attributed to this candidate or to pristine main by a clean-worktree run. A `/review` route before the multi-file commit, then the cross-vendor producer. Existing accepted evidence stays immutable: no ledger row is rewritten, relabelled or relocated.

Two scope reductions were measured before the criterion was sealed and are recorded here so the reduction is auditable rather than silent. The live-benchmark pin cascade is NOT in this unit: the pin holds 60 files, and over the last 20 first-parent merges only 4 touched it, two of which are release commits that must re-pin by construction - 2 of 18 non-release merges, after N4 (PR #235) cut the pin from 231 files to 60. The `routeIndependence: null` observation is NOT in this unit either: for a low risk tier `adjudicate` refuses `--checker` by design ("low-risk machine-only route must not spend a checker"), so binding a signed cross-vendor PASS there changes the cost policy of the low-risk route rather than a binding, and that is a separate decision. Both go to BACKLOG as records.

Forbidden: touching `PE5-008` or `PE5-009` (blocked until real external adoption evidence); weakening any existing binding - the empty-candidate refusal and the committed-head mode must both narrow what is accepted, never widen it; accepting `committed-head` on a dirty worktree or a merge-parent HEAD; changing `VERDICT_SCHEMA` or `UNIT_VERDICT_SCHEMA`; letting one review receipt unlock both the general and the security claim; introducing a round ceiling, which `.itd/STOP_RULE_POLICY.json` forbids by construction; `--no-verify` (if a gate refuses, the exact command goes to the owner); starting ROUTE-REPAIR-3 or RSI-DEBT-3 in this session.
