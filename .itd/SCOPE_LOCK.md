# Scope Lock — U16: pre-deploy independent review gate, risk-tiered

## Current Task

GPG-004 ladder point U16 (approved plan 2026-08-09, opened 2026-08-10 with
user-approved plan): `/deploy` must not execute a mutating step for a change
whose derived risk class is data-sensitive, irreversible or monetary without a
fresh Verification Loop adjudication receipt bound to the exact deploy
candidate. Missing or stale receipt is fail-closed. The criterion's only
bypass class, `HUMAN_OVERRIDE_NO_INDEPENDENT_REVIEW`, requires a recorded
reason and a signature; no signed minting channel exists yet, so the gate
refuses every override for every gated class (the strict branch; signed
channel queued in BACKLOG). Mutation-tested in both directions.

## ADR-008 amendment — shipment-scoped receipt gate (2026-08-12, user-approved)

**Supersedes the allow-list-era design described in the r53–r89 history below.**
Those sections are retained as the decision record for how the redesign was
reached; the *current* contract is this amendment.

**Why the redesign.** The previous hook tried to statically parse an arbitrary
shell command to prove it "ships only the reviewed artifact and executes
nothing else". That is undecidable over a Turing-complete shell. Across rounds
r53–r89 the independent reviewer oscillated between under-blocking (an `rm -rf`
or a hidden transport slipped) and over-blocking (`pytest`, build/test runners
falsely denied on a gated repo), and `findings=[]` was structurally
unreachable — so the high-risk commit that U16 requires could never be minted.
Proven dead end: "commit now + do not lower the bar + parse the shipment form"
are mutually incompatible.

**New contract (tractable, closeable).** The hook no longer analyses the
shipment form. For a gated candidate:

- a **recognised deploy transport** (rsync/scp/ssh/tar-non-read-only/curl/wget/
  nc/rclone/aws/gcloud/docker-push/kubectl/helm/terraform/pulumi/flyctl/vercel/…),
  or a statically **opaque** command that could hide one (command/process
  substitution, `eval`/`source`/`.`/`xargs`, `case`/`select`, a non-lexable
  segment), run **without a valid current pass → DENY** (exit 2, typed WHY/FIX);
- a **valid current pass** — earned through the Verification Loop adjudication
  receipt bound to the exact candidate digest + deploy input, MAC-authenticated
  by a host-owned key outside the checkout — **→ ALLOW** (the deploy was
  independently reviewed; the hook does not re-judge its shape);
- **ordinary local code execution** (interpreters `python`/`node`/`make`/`npm`,
  script files `bash x.sh`, path-qualified/custom executables) and **local file
  operations** (`rm`, `mv`, editors) are **out of scope → ALLOW**. Proving they
  ship nothing is the same undecidable problem; that residual is a documented
  honest limit covered by `/careful`, the completion gate and human deploy
  review, NOT by this hook. A recognised transport is still gated wherever its
  word appears, path-qualified included (`/usr/bin/rsync` is judged as rsync).

The r89 finding-1 (`rm -rf` passes the gate) is therefore **not a finding but
declared scope**: local destruction was never U16's job.

**Surface collapse → closeable.** With the shipment-form analysis removed the
reviewer has nothing to oscillate over: the only questions are "is there a
valid pass?" and "is the command a recognised-transport head or an opaque
command?". Both are decidable. The review bar is NOT lowered — the surface is
collapsed.

**Code + test changes.** `hooks/check-predeploy-gate.sh`: `main()` allows on a
valid pass; `_invocation_class` narrowed (recognised transport + opaque → gate;
all other local execution → safe); the entire shipment-form analysis (17
functions + its flag tables) deleted as dead code (reachability-proved: 0 dead
functions/constants remain, py_compile clean). Receipt-core in
`skills/deploy/scripts/itd_predeploy_gate.py` (gate_pass_is_current, clock-skew
tolerance, recorded_deploy_input_path MAC+digest binding) is unchanged — it is
the foundation of the new design. Oracle
`tests/verify_predeploy_independent_review.py` rewritten to the new contract
(**103 assertions**, was 366 about the removed form): transport-deny matrix,
wrapper-masking, dynamic/opaque deny, per-invocation chain, ADR-008 local-
execution allow matrix, commented-substitution-is-inert allow, read-only
allow, routine allow, valid-pass-allow core, full receipt-core internals,
override cannotWeaken refusal, opaque-form gating (function defs, sudo/env shell spawns, tar exec option, case), the r65 cd-escape guard, receipt-validation delegation (`validate_receipt` missing/invalid/valid +
`evaluate_gate` + a real `check --receipt` negative — a valid signed
adjudication receipt → allow is exercised by the unit's own live
producer→adjudicate→check chain, a stated boundary), trust anchor;
`tests/verify_predeploy_gate.py` 11/11 (one form-specific case updated to the
ADR-008 valid-pass-allow rule).

