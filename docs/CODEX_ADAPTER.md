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
classifies the 11 canonical hard gates as high risk and keeps low-risk probes
allow/advisory. If the Codex dispatcher cannot parse or execute a registered
high-risk gate, it emits the gate's native `deny`/`block` decision instead of
silently downgrading the failure; unregistered telemetry hooks remain
fail-open. Both bundled and repository-local Codex hook configurations include
`apply_patch` in the mutation matchers, so normalization is reached in real
tool traffic rather than only in adapter tests.

## Enable and trust

Install or enable the repository as a Codex plugin through the normal Codex
plugin UI. On first use, inspect and trust its command hooks with `/hooks`.

Codex 0.166+ binds that trust to the hook declaration and to a fingerprint of
the whole plugin contents (`trusted_content_hash`). Every plugin update - each
Idea to Deploy release - changes the fingerprint, so Codex marks all entries
"modified since last trusted" and skips them silently until the user trusts
them again: start `codex` and choose "Trust all and continue" (or `/hooks`,
then `t`). On Windows start `codex --no-daemon`: an older shared app-server
daemon (0.157.1 on the owner's host) shows the hooks as trusted and writes the
trust without the content fingerprint, which 0.166 then ignores.
`python3 scripts/itd_codex_hook_trust.py` asks Codex itself (`codex
app-server`, `hooks/list`) and names every entry whose trustStatus is not
"trusted"; without a Codex executable it reports the content trust as
unverified, never as OK.

On Windows Codex runs a hook as `<session shell> -Command <commandWindows>`.
PowerShell turns a native exit 2 into 1, and Codex blocks a PreToolUse call
only on exit 2 (or exit 0 with a JSON deny) - any other exit is a non-blocking
hook failure and the call runs. Every `commandWindows` therefore ends with
`; if ($LASTEXITCODE -is [int]) { exit $LASTEXITCODE } else { exit 1 }`, so a
dispatcher deny stays exit 2 in both PowerShell 7 and Windows PowerShell 5.1,
and a `py` that cannot start is a hook failure (exit 1) instead of a silent
`exit $null` = 0 (`tests/verify_codex_ask_gates.py` [32], [33]).

Codex 0.166 also re-checks that content fingerprint before every hook run and
counts it inside the hook's `timeout`. On the owner's Windows host 11 parallel
PreToolUse hooks took 4.2-5.07 s each, so a 5 s timeout made the gate a race:
a timed-out hook is a non-blocking failure and the call runs. Every Codex hook
registration therefore allows at least 30 s (`tests/verify_host_adapters.py`);
the Claude Code registrations in `scripts/sync-to-active.sh` are unchanged.
Plugin hooks are intentionally bundled; `/adopt` does not duplicate them into
the target repository when the plugin is active.

For a repository-local checkout instead of an installed plugin, copy the
template from `skills/adopt/references/codex-project-hooks.json` to
`.codex/hooks.json`, replace `{{ITD_ROOT}}` with the absolute methodology
checkout path, then review it with `/hooks`.

Host-global `itd` and Git `pre-push` are separate from bundled Codex lifecycle
hooks. Install them with `scripts/itd_install_cli.py --apply` and
`scripts/itd_install_git_hooks.py --apply` on each native host. Both commands
materialize the same minimal content-addressed runtime under the host data
directory and write wrappers that name only that snapshot; they never execute
the mutable development checkout. Runtime entry points use Python `-I -B`, so
ambient import paths and bytecode writes cannot mutate the snapshot.
Direct execution of the CLI, pre-push, machine oracle and Verification Loop
also sets `sys.dont_write_bytecode` before runtime dependency
imports, so omitting `-B` at those entrypoints cannot add dependency caches.
This does not protect an arbitrary external importing loader before an
entrypoint's first instruction has executed, or a standalone direct call to
other runtime modules such as the reviewer producer. Reinstall
with `--replace-existing` only after reviewing the existing wrapper; a
tampered/incomplete content-addressed runtime always fails closed.
The closed inventory includes transitive path-loaded gate dependencies (the
exact-context review-cache module, review skill and both rubrics), and the
runtime regression must compute candidate context through that loader on both
WSL and native Windows.

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

The outbound hard gate is registered for PreToolUse with matcher `.*`.
Connector and shell payloads reach the host-neutral exact-approval engine
through `codex-dispatch.py`; missing exact provenance/targets and live secrets
return `deny`. Codex PreToolUse does not support `permissionDecision: "ask"`
and runs the call (fail open), so the adapter never forwards an `ask`
(CODEX-ASK-GATES-1): it returns `deny` (exit 2) with the complete preview and
the line `ITD-APPROVE <hash>`, where the hash binds the asking hook, the tool,
its full input and the cwd (ASCII-escaped canonical JSON). The user answers
with exactly that line in the chat - `ITD-APPROVE`, one space, 64 lowercase
hex, nothing else on the line (an LF or CRLF line end is fine); the UserPromptSubmit transport records a one-time approval for the
session under `~/.claude/itd-codex-approvals/` (TTL 30 minutes), and the same
exact call passes once; the hooks' advisory `additionalContext` still reaches
the model. A changed target, body, attachment, cwd or session gets a new hash
(a missing field and an empty one differ); a replay is denied again; a `deny`
is never approvable.

The boundary is weaker than Claude's native prompt and is stated exactly:
- a record counts only from a real directory and file (no symlink or junction)
  owned by the OS user - on POSIX also not writable by group/other (the
  directories are created 0700); on Windows the owner SID must be the user's
  own SID (TokenUser); a record owned by any other SID - SYSTEM, TrustedInstaller
  or a group such as Administrators - is refused, and the DACL inherited from
  the profile is not inspected; a malformed record is spent, so the call can be approved
  again;
- the dispatcher records approvals only from a UserPromptSubmit payload, and
  denies any tool call whose input names the channel - a shell command, a file
  path or the content a file tool writes that mentions `ITD-APPROVE`, the
  store, or a hand-made UserPromptSubmit for this dispatcher (so Codex cannot
  edit text that mentions `ITD-APPROVE`, such as these docs);
- that guard is a guardrail, not a boundary: a process with the user's rights
  that bypasses the hook transport (an obfuscated command, another program)
  can still write a record. Approval is bound to one exact call.

The Codex hook bundle also routes `Task|Agent` through `model-policy.sh` via
`codex-dispatch.py`. Codex must preserve the advisory context for a weaker model
override; the ASK returned for a low-effort override outside bounded
low/medium mechanical `working_deadline` work becomes the same `deny` with an
`ITD-APPROVE <hash>` answer. The adapter does not infer task
semantics or remove evidence contours; the shared ledger and role frontmatter
remain authoritative.

## Bounded goal continuation

For an explicitly approved `/goal` with `runPolicy.mode:
bounded_autonomous`, Codex's native goal/automation surface may re-enter the
task. The durable controller is still `.itd-memory/GOAL.json`: seal it first,
resume one WIP unit, run the ordinary `/task` pipeline, and finish through
`itd_goal_verify.py` with an approach and fresh-checker evidence when required.
That evidence is the adjudication path produced by
`skills/_shared/itd_verification_loop.py`, not a prose reviewer summary. Codex
subagents write their exact prompt/report under `.itd-memory/verification-loop/`;
the parent orchestrator records the real SubagentStart/Stop session and model
metadata. Missing high/unknown model separation remains `UNVERIFIED`.

For PR preparation, `/review` and `/cross-review` use the same
`itd_free_reviewer_producer.py` route: `Sol -> Terra` and `Terra -> Sol`. Codex
also routes approved `gpt-6.1-sol` and `gpt-6-astra` makers to `gpt-5.6-terra`,
preserving their actual model identities. For a Claude maker the default
reviewer is `gpt-6.1-sol` with the `gpt-5.6-terra` standby (REVIEWER-61SOL-1). Codex
starts exactly one fresh opposite OpenAI model/session. Anthropic, GitHub
Copilot and other adapters are not automatic fallbacks. There is no caller bypass and no provider API key in
the default route. WSL uses WSL-native transports/auth; native Windows uses
Windows-native transports/auth. Cross-host credential execution is forbidden.

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
`python3 tests/verify_all_hard_gate_host_parity.py` for the behavioural 11/11
Claude-direct versus Codex-dispatch decision proof. Run
`python3 tests/verify_host_neutral_memory.py` and
`python3 tests/verify_fresh_session_resume.py` for local-first continuity and
cold-session reconstruction proof.

## Conditional Graph Lite transport

`hooks/graph-route.sh` calls the vendor-neutral `itd_graph_policy.py hook` with the standard lifecycle stdin. Its UserPromptSubmit additionalContext carries only an owner-authorized read-only serial plan; native Codex subagents execute it in layers. The hook itself never calls Claude CLI or a model. Shared contracts/schemas/receipts stay vendor-neutral; local native log paths and WSL monotonic/boot collection live only in the measurement adapter scripts/graph_v2_study.py and protocol. Codex-only efficacy is not a Claude/provider comparison.
