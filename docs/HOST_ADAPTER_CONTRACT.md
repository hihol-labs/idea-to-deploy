# Host adapter contract

Idea to Deploy has one methodology core and multiple runtime adapters. A host
adapter may translate transport details; it must not fork contracts, completion
criteria, risk policy, skill semantics, or persistent project state.

## Canonical core

- `skills/` contains workflows and shared operating rules.
- `docs/templates/itd/` contains project and verification contracts.
- `docs/templates/itd-memory/` defines persistent execution state.
- `hooks/` contains deterministic policy and telemetry checks.
- `tests/` defines observable behavior.

The machine-readable registry is `docs/host-adapters.json`.

`.itd-memory/` at the project root is the only canonical continuity location:
STATE, GOAL, events, progress, session checkpoints, MEMORY index, and the
active-session lock all converge there. A host may maintain a private mirror
for compatibility, but the mirror cannot be required, cannot override a local
file, and cannot make missing local state look healthy.

## Adapter responsibilities

An adapter owns only:

- plugin packaging and discovery;
- the project guidance entry file;
- hook registration, event and tool-name normalization;
- host-specific installation, trust, and optional writable-data mirrors;
- translation from a host's subagent mechanism to the roles in `agents/`.

An adapter must preserve hook exit status and deny decisions. When a host cannot
represent a capability, the adapter must declare the degradation and provide a
fallback based on shared contracts or structured output. Silent false parity is
not allowed.

External-write approval is computed by the shared
`skills/_shared/itd_external_write_gate.py`, not by host prompts. Every adapter
must route all PreToolUse traffic through `pii-egress-guard.sh`, preserve its
native `ask`/`deny` decision, and supply `session_id`, exact tool name, and
complete structured input. The host's approval UI is the only trusted grant:
the methodology stores no local approval ledger, and a caller-controlled tool
flag or file can never mint approval.
The shared hash binds canonical tool name + exact targets + full payload;
attachments remain inside that payload. Read-only actions are silent, while a
missing session/target or changed action fails closed.
`exactAlreadyAuthorizedActionRequiresRepeatApproval: false` means the host
executes the same pending invocation after the user accepts its native prompt;
the adapter must not re-enter the hook and ask twice for that invocation. A
later duplicate tool call is a new external action, not reusable approval.

Model/effort routing crosses the same PreToolUse adapter boundary through
`model-policy.sh` for `Task|Agent`. Adapters must preserve both its
`additionalContext` model hint and its native `ask` decision for an unsafe
explicit low-effort override. The automatic low route requires an active
low/medium-risk `working_deadline` unit and a description prefixed
`[itd:mechanical]`; protected roles and unknown/high risk are never silent.
Model/effort routing cannot remove any verification contour.

## Native continuation for bounded goals

The shared contract for autonomous delivery is the optional
`GOAL.json.runPolicy` plus the oracle seal, attempt ledger and typed stop written
by `skills/goal/scripts/itd_goal_verify.py`. A host-native goal or automation may
transport continuation, but it must not become the source of truth.

On each continuation the adapter must:

1. read the existing ledger; never recreate or re-decompose it;
2. resume only `currentUnitId`, otherwise the first pending unit (WIP=1);
3. preserve the approved attempt, wall-clock and token ceilings;
4. supply the attempt approach and any required fresh-checker evidence to the
   harness verifier;
5. stop on verifier exit `3`, `blocked`, `budget_exhausted`, or human input;
6. leave push, merge, deploy and other irreversible/external writes behind the
   ordinary human gate.

Token use is observed by the host/cost-tracker transport. When its ceiling is
reached, the adapter records it through `--budget-exhausted --budget-kind
tokens`; it does not merely end a transcript and lose the stop reason. Manual
`/goal` resume is the mandatory fallback when the native continuation surface is
absent. Background periodic automations remain read-only reporters; this
continuation path is only for a user-approved, sealed bounded goal.

## Parity rule

A change to shared methodology behavior is complete only when:

1. the shared test passes;
2. both adapter manifests remain valid;
3. the adapter registry still maps the affected capability;
4. any intentionally unavailable transport feature is documented.

Claude Code and Codex may expose different tools, but a project must converge
to the same `.itd/` contracts, `.itd-memory/` state, review verdict schema, and
verification evidence.