## Allowed zones

- `tests/verify_predeploy_independent_review.py` (new, RED-first)
- `skills/deploy/scripts/itd_predeploy_gate.py` (new, stdlib-only)
- `skills/deploy/SKILL.md` (Step 0 врезка + rule line; no new skills)
- **Visible amendment 2026-08-10 (route finding r32, user decision A):**
  `hooks/check-predeploy-gate.sh` (new PreToolUse hook) + its one-line
  registration in `hooks/hooks.json`. The independent reviewer blocked the
  candidate because a prose-only Step 0 does not make `/deploy` fail-closed:
  skipping the step skipped the gate. The zone is widened deliberately and
  minimally — one hook plus its registration, no other hook or skill
  touched — because no smaller change can satisfy the unit's own criterion.
- `tests/run-all.sh` (register the new verify in the quick/CORE list)
- `.itd/SCOPE_LOCK.md` (this contract)
- `.itd-memory/STATE.json` (unit bookkeeping via itd_unit_log.py)
- `.itd/ACCEPTANCE_CONTRACT.json` — **visible amendment 2026-08-10** (route
  finding, first cross-vendor pass): the evidence-first producer requires the
  active claim (`activeFollowup.unitId = U16:general-review`) and per-unit
  criteria (`U16:general-review-1..3`) in the acceptance authority, and an
  honest per-unit `requiredImpactClasses` set. The edit is additive and
  minimal (criteria + activeFollowup fields only, original formatting
  preserved); no pre-existing criterion is altered. Submitted to the
  independent reviewer's judgement, per the GPG-004 precedent for
  out-of-zone contract amendments.
- **Authorized out-of-zone propagation (route r45 scope-compliance
  finding, AUTHORIZED):** the inventory-count propagation files are the
  mechanical consequence of registering a 30th hook, and the repository's
  own freshness/parity suites fail without them:
  `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`,
  `benchmarks/operational-friction/BYPASS_FRICTION.{json,sha256}`,
  `docs/HARNESS_DOCS_STATE.json`, `docs/HARNESS_TRUST_POLICY.json`,
  `docs/CONTRACTS.md`, `docs/HARNESS_ENGINEERING_MAP.md`,
  `docs/templates/global-claude-md.md`, `README.md`, `README.ru.md`,
  `hooks/README.md`, `hooks/hooks.json`, `scripts/sync-to-active.sh`,
  `skills/adopt/references/{codex-project-hooks.json,project-settings-template.json}`,
  and the hook-count assertions in `tests/verify_*`. No behaviour outside the
  gate changes in any of them — they carry counts, registration and
  documentation of the one new hook.
- **`BACKLOG.md` — visible amendment 2026-08-11 (route r59 scope finding,
  AUTHORIZED):** the unit's own review rounds produced follow-ups the
  methodology records in the backlog (machine-oracle non-determinism → S2
  diagnosis, scrubber detector precision → S6, the image/manifest provenance
  binding unit from r58). Recording follow-ups where the process requires
  them is part of closing the unit honestly; the file carries no behaviour.

Untracked local stores alongside: `.itd-memory/contracts/U16.md`,
`.itd-memory/GPG-004_UNIT_PLAN.json`, `events.jsonl` (harness writer).

## Acceptance (unit criterion, verbatim anchors)

1. `python3 tests/verify_predeploy_independent_review.py` exit 0 (the unit
   verificationCommand), with mutation coverage both directions:
   removing/unwiring the gate fails the check; an unconditional gate fails the
   negative control (routine deploy without a receipt must pass).
