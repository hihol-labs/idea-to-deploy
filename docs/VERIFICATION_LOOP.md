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
| high / unknown | required | full, fresh session and different model or provider |

Missing checker evidence is `UNVERIFIED`, never implicit success. Majority
vote is not evidence. One checker is sufficient only when it closes a named
semantic contour that machine oracles cannot decide.

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
durable, Git-ignored Verification Loop directory.
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
  --checker-model "$CHECKER_MODEL" --checker-session "$CHECKER_SESSION")

ADJUDICATION_RECEIPT=$(sh "$SHD/itd_py.sh" "$VL" adjudicate --root . \
  --unit-id "$CLAIM_ID" --risk-tier "$RISK_TIER" \
  --machine "$MACHINE_RECEIPT" --checker "$CHECKER_RECEIPT")
```

The checker report must end with the canonical JSON verdict block containing
`verdict`, `findings`, and `unverified`. Any candidate, policy, prompt, report,
receipt dependency, risk, or unit change invalidates the chain.

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
