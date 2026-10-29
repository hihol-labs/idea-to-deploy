# Codex adoption branch

The Codex specifics of `/adopt`: the entry file is `AGENTS.md` (`--host codex`), the hooks come from the enabled
plugin, and the strict route binds a machine oracle the server can trust. The route is chosen by Step 0 of `SKILL.md`
exactly as on Claude Code; the minimal path writes one pointer block, the strict route follows
`references/strict.md`.

## Discovery and plan

1. Resolve the git root; the helper applies the self-reference guard.
2. Inspect `AGENTS.md`, `.codex/hooks.json`, `.itd/`, and `.itd-memory/`.
3. Resolve the plugin root from `PLUGIN_ROOT`, `CLAUDE_PLUGIN_ROOT`, or the current skill location. Verify
   `.codex-plugin/plugin.json` and `hooks/hooks.json` exist.
4. Run the helper plan and show it before writing:

   ```text
   sh <plugin-root>/skills/_shared/itd_py.sh <plugin-root>/skills/adopt/scripts/itd_adopt.py \
     --project <git-root> --plugin-root <plugin-root> --host codex --plan
   ```

   `itd_py.sh` picks a working Python (it avoids the Windows Store shim on native Windows / Git Bash).
   Minimal path: `AGENTS.md` create, append the guarded block, or skip; the discovered test, lint and build commands;
   nothing else. Strict route: add `--strict` and the first-unit values of strict S1:

   ```text
   sh <plugin-root>/skills/_shared/itd_py.sh <plugin-root>/skills/adopt/scripts/itd_adopt.py \
     --project <git-root> --plugin-root <plugin-root> --host codex --strict --plan \
     --baseline-command <existing-green-command> \
     --verification-command <first-unit-command> \
     --trusted-verifier-path <exact-tracked-test-or-runner-file> \
     --unit-id <id> --unit-criterion <checkable-criterion> \
     --allowed-area <path>
   ```

   The strict plan also shows the hook status (bundled and trusted, or the repo-local `.codex/hooks.json` fallback),
   the optional example test, runnability check and context index, and the GitHub gate coordinates of strict S6 (or
   that the repository will remain `UNVERIFIED`).

Then rerun the same command with `--apply --approved`. The helper is not an approval substitute: it refuses `--apply`
without `--approved`, refuses strict-only options without `--strict`, never writes product source or user-level
configuration, and reports every refusal as `WHY` + `FIX`. Use manual steps only when the helper is unavailable or
the user deliberately chooses a non-standard partial adoption; record that fallback as operational friction in the
final report.

Do not write a `CLAUDE.md`, `.claude/settings.json`, or a host-private memory mirror in the Codex branch.

## Strict: the machine oracle

The verification command must be one shell-free argv invocation (no pipes,
redirection, `&&`, or command substitution). Repeat
`--trusted-verifier-path` for the exact executable verifier and repeat it for
every verifier-side file that verifier reads or executes (plus any launcher).
Before the server-side machine oracle runs, those paths must resolve to
identical regular Git objects in the protected base and candidate. Python
commands are normalized to isolated `-I` mode, excluding the script directory,
candidate working directory, user site packages, and adjacent candidate
startup modules from import resolution. Non-isolated exact-file bindings are
rejected. Rotate a verifier in three merges: add it under a new path, update
the protected contract to trust that already-protected path, then use it for
implementation changes.

After the strict helper succeeds, run strict S5 (context index) only when its exact plan was
included in the same user approval. Use the enabled plugin's
`skills/adopt/scripts/itd_context_map.py`; `apply` still requires
`--approved` plus the exact `--plan-sha256` emitted by the shown plan. The
result is the single host-neutral `docs/agent-context`
family for both Codex and Claude Code. It must never replace `AGENTS.md`,
`.itd`, or `.itd-memory`.

For a GitHub origin, immediately continue with strict S6. The local
helper intentionally does not write host-global state; the workflow invokes
`itd gate adopt` as the separately visible, approved global registry write.
Do not report Codex adoption as gate-ready until the post-commit
`itd gate doctor --repository ...` result is `PROTECTED`.

## Guidance entry

The helper renders `agents-md-pointer.md` on the minimal path; a fresh strict adoption uses `agents-md-template.md`
(the strict Codex block, pinned by the live benchmark) with the commands and the `itd-route: strict` line added
before its end marker:

- If `AGENTS.md` is absent, it creates it from the template.
- If it exists without an idea-to-deploy marker, it appends the block without changing user content.
- If any marker exists, it leaves the file unchanged; a strict run only adds the strict paragraph inside the block.
- If the repository already uses nested `AGENTS.md` files, report their scope; do not consolidate or delete them
  automatically.

For an `AGENTS.md` over 300 lines, offer a router split analogous to strict S4, using `docs/agents/` for topic files.
Moving existing user content still requires explicit approval.

## Hooks

When the Idea to Deploy plugin is enabled, its `hooks/hooks.json` is canonical.
Ask the user to inspect/trust it with `/hooks` if Codex reports untrusted hooks;
`python3 scripts/itd_codex_hook_trust.py` (read-only) names the entries Codex will
not run. Switch hooks on or off in `~/.claude/itd-enabled-hooks.txt` and
`~/.claude/itd-disabled-hooks.txt` (the dispatcher reads them on Codex too), not
by position in `/hooks`. Do not copy bundled hooks into the target project.

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

The project-local `.itd-memory/` directory is canonical on Codex and Claude Code; only the strict route creates it
(strict S1). Do not depend on transcript files or a private host memory path: those are host implementation
details, not methodology state.

## Final report and self-validation

Report absolute paths and verify:

- `AGENTS.md` contains exactly one guarded idea-to-deploy block, with the discovered commands;
- minimal path: nothing else was written;
- strict route: the block holds the `itd-route: strict` line in the first 8 KB; `.itd/` and `.itd-memory/STATE.json`
  exist; the plugin manifest and bundled hooks exist, or the explicit repo-local fallback was merged into
  `.codex/hooks.json`; any example test and runnability check show their real results; `docs/agent-context/index.json`
  validates with observed-only path/hash-backed claims, or the context-index skip reason is visible; the GitHub
  checkout has an exact gate-registry entry created only after live App/organization-ruleset/broker validation and the
  post-commit doctor is `PROTECTED`, or the report is explicitly `UNVERIFIED`;
- no user-level Codex configuration and no Claude-specific project files were written.
