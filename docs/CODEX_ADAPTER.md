# Codex adapter

The Codex adapter makes this repository usable as the source methodology for
Codex while keeping the existing Claude Code adapter intact.

## What is native

- `.codex-plugin/plugin.json` exposes the shared `skills/` tree.
- Codex discovers `hooks/hooks.json` automatically from the enabled plugin.
- `AGENTS.md` is the durable project guidance entry point.
- Hooks use the native Codex lifecycle events and deny protocol.
- `.itd/` and `.itd-memory/` remain the canonical project contracts and state.

Codex sets `PLUGIN_ROOT` and also supplies `CLAUDE_PLUGIN_ROOT` for compatible
plugin hooks. `hooks/codex-dispatch.py` handles the remaining transport gap:
Codex reports file mutations as `apply_patch`, while the shared gates expect
`Write` or `Edit` with a `file_path`. The dispatcher expands one patch into the
affected paths and preserves the hook's output and exit status.

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

Run `python3 tests/verify_host_adapters.py` to validate packaging, registration,
normalization, and declared parity.
