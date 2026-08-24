# Verification Loop v1

Idea to Deploy accepts work through a risk-tiered, proof-carrying loop. An
agent's prose is a claim, not evidence. The harness executes machine oracles,
binds every artifact to the exact staged candidate, consumes a fresh checker
report when risk requires it, and issues an adjudication receipt. Only that
receipt may move a goal to `verified` or create a reusable review-cache hit.

## Trust boundary

The trust root is an honest host orchestrator. Receipts prove exact-candidate
integrity, command execution, freshness, dependency hashes, and the declared
maker/checker separation. They detect stale or edited evidence. They do **not**
cryptographically distinguish two malicious processes running as the same OS
principal, attest a model identity, or survive a compromised orchestrator.
Those stronger guarantees require a host/provider signature API that is not
portable across Codex and Claude today. External outcome claims remain
`UNVERIFIED` without external evidence.

This boundary is intentional: the loop targets false completion, correlated
reasoning errors, stale review reuse, and accidental self-certification. It is
not presented as a security boundary against the machine owner.

## Risk routes

| Risk | Machine oracle | Independent checker |
|---|---|---|
| low | required | forbidden as unnecessary cost |
| medium | required | targeted, fresh session |
| high / unknown | required | full, one fresh opposite-GPT model/session report |

Missing checker evidence is `UNVERIFIED`, never implicit success. One checker
is sufficient for medium/high/unknown risk; the host preserves machine, unit,
integration and reviewer negative evidence.

### Mandatory keyless pre-PR checker

Medium/high-risk PR publication uses one shared checker producer:
`skills/_shared/itd_free_reviewer_producer.py`. Its fixed route is
`Sol -> Terra` and `Terra -> Sol`: exactly one fresh opposite OpenAI
model/session. `BLOCKED`, `UNVERIFIED`, `UNAVAILABLE`, malformed
provenance, same-model/session evidence, or tool use stops the gate. If every
reviewer is unavailable, publication of that candidate remains unavailable.
Anthropic, GitHub Copilot, Antigravity and paid API adapters are optional
separately invoked facilities, not automatic fallbacks or quorum members.

An evidence-first policy runs before transport selection. Every active
acceptance criterion maps generic impact classes to one or more exact-tree
machine-oracle IDs. The active policy declares the complete required impact
set. Missing, failed, duplicate, foreign-tree or uncovered evidence is
`UNVERIFIED` before a model can return `PASSED`. The isolated machine oracle is
the read-only explorer; the model cannot replace an absent scale,
reconciliation, numerical-stability, generated-artifact, performance or output
bound with prose.

Transport absence is positive evidence, not a catch-all for CLI failure.
Missing validated auth/transport, an allowlisted auth/quota/network/status
failure, or a bounded process timeout may produce `UNAVAILABLE`. Unknown
non-zero exits, argument/protocol defects and oversized failure output are
terminal `UNVERIFIED` and cannot advance to another provider.

The keyless producer applies the broker's same frozen size policy before model
dispatch. A direct review is used only while the complete scrubbed diff fits
the direct bound. Larger valid candidates are deterministically partitioned at
complete-file then UTF-8 line boundaries into at most 16 exact byte-range
units; every unit is reviewed in a fresh isolated session by the selected
provider/model and one final integration review is mandatory. The signed
prompt artifact is then a canonical bundle of the root binding, plan, every
unit prompt/report, the raw integration report and the integration prompt.
The host deterministically unions all unit and integration findings; a clean
integration answer cannot erase a unit blocker. Missing, reordered, changed,
mixed-model, session-reused, incomplete, or oversized bundle evidence is
`UNVERIFIED`; no unit may be truncated or silently skipped.

