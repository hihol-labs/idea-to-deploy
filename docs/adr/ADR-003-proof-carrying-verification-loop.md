# ADR-003: Risk-tiered proof-carrying Verification Loop

- **Status:** Accepted
- **Date:** 2026-07-21
- **Decision owners:** Idea to Deploy maintainers

## Context

The methodology already had tests, review rubrics, exact-context cache keys,
goal oracles, and completion hooks. The remaining gap was compositional: an
agent could still narrate a result, reuse a stale review, or hand-edit shaped
state without one consumer revalidating the whole evidence chain. Always
adding more agents would increase cost and correlated confidence without
making the result more falsifiable.

## Decision

Adopt `verification-loop-v1` as the default acceptance protocol for new and
adopted projects:

1. the harness executes declared machine commands in a disposable local Git
   checkout materialized only from the staged candidate, so undeclared ignored
   workspace inputs cannot affect the oracle; any required non-Git input is
   explicitly snapshotted and hash-bound;
2. medium risk adds a targeted fresh-session checker; high/unknown adds a full
   checker from a fresh session and different model or provider; low remains
   machine-only;
3. prompt, report, command results, candidate, contracts, risk, unit, policy,
   provenance, timestamps, and dependency hashes are sealed into receipts;
4. a deterministic adjudicator produces the only receipt that `/goal`,
   `/task`, `/review`, or `/security-audit` may accept;
5. any dependency/candidate change invalidates the chain; failed or missing
   evidence is `failed`/`unverified`, never an inferred pass; attempts are
   bounded to three per candidate.

The trust root is an honest host orchestrator. Local receipts are integrity and
process evidence, not cryptographic model identity. We explicitly do not claim
resistance to a malicious process with the same OS principal or a compromised
orchestrator. Provider-signed identity can be added later without changing the
receipt consumer contract.

## Consequences

- False completion and stale review reuse become executable negative tests.
- Medium/high work pays a checker cost only where semantic residual risk
  remains; low-risk work avoids an unconditional agent tax.
- Review reports and prompts become durable project-local evidence under the
  ignored `.itd-memory/verification-loop/` directory.
- Every evidence producer publishes a unique immutable receipt; retrying a
  machine or checker cannot replace an earlier adjudication dependency.
- Existing plaintext `PASSED` cache/goal evidence fails closed and workflows
  must use the documented producer sequence.
- External outcome claims still require external evidence; internal receipts
  cannot manufacture deployment, user, revenue, or provider facts.

## Rejected alternatives

- **Majority vote:** correlated opinions are not independent evidence.
- **Always-on full multi-agent review:** unnecessary cost for low-risk work.
- **Unkeyed receipt described as cryptographic attestation:** overclaims what a
  same-principal local process can prove.
- **Vendor-specific verifier:** would fork the model-neutral methodology core.

## Verification

`tests/verify_verification_loop.py` covers risk routes, candidate/risk/unit
binding, ignored-overlay isolation, mutable-checkout rejection, immutable
repeat producers, checker independence, tampering, freshness dependencies,
failed oracles, and bounded attempts. Goal/cache/DoD integration tests consume
real receipt chains, and both host-adapter suites must remain green.