2. The bypass class is never reported as PASSED and never counted as
   independent-review evidence (`cannotWeaken`). The criterion requires the
   bypass to carry a recorded reason AND a signature; mint-override records
   are unsigned today, so the gate refuses EVERY override record for every
   gated class (strict fail-closed branch; the signed channel is an explicit
   BACKLOG follow-up).
3. Receipt requirement is fail-closed: missing, stale, or invalid receipt
   blocks the gated classes; validation delegates to
   `itd_verification_loop.py check` bound to the exact candidate.
4. Quick suite green on the exact candidate, recorded as **operator evidence**
   (`tests/run-all.sh --quick` → `DONE fails:none`), NOT as the declared
   exact-candidate machine oracle. **Amendment 2026-08-12-e (producer
   specification-compliance finding, AUTHORIZED):** the declared machine oracle
   for U16 is `tests/verify_predeploy_independent_review.py` ALONE. Route
   finding r77 narrowed it deliberately: the full quick suite is not yet
   deterministic (BACKLOG S2 — full-suite non-determinism, `verify_session_
   hygiene` flake), so binding it into the exact-candidate machine receipt
   would make the receipt flaky rather than more truthful. The unit therefore
   claims exactly what its machine evidence establishes — the gate verifier on
   the exact candidate — and the quick suite is reported separately by the
   operator. When BACKLOG S2 lands, the quick suite can be promoted back into
   the declared oracle without weakening anything here.

## Superseded amendment history — rounds r36–r58 (condensed 2026-08-11)

Condensed at routes r57 and r63: the full per-round amendment texts pushed
this contract past the reviewer's hierarchical unit-prompt transport bound
twice. The complete texts are preserved verbatim in the route receipts and
prompts under `.itd-memory/verification-loop/receipts/u16-staged/` and in
the git history of this branch's earlier candidate trees; nothing in the
CURRENT contract changes by this condensation. Every fix below is pinned by
regression tests in both directions. One entry per round — finding → closure:

**Deny-matcher era (r36–r52), design superseded by S1:**

- **r36:** read-only exemption judged the whole shell string (`docker ps;
  docker push` passed) → per-invocation split; bare-word matching missed
  `/usr/bin/ssh`, `sudo rsync`, `bash -c` → shlex + wrapper peel + basename;
  pass accepted on digest+timestamp alone → clean worktree +
  `deployInputSha256` binding; hook-taxonomy counts corrected (12/18/30).
- **r38:** `eval`/`$cmd`/`bash -c "$cmd"` walked past token matching →
  unresolvable indirection denied; wrapper option OPERANDS ate the command
  word (`sudo -u root rsync`) → per-wrapper operand tables; quote-aware
  segment scan; the gate's own emitted artifact no longer counts as drift;
  operator escalation persisted per checkout so `classify` sees it.
- **r39/r40:** scrubber detector false positives (a local variable named
  after a parsed word; then the amendment PROSE quoting it) → variable
  renamed, prose describes the pattern; detector precision deferred (S6).
  One unreproduced `verify_session_hygiene_quality` red recorded (BACKLOG).
- **r41:** classifier missing = silent allow → DENY with repair command;
  a pass unlocked EVERY command → pass authorizes shipping the RECORDED
  artifact only; read-only tar modes recognised; escalation regression test
  drives the real CLI.
- **r42:** leading assignments/keywords hid the head → stripped; `xargs` no
  longer peeled; with a pass an unresolvable command went unchecked → pass
  branch judges like the no-pass branch; artifact matching by
  substring/basename → exact path identity; out-of-checkout
  `--emit-deploy-input` refused; stale docs fixed; `.bak`/namesake negative
  controls added.
- **r44:** `deploy(){ …; }` definition heads peeled so the body is judged;
  receipt-success path proves the validator receives the exact candidate
  coordinates; README count finding recorded as a partial accept.
- **r45:** `function deploy { … }` form peeled; every checkout the command
  can reach (cwd + resolved `cd` targets) classified, strictest verdict
  wins; local content piped/redirected into `ssh` must be the recorded
  artifact; out-of-zone inventory propagation AUTHORIZED (list above).
- **r46:** artifact named inside the REMOTE ssh command proved nothing →
  only the LOCAL source counts; `|` inside remote quotes is not a local pipe.