The phase-one v2 signature binds the exact single-reviewer attempt prefix, the
fresh opposite-GPT identity and canonical prompt/report artifact. The producer
and broker reject missing, skipped, duplicated, mistyped, unauthorized-model
or foreign entries before publication evidence can be authorized. Phase-one
v3 remains readable compatibility evidence but is not required by this route.
The shared producer persists that receipt plus its exact direct prompt or
hierarchical prompt bundle and canonical integration report. The checker binds
all three together with the producer public-key
keyring. For local publication, the host-owned gate registry additionally pins
that keyring's SHA-256 and the installed validator rejects any candidate-chosen
replacement. A generic checker remains available for non-publication diagnostics,
but `local-submission` validation invokes `check --require-mandatory-route` and
therefore rejects any generic adjudication before guarded PR publication.
Structurally valid negative output persists the exact prompt, report, reviewer,
and attempt prefix for repair, but it never creates a phase-one receipt.
Before initial PR creation, the signed target binds the canonical repository
with `pullRequest=null` and `expectedHeadSha=null`; the unchanged commit bridge
then proves the reviewed parent/tree/diff. Existing-PR/App flows require the
positive PR number and exact head SHA. Local publication also compares the
signed repository with the selected gate registry entry.
The consumer proves signed `baseCommit` is an ancestor of `parentCommit`, then
reconstructs the complete binary base-to-staged/committed diff and compares
both its SHA-256 and byte count. A signed foreign base cannot skip exact-range
binding or borrow the machine/checker candidate.

The keyless producer normally sends that exact Git diff. If the candidate
contains a path ending in `.jsonl.gz`, it instead uses the broker's frozen
`gzip-jsonl-utf8-v1` transparent-review contract: complete base/index Git blobs
remain hash/size/mode bound, exactly one bounded gzip member is decoded, every
non-empty UTF-8 JSONL record is parsed with duplicate keys and non-standard
constants forbidden, and a separately hashed canonical logical diff is sent
to the checker. The signed raw candidate digest and byte count do not change.
Any other binary path, malformed/extra gzip member, invalid JSONL, oversized
logical representation, or scrub finding is terminal `UNVERIFIED`. The
producer also recomputes the prompt from the frozen packet before signing, so
a caller cannot substitute a different review representation after freezing.

There is no caller bypass. `/review` and `/cross-review` are two entry points to
this same producer, not separate evidence authorities. The default route uses
installed user/subscription authentication, does not require provider API
keys, and does not dispatch a paid API request. The resulting exact-candidate
checker evidence is accepted only through normal Verification Loop
adjudication.

The frozen independent-review efficacy pack is a release oracle. Deterministic
mutations measure missing-evidence detection and unit-finding retention. Real
no-tools keyless reports over hidden expected faults measure 100%
critical/high blocker detection, at least 90% medium detection and at most 10%
clean-control false blocks. Reconstructed prompt hashes, current
producer/manifest hashes, distinct sessions and coherent host runtimes must all
match, and fresh reports must independently pass on WSL and native Windows.

Reviewer model identity is never copied from the caller's requested argument.
The producer reads one pinned transport runtime source: the single rollout in
an otherwise empty temporary Codex home, Claude's one `modelUsage` entry, or
Copilot's JSONL event stream. It requires the observed model to match the requested
approved model/alias or the closed Copilot Free auto-model allowlist. Missing telemetry is `UNAVAILABLE`; multiple or changed
models are `UNVERIFIED`. The temporary Codex rollout exists only long enough to
read session/model provenance and is deleted with the isolated auth home.
Independence compares conservative canonical provider/model families, not only
raw strings. In particular, Anthropic aliases such as `opus`, `sonnet`, and
`haiku` are the same identities as their runtime `claude-<family>-*` telemetry
within the Anthropic provider family. The route, phase-one producer, and
phase-one verifier all apply this comparison, so a re-signed alias cannot turn
a same-model fallback into independent evidence. The broker applies that same
identity to enrollment authorization: an enrolled `opus` family accepts its
observed `claude-opus-*` runtime name but not an unlisted `claude-sonnet-*`.

GitHub Copilot receives the exact self-contained packet only through stdin.
Its pinned native executable must advertise every invoked flag before review.
The producer runs an empty temporary project and `COPILOT_HOME`, forces free
`auto` mode with a bounded session, disables custom instructions, builtin MCP,
remote control/export, updates, tools and logging, and preserves only the
host-native GitHub credential coordinate. The oracle requires exact stdin,
one stable allowed runtime model/session, zero tool requests, zero file
changes, and a closed 0..1 included-premium-request bound from the JSONL stream.

