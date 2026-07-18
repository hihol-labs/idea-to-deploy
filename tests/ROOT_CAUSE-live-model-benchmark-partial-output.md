# Root Cause: live-model benchmark rejects recoverable partial output

## Summary

- Symptom: the Codex-backed live benchmark exited `FAIL` three times after a
  successful model turn because `PRD.md` and `IMPLEMENTATION_PLAN.md` were
  missing.
- Impact: the v1.91.1 meta-review could not refresh content-pinned H4 evidence,
  even though the repository-local harness loaded and four of six required
  blueprint documents were created.
- First observed: 2026-07-18 while refreshing PR #167 live-model evidence.
- Severity: release-blocking test-harness defect; no production methodology
  runtime or user project was affected.

## Reproduction

1. Run `tests/run-live-model-benchmark.py` with the authenticated OpenAI Codex
   provider and the active `fixture-03-cli-tool` fixture.
2. Let the live model complete successfully after loading
   `skills/blueprint/SKILL.md` and its document template.
3. Observe that four required documents exist, while `PRD.md` and
   `IMPLEMENTATION_PLAN.md` do not.
4. Observe that the runner invokes the snapshot oracle once, writes a minimal
   `FAIL` report, deletes the temporary project, and never lets the same model
   continue the already-started work.

## Evidence

- Three authenticated Codex runs failed with the same two missing files,
  including a run after the fixture prompt explicitly named all six oracle
  outputs.
- The first authenticated post-fix run exhausted both bounded attempts with all
  six files absent at the end. The old minimal `FAIL` report discarded
  per-attempt transcript and workspace state, so it could not distinguish
  "created nothing" from "created files, then removed them."
- A second run preserved the full inherited `PATH` and reproduced the zero-file
  result, refuting the PATH hypothesis. Its retained transcript shows the actual
  cause: both attempts loaded the ITD skill, then Codex rejected `apply_patch`
  with "writing is blocked by read-only sandbox; rejected by user approval
  settings." Read commands succeeded, but the Windows Codex bridge treated the
  WSL `/tmp` project as read-only despite the requested `workspace-write` mode.
- Moving the workspace under `/mnt/c/tmp` crossed the managed write boundary,
  but the first transport attempt then failed fast with Windows `os error 3`:
  the bridge received the POSIX `-C /mnt/c/tmp/...` argument literally. The
  candidate workspace therefore also requires WSL-to-Windows path translation.
- With the native path in place, writes were still rejected. `codex doctor`
  reported the effective approval policy as `OnRequest`. A non-interactive
  `codex exec` cannot service that prompt, so the model's valid workspace patch
  was declined even though `--sandbox workspace-write` was present.
- Explicit `never + workspace-write` was accepted by the CLI parser but the
  managed Windows desktop build still forced a read-only filesystem. A
  one-file smoke reproduced the rejection, so the bridge path is unsuitable
  for live write benchmarks in this managed session.
- The existing native WSL `@openai/codex` 0.144.3 wrapper was missing only its
  matching optional Linux binary package. After installing the exact
  `0.144.3-linux-x64` package, the already-authorized native CLI completed a
  one-file `apply_patch` smoke inside `/tmp` under
  `never + workspace-write`. No API key or sandbox bypass was needed.
- The first full native WSL benchmark then passed in one model attempt as
  immutable run `20260718T215215Z-4bce7dca`. The independent verifier replayed
  the archived snapshot and accepted all 80 checks. Bounded recovery was
  therefore not needed in that successful run and is not claimed as
  live-exercised.
- The last known passing evidence from 2026-07-17 completed all files in one
  model turn, so the runner's implicit one-turn assumption happened to hold.
- `run()` in `tests/run-live-model-benchmark.py` contained exactly one
  `run_candidate(...)` call before the only oracle invocation.
- Prompt hardening alone did not change the failure, excluding omitted output
  names as the root cause.

## Fix Hypothesis

- Add at most one recovery attempt in the same temporary adopted project when
  the first successful turn is missing required files.
- Tell the recovery turn to inspect and preserve existing work and create only
  the missing required outputs.
- Share the original candidate deadline across both attempts and split the
  Anthropic budget so their maximum aggregate remains the original value.
- Combine both raw transcripts, retain proof that the real ITD skill/reference
  was loaded, and run the unchanged independent snapshot oracle only after the
  required file set is complete.
- Archive the combined transcript, per-attempt boundaries, and any present
  required outputs on real `FAIL` runs so a failed recovery is diagnosable
  without immediately spending another external-model run.
- When an authenticated Windows Codex executable is invoked from WSL, create
  the isolated adopted project below a host-mounted writable temp root
  (`C:\tmp` by default, configurable with
  `ITD_LIVE_MODEL_TEMP_ROOT`). Keep `workspace-write`; do not bypass approvals
  or disable the sandbox.
- For that Windows bridge only, translate the candidate's `-C` argument from
  `/mnt/<drive>/...` to `<DRIVE>:\...`. Native Linux and Claude candidates keep
  their normal POSIX paths.
- Invoke headless Codex with explicit global
  `--ask-for-approval never --sandbox workspace-write` before `exec`. This is a
  no-escalation policy: in-workspace operations may run, while anything outside
  the sandbox fails immediately. Do not use the full-access bypass flag.
- On WSL, prefer the native Linux Codex executable for write benchmarks. A
  Windows desktop bridge may still be used for read-only diagnostics, but a
  managed host that forces it read-only cannot satisfy H4.
- Exhausted recovery, timeout, non-zero exit, missing successful result events,
  or oracle rejection remain `FAIL`.

## Regression Test

- `tests/verify_live_model_benchmark.py` must prove that:
  - the policy is exactly two attempts;
  - missing outputs are detected without treating existing documents as
    missing;
  - the first partial result creates a continuation prompt for only the missing
    files;
  - the second partial result cannot schedule a third attempt;
  - the candidate deadline and Anthropic budget are bounded across attempts;
  - real candidate failures retain bounded transcript/output diagnostics;
  - a one-shot mutation is rejected.
- A real authenticated Codex run must produce fresh `PASS` evidence accepted by
  `tests/verify_live_model_benchmark.py --require-evidence`.

## Constraints

- Do not weaken or replace `tests/verify_snapshot.py`.
- Do not claim universal model/provider support.
- Do not add a third attempt, a new dependency, or a larger time/cost allowance.
- Do not alter production skills, hooks, contracts, or host adapter semantics.