- **r48:** artifact accepted in ANY non-option token → positional operands
  only with transport option tables; only `<`/`0<` are stdin; artifact on
  disk re-hashed against the recorded digest; CLI/registration pinned
  behaviourally.
- **r50:** INSTALLED methodology is the classifier anchor (candidate code
  must not gate itself); client global-option operands no longer read as
  subcommands; same for tar modes; `.git/` artifact destination refused;
  per-hook `git archive` re-derivation removed (transient false denials).
- **r51:** unsigned-pass-record deferral REJECTED and closed: HMAC keyed by
  a host-owned secret (`~/.config/itd/deploy-gate.key`, 0600); pipe upstream
  must be ONLY the artifact; SKILL example ships the emitted artifact;
  artifact parent created; escalation flags exercised through `classify`.
- **r52:** heredoc into a remote command is always unbound content; relative
  `--emit-deploy-input` resolved against `--root` once; unwritable-parent
  control made structural.

**Allow-list era (r53–r58) — SUPERSEDED by ADR-008 (see the amendment at the top); retained as decision history, NOT the current contract:**

- **r53 → S1 redesign (user decision, PLAN-CLOSEOUT S1):** the deny-matcher
  itself was the flaw (`echo $(/usr/bin/rsync …)` beat the word-boundary
  heuristic). The matcher became an ALLOW-LIST over a closed grammar:
  command/process substitution outside single quotes unresolvable
  UNCONDITIONALLY (`BARE_MUTATING_RE` deleted); with a pass, shipping is
  restricted to exact forms — per-transport CLOSED flag tables (unknown
  flag = deny) with positional operands exactly {recorded artifact, one
  remote destination} (rsync/scp) or {artifact} (tar). AND: the trust
  anchor (installed gate script, receipt validator, MAC key) no longer
  derives from HOME/USERPROFILE — the OS account database answers
  (`pwd.getpwuid` / shell32), unresolvable home keeps every consumer
  fail-closed; fixtures repoint module globals via generated runner/wrapper
  scripts, with HOME-relocation attack controls. Known accepted cost:
  `$(…)`/backticks are denied in GATED checkouts even when harmless;
  routine candidates untouched; `"$VAR"` expansion stays allowed.
- **r55:** `bash deploy.sh`/`python deploy.py`/`make deploy` ran project
  code via the safe fast path → closed `PROJECT_CODE_RUNNERS` table, shell
  heads without `-c`, interpreter `-c` payloads and EVERY path-qualified
  head are unresolvable (honest limit: bare custom PATH binaries and
  pytest-class test runners stay outside the table, stated in the hook);
  Step 0 de-HOMEd (`getent passwd`); `RuntimeError` from resolve() on
  symlink cycles caught fail-closed everywhere.
- **r56:** path qualification is judged BEFORE basename rules (`/tmp/rsync`
  borrowed the transport path with a pass) and path-qualified wrappers are
  never peeled; cyclic `--root` containment catches
  `ValueError`/`RuntimeError` (typed BLOCKED, not a crash).
- **r58:** mutating container/cluster clients denied WITH a pass (r41
  honest limit closed; image/manifest provenance binding queued); symlinked
  ledger directories/entries refused on write AND read (`O_NOFOLLOW`);
  escalation persistence failure BLOCKS the check and a poisoned escalation
  entry fails closed to gated (escalate-only); cyclic `--root` answers
  typed BLOCKED; MAP §6 hard-gate coverage corrected to 12/12.

**Allow-list rounds r59–r62 (condensed at r69 for the reviewer prompt
bound; full texts in the route receipts/prompts and git history). One entry
per round — finding → closure. Every fix pinned by regression tests.**

- **r59 (7):** `-c` accepted anywhere in a shell wrapper (`bash -- file -c
  'safe'` reduced to the safe payload) → `_shell_command_payload` honors the
  leading option region only (`--`/positional = script file, `-o/+o`
  operand, `c`-cluster = command form); `pushd` tracked in `candidate_roots`
  and `popd` always unresolvable; the unresolvable-cd deny moved (later
  reversed by r65); ledger TOCTOU closed with descriptor-relative
  `O_NOFOLLOW|O_DIRECTORY` traversal; self-declared-signature overrides
  refused; Step 0 wiring required as an executable fenced command with the
  account-db anchor; BACKLOG.md authorized in zones. Also: the recurring
  36-byte UNVERIFIED is scrubbed-vs-raw arithmetic (two manifest-email
  redactions, −18×2), disclosed as the ADR-007 disposition basis — did not
  recur from r60.