Codex model/session telemetry is read from its one private fresh-session
rollout. The review packet remains capped at 2 MB and captured stdout/stderr at
1 MB. Because the rollout also contains internal runtime events, that ephemeral
container has its own 16 MiB hard cap; it is never durable evidence and is
deleted with the isolated auth home after provenance is extracted.

The clean-checkout invariant is rechecked before machine execution, when
checker evidence is minted, during adjudication, and whenever an accepted
receipt is consumed. The machine oracle itself runs in a disposable local Git
checkout materialized only from the staged tree. Ignored source-worktree
inputs such as `.env`, build output, `.venv`, or `node_modules` are therefore
not copied and cannot create a false pass. The isolated tree and index are
rechecked after the oracle; tracked mutation invalidates the result. A command
that genuinely needs a non-Git input must declare each minimal path with
`--input`. The harness snapshots it into the isolated checkout, seals its hash
in the machine receipt, and revalidates both source and snapshot before the
receipt can be adjudicated or reused. Machine run records use a closed schema
that retains SHA-256 digests of stdout/stderr but never raw output or diagnostic
tails, so alternate field names cannot turn secrets or PII into durable memory.

## Canonical producer sequence

Keep the checkout identical to the staged index; unstaged or non-ignored
untracked files fail closed. Put the exact checker prompt and report under the
durable, Git-ignored Verification Loop directory. Start the prompt from
[docs/templates/CHECKER_PROMPT.md](templates/CHECKER_PROMPT.md): it carries the
literal verdict block and the closed verdict set, because a checker that
finishes with `PASS` instead of `PASSED` produces an `UNVERIFIED` receipt and
the whole review has to be run again (live incident, 2026-08-18).
Checkout probes allow a 60-second host-adapter deadline so native Windows Git
can inspect a WSL UNC worktree without weakening the exact-tree comparison.
Oracle commands use the native shell transport: `cmd.exe /d /c` on Windows
and `sh -c` on Unix/WSL. Windows UNC worktrees are entered with process-local
`pushd`; the selected executable and `isolated-staged-tree` execution mode are
recorded in each run. Maker and checker provider/model/session fields must all
be present and are compared after normalization; missing or padded provenance
cannot manufacture apparent independence.

```bash
SHD="skills/_shared"
VL="$SHD/itd_verification_loop.py"

# CLAIM_ID is G-00X for /goal, or <active-unit>:general-review /
# <active-unit>:security-review for cache gates.
MACHINE_RECEIPT=$(sh "$SHD/itd_py.sh" "$VL" machine --root . \
  --unit-id "$CLAIM_ID" --risk-tier "$RISK_TIER" \
  --command "oracle=$VERIFICATION_COMMAND" \
  ${DECLARED_MACHINE_INPUT:+--input "$DECLARED_MACHINE_INPUT"})

# Omit checker + --checker only for low risk. Provider/model/session values
# come from host-observed orchestration metadata, never reviewer narration.
CHECKER_RECEIPT=$(sh "$SHD/itd_py.sh" "$VL" checker --root . \
  --unit-id "$CLAIM_ID" --risk-tier "$RISK_TIER" --mode "$CHECKER_MODE" \
  --prompt-file "$PROMPT_FILE" --report "$REPORT_FILE" \
  --maker-provider "$MAKER_PROVIDER" --maker-model "$MAKER_MODEL" \
  --maker-session "$MAKER_SESSION" --checker-provider "$CHECKER_PROVIDER" \
  --checker-model "$CHECKER_MODEL" --checker-session "$CHECKER_SESSION" \
  --phase-one-receipt "$PHASE_ONE_RECEIPT" \
  --producer-keyring "$PRODUCER_KEYRING")

ADJUDICATION_RECEIPT=$(sh "$SHD/itd_py.sh" "$VL" adjudicate --root . \
  --unit-id "$CLAIM_ID" --risk-tier "$RISK_TIER" \
  --machine "$MACHINE_RECEIPT" --checker "$CHECKER_RECEIPT")
```

