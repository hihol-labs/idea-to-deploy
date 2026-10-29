<!--
Minimal AGENTS.md pointer block for projects adopted into the idea-to-deploy methodology on Codex (ITD-PLAN-S9).

/adopt (skills/adopt/scripts/itd_adopt.py --host codex) appends everything between the BEGIN and END markers to the
project's AGENTS.md (or writes the whole file if AGENTS.md is absent). Re-running /adopt detects any idea-to-deploy
marker and does nothing - idempotent; only a --strict run adds the strict paragraph to a block that lacks it.
{{COMMANDS}} becomes the test, lint and build commands found in the manifests (or nothing); {{STRICT}} is empty here.
A fresh strict adoption uses agents-md-template.md (the strict Codex block the live benchmark pins) with the
commands and the `itd-route: strict` line added before its end marker. The block is a pointer, not a copy of the rules.
-->

<!-- idea-to-deploy:begin codex-v1 -->
## Idea to Deploy methodology

This project uses the model-neutral Idea to Deploy methodology from the
enabled plugin (skills, hooks, agents; global rules in `~/.codex/AGENTS.md`).
The minimal path is the default (ADR-012):

- Do ordinary work directly: understand the task, change the code, write or
  fix the tests, run the suite, show the result with numbers.
- Use a plugin skill when asked or when it clearly shortens the work; a plan
  only for a large or unclear task.
- Ask the owner before anything irreversible or external: deploy, migrations
  and production data, money, push/PR, deletion. Never print or send secrets.

Codex hooks are supplied by the enabled Idea to Deploy plugin. Review and
trust them with `/hooks`; do not duplicate them into `.codex/hooks.json` unless
this project intentionally uses a repository-local methodology checkout.

{{COMMANDS}}Adopted {{ADOPTED_AT}} through `/adopt`.{{STRICT}}
<!-- idea-to-deploy:end codex-v1 -->