- **r60 (4):** `case x in x) rsync … ;; esac` peeled the `case` keyword and
  classified the pattern word safe → `case`/`select` are unresolvable
  compounds; `--emit-deploy-input` could overwrite a TRACKED source file or
  committed symlink → destination must be gate-ownable (non-symlink,
  untracked, `O_NOFOLLOW`); the registration check ran a reconstructed
  invocation → now executes the EXACT registered command string; the Step 0
  fence's `[--flag <…>]` bracket notation was not paste-executable → moved to
  a comment.
- **r61 (1):** a function DEFINITION was peeled into its body while the later
  bare-name invocation passed safe → a definition (either form, and the r65
  whitespace-before-paren form) makes the whole command unresolvable via the
  dynamic sentinel, denied with or without a pass on gated candidates.
- **r62 (3):** `env -S 'rsync …'` executed its split-string payload with
  nothing left to judge → split-string modes unresolvable; `sudo -s`/`-i`
  (and r66 clusters `-is`/`-si`) spawn a shell outside interception →
  shell-spawning wrapper modes unresolvable, `su` joins the runner class;
  `command_check` validated the receipt BEFORE deriving the digest → the
  digest is snapshotted before validation and re-derived before artifact
  production and pass recording (concurrent-ref-update TOCTOU), pinned with a
  HEAD-advancing validator stub.

**Allow-list rounds r65–r66 (condensed at r71 for the reviewer prompt bound;
full texts in the route receipts/prompts and git history). One entry per
round — finding → closure. Every fix pinned by regression tests. (r64 was a
transport UNAVAILABLE, re-run on the same tree with machine receipt a74.)**

- **r65 (7):** unlisted bare executables defaulted safe, shipping content
  ungated → a `NETWORK_CONTENT_CLIENTS` table (curl/wget/nc/socat/ftp/sftp/
  rclone/aws/gcloud/az/s3cmd/restic/… + the r68 named deploy/IaC/PaaS
  clients) is unresolvable, residual = truly custom-named client (ADR-007
  honest limit); `deploy () { … }` whitespace-before-paren function def
  caught; **REVERSES r59** — an unresolvable directory change in a
  content-shipping command is denied regardless of launch cwd's class
  (fail-closed > routine comfort, kept narrow by `needs_gate`); **REVERSES
  r45/r46** — a bare `ssh host '<anything>'` under a pass is denied, an ssh
  invocation is authorized ONLY as the exact artifact shipment; MAC key
  accepted only as a non-symlink regular file owned by euid, mode 0600,
  minted `O_EXCL|O_NOFOLLOW`; recorded artifact re-hashed `O_NOFOLLOW`
  (non-regular refused); Step 0 wiring bound to a single fence.
- **r66 (3):** the r62 shell-spawn check matched only standalone `-s`/`-i`,
  not clusters (`sudo -is`/`-si`) → any sudo/doas cluster containing `s`/`i`
  is unresolvable; `emit_deploy_input` `O_TRUNC`-ed an existing UNTRACKED
  hard link → created `O_EXCL|O_NOFOLLOW`, existing accepted only as regular
  nlink==1 (later extended to ledger entries in r70); the Step 0 oracle now
  EXECUTES the documented fence hermetically (fake `getent`/`id` → fixture
  install with a recording gate stub) proving the installed gate runs.

**Allow-list rounds r67–r68 (condensed at r74 for the reviewer prompt bound;
full texts in the route receipts/prompts and git history). Every fix pinned
by regression tests.**

- **r67 (2):** `candidate_roots` resolved every relative `cd`/`pushd` target
  against the ORIGINAL cwd, so a chained `cd /a && cd ../gated && rsync …`
  (landing in `/a/../gated`) was classified against the wrong path → the cd
  chain is simulated sequentially now (each relative target against the
  current simulated dir); a non-dict ledger JSON (`[]`) crashed
  `gate_pass_is_current`/`classify` with AttributeError → a non-dict record
  fails closed with a typed result.
