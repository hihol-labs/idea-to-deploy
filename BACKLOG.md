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
- [ ] Codex error-item classification (A19): the candidate's `run_codex_review`
  handles a reviewer error item that the slice's HEAD-derived version does not.
  Not observed to fail on codex 0.146.0 during acceptance, so it stays a separate
  bounded fix rather than a silent slice extension.
- [ ] Explain one unreproduced `UNVERIFIED` reviewer failure seen on the first WSL
  efficacy attempt (`high-export-capacity`, no unavailability marker in the CLI
  output). The case passed on every later attempt and the suppressed CLI detail was
  not captured, so the cause is currently unknown rather than diagnosed.
- [ ] Strict POSIX descendant containment in `run_bounded_process` (route finding,
  2026-08-09): cleanup kills the call's process group, so a descendant that
  re-calls `setsid()` escapes and is not reaped; Windows is already strict via the
  Job Object. Close the gap with a PPID-walk reap or cgroup/PID-namespace
  containment, with tests that actually daemonize.
- [ ] Harden the run-all host-pin boundary (route finding F4, 2026-08-09): the
  efficacy keyring pin path is chosen by candidate code (`tests/run-all.sh`) and
  only existence-checked. The strict receipt path already passes it as a declared
  host input; move the convenience path to a host-owned location outside the
  checkout (env var or absolute host path) so candidate code cannot select the pin.
- [ ] Make the methodology tree pin ignore harness debris. `methodology_tree_sha256`
  in `tests/verify_live_model_benchmark.py` skips `__pycache__` and `.pyc` but not
  Git-ignored harness output such as `.claude/`. A stray 800-byte trace file under
  `skills/_shared/.claude/traces/` silently entered the H4 tree pin, and the mismatch
  only surfaced later in the isolated staged candidate as three failing checks. The
  pin should either exclude the same paths Git ignores or fail loudly at run time.
- [ ] Exclude `__pycache__`/`*.pyc` bytecode from the `sync-to-active.sh` drift
  scan (found closing U6, 2026-08-10): the only reported skill drift on a fully
  synced install was `skills/_shared/__pycache__` — pure noise that makes a
  clean parity check read as "~1 updated".
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
- [ ] Sync-manifest gap: `scripts/sync-to-active.sh` verifies that
  `.claude-plugin/plugin.json` exists but never syncs it, so the installed
  manifest `~/.claude/.claude-plugin/plugin.json` is aligned manually today.
  Add the manifest to the sync and verify-sync surface.
- [ ] Bounded-process transport hardening (route-adjudication accepted
  trade-offs): reject NaN/inf timeout values before deadline arithmetic and
  harden relative-cwd handling in the Windows wrapper. POSIX descendant
  containment and the run-all host-pin boundary are already tracked in the
  slice section above.
- [ ] Pre-existing ledger drift: `GOAL-2026-07-06-axis*` / `PE5-015` unit
  ledgers drifted from current evidence before GPG-004 started. Reconcile the
  ledgers honestly — no synthetic evidence backfill.
- [ ] Surface the reviewer-independence label in the local-review profile
  doctor: `validate_local_adjudication` already receives `routeIndependence`
  in the check stdout, but its `str | None` route-label contract (stubbed by
  the doctor regression suite) keeps the doctor entry at
  `routeEvidence`-only. Extend the callable contract and the doctor suite
  together in one bounded change.
- [ ] Completion-ledger writer schema: agent-delegation telemetry rows are
  written without the `producer` field, so the strict completion evaluation
  fails to parse the ledger (observed 2026-08-09, signals.jsonl line 270,
  audited COMPLETION_BYPASS). Fix the writer and make the evaluator skip
  layer-0 telemetry rows instead of failing closed on them.
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
