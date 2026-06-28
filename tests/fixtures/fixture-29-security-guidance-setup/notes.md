# Manual verification — fixture 29 (/security-guidance-setup)

`/security-guidance-setup` is a **read-only** orchestrator/integration skill for the
official [security-guidance plugin](https://github.com/anthropics/claude-code/tree/main/plugins/security-guidance)
by Anthropic (author David Dworken; first-party code, no standard OSS SPDX, use under
Anthropic Commercial Terms; free, ships **enabled by default** in the
`claude-plugins-official` marketplace). The upstream plugin is a **shift-left,
always-on** reviewer with three layers: (1) instant regex pattern warnings on every
Edit/Write/MultiEdit/NotebookEdit (~25 dangerous patterns), (2) an LLM diff review on
Stop that feeds high-severity findings back before you see the turn, (3) an agentic
commit/push reviewer that traces cross-file data flow (IDOR, auth bypass, SSRF). This
skill ships **no** upstream source: it detects install state, runs/prints the
verified install command, and maps the plugin onto the idea-to-deploy lifecycle. It
MUST NOT modify project files. This fixture regressionally fixes the
detect-before-claim rule, the no-vendoring contract, the accurate-mechanism rule, the
lifecycle fit, the gate-coexistence guarantee, and the complement-not-replace
relationship to `/security-audit`.

Named `security-guidance-setup`: a distinct, explicit handle for the integration,
kept separate from idea-to-deploy's own `/security-audit` skill (a different thing —
on-demand audit report vs. always-on shift-left review).

## Fixture status

`pending` — **deferred**, same bucket as `fixture-15-advisor`,
`fixture-21-mcp-docs`, `fixture-26-caveman`, `fixture-27-context-mode-setup`, and
`fixture-28-seo-setup` (read-only, detect/advise stdout flow). For now: manual
checklist below. The stub satisfies `check-skill-completeness.sh`.

## Scenario A: shift-left security need, not installed (happy path)

User pastes the prompt from `idea.md`: wants Claude to catch vulnerabilities as it
writes code.

### Critical contract: no files written

After the run, `output/` must contain no skill-authored files.
`/security-guidance-setup` only detects and advises.

### Expected output shape

- Recognizes a shift-left / realtime-security need → routes to
  /security-guidance-setup.
- Runs read-only detection (`claude plugin list | grep security-guidance`,
  `claude plugin details`); the plugin ships default-on, so **verifies** rather than
  assumes — if not active, says so explicitly (never claims it is active).
- Runs/prints the verified CLI install command
  (`claude plugin install security-guidance@claude-plugins-official`), the restart
  step, and the CC ≥ v2.1.144 / Python 3.8+ / API-path requirement for layers 2–3.
- After install + restart, instructs to verify with
  `claude plugin details security-guidance` (or a deliberate unsafe edit).

## Scenario B: already installed, map onto the phase

User: "security-guidance стоит, мы перед деплоем — что он даст?"

### Expected

- Runs `claude plugin details security-guidance` (hook list); reports it.
- Maps `/deploy` + `/harden` → layer 3 agentic commit/push review on the release
  commit (cross-file IDOR / auth-bypass / SSRF); layer 2 diff review each turn.
- Confirms idea-to-deploy gates still fire: the DoD/review **PreToolUse** gate still
  blocks a non-compliant commit *before* security-guidance's **PostToolUse**
  post-commit review runs. Reports pass/fail honestly.

## Scenario C: distinguish from /security-audit

User: "у нас же есть /security-audit, зачем ещё security-guidance?"

### Expected

- Explains the complement: `/security-audit` = on-demand deep audit report at a
  gate; security-guidance = always-on shift-left warnings + diff/commit review that
  fix issues in-session.
- Recommends running both. Presents neither as a replacement for the other, for
  `/review`, or for human review / SAST / pen-testing.

## Scenario D: vendoring / multi-agent boundary

User: "давай скопируем хуки security-guidance прямо к нам в репозиторий и врубим на
всех агентов".

### Expected

- Declines vendoring by default: first-party Anthropic code (no standard OSS license;
  Commercial Terms), free and default-on from the official marketplace, actively
  maintained — vendoring forks it and loses updates.
- Offers the supported path: marketplace install + this skill.
- For multi-agent: advises `ENABLE_STOP_REVIEW=0` (keeps commit/push review) per
  upstream guidance for shared-worktree setups, instead of copying hooks.

## Why pending (not active)

Phase 1 snapshot validation is file-shaped (`verify_snapshot.py` checks written
files against `expected-files.txt`). `/security-guidance-setup` writes nothing and
only affects a detect/advise stdout flow, so structural automation is deferred to the
Phase 2 stdout-snapshot scheme. This stub anchors the contract for manual regression
until then.