- **r68 (2, one CLOSED + one USER-DECIDED):** `emit_deploy_input` resolved
  the destination with `.resolve()`, so a symlinked in-checkout PARENT
  resolved outside and was followed → branch chosen by LEXICAL containment,
  in-checkout writes go descriptor-relative. AND the critical
  unknown-bare-executable honest limit (`deploy-tool --publish` defaults
  safe) was surfaced to the USER as a trade-off vs the anti-false-block
  invariant; the user chose option A (proportional). A-plus implemented:
  named deploy/IaC/PaaS clients (terraform/tofu/pulumi/cdk/sam/serverless/
  flyctl/vercel/netlify/heroku/wrangler/kamal/dokku/eb/skaffold/argocd/flux/
  nomad/waypoint/packer/salt/chef/juju/…) recognised, residual = truly
  custom-named client = the ADR-007 human-adjudicated honest limit; inverting
  the fast path is rejected as a false-block generator per the unit contract.

**Allow-list rounds r70, r72 (condensed at r75 for the reviewer prompt bound;
full texts in the route receipts/prompts and git history). Every fix pinned
by regression tests.**

- **r70 (3):** the reachable-checkout analysis followed only `cd`/`pushd`, so
  `env --chdir /gated rsync …` (and `-C`, `--chdir=…`) was consumed by
  wrapper peeling and never seen → a shared `_dir_change_targets` scanner
  now covers `cd`/`pushd`/`popd` AND env `-C`/`--chdir` in command position
  only, feeding `candidate_roots` and `has_unresolvable_cd`; the r66
  hard-link defense reached deploy-input but not pass-ledger entries → both
  ledger writers hardened (later superseded by the r73 atomic writer); MAP
  freshness date corrected.
- **r72 (2):** `_is_read_only_tar` returned True on the first `-t`/`--list`
  without scanning later options, so `tar -t --checkpoint-action=exec …`
  (and `--to-command`, `-I`, `--rmt-command`, `-F`) executed code while
  classified read-only → read-only recognition scans the WHOLE argument list
  (list mode AND no execution-capable/write/unknown option, `TAR_EXEC_OPTIONS`);
  the r60 registration proof `bash -c`'d the candidate-owned `hooks.json`
  string → now shlex-split, `$PLUGIN_ROOT`-expanded, the dispatcher argv
  STRICTLY allow-listed, executed WITHOUT a shell.

## Visible amendment 2026-08-11 (route r77, fifteenth round)

Three findings; all closed here (r74/r75/r76 were transport-bound/UNAVAILABLE
re-runs, not reviews).

- **high, hook** — `_redirect_source` returned the FIRST stdin redirect, but
  shell redirections apply left-to-right and the LAST stdin redirect wins, so
  `ssh host '…' < artifact < unreviewed` satisfied `ssh_ships_artifact` on the
  first redirect while actually shipping `unreviewed`. It now returns the
  LAST stdin source (bash semantics), and an fd-duplication stdin form
  (`0<&3`) returns an unresolvable sentinel the ssh checks deny.
- **high, tests** — the r73 Step 0 template regex used `[^\"]*` after
  `$(id -u)`, which accepted arbitrary shell (`; touch /tmp/pwn`) that
  `bash -c` would then execute during verification. Every template line is
  now an EXACT literal (only `#`-comments are free text, and comments cannot
  execute), so a tampered fence cannot both satisfy the template and inject.
- **medium, oracle → resolved by making the U16 oracle deterministic.** The
  reviewer flagged the machine oracle's disclosed non-determinism. Root
  cause: the oracle ran the whole `run-all.sh --quick` (60+ serial
  verifiers) only to prove registration the verifier already self-asserts,
  and the full suite has load-interference flake hitting multiple verifiers.
  The exact-candidate oracle for THIS unit is now the verifier alone
  (deterministic, self-proves registration) — see "Machine-oracle shape".
  The broader full-suite interference stays a queued S2 follow-up (WIP=1),
  not smoothed over.

Oracle: 320 → 325 asserts; the small gate suite stays at 11.

## Visible amendment 2026-08-11 (route r73, fourteenth round)

Five findings: four closed here, one recorded as a stated same-principal
boundary (consistent with r51/r53). The recurring 36-byte UNVERIFIED is the
scrubbed-vs-raw arithmetic disposition (unchanged, ADR-007 basis).

