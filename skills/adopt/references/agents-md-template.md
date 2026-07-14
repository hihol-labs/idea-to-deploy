<!-- idea-to-deploy:begin codex-v1 -->
## Idea to Deploy methodology

This project uses the model-neutral Idea to Deploy engineering harness.

- Read the applicable plugin skill before executing a lifecycle workflow.
- Treat `.itd/` as the project/verification contract and `.itd-memory/` as the
  canonical persistent execution state.
- Preserve WIP=1. Do not mark a unit complete from narration alone; attach the
  runtime or static evidence required by `.itd/VERIFICATION_CONTRACT.json`.
- Before changing scope, update `.itd/SCOPE_LOCK.md` and reconcile the active
  unit in `.itd-memory/STATE.json` or `.itd-memory/GOAL.json`.
- Use native Codex subagents when useful. Give each subagent the applicable
  role contract from the Idea to Deploy plugin's `agents/` directory and
  require the shared machine-readable verdict contract.
- End work handoff-ready: tests recorded, state reconciled, and next action
  explicit.

Codex hooks are supplied by the enabled Idea to Deploy plugin. Review and
trust them with `/hooks`; do not duplicate them into `.codex/hooks.json` unless
this project intentionally uses a repository-local methodology checkout.
<!-- idea-to-deploy:end codex-v1 -->
