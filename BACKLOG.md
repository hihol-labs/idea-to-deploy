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
- [ ] Live-model benchmark fixture hardening — three defects of the RECORDED
  benchmark run, not of the methodology: fail-open self-validation visible in
  the transcript; no originating user request in the capture; the run
  substituted the Devil's Advocate subagent invocation with inline
  self-critique. Fix the benchmark scenario so the real devils-advocate
  subagent is invoked, then re-record. `/blueprint`'s Devil's Advocate itself
  stays as designed; the independent reviewer does not replace it.
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