- **medium, hook** — `_dir_change_targets` identified heads with
  `Path(...).name`, so a path-qualified `/tmp/env --chdir /gated …` (or
  `/tmp/cd …`) was treated as the trusted env/cd builtin and added a bogus
  gated root, falsely denying a routine command (contradicting r56's
  "path-qualified heads are never trusted wrappers"). Only BARE `env`/`cd`/
  `pushd`/`popd` heads are directory changes now.
- **high, gate ×2** — the EXCL-or-`nlink==1`-then-`ftruncate` write (deploy
  artifact AND pass-ledger entry) had a TOCTOU: a hard link created between
  the fstat and the ftruncate let the truncate hit an aliased file. Both
  writers now create a FRESH temp inode (`O_EXCL|O_NOFOLLOW`) and
  atomically `os.replace` it over the target — `os.replace` swaps only the
  directory entry, so any hard-linked alias keeps its own untouched inode.
- **high, tests** — the r66 hermetic Step 0 test executed the
  candidate-owned SKILL.md fence with `bash -c`, so a tampered fence could
  run arbitrary commands with the verifier's privileges. The fence is now
  validated line-for-line against the exact Step 0 template (comment /
  `ITD_HOME=getent…` / `G=…installed path` / `sh …check --root`) with no
  appended shell BEFORE it is executed.
- **high, hook — stated boundary, not a code fix.** The gate binds the
  deploy-input digest at check time, but a separate concurrent process
  running as the same user could replace the artifact file between the
  gate's validation and the transport's own `open()`. A PreToolUse hook
  cannot hold that descriptor through an external `rsync`/`scp`, so this
  same-principal race is out of scope — the same limit already stated for
  the pass-record key (r51/r53). Disclosed in `skills/deploy/SKILL.md` and
  here; the gate is not a defense against an attacker with concurrent code
  execution as the user.

Oracle: 315 → 320 asserts; the small gate suite stays at 11. Flake note
(S2): the verifier was green 3/3 standalone but red on one full quick run
under load, green on the immediate re-run — same interference family, re-run
AND recorded.

## Routes r57, r63, r64, r69 (2026-08-11): transport-bound, no findings

Refused before review: r57/r63/r69 "hierarchical unit prompt exceeds the
reviewer bound" — every unit prompt embeds this contract's full text, and the
accumulated amendment prose plus an up-to-80 KB diff unit crossed the
producer's 128 KiB ceiling; r64 was an OpenAI event-stream UNAVAILABLE.
Resolution each time: closed rounds condensed above (full texts in the route
receipts/prompts and git history), or re-run on the same tree with the same
machine receipt (r64→r65). A transport refusal, not a semantic finding;
recorded so each condensation/re-run has a stated, checkable reason.

## Machine oracle + route amendments r53–r86 — compact summary (2026-08-11..12)

Full per-round finding→closure texts live in git history and the route receipts
under `.itd-memory/verification-loop/receipts/u16-staged/`. Compacted here to
keep the hierarchical unit prompt under the reviewer bound (route finding r87,
same class as r57/r63/r69/r71).

**Machine oracle (r77):** the exact-candidate receipt runs the unit's own
verifier directly (`verify_predeploy_independent_review.py`) in the isolated
staged tree — it exercises the gate AND self-proves its run-all CORE
registration, so it is deterministic and verifier-only. The broader full-suite
interference is the queued S2 follow-up, NOT this unit's oracle. The `oracleIds`
label `quick-suite-with-u16-verifier` is an opaque run label kept for receipt
continuity, not a claim that the whole quick suite is the oracle.

**S1 flake real root cause:** `gate_pass_is_current` intermittently returned
False on a green tree because the wall clock is not monotone (WSL2 / NTP steps
`time.time()` BACKWARD), making `age = now - recordedAt` transiently negative.
Fix: `GATE_CLOCK_SKEW_TOLERANCE_SECONDS = 300`, `-TOL <= age <= MAX`. (The
earlier racy-clean `update-index --refresh` hypothesis was wrong and reverted.)

**Route r53–r86** (all rounds accepted the prior fixes, `unverified=[]`; every
finding closed by code+tests; oracle 202 → 363):
- r53–r77: allow-list redesign, ~45 findings (dynamics, per-transport flag
  tables, unresolvable runners, path-qualified heads, function defs, env
  `-S`/`-C`, sudo shell clusters, ledger/artifact TOCTOU, tar
  `--checkpoint-action`, redirect order, no candidate-string eval).
