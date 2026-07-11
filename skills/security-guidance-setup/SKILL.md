---
name: security-guidance-setup
description: 'Security companion — sets up and integrates the official Anthropic security-guidance plugin (anthropics/claude-code, free, ships in the claude-plugins-official marketplace) into idea-to-deploy. security-guidance is a shift-left, always-on reviewer of Claude-generated code: instant regex pattern warnings on every Edit/Write, an LLM diff review on Stop that feeds high-severity findings back before you see the response, and an agentic commit/push reviewer that traces cross-file data flow (IDOR, auth bypass, SSRF). Use when the user asks about the security-guidance plugin, realtime/shift-left security review as code is written, automatic vulnerability catching on edit or commit, or wiring continuous security review into the lifecycle. Distinct from /security-audit (on-demand deep audit report) — security-guidance is the continuous layer that complements it. Detects install, prints the verified CLI commands, and maps the plugin onto the lifecycle; does NOT vendor upstream code.'
argument-hint: status, install, lifecycle-map, or off
license: MIT
allowed-tools: Read, Bash
metadata:
  effort: low
  side_effect: read-only
  explicit_invocation: false
  author: HiH-DimaN
  version: 1.0.0
  category: quality-assurance
  tags: [security, shift-left, vulnerability-review, code-review, integration]
---


# Security Guidance Setup

Security companion for idea-to-deploy. The upstream **security-guidance** plugin —
[official, by Anthropic](https://github.com/anthropics/claude-code/tree/main/plugins/security-guidance) —
makes Claude review its own code for vulnerabilities and fix them in the same
session. It is a **shift-left, always-on** reviewer with three layers:

1. **Pattern warnings** — instant regex-based reminders on every `Edit`/`Write`/
   `MultiEdit`/`NotebookEdit` for ~25 known-dangerous patterns (`yaml.load`,
   `pickle.load` on untrusted data, `eval`/`new Function`, `os.system`,
   `child_process.exec`, raw `innerHTML`/`dangerouslySetInnerHTML`,
   `torch.load(weights_only=False)`, hardcoded secrets, …). No model call, instant.
2. **LLM diff review** — when Claude finishes a turn (`Stop` hook), the plugin sends
   the diff to a fast model call (Opus 4.7 by default) and feeds high-severity
   findings back to Claude so it can fix them *before you see the response*.
3. **Agentic commit/push review** — on `git commit` / `git push`, an SDK-driven
   reviewer reads related files (`Read`/`Grep`/`Glob`) to trace data flow across the
   codebase, catching multi-file vulnerabilities pattern matching misses (IDOR, auth
   bypass, cross-file SSRF). Findings come back via async re-wake.

Findings cover common web-vulnerability classes — injection, XSS, SSRF, hardcoded
secrets, IDOR, auth bypass, unsafe deserialization, and path traversal among others.

This is the idea-to-deploy-native **setup/integration** skill: it tells you *when*
the plugin pays off in the methodology, detects whether it is installed, gives the
verified install commands, maps its review layers onto the lifecycle, and confirms
it coexists with idea-to-deploy's own hooks/gates. It is named
`security-guidance-setup` to keep a distinct, explicit handle for the integration
and to avoid being confused with idea-to-deploy's own `/security-audit` skill (a
different thing — see "Relationship to `/security-audit`" below).

