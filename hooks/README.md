# Hooks — Skill Discovery Enforcement

These 27 hooks turn the methodology from "use it if you remember" into "you literally cannot forget". Without them, even Claude itself will skip the methodology under time pressure (verified the hard way during a 2026-04-07 production incident — see [the case study](#case-study) below).

## Defense-in-depth overview (v1.19.0)

Quality enforcement now spans **five layers**, from earliest-feedback to latest. Each layer catches something the previous ones missed:

| # | Layer | Where it runs | When | What it catches | Bypass? |
|---|---|---|---|---|---|
| 0 | `pre-flight-check.sh` *(v1.5.0)* | Local | UserPromptSubmit | Stale context, parallel session conflicts, missing memory | Soft context injection only |
| 1 | `check-skills.sh` | Local | UserPromptSubmit | Ambiguous prompts → wrong routing | Soft reminder only |
| 2 | `check-tool-skill.sh` *(v1.19.0: enforcement mode)* | Local | PreToolUse on Bash/Edit/Write | Ad-hoc tool calls when a skill fits | **Soft → Hard after 3 ignores** |
| 3 | `check-skill-completeness.sh` + `check-commit-completeness.sh` | Local | PreToolUse on Write/Edit/MultiEdit, PreToolUse on `git commit` | Incomplete skills (missing references/triggers/fixtures), incomplete commits | Only via `.methodology-self-extend-override` file |
| 4 | **[CI workflow](../docs/CI.md)** (new in v1.8.0) | GitHub Actions | Push to main, every PR | Everything in the meta-rubric that local hooks missed OR scenarios where local hooks were never installed | Only by admin override of branch protection (audit-logged) |

Layers 1–3 give fast local feedback. Layer 4 is the server-side last line of defense — catches contributors who never installed local hooks and future Claude sessions on unprepared machines. See [`docs/CI.md`](../docs/CI.md) for how to enable it as a required check on the main branch.

## What they do

| Hook | When it fires | What it does | Blocks? |
|---|---|---|---|
| `pre-flight-check.sh` *(v1.67.0)* | Every user prompt (UserPromptSubmit) | Loads `git log -10`, `git status`, recent commits, and the project memory index (`MEMORY.md`) into Claude's context before each turn. Detects stale parallel-session lockfiles (`.active-session.lock`) and warns if another Claude session has touched this project in the last 10 minutes. v1.68.0: warns when key `.itd/` contracts are template prose (`--filled` mirror) and when `IMPLEMENTATION_PLAN.md` has no `.itd-memory/GOAL.json` mirror (resume surface missing) — both advisory, rate-limited 4h. v1.67.0: also auto-consumes crash checkpoints — a `claude-checkpoint-*.json` for the SAME cwd whose `clean_exit` is still false (session died mid-work) is surfaced once (last tool calls + branch), then marked consumed. | No — soft context injection only |
| `check-skills.sh` | Every user prompt (UserPromptSubmit) | Scans the prompt for Russian/English trigger words. If matched, injects a system reminder telling Claude which skill should be invoked first. Silent if no trigger matches. | No — soft reminder only |
| `check-tool-skill.sh` *(v1.19.0: enforcement)* | Before every Bash/Edit/Write/NotebookEdit (PreToolUse) | Rate-limited skill reminder (60s). **Now tracks consecutive ignores.** After 3 ignored reminders, BLOCKS the next tool call until Claude either invokes a Skill or provides a `SKILL_BYPASS: <reason>` justification. Counter resets on Skill call or bypass. | **Yes — after 3 ignores** |
| `session-open-diagnostic.sh` *(v1.19.0)* | First user prompt of session (UserPromptSubmit) | Reads last `session_*.md`, next-session plan, LAUNCH_PLAN.md, BACKLOG.md, latest ROADMAP. Injects diagnostic context so Claude starts with full awareness of prior work and planned next steps. Fires once per session (sentinel file). | No — soft context injection only |
| `check-skill-completeness.sh` *(v1.5.1)* | **Before** Write/Edit/MultiEdit on `skills/*/SKILL.md` (PreToolUse) | Parses the pending tool input, extracts the skill name from the file path, verifies that `references/` exists and is non-empty (if the pending content mentions it), that `hooks/check-skills.sh` has a trigger phrase for the skill, and that a matching fixture exists in `tests/fixtures/`. | **Yes — exit 2 with `hookSpecificOutput.permissionDecision: "deny"`.** The Write never runs, the file never lands on disk. |
| `check-commit-completeness.sh` *(v1.5.1)* | Before every Bash command matching `git commit` (PreToolUse) | Parses the staged diff. If any `skills/<name>/SKILL.md` is staged, the hook requires matching references/hook/fixture to also be staged (or already present on disk). Written to be the last line of defense against the v1.4.0 "Potemkin release" pattern. | **Yes — exit 2 with `hookSpecificOutput.permissionDecision: "deny"`.** The commit never runs. |
| `check-review-before-commit.sh` *(v1.19.0, fixed v1.19.1)* | Before every Bash command matching `git commit` (PreToolUse) | Blocks the commit if more than 2 files are staged AND `/review` has not been invoked in the current session. `/review` signals via the marker file `/tmp/claude-review-done-{session_id}` which the skill itself writes at its final step. | **Yes — exit 2 with `hookSpecificOutput.permissionDecision: "deny"`.** The commit never runs. |
| `check-dod-before-commit.sh` *(v1.23.0)* | Before every Bash command matching `git commit` (PreToolUse) | Definition-of-Done gate. Inspects the staged diff and blocks the commit when a high-risk signal is present but the matching skill was not run this session: migration/schema → `/migrate`+`/test`; payments/auth/secrets in a file path → `/security-audit`; brand-new source file with no test staged → `/test`. Generalises the review gate to other risk signals. Escape: `SKILL_BYPASS:` in the commit message. | **Yes — exit 2 with `hookSpecificOutput.permissionDecision: "deny"`.** The commit never runs. |
| `record-agent-skill.sh` *(v1.25.0)* | **After** a `Task`/`Agent` subagent finishes (PostToolUse) | Counts review/test/security work delegated to a subagent toward the commit gates above (bug #2 follow-up). When the finished subagent is `code-reviewer`→`/review`, `test-generator`→`/test`, or `security-reviewer`→`/security-audit`, it writes that skill's completion sentinel on the agent's behalf — the agents are read-only (no Write/Bash) and the Skill tool emits no hook events, so the gates would otherwise never see the work. | No — pure side-effect, always exits 0 (a PostToolUse block is non-blocking anyway; see v1.5.1 note). |
| `wip-gate.sh` *(v1.41.0)* | Before Write/Edit/MultiEdit (PreToolUse) | WIP=1 activation gate. When `.itd-memory/STATE.json` has `currentUnit.status` ∈ `verifying`/`recovery_required` AND the edited path falls outside the `Allowed Change Areas` of `.itd/SCOPE_LOCK.md`, injects a soft hint: finish the current unit's verification (or explicitly reclassify — update SCOPE_LOCK + currentUnit) before starting new work. Computational detect, soft by design (map §8.3): "is this really a new task?" is semantic. Silent when no `.itd-memory/` or no real scope declared. Rate-limited (`ITD_WIP_GATE_RATE_MIN`, default 30 min); disable with `ITD_WIP_GATE=0`. | No — soft additionalContext only |
| `handoff-readiness.sh` *(v1.40.0)* | End of each assistant turn (Stop) | Handoff-readiness detector — the "end every session handoff-ready" half of the Anthropic long-running-agents research (session start is covered by pre-flight + session-open-diagnostic + crash-recovery). When the turn ends with a **dirty git tree** AND **no fresh `session_*.md`** in the project memory dir (fresher than `ITD_HANDOFF_FRESH_MIN`, default 120 min), emits a soft `systemMessage` reminding the user to run `/session-save` or `/handoff` and leave a clean checkpoint. Rate-limited (`ITD_HANDOFF_RATE_MIN`, default 45 min per session); disable with `ITD_HANDOFF_READINESS=0`. Purely computational detect, semantic decision ("am I done?") stays with the human — hence hint, not deny (map §8.3). | No — soft systemMessage only |
| `narration-final.sh` *(v1.49.0)* | When a subagent finishes (SubagentStop) | Mechanical narration-final detector — retro signal ×5 in one v1.48.0 review run: a reviewer's FINAL message ends on process narration ("Now check…", «Далее проверю…») instead of the verdict, even after the named anti-pattern entered the agent contract (v1.47.0) — prompt-level contracts don't hold. If the subagent's final paragraph starts with a narration opener AND the whole message carries no verdict marker (PASSED/BLOCKED/FAILED/FINAL STATUS/Вердикт/Итог), blocks the subagent's stop and feeds a "finish with the deliverable in one message" instruction back to it. A verdict-final (including a valid «Не успел проверить» tail) is never blocked. At most `ITD_NARRATION_MAX_PINGS` (default 2) blocks per subagent run; `stop_hook_active` loop guard; fail-open on any parse/IO error; disable with `ITD_NARRATION_FINAL=0`. | **Yes — blocks the subagent's stop (≤2×); never touches the main session** |
| `verdict-contract.sh` *(v1.51.0)* | When a subagent finishes (SubagentStop) | Vendor-neutral verdict-contract validator (release C, part c). A review subagent must emit its verdict as a machine-readable fenced ```json block (`{verdict, findings[]}`) so downstream consumers parse a stable contract, not prose — the native `ReportFindings` tool is only an optional transport (harness best-effort invariant). If the final message declares a review verdict in prose (`FINAL STATUS:`, `Вердикт:`/`Verdict:`, or the compound token `PASSED_WITH_WARNINGS`) but carries no valid JSON verdict block, blocks the subagent's stop and asks it to append the block. Deliberately narrow — bare "PASSED"/"BLOCKED" don't trip it, so test-generator/researcher finals pass through. Complementary to `narration-final.sh` on the same event (one catches a missing verdict, the other a verdict missing its block); no loop. At most `ITD_VERDICT_MAX_PINGS` (default 2) blocks per subagent run; `stop_hook_active` loop guard; fail-open on any parse/IO error; disable with `ITD_VERDICT_CONTRACT=0`. | **Yes — blocks the subagent's stop (≤2×); never touches the main session** |
| `cross-review-precommit.sh` *(v1.34.0)* | Before every Bash command matching `git commit` (PreToolUse) | **Opt-in, fail-open** cross-vendor second opinion — the deliberate opposite of the DoD gate. When opted in (env `CROSS_REVIEW_EGRESS_OK=1` per-machine, or a `.cross-review-egress-ok` marker file at the repo root — detected by presence, so it can be local/untracked and never enter a commit/PR; committing it is only for a team-wide opt-in) AND the staged diff touches a sensitive path (migration/money/auth), it scrubs the diff and dispatches a **detached background** review (codex → gemini → honest "unavailable" note), writing findings to a `claude-cross-review-*.md` notes file. Auto-disables in Agent Teams / linked-worktree mode; never egresses if a secret survives scrubbing; never writes the `/review` sentinel. Disable: `ITD_CROSS_REVIEW=0`. | **No — never blocks. Additive second opinion on top of `/review`, which remains the mandatory floor.** |

### Safety guardrails (v1.17.0, optional)

| Hook | When it fires | What it does | Blocks? |
|---|---|---|---|
| `careful.sh` | Before Bash (PreToolUse) | Detects destructive commands (rm -rf, DROP TABLE, git push --force, git reset --hard, chmod 777, pipe-to-bash) and injects a warning asking Claude to confirm with the user. Activated via `CAREFUL_MODE=1` env var or a state file. | No — soft warning only |
| `freeze.sh` | Before Write/Edit/MultiEdit/NotebookEdit (PreToolUse) | Restricts file modifications to a specific directory scope. Any edit outside the frozen scope triggers a warning. **Registered always-on since v1.42.0** (no-op until a scope state file exists). Activated by the freeze snippets in `/bugfix`, `/refactor`, `/perf` (they write `claude-freeze-<session>.state` to both temp dirs), or manually: `echo "/path/to/scope" > "$(python3 -c 'import tempfile;print(tempfile.gettempdir())')/claude-freeze-${CLAUDE_SESSION_ID:-default}.state"`. Deactivate by deleting the state file. There is no `/freeze` skill — the state file IS the interface. | No — soft warning only |
| `pii-egress-guard.sh` *(v1.30.0)* | Before Bash egress commands & WebFetch (PreToolUse, matcher `Bash\|WebFetch`) | PII/secret deny-before-egress (omnigent egress-policy port). Scans outbound content (curl/wget/scp/ssh/rsync/`git push`, WebFetch) just before it leaves the box: high-confidence secrets (private keys, AWS/GitHub/Slack/Google/Stripe/Anthropic/OpenAI keys, Bearer tokens) → **DENY**; weaker PII signals (emails, card-shaped numbers, `password=`/`api_key=` assignments) → **ASK**. Scoped to egress only (a secret written to a local file is not flagged); complements `careful.sh` (destructive commands). **Wired by default in the `/adopt` settings template**, not merely opt-in. Disable: `ITD_PII_GUARD=0`. | **Yes — DENY on live secrets (exit 2); ASK on PII** |
| `context-budget.sh` *(v1.21)* | Before Bash (PreToolUse) | Detects commands likely to dump a large unbounded output (raw HTTP/API bodies, `cat` of big files, wide `grep`/`find`/`rg` with no cap) and injects a reminder to bound/summarize or write to a file + reference the path. See `skills/_shared/helpers.md` §7. Opt-in via settings.json. | No — soft reminder only |
| `execution-trace.sh` *(v1.21)* | Before any tool (PreToolUse, register with matcher `*`) | Appends one JSON line per tool call (`{ts, tool, target}`) to `.claude/traces/session-<id>.jsonl` — a live, replayable record of which tool ran against what, for debugging the methodology and user oversight. Pure side-effect telemetry: injects **nothing** into context (zero context-budget cost). `.claude/` is gitignored. Opt-in via settings.json. | No — never blocks |

### Budget, observability & session-management hooks (v1.18–v1.30)

Ported *outcomes* of GSD v2 and the omnigent policies — a plugin hook cannot pause
the loop, so a "limit" is realized as a high-priority ASK/reminder, never a hard
stop (see ADR-001). `cost-tracker.sh` and `risk-score.sh` are **wired by default in
the `/adopt` settings template** (`PostToolUse`, matcher `*`); the other three are
opt-in per project.

| Hook | When it fires | What it does | Blocks? |
|---|---|---|---|
| `cost-tracker.sh` *(v1.18.0; budget gate v1.31.0)* | After every tool (PostToolUse, matcher `*`) | Per-session token/USD ledger with a two-stage budget gate: SOFT (≥80% of ceiling) warns via additionalContext (suggests `/session-save`); HARD (≥100%) escalates to an ASK to STOP and get user approval, re-firing every +500k tokens so a runaway loop keeps surfacing. Set `ITD_COST_CEILING_TOKENS` (+ `ITD_COST_PER_1M_USD`) to make the ceiling meaningful. **Wired by default in the `/adopt` template.** | No — soft reminder / high-priority ASK, never a hard stop |
| `risk-score.sh` *(v1.30.0)* | After every tool (PostToolUse, matcher `*`) | Cumulative "safety budget" for death-by-a-thousand-edits that binary gates miss. Every mutating call adds risk points (×4 on security/data-sensitive paths); when the running score crosses `ITD_RISK_THRESHOLD` (default 12) it injects an escalation to pay the risk down with `/review` (or `/security-audit` when the accrued risk is mostly security). Running either skill resets the budget. **Wired by default in the `/adopt` template.** | No — soft escalation via additionalContext |
| `crash-recovery.sh` *(v1.69.0)* | After significant tools (PostToolUse), end of turn (Stop) **and** subagent finish (SubagentStop) | Auto-saves a lightweight checkpoint (last N tool calls, cwd, branch + last commit, timestamp) to `claude-checkpoint-<session>.json` on every significant call with `clean_exit: false`; the Stop/SubagentStop registrations flip `clean_exit: true` when a turn or a background subagent ends normally (v1.69.0 — without the SubagentStop leg, subagent checkpoints surfaced as phantom crash banners in the main session). A checkpoint left with `clean_exit: false` = the session died mid-work — `pre-flight-check.sh` surfaces it to the next session in the same project and marks it consumed (v1.67.0 closes the "written but not consumed" gap). | No — pure side-effect telemetry |
| `context-aware.sh` *(v1.18.0)* | Every user prompt (UserPromptSubmit) | Detects long sessions (many tool calls / large context) and recommends fresh-context strategies (`/session-save` + fresh start, tiered subagent dispatch) to fight context rot. Opt-in via settings.json. | No — soft reminder only |
| `stuck-detection.sh` *(v1.18.0)* | After every tool (PostToolUse) | Sliding-window no-progress detector — same file edited 3+×, or same Bash/Grep retried 3+× in a row → injects diagnostic advice to try a different approach. Opt-in via settings.json. | No — soft reminder only |

**Activation:**
- **`careful.sh`** — **always active** inside methodology repos (auto-detected via `.claude-plugin/plugin.json`). Outside methodology repos: opt-in via `CAREFUL_MODE=1` env var or state file.
- **`freeze.sh`** — **automatic** when skills like `/bugfix`, `/refactor`, `/perf` start work (they dual-write the scope state file to `/tmp` AND the platform temp dir, v1.42.0). Manual activation/deactivation = create/delete the state file (see the table row above); there is no `/freeze` command.

All 27 hooks are written in Python 3 (works out of the box on macOS/Linux/WSL), depend only on the standard library, and exit silently in degenerate cases (bad JSON, empty payload, not in the methodology repo) — they never break your session on unrelated work.

**Enforcement hooks are scoped to methodology-repo work only.** The two v1.5.0 hooks walk up from `cwd` looking for `.claude-plugin/plugin.json`; if not found, they return 0 immediately. You can safely install them globally and still use Claude Code on ordinary projects — they fire only when you're inside a methodology (or methodology-like) repository.

## Recommended setup

```bash
# 1. Copy hooks to your user-level Claude config
mkdir -p ~/.claude/hooks
cp hooks/check-skills.sh ~/.claude/hooks/
cp hooks/check-tool-skill.sh ~/.claude/hooks/
cp hooks/check-skill-completeness.sh ~/.claude/hooks/   # v1.5.0 enforcement
cp hooks/check-commit-completeness.sh ~/.claude/hooks/  # v1.5.0 enforcement
cp hooks/check-review-before-commit.sh ~/.claude/hooks/ # v1.19.0 — blocks >2-file commits without /review
cp hooks/check-dod-before-commit.sh ~/.claude/hooks/    # v1.23.0 — Definition-of-Done gate (migrations/payments/new code)
cp hooks/record-agent-skill.sh ~/.claude/hooks/         # v1.25.0 — counts subagent review/test/security toward the gates
cp hooks/careful.sh ~/.claude/hooks/                     # v1.17.0 safety guardrail
cp hooks/freeze.sh ~/.claude/hooks/                      # v1.17.0 scope guardrail
cp hooks/session-open-diagnostic.sh ~/.claude/hooks/     # v1.19.0 session diagnostic
chmod +x ~/.claude/hooks/*.sh

# 2. Register them in ~/.claude/settings.json
```

Add this `hooks` block to your `~/.claude/settings.json` (merge with existing settings, do not replace):

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/session-open-diagnostic.sh",
            "timeout": 5
          },
          {
            "type": "command",
            "command": "~/.claude/hooks/check-skills.sh",
            "timeout": 5
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash|Edit|Write|NotebookEdit",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/check-tool-skill.sh",
            "timeout": 5
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/check-commit-completeness.sh",
            "timeout": 5
          },
          {
            "type": "command",
            "command": "~/.claude/hooks/check-review-before-commit.sh",
            "timeout": 5
          },
          {
            "type": "command",
            "command": "~/.claude/hooks/check-dod-before-commit.sh",
            "timeout": 5
          }
        ]
      },
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/check-skill-completeness.sh",
            "timeout": 5
          }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/careful.sh",
            "timeout": 5
          }
        ]
      },
      {
        "matcher": "Edit|Write|NotebookEdit",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/freeze.sh",
            "timeout": 5
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Task|Agent",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/record-agent-skill.sh",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

> **v1.5.1 note:** `check-skill-completeness.sh` moved from PostToolUse to PreToolUse in v1.5.1 because PostToolUse exit 2 is non-blocking per [Anthropic's hooks spec](https://code.claude.com/docs/en/hooks.md) — the tool already ran by that point, so the file would land on disk and the "block" would only be a message. PreToolUse exit 2 actually prevents the Write from executing. Both v1.5.1 hooks emit the correct `hookSpecificOutput.permissionDecision` field (v1.5.0 used a top-level `decision` field that was silently ignored by the schema validator).

**Important — enforcement vs. reminder hooks:**

- `check-skills.sh` and `check-tool-skill.sh` are **soft reminders** (no blocking). Safe to run on all projects.
- `check-skill-completeness.sh` and `check-commit-completeness.sh` are **hard blocks** (exit 2, decision: deny/block). They only fire inside methodology repos (detected via `.claude-plugin/plugin.json`). Outside the methodology repo they return 0 immediately.

If you never work on methodology repos, the two enforcement hooks (`check-skill-completeness.sh` and `check-commit-completeness.sh`) are harmless but unused — you can skip registering them. The other three (`pre-flight-check.sh`, `check-skills.sh`, `check-tool-skill.sh`) are useful on every project regardless of whether it's a methodology repo.

After saving, the hooks fire on the very next prompt — no restart needed (Claude Code's settings watcher picks them up live).

## Verifying

Pipe-test the prompt hook:

```bash
echo '{"prompt":"у меня баг в auth"}' | ~/.claude/hooks/check-skills.sh
```

You should see JSON output with `additionalContext` mentioning `/bugfix` and `security-guidance`. If you see nothing, the hook is silent — try a clearer trigger word.

Pipe-test the tool hook:

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"ls"}}' | ~/.claude/hooks/check-tool-skill.sh
```

You should see JSON with a SKILL CHECK reminder about Bash.

Pipe-test the completeness hook (v1.5.1) — must be run inside a methodology repo to see the block:

```bash
cd /path/to/idea-to-deploy
echo '{"tool_name":"Write","tool_input":{"file_path":"skills/fake-skill/SKILL.md","content":"body references/foo-checklist.md"}}' \
  | ~/.claude/hooks/check-skill-completeness.sh
```

You should see JSON with `hookSpecificOutput.permissionDecision: "deny"` and a list of missing artifacts (references, trigger, fixture). Exit code 2.

Pipe-test the commit-gate hook (v1.5.1) — must be inside a methodology repo with a staged SKILL.md:

```bash
cd /path/to/idea-to-deploy
# Stage a fake SKILL.md without its supporting files first, then:
echo '{"tool_name":"Bash","tool_input":{"command":"git commit -m test"}}' \
  | ~/.claude/hooks/check-commit-completeness.sh
```

You should see JSON with `hookSpecificOutput.permissionDecision: "deny"` explaining which skill is incomplete. Exit code 2.

## Customizing triggers

Open `check-skills.sh` and edit the `TRIGGERS` list (line ~25). Each entry is a tuple `(regex_pattern, hint_text)`. The pattern matches against the lowercased prompt; add Russian or English phrases as needed. The script handles Unicode lowercasing correctly (uses Python's `str.lower()`, not `tr`).

Common pitfalls to avoid:
- Don't use `tr '[:upper:]' '[:lower:]'` for Russian — it doesn't lowercase Cyrillic without a UTF-8 locale.
- Don't make patterns too greedy. `*` matches everything; prefer word boundaries (`\b`).
- Avoid duplicate hint text — the dedup is by exact string match.

## Case study

In a 2026-04-07 hotfix session, Claude (Opus 4.6) spent ~2 hours doing direct SSH/sed/curl work to fix a 3-week-old production auth outage. Throughout that work, `/bugfix` was a perfect fit and was never invoked. The user noticed and asked: "почему ты не используешь методологию?". The honest answer: nothing was forcing it.

These hooks are the answer. After installation, the same prompt — "у меня баг в auth" — would inject a SKILL HINT about `/bugfix` and `security-guidance` into Claude's context **before** Claude's first response. It then becomes physically impossible to skip the methodology without acknowledging it first.

## Limitations

- The hooks are user-level (`~/.claude/`), not project-level. If you want them only for specific projects, move them to `.claude/settings.json` in the project root and gitignore them.
- The PreToolUse hook fires on every Bash/Edit/Write — that's a lot of noise on long sessions. If it bothers you, change the matcher to match only specific tools or specific commands (e.g., `Bash(git:*)`).
- Hooks slow each prompt by ~50ms (Python startup). Acceptable for interactive use; might matter for scripted/CI use.
- Only Russian + English triggers are included by default. Add your language by editing `check-skills.sh`.

## Completion Gate (v1.51.0)

Anti-premature-completion subsystem. Judges task completion from an objective
runtime-signal ledger, not agent confidence. Vendor-neutral contract (JSON in
`.claude/completion/` + the "Определение завершения" section in the global
CLAUDE.md); the hooks only transport it and degrade to advisory when no ledger
exists (best-effort invariant).

| File | Event | Role |
|---|---|---|
| `completion_lib.py` | — (library) | signal classification into layers L1 static / L2 tests / L3 e2e, three-layer verdict with blocked-transition, `red_mark`+`FIX_HINTS` |
| `completion-signals.sh` | PostToolUse · Bash | appends each Bash call to `.claude/completion/signals.jsonl`; returns a WHY+FIX teacher mark on a failed test/build. Soft. |
| `completion-gate.sh` | PreToolUse · Bash | on a `git commit` touching source: **deny** when a completion layer is FAIL or tests exist-but-unrun; degrade to advisory when no signals; pass when green. **Hard gate.** |
| `completion-stop.sh` | Stop | reminder when the turn ends with a dirty code tree and a non-green verdict; never blocks. Soft. |

**Ladder (cheap→expensive, blocked transition):** L1 syntax/static → L2 runtime
tests (green or not done) → L3 e2e/smoke. No layer advances until the previous is
green.

**Projects without unit tests** declare an L2 equivalent in
`.claude/completion/config.json` (`l2_evidence_patterns`) — a behaviour-proving
command (e.g. a register-diff / repost script) counts as `test_run`.

**Toggles:** `ITD_COMPLETION_GATE=0` (veto), `ITD_COMPLETION_STOP=0` (Stop),
`ITD_COMPLETION_SIGNALS=0` (collection). Conscious bypass of one commit:
`COMPLETION_BYPASS: <reason>` in the Bash `description` field.

Behavioural proof: `tests/verify_completion_gate.py` drives the gate to `deny`.

## License

Same as the parent project (MIT).
