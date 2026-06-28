---
name: context-mode-setup
description: 'Context-window optimization companion — sets up and integrates the upstream Context Mode plugin (mksglu/context-mode) into idea-to-deploy. Context Mode sandboxes large tool output into a local FTS5 store so the agent searches it instead of dumping it into context (vendor claim ~98% per-call reduction). Use for long /kickstart builds, long /task or /bugfix debugging sessions, or any step where Bash/Read/Grep/WebFetch produce huge output. Detects install, prints the verified CLI commands, and maps the plugin onto the lifecycle; does NOT vendor upstream code.'
argument-hint: status, install, doctor, or off
license: MIT
allowed-tools: Read, Bash
metadata:
  effort: low
  side_effect: read-only
  explicit_invocation: false
  author: HiH-DimaN
  version: 1.0.0
  category: efficiency
  tags: [context-mode, context-window, token-efficiency, sandbox, fts5, integration]
---


# Context Mode Setup

Context-window optimization companion for idea-to-deploy. The upstream **Context
Mode** plugin intercepts large tool output *before* it reaches the context
window — raw data goes into a local SQLite FTS5 store, and the agent searches it
on demand instead of pasting it all in. Vendor claim: up to ~98% per-call context
reduction (e.g. a 315 KB session of raw tool output collapses to ~5 KB in
context).

This is the idea-to-deploy-native **setup/integration** skill: it tells you
*when* in the methodology to reach for Context Mode, detects whether it is
installed, gives the verified install commands, and maps its components onto the
lifecycle. It is named `context-mode-setup` on purpose — the upstream plugin
ships its own skill literally named `context-mode`, so this skill carries a
distinct name to avoid a collision when both are installed.

It does **not** vendor or re-implement the upstream engine — that engine is a
bundled Node program (`server.bundle.mjs`) with a native `better-sqlite3`
dependency, and idea-to-deploy stays bash/python/markdown with zero native deps.

Use this skill when the user asks about context mode, context-window pressure,
sandboxing tool output, big tool dumps eating the context, or session continuity
across compaction.

## Trigger phrases

These are the user phrases (Russian and English) that should auto-invoke this skill. They are kept here, not in the description, to avoid diluting the embedding-based matcher in the frontmatter. The hook `hooks/check-skills.sh` also uses this list — keep them in sync.

- context mode, режим контекста, context-mode, ctx mode
- экономия контекста, сжать контекст, контекстное окно забивается, забивается контекст
- большой вывод инструмента, огромный вывод, sandbox вывод, песочница для вывода
- save context window, context window optimization, sandbox tool output, huge tool output, too much context

## Recommended model

**sonnet** — This skill is an orchestrator/bridge: it explains fit, checks install state, and prints commands. No code or doc generation, no heavy reasoning. Sonnet is plenty.

## Upstream