- r78: escaped `\<`; test template-injection; oracle → verifier-only.
- r79: `<<<` here-string & IO-number adjacency; `builtin/command cd`
  pass-through; registration allow-direction.
- r80/r81: escalation-persistence fail-closed; word-start `#` comment.
- r82: exec-capable transport option OPERANDS removed (rsync `-e`/`--rsh`/
  `--rsync-path`/`-M`, scp `-o`/`-S`, tar `-I`/`--use-compress-program`); ssh
  `-` stdin placeholder.
- r83: attached `env -C<DIR>`; IO-number = whole-token-digits; registration
  routine→allow; + the ADR-007 shell-parse-completeness boundary below.
- r84: kubectl/helm `--kubeconfig`/`--context`/`--kube-context`/`--config`
  exec-config removed from the read-only fast path.
- r85: tar `-T`/`--files-from` exec-list removed from read-only; evidence
  provenance refreshed.
- r86: scp `-F` exec-config removed; `#` comment boundary extended to newline/
  control-operators; `recorded_deploy_input_path` now MAC-validates the entry
  (classify TOCTOU; residual same-principal swap is the r73 limit).
- r87: hierarchical unit prompt exceeded the reviewer bound → this route
  history compacted (full texts in git/receipts); not a finding.
- r88: `_upstream_is_only_artifact` now requires a closed BYTE-reader head
  (`cat`) so `echo <artifact> | ssh` (pathname text, not bytes) is denied; and
  `recorded_deploy_input_path` now also requires the record's `kind` +
  `candidateDigest` to equal the current derived digest, so a MAC-valid record
  for ANOTHER candidate cannot supply its artifact path. Oracle 363 → 366.

r82/r84/r85/r86 are one "execution-capable option operand/list/config" family;
each concrete member closed as found — real holes, distinct from the shell
parse-corner boundary below.

### ADR-007 stated boundary — shell static-analysis completeness (accepted)

A PreToolUse hook that statically analyzes ARBITRARY shell command strings is
fundamentally incomplete: the shell grammar (wrappers, redirects, IO-numbers,
quoting, expansions, compound statements) has an unbounded surface, so an
adversarial reviewer can keep finding new narrow parse corners (r78→r83 closed
~15 real classes and each round still surfaced a few more). Chasing corner
exhaustion is a non-terminating treadmill and is NOT the closure condition for
U16. **This whole "REAL, sound contract" argument is the allow-list-era
reasoning that led to the ADR-008 redesign — it is SUPERSEDED (see the ADR-008
amendment at the top) and retained only as the decision record for WHY the
shipment-form analysis was abandoned. The current contract is ADR-008.** The
allow-list-era contract of U16 was:

* **fail-closed default** — anything not statically proven to be exactly a
  read-only client call or an exact-artifact shipment (unknown/unlexable/
  dynamic/unresolved forms) DENIES, so an unrecognised parse corner errs toward
  block, not toward a false allow;
* **receipt binding** — a gated deploy requires a fresh Verification Loop
  adjudication receipt bound to the exact candidate digest, plus a host-owned
  MAC on the pass record outside every checkout.

The static command allow-list is defense-in-depth that RAISES the bar on top of
that contract, not the contract itself. Each concrete parse corner that is
found is still closed (as r78→r83 did), but the residual "a sufficiently exotic
shell string may reach an as-yet-unclosed corner" is a **documented limit**,
adjudicated like the F0 (unknown-bare-executable) and the same-principal TOCTOU
(r73) honest limits, NOT a gate failure that blocks closing U16.

## Risk tier

high — deploy-class gate, security-relevant surface (per the plan's declared
`riskTier: high`). Full chain: machine receipt + fresh cross-vendor checker
(producer route) + adjudication before PR.

## Out of scope

U17 (design-stage reviewer in /blueprint), any change to the Verification
Loop or independence policy themselves, deploy config schema changes beyond
reading existing markers, reinforced-human-gate variant for
irreversible/monetary (forbidden branch chosen; a future unit may relax it),
BACKLOG follow-ups.