The checker report must end with the closed canonical JSON verdict block
containing exactly `verdict`, `findings`, and `unverified`; no missing field is
defaulted. For publication, `PHASE_ONE_RECEIPT`, `PROMPT_FILE`, and
`REPORT_FILE` are the three outputs of the shared keyless producer and the
keyring maps its key ID to the trusted Ed25519 public key. Any candidate,
policy, prompt, report, signed route, machine receipt, risk, or unit change
invalidates the chain. The producer also writes a prompt ledger next to
`PROMPT_FILE` (`<prompt-output>.ledger.jsonl`, or `--prompt-log`): every prompt
handed to the reviewer transport, byte-exact, appended before the send and
bound into the signed receipt (`promptLedger`). `itd_free_reviewer_producer.py
verify-prompt-log --prompt-log <ledger> --receipt <phase-one.json>` recomputes
the hashes and exits non-zero with `UNVERIFIED` on any missing, extra, or
altered entry — model-visible means logged, checked by machine, not by prompt
discipline.

An external model is only a checker transport. The canonical keyless producer
above prepares and validates the exact-candidate review and records
host-observed maker/checker provenance. Any separately operated paid API
adapter is optional infrastructure and cannot replace, weaken, or mint the
mandatory route's evidence. See `docs/API_REVIEWER.md` and ADR-003.

## Repair and terminal states

The harness atomically allocates an append-only attempt ledger for each
candidate and claim. `--attempt N` is only an optional assertion of the next
sequence number; it cannot reset the counter. The loop is bounded to three
adjudication attempts per candidate. A machine failure is journalled as
`failed`; a machine pass without accepted checker evidence is journalled as
`unverified`. Neither may transition to `verified`. After the attempt budget,
stop at `budget_exhausted`/`RECOVERY_REQUIRED` and escalate instead of adding
more agents or votes.

Every machine, checker, adjudication, and ledger receipt is published as a
complete immutable file with a collision-resistant producer-run/content name:
an atomic hard link on Unix, and an atomic no-replace rename on Windows
(including WSL UNC/SMB worktrees). Retries append evidence instead of replacing
dependencies of an earlier adjudication. After a host interruption, a dead
allocation lock is reclaimed and a complete adjudication receipt published
immediately before the interruption is validated and reconciled into its
missing ledger entry. Conflicting or partial evidence fails closed and is
preserved for explicit recovery.
The `itd-live-fixture-v1` transcript proves workflow output quality in an
adopted repository; it is explicitly **not** independent-review isolation or
efficacy evidence. Reviewer efficacy is measured separately by the frozen
`benchmarks/independent-review-efficacy` corpus, using real no-tools keyless
reports on both WSL and native Windows plus deterministic evidence/union
canaries.

## Authority snapshot: minting and byte-parity (LPD002-A8)

The pre-PR producer runs from a snapshot OUTSIDE the repository
(`~/.cache/itd-review-authority/<id>/`) and inserts its own directory into
`sys.path`, so it judges candidates with the snapshot's modules — the gate
behavior is frozen at minting time. Measured on R5: a pre-R5 snapshot would
have judged a ledger-close candidate with the old gate and reproduced the
exact circle R5 removed.

**Minting procedure** (from the MERGED main, never from a working branch):

1. Create `~/.cache/itd-review-authority/<UNIT>-<tree8>-a1/` where `<tree8>`
   is the first 8 hex of the merged tree the modules are copied from.
2. Copy every `skills/_shared/*.py` module and `skills/_shared/*.json`
   policy byte-for-byte into the snapshot directory.
3. Carry over the signing material unchanged from the previous snapshot:
   `producer-ed25519.key` and `producer-keyring.json` (key id stays; the
   keyring sha is what gate registration pins). Keys are snapshot-local by
   design and are NOT part of parity.
4. The boundary stands: the producer executes from the snapshot, outside the
   repository checkout.

