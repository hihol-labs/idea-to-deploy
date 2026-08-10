# ADR-009 — Graph Contract Layer (GENG program), host-neutral, no owned runtime

- **Status:** accepted (user approval 2026-08-10 — approval gate v1.42.0)
- **Date:** 2026-08-10
- **Review date:** 2026-09-28 — jointly with the ADR-001 review, as proposed in
  the originating Codex (GPT 5.6) session.
- **Amends:** [ADR-001](ADR-001-no-own-runtime.md) — refines, does not revoke:
  ITD still builds no runtime of its own; graph *contracts, policies, and
  proofs* are ITD-owned, graph *execution* stays native to the host.
- **Numbering note (amendment 1):** the originating plan named this record
  "ADR-007". That number was already taken on `main` by
  [ADR-007-human-adjudication-of-independent-review.md](ADR-007-human-adjudication-of-independent-review.md)
  (and by `ADR-007-vendor-neutral-independent-review.md` in the frozen GPG-003
  candidate). The next number, ADR-008, is already reserved by
  `.itd/DECISIONS.md` (entry 2026-08-09) for the deferred
  reviewer-independence-ladder ADR that ADR-007 explicitly defers. The GENG
  decision record therefore takes the next free number after that reservation,
  **ADR-009**. All references to "GENG-ADR" resolve here.

## Context

Advisory session 2026-08-07 (`/advisor`; business-analyst
PASSED_WITH_WARNINGS, devils-advocate BLOCKED for any runtime-owning variant)
analyzed the proposal to bring Graph Engineering into idea-to-deploy, against
five public sources (LangChain "3 Years of Graph Engineering", the Claude
dynamic-workflows blog, a deep-research workflow gist, Anthropic Institute
RSI, 0xCodez "14-step Graph Engineering"). In a parallel Codex (GPT 5.6)
session the user approved **variant B: "Codex-first host-neutral Graph
Contract Layer"**, program **GENG-000 … GENG-010**, and then approved three
amendments to that plan (recorded 2026-08-07 in project memory,
`project_geng_plan_amendments.md`). Formalization was deliberately deferred
until GPG-004 closed (WIP=1, Scope Lock); GPG-004 is `verified` and released
in v1.96.0, so the deferral condition is met.

Host constraints confirmed against the harness contract: dynamic-workflow
concurrency min(16, cores−2), 1000-agent ceiling, resume only within the same
session ⇒ a host checkpoint is a cache, never canonical durability.

## Decision

Adopt the Graph Contract Layer under these locked invariants:

1. **No owned graph runtime.** ITD owns graph contracts, policies, and proof
   formats; execution is native to the host (per ADR-001).
2. **Proposal ≠ authorization.** Claude/Codex may *propose* a graph; only the
   human authorizes, and authorizes an **exact `graphDigest`**.
3. **Verification Loop stays the single completion authority.** No graph
   mechanism mints `verified`.
4. **Durability lives in `.itd-memory` + receipts.** Host checkpoints are
   cache only.

### Amendment 2 — entry criterion for GENG-004 (Codex Shadow Mode)

GENG-004 may not start until the **Codex isolated transport is demonstrably
stable**, established by a dedicated transport-stability check (repeated
clean isolated-transport passes), not inferred from unit closure. The
GPG-004 U8 line is closed, but its closure criterion was acceptance on one
exact candidate via a human-adjudicated route — that closure does not itself
certify transport stability. Rationale: 13 probes showed non-deterministic
Codex transport failure depending on the shape of `CODEX_HOME`; the
mechanism remains unknown and is not to be guessed at. Until the dedicated
check passes, the **serial fallback is first-class**, not an emergency path.

### Amendment 3 — incremental proof graph as a separate GENG-003 exit criterion

GENG-003 is not done without **content-addressed node receipts** binding:
graph version + node version + input digest + dependency digests + policy
digest + candidate/tree + provenance — with **downstream-only invalidation**
(a changed node re-proves itself and its descendants, nothing upstream).
The **final integration oracle always runs over the single exact candidate**;
node-level receipts never substitute for it. This is the element that
addresses the pain of multi-day runs re-proving everything from scratch.

## Alternatives considered

- **ITD-owned graph runtime / scheduler** — rejected (devils-advocate
  BLOCKED): contradicts ADR-001, the harness-best-effort invariant, WIP=1,
  and exact-candidate adjudication. Also already in the BACKLOG icebox
  ("Ralph or any ITD-owned scheduler/runtime").
- **Do nothing (no graph work)** — rejected: multi-day proof runs re-execute
  the full ladder on every change; the contract layer attacks that cost
  without new runtime surface.
- **Keep the plan's original "ADR-007" number** — rejected: collides with the
  merged ADR-007 on `main`.

## Consequences

- **Positive:** graph work becomes plannable as ordered GENG units under the
  existing /goal + Verification Loop machinery; incremental proof receipts
  bound re-verification cost; the transport entry criterion prevents building
  Shadow Mode on a flaky channel.
- **Negative / cost:** proof-graph receipt schemas are new security-relevant
  surface; contract-only ownership means host behavior changes can still
  invalidate assumptions (mitigated by the best-effort invariant: a missing
  host feature degrades to the serial path, never to a false green).
- **Risks:** Codex transport root cause stays unknown — GENG-004 may stay
  gated for a long time; that is intended fail-closed behavior.

## Follow-up

The full GENG-000…GENG-010 unit text lives in the two originating session
transcripts and project memory; it enters the repo as a `/goal` unit ledger
when GENG-000 (Harness Readiness Freeze) is started as the next unit after
the currently queued GPG follow-ups (U6/U16/U17). No GENG code before that.
