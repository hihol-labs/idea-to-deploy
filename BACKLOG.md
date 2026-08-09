# BACKLOG — Harness-demo UX absorption

**Decision:** [ADR-004](docs/adr/ADR-004-harness-demo-ux-absorption.md)
**Last reviewed:** 2026-07-26
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

## P1 — Should do

- [ ] Build project-aware incremental diagnostics with latency/noise telemetry and a
  default-off policy.
- [ ] Decide promotion only after at least 30 labeled A/B emissions.
- [ ] Build the fresh-session worktree/resource-isolation pilot kit.
- [ ] Run three serial, user-authorized brownfield units in named project roots with
  isolated mutable resources and exact-candidate receipts.

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