Integrates the public **Context Mode** plugin —
`https://github.com/mksglu/context-mode` by [@mksglu](https://github.com/mksglu)
(license **Elastic License 2.0 / ELv2**, *source-available*, not MIT). This skill
is MIT (our own orchestration text); it ships **no** upstream source. The ELv2
terms (no offering it as a hosted/managed service, no removing license notices)
apply to the upstream plugin itself — this skill only points at it and prints
its documented install commands.

There is also a Cowork port at `https://github.com/scottconverse/context-mode`
(same ELv2, ported by @scottconverse). For Claude Code, prefer the upstream
`mksglu/context-mode`.

## What Context Mode provides

Verified against the installed plugin (`claude plugin details context-mode`,
version 1.0.168):

- **8 skills** — `context-mode` (the upstream usage/decision skill) plus
  `ctx-doctor`, `ctx-search`, `ctx-stats`, `ctx-index`, `ctx-insight`,
  `ctx-purge`, `ctx-upgrade`. (Note: the upstream `context-mode` skill name is
  why this idea-to-deploy skill is `context-mode-setup`.)
- **6 lifecycle hooks** — PreToolUse / PostToolUse / PreCompact / SessionStart /
  UserPromptSubmit / Stop — **harness-only** (they run as scripts, no per-call
  model-context cost). They auto-route heavy Bash/Read/Grep/WebFetch/Agent output
  through the sandbox instead of dumping raw output into context.
- **Bundled engine** — `server.bundle.mjs` (Node) with `better-sqlite3` for the
  FTS5 store, invoked by the hooks/scripts. `claude plugin details` reports
  **MCP servers: 0** for 1.0.168 — the work is done via hooks + the bundled
  program, not a registered MCP server exposing `ctx_*` tools.
- **Session continuity** — persists session memory so context survives compaction.

**Cost tradeoff:** `claude plugin details` projects **~631 tokens always-on**
added to every session (plus on-invoke cost when a `ctx-*` skill fires). Worth it
for long, output-heavy sessions; not worth it for short single-shot tasks.

Requirements: **Node.js ≥ 22.5** (or Bun) and **Claude Code ≥ 1.0.33**.

## Install / detect

`/context-mode-setup` never installs anything silently. It detects state and,
only with your go-ahead, runs (or prints) the documented commands.

**Detect** whether it is installed (read-only):

```bash
claude --version                                    # need ≥ 1.0.33
node --version                                       # need ≥ 22.5 for the engine
claude plugin list 2>/dev/null | grep -i context-mode || echo "context-mode: NOT installed"
claude plugin details context-mode 2>/dev/null       # components + token cost, if installed
```

**Install** — both paths are equivalent; the CLI path is verified to work from a
shell:

```bash
# CLI (verified)
claude plugin marketplace add mksglu/context-mode
claude plugin install context-mode@context-mode
```

```text
# or in-app, inside Claude Code
/plugin marketplace add mksglu/context-mode
/plugin install context-mode@context-mode
```

Then **restart Claude Code** (plugins load at startup) and verify with the
upstream **`ctx-doctor`** skill — it checks the engine, FTS5, and warns about
duplicate hook firings. To remove later: `claude plugin uninstall context-mode`.

If `node --version` is below 22.5 or `ctx-doctor` reports a failure, report the
blocker plainly — do **not** claim Context Mode is active when it is not.

## idea-to-deploy fit

Context Mode is an **optional efficiency companion**, not a work route. It changes
*how much tool output reaches context*, never *what the methodology requires*. The
gates still win: `/review`, `/test`, `/security-audit`, DoD, and the
skill-decision line are unaffected.

Where it pays off most in the lifecycle:

| Lifecycle step | Why Context Mode helps |
|---|---|
| `/kickstart`, `/blueprint` big scaffolds | Long build/test logs from many `npm`/`pytest`/`cargo` runs stay out of context; search them with `ctx-search` only when a failure needs reading. |
| `/task`, `/bugfix` long sessions | Hours of grep/log/stack-trace output sandboxed; the actual context window stays free for reasoning. Session continuity survives compaction. |
| `/test`, `/deps-audit` | Large test matrices / dependency trees indexed once, queried on demand instead of re-dumped. |
| `/review`, `/perf` over large diffs/profiles | Big `git diff` / profiler output captured into the store, queried with `ctx-search`. |

**Do not** enable it for short, single-shot tasks — the ~631-tok always-on
overhead and the sandbox indirection cost more than they save when output is
already small.

## Coexistence with idea-to-deploy hooks

idea-to-deploy registers **19 enforcement hooks** (PreToolUse/PostToolUse/
UserPromptSubmit/Stop/PreCompact/SessionStart). Context Mode registers **6**
lifecycle hooks on overlapping events. Claude Code runs multiple plugins' hooks
side by side — verified: after installing Context Mode, `~/.claude/settings.json`
holds both plugins' hooks with no overwrite. Still confirm there is no
interference after install:

- Run the upstream **`ctx-doctor`** skill — it warns on duplicate hook firings /
  stale entries.
- Sanity-check that idea-to-deploy gates still fire: a >2-file commit without a
  review must still be blocked by `check-review-before-commit.sh`; the
  skill-enforcement counter must still escalate. Context Mode redirects *tool
  output*, it must not swallow our hooks' *stderr guidance*.
- If a conflict appears (a gate stops firing, or guidance is hidden), report it;
  do not paper over it. The two plugins are independent — `claude plugin disable
  context-mode` reverts Context Mode without touching idea-to-deploy.

## Self-validation

Before responding, check:

- Install state was actually detected (not assumed) — if Context Mode is not
  installed, say so and offer the install commands; never claim it is active.
- Node ≥ 22.5 and Claude Code ≥ 1.0.33 were checked before declaring it usable.
- The mechanism is described per the installed plugin (skills + harness-only
  hooks + bundled engine), not invented `ctx_*` MCP tools.
- No upstream ELv2 source was copied into the repo; attribution to @mksglu is intact.
- idea-to-deploy gates/verification/commit-status are reported truthfully and were
  not affected by the integration.

## Examples

### Example 1: User hits context pressure mid-build

User: «контекст забивается от логов сборки, что делать»

Actions:
1. Recognize context-window pressure from large tool output → this skill.
2. Detect: run `claude plugin list | grep context-mode`. Not installed.
3. Explain the fit (long build logs → sandbox + `ctx-search`) and run/print the
   two CLI install commands. Note Node ≥ 22.5 / CC ≥ 1.0.33 and the ~631-tok
   always-on cost.
4. After they install + restart, have them run the `ctx-doctor` skill to confirm.
5. Remind: idea-to-deploy gates are unaffected; this only frees context.

### Example 2: Already installed — verify coexistence

User: «context mode уже стоит, не мешает он методологии?»

Actions:
1. Run `claude plugin details context-mode` (components + cost) and the
   `ctx-doctor` skill (duplicate-hook / stale check); report results.
2. Confirm idea-to-deploy gates still fire (review gate blocks an unreviewed
   multi-file commit; skill counter escalates). Report pass/fail honestly.
3. If clean → "17 idea-to-deploy hooks + 6 Context Mode hooks coexist, no
   conflict." If not → name the conflict, don't hide it.

### Example 3: Short task — recommend against

User (one-line fix): «включи context mode для этого»

Actions:
1. Output is already small → the ~631-tok always-on overhead + indirection cost
   more than they save.
2. Recommend against enabling it here; reserve it for long sessions / big dumps.

## Troubleshooting

### `node --version` < 22.5
The upstream engine needs Node ≥ 22.5 (or Bun). Report the blocker; do not claim
Context Mode is active. Suggest upgrading Node or using Bun, then re-run the
`ctx-doctor` skill.

### `ctx-doctor` reports duplicate hook firings
A prior partial install left stale hook entries. Follow upstream `ctx-doctor`
guidance to clean them. This does not affect idea-to-deploy's own hooks.

### A gate stopped firing after installing Context Mode
Report it as a real conflict — do not work around it silently. Verify by
temporarily checking the gate (e.g. attempt a >2-file commit without review). The
two plugins are independent; if needed, `claude plugin disable context-mode` to
confirm the gate returns, then file the conflict.

### User wants the engine vendored into idea-to-deploy
Decline by default: the upstream is ELv2 (idea-to-deploy is MIT) and needs a
native dependency (`better-sqlite3`). Vendoring would create a license conflict
and break the zero-native-dep design. The integration + marketplace install is
the supported path.

## Rules (hard)

- Never perform a global/network install or edit shell profiles / plugin config
  without explicit user approval — detect and print/run commands on their say-so.
- Never copy upstream ELv2 source into this repo; keep attribution to @mksglu.
- Never claim Context Mode is installed/active without detecting it (`claude
  plugin list` / `claude plugin details` / `ctx-doctor`).
- Describe the mechanism per the installed plugin (skills + harness-only hooks +
  bundled engine), not invented `ctx_*` MCP tools.
- Never let the integration hide or weaken an idea-to-deploy gate, verification
  result, or the skill-decision line.
- This skill is an efficiency companion; it does **not** replace `/review`,
  `/test`, `/security-audit`, `/caveman`, or any work route.