It does **not** vendor or re-implement the upstream plugin. security-guidance is
**first-party Anthropic code**, free, ships **enabled by default** in the official
`claude-plugins-official` marketplace, and is actively maintained — vendoring would
fork it (we'd miss its pattern/rule and reviewer updates) and it is not ours to
redistribute. The supported path is the official marketplace install.

Use this skill when the user asks about the security-guidance plugin, realtime /
shift-left security review, catching vulnerabilities as code is written or on
commit, an automatic security reviewer for Claude Code, or wants continuous security
review wired into the project lifecycle.

## Trigger phrases

These are the user phrases (Russian and English) that should auto-invoke this skill. They are kept here, not in the description, to avoid diluting the embedding-based matcher in the frontmatter. The hook `hooks/check-skills.sh` also uses this list — keep them in sync.

- security-guidance, security guidance plugin, плагин security guidance, секьюрити-гайденс
- shift-left security, shift left security, сдвиг безопасности влево
- realtime security review, real-time security review, ревью безопасности на лету, ревью безопасности в реальном времени
- security review as I write, review code as it is written, проверка безопасности при написании кода
- автоматический security-ревью, авто-ревью безопасности, automatic security reviewer
- catch vulnerabilities as you code, ловить уязвимости при написании, ловить уязвимости на лету
- official security plugin for claude code, официальный security-плагин claude code
- security review on commit, commit security review, ревью безопасности при коммите

**Do NOT** route generic security-audit phrasing here — "проверь безопасность",
"OWASP", "auth check", "найди уязвимости" (on-demand) belong to `/security-audit`.
This skill triggers on the *plugin* and the *realtime/shift-left* concept, not on
an audit request.

## Recommended model

**sonnet** — This skill is an orchestrator/bridge: it explains fit, checks install
state, and prints commands. No code or doc generation, no heavy reasoning. Sonnet
is plenty.

## Upstream

Integrates the official **security-guidance** plugin —
`https://github.com/anthropics/claude-code/tree/main/plugins/security-guidance`
(author David Dworken, Anthropic). It is **first-party Anthropic code**: the
`anthropics/claude-code` repo carries Anthropic's own license (GitHub reports no
standard SPDX OSS license), and plugin use is governed by Anthropic's
[Commercial Terms](https://www.anthropic.com/legal/commercial-terms). This
idea-to-deploy skill is MIT (our own orchestration text); it ships **no** upstream
source — it points at the official plugin and prints its documented install
command. The plugin is **free for all users on all plans**.

Not vendoring is the only correct choice here: it is Anthropic's maintained,
default-on plugin (the pattern set, the LLM reviewer, and the agentic reviewer are
updated upstream), and re-distributing first-party code we don't own is out of
scope. The marketplace install is the supported path.

## What security-guidance provides

Verified against the upstream repo (`plugin.json` / `hooks/hooks.json`, version
**2.0.0**):

- **Three review layers** (above): pattern warnings (layer 1, no model call),
  LLM diff review on `Stop` (layer 2), agentic commit/push reviewer (layer 3).
- **Hooks** (`hooks/hooks.json`) — `SessionStart` (provisions the Agent SDK),
  `UserPromptSubmit`, `PostToolUse: Edit|Write|MultiEdit|NotebookEdit` (pattern
  warnings), `PostToolUse: Bash` with `if: Bash(git commit:*)` / `if: Bash(git
  push:*)` (agentic review, `asyncRewake`), and `Stop` (diff review, `asyncRewake`).
  All run the Python entrypoint `security_reminder_hook.py` via `sg-python.sh`.
- **~25 dangerous-pattern rules** covering injection, XSS, SSRF, hardcoded secrets,
  IDOR, auth bypass, unsafe deserialization, path traversal, and more.
- **Configuration via env vars** (none required for default behavior):
  `SECURITY_GUIDANCE_DISABLE=1` (kill switch), `ENABLE_PATTERN_RULES=0` (off layer
  1), `ENABLE_CODE_SECURITY_REVIEW=0` (off all LLM reviews), `ENABLE_STOP_REVIEW=0`
  (off only the Stop diff review — **recommended for multi-agent / shared-worktree**
  setups), `ENABLE_COMMIT_REVIEW=0` (off layer 3), `SECURITY_REVIEW_MODEL` /
  `SG_AGENTIC_MODEL` (pick the model), `SG_DUAL_OR=on` (higher recall, ~2× cost).
- **Org/repo policy file** — drop a `claude-security-guidance.md` in
  `~/.claude/` (user-wide), `<project>/.claude/` (committed), or
  `<project>/.claude/claude-security-guidance.local.md` (gitignored); all three are
  concatenated into the LLM diff-review prompt (8 KB budget). For codebase-specific
  rules the model can't infer; built-in rules cover the common classes without it.

**Cost / privacy tradeoff:** layers 2–3 send the changed file paths, diff hunks, and
relevant file contents (plus any files the agentic reviewer pulls in) to a model
endpoint — `api.anthropic.com` by default, or your gateway / 3P provider per your
Claude Code config. The plugin writes a local debug log to `~/.claude/security/
log.txt` (categories + diffstate metadata, no file contents; rotates at 1 MB,
nothing uploaded). Don't put secrets in `claude-security-guidance.md`. Layer 1 is
local-only.

Requirements: **Claude Code CLI ≥ v2.1.144**, **Python 3.8+** on `PATH` (`python3`,
`python`, or `py -3`), and a working API path (subscription, API key, or 3P
provider) for layers 2–3.

## Install / detect

`/security-guidance-setup` never installs anything silently. It detects state and,
only with your go-ahead, runs (or prints) the documented command.

**Detect** whether it is installed (read-only):

```bash
claude --version                                              # need ≥ v2.1.144
python3 --version 2>/dev/null || python --version             # need ≥ 3.8 (win-ok: probe с fallback)
claude plugin list 2>/dev/null | grep -i security-guidance || echo "security-guidance: NOT installed"
claude plugin details security-guidance 2>/dev/null           # hooks/components, if installed
```

**Install** — it ships **enabled by default** in the official marketplace, so on a
current Claude Code it may already be active. If not, install from the official
marketplace:

```bash
# CLI
claude plugin install security-guidance@claude-plugins-official
```

```text
# or in-app, inside Claude Code
/plugin install security-guidance@claude-plugins-official
```

Then **restart Claude Code** (plugins/hooks load at startup). The first turn after
restart triggers the `SessionStart` hook, which provisions the Agent SDK (needs
network + a working API path). Verify with `claude plugin details security-guidance`
for the hook list, or make a deliberately unsafe edit (e.g. add an `eval(...)` line)
and confirm the pattern warning fires. To remove later:
`claude plugin uninstall security-guidance`. To silence without uninstalling, set
`SECURITY_GUIDANCE_DISABLE=1`.

If `claude --version` is below v2.1.144, Python 3.8+ is missing, or the API path
doesn't work, report the blocker plainly — do **not** claim security-guidance is
active when layers 2–3 cannot run (layer 1 pattern warnings still work offline).

## Relationship to `/security-audit`

These are complementary, not duplicates — report both, never present one as a
replacement for the other:

| | `/security-audit` (idea-to-deploy) | security-guidance plugin |
|---|---|---|
| Trigger | On-demand, you invoke it | Always-on, fires automatically |
| Shape | Read-only **audit report** (status enum, OWASP-style) | **Shift-left** warnings + diff/commit review, fixes in-session |
| When | Before `/review`, at a gate, on request | Continuously, as code is written and committed |
| Output | A findings report you act on | Inline pattern warnings + model findings fed back to Claude |

Run security-guidance as the continuous safety net **and** `/security-audit` as the
on-demand deep pass at the gate. Neither replaces human review, SAST/DAST, dep
scanning, or pen-testing (the upstream README is explicit: best-effort assistive
tool, no warranty).

## idea-to-deploy fit

security-guidance is an **always-on capability companion**, not a work route. It adds
security review *into* every coding step; it never changes *what the methodology
requires*. The gates still win: `/review`, `/test`, `/security-audit`, the DoD
pre-commit gate, and the skill-decision line are unaffected.

Where it pays off most in the lifecycle:

| Lifecycle step | Why security-guidance helps |
|---|---|
| `/kickstart`, `/task`, `/bugfix`, `/refactor` | Layer 1 + 2 catch injection / XSS / unsafe deserialization / hardcoded secrets **as code is generated or edited** — the highest-volume moment for new vulnerabilities. Findings come back before you read the turn. |
| `/review` | Layer 2's diff review is a pre-`/review` hygiene pass: high-severity findings are fixed before the human/`/review` rubric even looks. Complements, does not replace, `/review`. |
| `/security-audit` | The continuous shift-left layer underneath the on-demand audit (see table above). Use both. |
| `/migrate`, `/harden` | Layer 3's agentic commit/push reviewer traces cross-file data flow (IDOR, auth bypass, cross-file SSRF) on the exact commits that touch schema/auth/prod — the same surface the DoD gate guards. |
| `/deploy` | Layer 3 reviews the release commit/push for vulnerabilities introduced late, after the pre-commit gates have run. |

It is worth enabling on essentially **any** project that ships code (the cost is a
model call per turn/commit on layers 2–3, and zero on layer 1). For a throwaway
spike with no security surface, or to cut model cost, disable layers 2–3
(`ENABLE_CODE_SECURITY_REVIEW=0`) and keep the free layer-1 warnings.

## Coexistence with idea-to-deploy hooks

idea-to-deploy registers its enforcement hooks (PreToolUse/PostToolUse/
UserPromptSubmit/Stop/PreCompact/SessionStart). security-guidance registers its own
on `SessionStart`, `UserPromptSubmit`, `PostToolUse: Edit|Write|MultiEdit|
NotebookEdit`, `PostToolUse: Bash` (git commit/push), and `Stop`. Claude Code runs
multiple plugins' hooks side by side, so confirm there is no interference after
install:

- **Pre- vs post-commit, no conflict — they stack.** idea-to-deploy's review gate
  (`check-review-before-commit.sh`) and DoD gate run on **PreToolUse** `Bash(git
  commit)` and **block** a non-compliant commit. security-guidance's commit reviewer
  runs on **PostToolUse** `Bash(git commit/push)`, *after* the commit succeeds, and
  feeds findings back via async re-wake. Different phase → no collision: the DoD/
  review gate decides whether the commit happens; security-guidance then reviews
  what was committed. This is defense-in-depth, not duplication.
- **Stop / UserPromptSubmit / PostToolUse(Edit|Write) overlap is additive.** Both
  plugins fire on these; Claude Code aggregates the output. Confirm idea-to-deploy's
  skill-decision line and gate guidance are still visible and not swallowed — the
  security findings are *supplementary*, the methodology's status reporting stays
  authoritative.
- **Multi-agent / shared-worktree caveat.** idea-to-deploy uses subagents (and Agent
  Teams). Upstream explicitly recommends `ENABLE_STOP_REVIEW=0` for multi-agent /
  shared-worktree setups where another agent can move `HEAD` between a worker's
  turns; keep the commit/push review (layer 3) on. Set this if you run parallel
  agents on one worktree and see noisy or stale Stop-review findings.
- If a conflict appears (a gate stops firing, or methodology guidance is hidden),
  report it; do not paper over it. The two plugins are independent — `claude plugin
  disable security-guidance` (or `SECURITY_GUIDANCE_DISABLE=1`) reverts it without
  touching idea-to-deploy.

## Self-validation

Before responding, check:

- Install state was actually detected (not assumed) — if security-guidance is not
  installed, say so and offer the install command; if it ships default-on, verify
  rather than assume. Never claim it is active without `claude plugin list` /
  `claude plugin details`.
- Claude Code ≥ v2.1.144 and Python 3.8+ were checked, and the API-path requirement
  for layers 2–3 noted, before declaring it usable.
- The mechanism is described per the upstream repo (3 layers; hooks on SessionStart/
  UserPromptSubmit/PostToolUse Edit-Write-MultiEdit-NotebookEdit/PostToolUse Bash
  git commit-push/Stop; ~25 patterns; env-var config), not invented tools.
- No upstream first-party source was copied into the repo; attribution to Anthropic /
  the official plugin is intact.
- `/security-audit` is presented as **complementary**, not replaced.
- idea-to-deploy gates/verification/commit-status are reported truthfully and were
  not affected by the integration.

## Examples

### Example 1: User asks about realtime security review, plugin not installed

User: «можно ли, чтобы Claude сам ловил уязвимости прямо когда пишет код?»

Actions:
1. Recognize a shift-left / realtime-security need → this skill.
2. Detect: `claude plugin list | grep security-guidance`. Not installed.
3. Explain the three layers and the fit (catches issues as code is written +
   commit-time agentic review), and run/print the install command
   `claude plugin install security-guidance@claude-plugins-official`. Note CC ≥
   v2.1.144 / Python 3.8+ / API path for layers 2–3.
4. After they install + restart, verify with `claude plugin details
   security-guidance` (or a deliberate unsafe edit).
5. Remind: idea-to-deploy gates are unaffected; this complements `/security-audit`,
   it does not replace it.

### Example 2: Already installed — map onto the current phase

User: «security-guidance стоит, мы перед деплоем — что он даст?»

Actions:
1. Run `claude plugin details security-guidance` (hook list); report it.
2. Map `/deploy` + `/harden` → layer 3 agentic commit/push review on the release
   commit (cross-file IDOR / auth-bypass / SSRF); layer 2 diff review each turn.
3. Confirm idea-to-deploy gates still fire: the DoD/review pre-commit gate still
   blocks a non-compliant commit *before* security-guidance's post-commit review.
   Report pass/fail honestly.

### Example 3: Distinguish from `/security-audit`

User: «у нас же есть /security-audit, зачем ещё security-guidance?»

Actions:
1. Explain the complement (table above): `/security-audit` = on-demand deep audit
   report at a gate; security-guidance = always-on shift-left warnings + diff/commit
   review that fix issues in-session.
2. Recommend running both: continuous net + on-demand deep pass.
3. Do not present either as a replacement for the other or for human review.

### Example 4: Vendoring / multi-agent boundary

User: «давай скопируем хуки security-guidance прямо к нам в репозиторий и врубим на всех агентов»

Actions:
1. Decline vendoring by default: it is first-party Anthropic code (no standard OSS
   license; Commercial Terms), free and default-on from the official marketplace,
   and actively maintained — vendoring forks it and loses updates.
2. Offer the supported path: marketplace install + this skill.
3. For the multi-agent part, advise `ENABLE_STOP_REVIEW=0` (keep commit/push review)
   per upstream guidance for shared-worktree setups, instead of copying hooks.

## Troubleshooting

### `claude --version` < v2.1.144 or no Python 3.8+
The plugin needs CC ≥ v2.1.144 and Python 3.8+ on `PATH`. Report the blocker; do not
claim it is active. Layer 1 (pattern warnings) still works offline, but layers 2–3
(LLM diff + agentic commit review) need both prerequisites and a working API path.

### "Review never finds anything"
Verify the API path works (layers 2–3 call a model). On 3P providers, set
`SECURITY_REVIEW_MODEL` to a provider-specific id (not a bare `claude-opus-4-7`); on
gateways, check the gateway logs for `POST /v1/messages` from the plugin. Layer 1 is
independent and fires regardless.

### Noisy or stale Stop-review findings under parallel agents
You're in a multi-agent / shared-worktree setup and another agent moved `HEAD`
between turns. Set `ENABLE_STOP_REVIEW=0` (keeps commit/push review). This is the
upstream-recommended config for that case — not a bug in either plugin.

### A gate stopped firing after installing security-guidance
Report it as a real conflict — do not work around it silently. Verify by attempting
a >2-file commit without review (the DoD/review gate must still block it). The two
plugins are independent; if needed, `claude plugin disable security-guidance` (or
`SECURITY_GUIDANCE_DISABLE=1`) to confirm the gate returns, then file the conflict.

### Too many false positives
Drop `SECURITY_REVIEW_MODEL` to a cheaper model (`claude-sonnet-4-6`) and re-evaluate,
or add an inline comment justifying a specific line (the LLM reviewer treats inline
justifications as exclusions). For systemic exclusions, document them in
`claude-security-guidance.md`.

## Rules (hard)

- Never perform a global/network install or edit shell profiles / plugin config
  without explicit user approval — detect and print/run the command on their say-so.
- Never copy upstream first-party source (hooks, patterns, reviewer) into this repo;
  keep attribution to Anthropic / the official plugin.
- Never claim security-guidance is installed/active without detecting it (`claude
  plugin list` / `claude plugin details`) — even though it ships default-on, verify.
- Describe the mechanism per the upstream repo (3 layers; the SessionStart/
  UserPromptSubmit/PostToolUse/Stop hooks; ~25 patterns; env-var config), not
  invented tools.
- Always present security-guidance as **complementary** to `/security-audit`, never
  as a replacement for it, for `/review`, or for human review / SAST / pen-testing.
- Never let the integration hide or weaken an idea-to-deploy gate, verification
  result, or the skill-decision line.
- This skill is a capability companion; it does **not** replace `/review`, `/test`,
  `/security-audit`, or any work route.
