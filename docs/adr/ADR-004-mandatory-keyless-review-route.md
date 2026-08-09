# ADR-004: one mandatory keyless independent pre-PR review route

**Date:** 2026-08-03
**Status:** Accepted, mandatory route amended by ADR-006
**Supersedes:** ADR-002 and ADR-003 for `/review`, `/cross-review`, and default
pre-PR routing. ADR-003 remains applicable only to separately configured paid
operator infrastructure.

## Context

The methodology exposed two visibly similar review paths: a local reviewer and
an optional managed API checker. In another project session this caused the
agent to request `OPENAI_API_KEY` even though the intended independent review
was a different model with no development context and user/subscription login.
The duplicate paths made unavailable paid infrastructure look like a missing
mandatory prerequisite.

## Decision

Idea to Deploy has one mandatory independent pre-PR producer:
`skills/_shared/itd_free_reviewer_producer.py`.

Its route is fixed: `OpenAI -> Anthropic -> GitHub Copilot`.

- OpenAI uses a fresh subscription session and a model different from the
  maker. Sol and Terra automatically alternate when necessary.
- Anthropic uses an isolated Claude subscription session.
- GitHub Copilot uses the official GitHub user session. The producer binds one
  installed native `copilot` executable, creates an empty temporary
  project/`COPILOT_HOME`, passes the packet only on stdin, forces free `auto`
  mode, disables instructions/MCP/remote/tools/updates/logging, and requires
  at most one included premium request per call plus zero file changes from
  runtime telemetry; it never enables paid overage.
- Only typed `UNAVAILABLE` advances to the next provider.
- `BLOCKED`, `UNVERIFIED`, invalid provenance, tool use, and same model/session
  are terminal.
- A structurally valid negative report persists its exact prompt, findings,
  reviewer, and attempt prefix for repair but cannot mint phase one.
- Exhaustion is `UNAVAILABLE`; there is no caller bypass.
- The signed phase-one receipt contains the exact ordered attempt prefix. Every
  predecessor must be `UNAVAILABLE`, and its terminal `PASSED` provider must
  equal the signed reviewer; the broker revalidates this before authorization.
  This incompatible closed-schema correction is phase-one receipt version 2;
  legacy version-1 receipts fail closed and must be regenerated.
- The default producer removes provider API keys and never dispatches a paid
  API endpoint.
- Signed reviewer model identity comes from pinned runtime telemetry, never
  the caller's argument: one temporary Codex rollout, Claude `modelUsage`, or
  the Copilot JSONL stream. Missing telemetry advances only as
  `UNAVAILABLE`;
  ambiguity/mismatch is terminal `UNVERIFIED`.
- Independence uses canonical provider/model families at live routing,
  phase-one minting, phase-one verification, and broker enrollment
  authorization. Anthropic short aliases and their `claude-<family>-*`
  telemetry are the same model identity; re-signing the raw strings cannot
  create independence, and an unlisted family remains unauthorized.
- Initial local pre-PR review uses a repository-bound target with null PR/head
  coordinates, because neither exists yet; candidate parent/tree/diff and the
  later unchanged single-parent commit bridge remain exact. Existing PR and
  App flows require a positive PR number plus exact head SHA.
- Mandatory-route consumption independently reconstructs the signed
  base-to-candidate binary diff after proving base-to-parent ancestry and
  compares both digest and byte count; a substituted base fails closed.
- Required `.jsonl.gz` evidence uses the same bounded transparent-review
  contract as the broker. Raw Git blob SHA/size/mode and the complete raw diff
  stay bound while the isolated model receives a separately hashed canonical
  diff of strictly validated logical JSONL. No other binary format is allowed,
  and the producer refuses to sign a caller-mutated prompt.
- GitHub Copilot receives the complete bounded packet through stdin. A
  transport mutation proves exact prompt bytes; malformed JSONL, absent or
  unauthorized runtime model/session telemetry, more than one premium request,
  workspace changes, or any attempted tool event is terminal `UNVERIFIED`.
- Codex's private rollout is bounded independently from the packet because it
  contains that packet plus runtime events. Its 16 MiB ephemeral cap does not
  enlarge the 2 MB model input or 1 MB captured-process-output boundaries.
- A valid diff above the broker's direct bound uses that same deterministic
  complete-file/UTF-8-line plan instead of one oversized subscription request.
  The selected provider/model reviews every one of at most 16 exact units in a
  distinct isolated session and performs a final integration review. Phase one
  signs the canonical root/plan/unit-prompt/unit-report/integration-prompt
  bundle; coverage, ordering, byte ranges, model consistency and fresh-session
  uniqueness all fail closed.

`/review` and `/cross-review` are entry points to the same producer. They do
not own separate completion states. Only a current exact-candidate Verification
Loop adjudication receipt accepts the result. For publication, its checker must
bind the verified phase-one receipt, exact prompt/report, producer keyring, and
machine receipt. The local doctor requests this mandatory-route validation;
generic checker/adjudication evidence is diagnostic only.

Host adapters use native transports and credentials: WSL-to-WSL and
Windows-to-Windows. Cross-host credential execution is forbidden. The review
identity has no merge/deploy permissions; repository owners retain their normal
merge and deployment responsibilities.

The legacy paid API adapter may remain installed for an explicitly requested
operator workflow, but cannot run automatically, replace the keyless route, or
be presented as its fallback.

## Consequences

- Normal pre-PR review requires no provider API key.
- Provider outages remain visible and cannot be converted into approval.
- A single signed producer key may authorize the closed model list for all
  three route providers; the broker validates the actual provider/model pair
  and its signed ordered attempt ledger.
- Windows and WSL share policy and tests while keeping credentials native to
  each host.
- Updating a CLI/model requires an explicit executable/model authorization
  update rather than caller-controlled routing.
- Compressed benchmark evidence is reviewable without a generic binary bypass;
  invalid gzip/JSONL and unsupported binaries remain terminal.
- Copilot stdin delivery and free-usage telemetry are covered at the actual
  subprocess boundary.
- Large but bounded Codex rollouts retain provenance without becoming durable
  review evidence or weakening input/output caps.
- Large but bounded keyless candidates retain complete semantic coverage
  through signed unit and integration evidence rather than truncation or a
  model-input overflow.
- Existing generic Verification Loop receipts remain valid for internal
  diagnostics, but cannot be promoted into local PR-publication authority.
