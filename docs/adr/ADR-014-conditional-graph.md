# ADR-014 — Owner-authorized conditional Graph Lite

Status: implemented experimental per-project opt-in; global mandatory rollout requires separate positive evidence.

Owner request 2026-10-11 explicitly approves the previously proposed contract-first improvements, semantic scorer, conditional auto-start and fresh Codex-only study. This amends ADR-013 default-off only inside a current exact owner-policy envelope; unconfigured projects retain no-op behavior and manual /graph remains available.

Two complementary explorers (local contract/boundary inputs, caller/state/integration) run in parallel, followed by a separate checker and a human terminal. Every node receives the original task, contract IDs and function inventory. The checker assesses contract truth and reachability separately. Unknown is retained; upstream guards do not automatically repair a local contract failure. Stable proposal IDs prevent same-line claims being merged or lost. Synthesis is deterministic and bound into the existing receipt.

Conditional routing requires an exact authorized project/template fingerprint, allowed module, valid bounded request, expiry and caps bound to the policy and owner authorization across sessions. It selects a graph for a sensitive cross-boundary contract change or a concrete content-bound evidence dispute. A filename alone, file count or model confidence is not a trigger. Missing/disabled policy and absent owner authorization choose the ordinary path; malformed or stale enabled permission refuses preparation. A repeated request reuses only revalidated policy-bound evidence. The native host executes the emitted plan; the Python hook never calls a provider/CLI/model.

The project owner approves policySha256 once via an explicit command; each run binds its own graphDigest, request, current tree, session and monotonic clock/boot. This is honest-host provenance, not same-principal cryptographic attestation. The human remains the terminal decision and no graph mechanism sets verified or replaces the required Verification Loop or external-action approvals.

Evidence: tests/verify_graph_v2.py, verify_graph_policy.py and verify_graph_semantics.py, existing graph and host suites, plus docs/measurements/graph-v2/PROTOCOL.json and its separately recorded fresh results. Every seed match is semantically judged, including proximity matches. Old measurements are preserved unchanged. A controlled synthetic result does not prove production representativeness or superiority over another provider.

R2 with owner-authorized Astra grading is LOSE: both arms caught 8/8 seeded behaviors, median complete-policy duration ratio was 2.651, and one G single-route output was invalid JSON. The implementation remains experimental project opt-in. These results do not support global mandatory activation; see docs/measurements/graph-v2/REPORT.md for the full evidence and protocol deviations.
