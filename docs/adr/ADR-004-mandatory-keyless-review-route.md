# ADR-004: one mandatory keyless independent pre-PR review route

**Date:** 2026-08-03
**Status:** Accepted
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

Its route is fixed: `OpenAI -> Anthropic -> Gemini`.

- OpenAI uses a fresh subscription session and a model different from the
  maker. Sol and Terra automatically alternate when necessary.
- Anthropic uses an isolated Claude subscription session.
- Gemini uses an isolated personal OAuth session and binds/copies the complete
  installed JavaScript bundle plus its native runtime.
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
  the Gemini init event. Missing telemetry advances only as `UNAVAILABLE`;
  ambiguity/mismatch is terminal `UNVERIFIED`.
- Initial local pre-PR review uses a repository-bound target with null PR/head
  coordinates, because neither exists yet; candidate parent/tree/diff and the
  later unchanged single-parent commit bridge remain exact. Existing PR and
  App flows require a positive PR number plus exact head SHA.
- Mandatory-route consumption independently reconstructs the signed
  base-to-candidate binary diff after proving base-to-parent ancestry and
  compares both digest and byte count; a substituted base fails closed.

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
- Existing generic Verification Loop receipts remain valid for internal
  diagnostics, but cannot be promoted into local PR-publication authority.
