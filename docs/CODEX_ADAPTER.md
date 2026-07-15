# Codex adapter

The Codex adapter makes this repository usable as the source methodology for
Codex while keeping the existing Claude Code adapter intact.

## What is native

- `.codex-plugin/plugin.json` exposes the shared `skills/` tree.
- Codex discovers `hooks/hooks.json` automatically from the enabled plugin.
- `AGENTS.md` is the durable project guidance entry point.
- Hooks use the native Codex lifecycle events and deny protocol.
- `.itd/` and `.itd-memory/` remain the canonical project contracts and state.

The continuity rule is shared with Claude Code: `.itd-memory/` also owns
`session_*.md`, `MEMORY.md`, and `.active-session.lock`. Host-private transcript
or memory directories are optional compatibility mirrors and never override
project-local state.

Codex sets `PLUGIN_ROOT` and also supplies `CLAUDE_PLUGIN_ROOT` for compatible
plugin hooks. `hooks/codex-dispatch.py` handles the remaining transport gap:
Codex reports file mutations as `apply_patch`, while the shared gates expect
`Write` or `Edit` with a `file_path`. The dispatcher expands one patch into the
affected paths and preserves the hook's output and exit status.

`docs/HARNESS_TRUST_POLICY.json` is the shared graduated-trust registry. It
classifies the ten canonical hard gates as high risk and keeps low-risk probes
allow/advisory. If the Codex dispatcher cannot parse or execute a registered
high-risk gate, it emits the gate's native `deny`/`block` decision instead of
silently downgrading the failure; unregistered telemetry hooks remain
fail-open. Both bundled and repository-local Codex hook configurations include
`apply_patch` in the mutation matchers, so normalization is reached in real
tool traffic rather than only in adapter tests.

## Enable and trust

Install or enable the repository as a Codex plugin through the normal Codex
plugin UI. On first use, inspect and trust its command hooks with `/hooks`.
Plugin hooks are intentionally bundled; `/adopt` does not duplicate them into
the target repository when the plugin is active.

For a repository-local checkout instead of an installed plugin, copy the
template from `skills/adopt/references/codex-project-hooks.json` to
`.codex/hooks.json`, replace `{{ITD_ROOT}}` with the absolute methodology
checkout path, then review it with `/hooks`.

## Known transport differences

- Codex `apply_patch` is normalized by the dispatcher. Bash and lifecycle
  payloads already match the shared hook protocol.
- Claude `Task|Agent` PostToolUse hooks have no direct Codex tool equivalent.
  Codex uses `SubagentStart` and `SubagentStop`; final narration and structured
  verdict gates run on `SubagentStop`.
- Role files under `agents/` are methodology role definitions, not Codex
  manifest entries. A Codex workflow should start a native subagent and provide
  the applicable role file as its task contract.
- Hook interception is a guardrail, not a security boundary. Codex may expose
  tool paths that do not emit every hook event; `.itd` verification contracts
  and final evidence remain mandatory.

## Bounded goal continuation

For an explicitly approved `/goal` with `runPolicy.mode:
bounded_autonomous`, Codex's native goal/automation surface may re-enter the
task. The durable controller is still `.itd-memory/GOAL.json`: seal it first,
resume one WIP unit, run the ordinary `/task` pipeline, and finish through
`itd_goal_verify.py` with an approach and fresh-checker evidence when required.

Map the host/session token ceiling to `runPolicy.maxTokensPerSession`. When the
host reports exhaustion, persist it with `--budget-exhausted --budget-kind
tokens`; exit `3`, `blocked`, and `budget_exhausted` stop continuation and go to
human triage. Do not turn a recurring background automation into a code writer:
only the already user-approved bounded goal may make reversible scoped edits;
push, merge, deploy and other external writes remain manual.

If native continuation is unavailable, reopening the task and invoking
`/goal` resumes the same ledger. No Codex-specific state is required.

Run `python3 tests/verify_host_adapters.py` to validate packaging,
registration, and normalization. Run
`python3 tests/verify_all_hard_gate_host_parity.py` for the behavioural 10/10
Claude-direct versus Codex-dispatch decision proof. Run
`python3 tests/verify_host_neutral_memory.py` and
`python3 tests/verify_fresh_session_resume.py` for local-first continuity and
cold-session reconstruction proof.
