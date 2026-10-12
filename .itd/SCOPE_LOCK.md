# Scope Lock

## Current Task

- GLV2-001: implement the user-approved Graph Lite improvements, conditional automation, semantic evaluation and fresh Codex-only measurement.

## Allowed Change Areas

- `skills/graph/scripts/itd_graph.py`
- `skills/graph/scripts/itd_graph_v2.py`
- `skills/graph/scripts/itd_graph_policy.py`
- `skills/graph/scripts/itd_graph_score.py`
- `skills/graph/SKILL.md`
- `skills/task/SKILL.md`
- `hooks/graph-route.sh`
- `hooks/hooks.json`
- `hooks/hooks.codex.json`
- `tests/verify_graph_v2.py`
- `tests/verify_graph_policy.py`
- `tests/verify_graph_semantics.py`
- `tests/verify_graph_skill.py`
- `tests/run-all.sh`
- `scripts/graph_v2_study.py`
- `scripts/graph_v2_native.py`
- `docs/graph-engineering.md`
- `docs/HOST_ADAPTER_CONTRACT.md`
- `docs/CODEX_ADAPTER.md`
- `docs/adr/ADR-013-graph-lite-measured-exception.md`
- `docs/adr/ADR-014-conditional-graph.md`
- `docs/measurements/graph-v2/`
- `.itd/SCOPE_LOCK.md`
- `.itd/ACCEPTANCE_CONTRACT.json`
- `.itd/IMPACT_GRAPH.json`

- `README.md`
- `README.ru.md`
- `hooks/README.md`
- `tests/verify_graph_study.py`

- `docs/HARNESS_ENGINEERING_MAP.md`
- `docs/HARNESS_DOCS_STATE.json`
- `docs/templates/global-claude-md.md`
- `.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `scripts/sync-to-active.sh`
- `tests/verify_gate_taxonomy.py`
- `tests/verify_harness_docs_freshness.py`

- `scripts/graph_v2_grade.py`
- `tests/verify_graph_study_result.py`

- `tests/verify_graph_grading.py`

- `.itd-memory/STATE.json` (remove from Git tracking; keep local canonical evidence-derived bookkeeping, preserving historical tracked bytes in the archived source)
- `.itd-memory/events.jsonl` (remove from Git tracking; retain local lifecycle journal and historical source archive)

- `tests/verify_review_evalset.py` (equivalent explicit manifest path for generated impact ownership)

## Approved publication compatibility follow-up

User approval (2026-10-12): add the actual maker gpt-6.1-sol to the closed mandatory reviewer route, selecting gpt-5.6-terra. Preserve existing routes and rejection of unknown/third models; no review bypass or provider fallback. Allowed: skills/_shared/itd_free_reviewer_producer.py, tests/verify_free_reviewer_producer.py, tests/verify_reviewer_model_compatibility.py, tests/verify_mandatory_keyless_review.py (align stale diagnostic fixture to immutable attempt paths, preserving no-overwrite assertions), and immutable host runtime installation after verification. Efficacy refresh includes tests/run-independent-review-efficacy.py: clarify that all rubric contours apply to concrete changed behavior and required dependencies, preserving relevant uncertainty and all thresholds after observed out-of-scope false blocks. Efficacy refresh is in scope: tests/verify_independent_review_efficacy.py (the same approved maker pair and a bounded containing-function declaration anchor, with substantive/file/severity checks retained after an observed false miss), benchmarks/independent-review-efficacy/results/, and append-only history/route-debts/ archive entries; existing history bytes remain immutable. Ordinary guarded publication is authorized by the continuation request.

## Independent-review correction and fresh r2 study

The mandatory Terra report for candidate a3a4d6b is BLOCKED and retained in full. Correct confirmed budget, retry, coverage, relative-path, nested-anchor and documentation defects; retain evidence refuting the unsupported depth allegation. Additional allowed adapter area: scripts/graph_v2_context.py. Prepare eight independently authored/refuted fresh tasks, separate gv2r2 actor/clone/grader namespace and study directory; preserve r1 unchanged and replay only its exact archived source. Never weaken current-source freshness or reuse old model answers. Current r2 protocol, source snapshot, native collection and blind grading must all be bound before acceptance.

The deletion diff exposed an existing entropy false positive on ordinary hash-bound local review artifact basenames. Allow skills/_shared/itd_external_reviewer.py and tests/verify_scrubber_precision.py for a narrow entropy-only exclusion; retain high-confidence and residual secret detection over original text. No shared secret-reference allowlist expansion. All measured agents and graders use immutable capped source capsules and exactly one assigned read; all further tool calls fail audit. Both measured arms retain identical source access. The advisory deadline allegation was refuted at the existing shared cmd_record boundary; the study adds an explicit redundant precheck. Stored accepted grader identity and dispatch proof are revalidated on every replay. Semantic blinding must refuse collisions in behavior data instead of altering their meaning.

Owner-authorized follow-up "делай на астра": additive judge-only adapter scripts/graph_v2_astra.py, exact pre-session dispatch recovery scripts/graph_v2_astra_dispatch_recovery.py, tests/verify_graph_astra_amendment.py, and docs/measurements/graph-v2/ASTRA_AMENDMENT.json. Original measured code, source snapshot, sealed collection, question capsules and scoring thresholds remain hash-verified unchanged. Report the changed judge model and infrastructure recovery explicitly. That judge-only authorization was subsequently extended by the explicit publication request below.

## Approved Astra publication follow-up

The refreshed reviewer checks exposed an exact semantic finding anchored at the immediately closing function brace. The efficacy matcher may recognize that adjacent boundary while retaining file, severity and fault-term requirements, rejecting neighboring/nested function attribution and ambiguous lexical structure. Existing reports and detection thresholds remain unchanged.

Owner explicitly requested Astra support in independent review, current-candidate checks and a draft PR, keeping Graph optional and prohibiting a new Graph measurement. Extend only the approved maker map with gpt-6-astra -> gpt-5.6-terra; preserve actual provenance, existing routes, fresh-session review, closed reviewer/standby set and all exact-candidate gates. Update routing regressions, affected route documentation, evidence/oracle matrix and trusted runtime as required. Reuse and replay the sealed Graph measurement; do not rerun its actors or judges.

## Forbidden Change Areas

Installed plugin caches, production sources/data, unrelated reviewer trust policy and unrelated methodology units. No production deployment. Old measurement remains immutable.
