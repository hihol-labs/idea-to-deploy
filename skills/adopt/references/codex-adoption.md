# Codex adoption branch

This branch replaces the Claude-specific host steps in `/adopt`. Shared
contract scaffolding, example-test, runnability, and voice-chain steps still
apply unchanged.

## Discovery and plan

1. Resolve the git root and apply the self-reference guard.
2. Inspect `AGENTS.md`, `.codex/hooks.json`, `.itd/`, and `.itd-memory/`.
3. Resolve the plugin root from `PLUGIN_ROOT`, `CLAUDE_PLUGIN_ROOT`, or the
   current skill location. Verify `.codex-plugin/plugin.json` and
   `hooks/hooks.json` exist.
4. Detect stack and product type using the same heuristics as shared Step 0.
5. Show this plan before writing:

   - `AGENTS.md`: create, append the guarded block, or skip;
   - plugin hooks: confirm bundled and trusted, or offer the repo-local
     `.codex/hooks.json` fallback;
   - `.itd/` and `.itd-memory/`: scaffold or skip using shared Step 3.5;
   - example test and runnability check: offer the shared optional steps.

Do not write a `CLAUDE.md`, `.claude/settings.json`, or a host-private memory
mirror in the Codex branch.

For the repeatable mechanical part, use the bundled stdlib-only helper after
the user approves the shown plan:

```text
python3 skills/adopt/scripts/itd_adopt.py \
  --project <git-root> --plugin-root <plugin-root> --plan \
  --baseline-command <existing-green-command> \
  --verification-command <first-unit-command> \
  --unit-id <id> --unit-criterion <checkable-criterion> \
  --allowed-area <path>
```

Then rerun the same command with `--apply --approved`. The helper is not an
approval substitute: it refuses `--apply` without `--approved`, never writes
product source or user-level configuration, and reports every refusal as
`WHY` + `FIX`. Use the ordinary manual steps only when the helper is unavailable
or the user deliberately chooses a non-standard partial adoption; record that
fallback as operational friction in the final report.

## Guidance entry

Read `agents-md-template.md`.

- If `AGENTS.md` is absent, create it from the template.
- If it exists without `<!-- idea-to-deploy:begin codex-v1 -->`, append the
  block without changing user content.
- If the marker exists, leave the file unchanged.
- If the repository already uses nested `AGENTS.md` files, report their scope;
  do not consolidate or delete them automatically.

For an `AGENTS.md` over 300 lines, offer a router split analogous to shared
Step 3.8, using `docs/agents/` for topic files. Moving existing user content
still requires explicit approval.

## Hooks

When the Idea to Deploy plugin is enabled, its `hooks/hooks.json` is canonical.
Ask the user to inspect/trust it with `/hooks` if Codex reports untrusted hooks.
Do not copy bundled hooks into the target project.

Only when the user intentionally runs from a repository checkout without an
enabled plugin:

1. Read `codex-project-hooks.json`.
2. Replace `{{ITD_ROOT}}` with the absolute POSIX/WSL checkout path and
   `{{ITD_ROOT_WINDOWS}}` with the absolute Windows checkout path.
3. Remove `_comment`, then create or merge `.codex/hooks.json` by event,
   matcher, and command without deleting foreign hooks.
4. Tell the user to review the new definitions with `/hooks`.

Never modify `~/.codex/hooks.json` or `~/.codex/config.toml` during adoption.

## State and memory

The project-local `.itd-memory/` directory is canonical on Codex and Claude
Code. Initialize it through shared Step 3.5. Do not depend on transcript files
or a private host memory path: those are host implementation details, not
methodology state.

## Final report and self-validation

Report absolute paths and verify:

- `AGENTS.md` contains the guarded Codex block;
- the plugin manifest and bundled hooks exist, or the explicit repo-local
  fallback was merged into `.codex/hooks.json`;
- `.itd/` and `.itd-memory/STATE.json` exist, or a visible skip reason was
  recorded;
- any example test and runnability check show their real results;
- no user-level Codex configuration and no Claude-specific project files were
  written.

Describe the next session in host-neutral terms: contract loading, skill
routing, scope/commit gates, state validation, and handoff readiness.
