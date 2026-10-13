# Graph Lite v2 — R2 with owner-authorized Astra grading

**Outcome: LOSE under the registered thresholds.** Conditional Graph found no additional seeded defects and cost a median **2.651×** as much elapsed time. This experiment does not support mandatory or global automatic activation.

All **32 arms and 52 measured sessions** used `gpt-6.1-sol/high`. Before any judge ran, the owner requested Astra instead of the originally planned judge. All **116 blind questions** were answered by **18 fresh `gpt-6-astra/high` sessions**, without answer retries or operator-authored verdicts. This is a uniformly measured study with a different uniform judge model, not an end-to-end single-model experiment. See [ASTRA_AMENDMENT.json](ASTRA_AMENDMENT.json).

| Metric | Conditional policy G | Control K |
| --- | ---: | ---: |
| Seeded defects caught in each repeat | 8/8 | 8/8 |
| Catch rate | 100% | 100% |
| Proposed findings judged real | 30/30 | 16/16 |
| Seed matches across both repeats | 16 | 16 |
| Additional duplicate findings | 14 | 0 |
| False-positive claims on clean tasks | 0 | 0 |
| Structured-output failures | 1/16 | 0/16 |
| Graph / single routing | 10 / 6 | 0 / 16 |

Duplicates count toward realness precision but earn no extra seed credit. One clean-task G arm had invalid output, so its lack of claims is not a valid clean inspection.

| Registered condition | Actual | Pass |
| --- | --- | --- |
| Catch gain ≥ 1/4 | 0 | No |
| Unique-defect paired sign p ≤ 1/10 | 1; 0 wins, 0 losses, 8 ties | No |
| G precision within 1/10 of K | 1 vs 1 | Yes |
| Median complete-policy time ratio ≤ 3 | 2.6510174292170294 | Yes |
| Every G arm has valid output | T8-GK-G failed JSON parsing | No |

## Hunters and critic

The checker retained all **26 graph proposals** as contract violations: none refuted, none unknown. Both final arms caught every seeded behavior. Extra Graph volume consisted of duplicates. In T3, the contract hunter reported destination canonicalization as one issue, while the integration hunter split whitespace and Unicode examples. One-to-one semantic matching prevented extra credit for these variants. This corpus supplies no new evidence of hunter misses or critic suppression.

T8-GK-G used the policy's single route and returned malformed JSON. Its model and isolation audit passed; strict answer parsing failed. The failure and elapsed time were retained, with no findings and no rerun. This is an operational policy-arm failure, not evidence that T8 needed graph reasoning.

## Evidence and deviations

Eight independently authored synthetic projects contain eight seeded behaviors across six tasks and two independently checked clean controls. Each task has both G/K orders. Both arms received identical hash-bound source text; each node and judge read one assigned capsule and then used no further tools.

Original collection/scoring sources, seal, capsules and thresholds remain unchanged. The additive Astra adapter changes judge identity and artifact namespace only. One grader spawn was refused by the app before session creation because of its concurrent-agent limit. Its native call/return is preserved; the later successful dispatch produced the sole answer for that batch. Recovery excludes only that exact pre-session refusal from dispatch cardinality.

A pre-arm freeze with a parent-model mismatch was archived unused. An earlier two-hunter attempt exposed nullable token telemetry in the adapter. That attempt and its source snapshot were archived; the corrected retained run used a new namespace, with no reused answers. This restart is a procedural deviation from the original uninterrupted-run plan.

Recorded arm time totals 5966.148875943 seconds. It includes routing, serialization, service waiting and orchestration, not just inference. Replay the declared local dataset with:

```sh
python3 -I -B scripts/graph_v2_study.py replay
python3 -I -B scripts/graph_v2_astra.py verify
```

The latter returns `AMENDED_STUDY_VERIFIED` and `LOSE`, checking frozen/current source hashes, collection provenance, native Astra answers and bindings, the unchanged queue, and exact arithmetic. Raw evidence is under `.itd-memory/graph-v2-study-r2/` and must be declared as a hash-bound input in an isolated oracle. R1 remains separate in [R1_REPORT.md](R1_REPORT.md) and [R1_RESULTS.json](R1_RESULTS.json).

## Adoption

Keep single-agent work as the default. Retain Graph Lite as a bounded project opt-in. Automatic routing requires either a sensitive change touching at least two declared responsibility boundaries, or an unresolved dispute with a concrete counterexample and two distinct content-hash-bound evidence files. Both require a current owner-approved policy, matching project/template, an allowed module and remaining run/time budget. The run allowance is bound to the policy and authorization across sessions.

These are eligibility conditions, not proven benefit predictors. This small synthetic corpus again reached a detection ceiling; within-task defects may be correlated, and host/service latency affects timing. The study neither proves Graph never helps larger projects nor compares Codex with Claude. Any further efficacy claim needs a separately approved realistic corpus where the control does not saturate, with duplicate burden and valid-output rate reported.

Study replay is verified. Final implementation acceptance, publication review and release remain separate and are not claimed here.