**When to re-mint:** whenever a merged change alters review-gate behavior —
any edit to `skills/_shared/itd_review_evidence.py`,
`itd_free_reviewer_producer.py`, `itd_review_broker.py`, the review policies,
or their dependencies. When in doubt, run the parity check.

**Byte-parity check (fail-closed, run before trusting a producer receipt):**

```bash
python3 scripts/itd_authority_check.py --snapshot ~/.cache/itd-review-authority/<id>
```

Exit 0 — every snapshot module/policy is byte-identical to `skills/_shared/`
(quiet). Exit 1 — divergence, each line names the file with WHY and FIX
(re-mint from merged main). Exit 2 — input error, including a `--repo` that
is not a git checkout: parity against a bare directory that merely contains
`skills/_shared` proves nothing, so the check refuses it fail-closed. The
check attests byte-parity against the checkout you point it at — the
merged-main provenance comes from the minting procedure above and from
running the check in the canonical checkout at gate registration. The oracle
is `tests/verify_authority_check.py`.

## Stop rule over finding content (LPD-003-3)

Раунды ревью останавливали по их числу. Замер трёх записанных историй
показал, что число раундов не измеряет ничего.

- **Заход не равен раунду.** Из десяти заходов публикации LPD-003-1 вердиктов
  ревьюера было три: два отказа предусловия (критерии приёмки в статусе
  `pending`, несовпадение `--unit-id`) и пять отказов транспорта суждениями о
  кандидате не являются. Правило считает только вердикты; вход без
  объявленного класса терминала отвергается fail-closed.
- **Потолок раундов останавливает сходящийся маршрут.** R6 шёл тринадцать
  раундов, каждый называл НОВЫЙ механизм и закончился чистым PASS. Потолок в
  три или в восемь раундов отгрузил бы кандидата с воспроизведённым эксплойтом
  (PUB9).
- **Зелёный сэмпл не доказывает исчерпания.** В S04b раунд PUB5 дал `PASSED`,
  а следующие раунды нашли в том же механизме ещё четыре реальных дефекта.

Сигнал остановки — **повтор одного механизма через раунды**. Ключ механизма —
пара (файл, класс дефекта), вычисляемая прямо из отчёта; ни severity, ни номер
строки в ключ не входят (номер строки дрейфует внутри одного механизма).
Один ключ в двух и более РАЗНЫХ раундах означает, что после попытки фикса тот
же механизм сломался снова: дефектна форма решения, а не экземпляр.

```bash
python3 scripts/itd_stop_rule.py --history tests/references/stop-rule/s04b.json
```

Повтор засчитывается только тогда, когда запись устанавливает, что между
вхождениями МЕНЯЛСЯ КАНДИДАТ: два независимых ревью одного и того же
неисправленного кандидата — это не повтор механизма, а два взгляда на одну
находку. Личность кандидата раунд объявляет полем `candidate`; если её нет,
правило говорит `RECURRENCE_UNCONFIRMED` и называет нехватку улики вместо
вердикта, которого не заслужило.

Порядок применения: `ROUTE_DEFECT` -> `REDESIGN_OR_DISCARD` ->
`RECURRENCE_UNCONFIRMED` -> `ROUTE_REPAIR` -> `CLOSE` -> `CONTINUE`.
`ROUTE_REPAIR` — исход истории, в которой вердиктов нет вовсе или последним
сорвался маршрут: чинить надо то, что сломалось, а не звать новый раунд.
`ROUTE_DEFECT` идёт первым, потому что вердикты, вынесенные по политике чужого
юнита, о кандидате не свидетельствуют вовсе — это проверка привязки приёмочной
бухгалтерии, и её стоит делать ДО первого захода:

```bash
python3 scripts/itd_stop_rule.py --check-binding
```

Правило **advisory**: оно печатает терминал, основание и поимённый список
раундов; решение принимает владелец. Контракт — `.itd/STOP_RULE_POLICY.json`,
оракул — `tests/verify_stop_rule.py`, записанные истории и байт-копии
цитируемых отчётов — `tests/references/stop-rule/`.
