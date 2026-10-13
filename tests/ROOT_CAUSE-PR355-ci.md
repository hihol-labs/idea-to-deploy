# PR #355 CI evidence repair

## Root cause

The new methodology source invalidated the retained live-benchmark fingerprint, and the Graph result verifier lacked a required out-of-mirror registry entry.

## Reproduction

Linux CI 38313898983: the unchanged live-model oracle fails three current-methodology fingerprint checks. The retained successful run 20261008T200636Z-5b2c36d7 belongs to earlier source. Windows CI 38313898996: drift guard reports unclassified verify_graph_study_result.py (120 passed, one failed); reproduced locally before changes.

## Fix and verification

Produce fresh evidence with the canonical runner and native Codex/Astra, preserving old runs. Register the local-evidence-dependent Graph result verifier with its self-test command and full-replay prerequisite. Run the unchanged freshness oracle, drift guard on both hosts, result self-test, cumulative regression and independent review; publish through the guard and inspect CI at the updated head. Graph stays optional and its measurement is not repeated.

## Transport correction

The first refresh attempt, 20261013T083628Z-fail-4cdc16cf, produced no model output. The retained transcript records HTTP 400: Astra requires a newer Codex CLI. The earlier stderr also reports an incompatible models cache. This failed attempt remains archived. A separate Codex CLI 0.162.1 and an isolated authentication profile are used for the corrected run; the pinned reviewer CLI and benchmark/oracle source are unchanged.

## Clean-checkout reproduction

Run 20261013T085746Z-96b9f18a passed its live and local oracle checks but recorded a dirty worktree fingerprint. The isolated candidate rejected that fingerprint, despite identical methodology file hashes. That report remains unchanged and is not sufficient for clean CI.

The publication evidence is regenerated from a clean checkout of published commit 0890d18. Its pinned methodology, benchmark runner and oracle are byte-identical to this follow-up. The exact-candidate machine replay materializes its staged Git tree as a clean temporary checkout, verifies the tree and clean status before/after the unchanged oracle, and copies no working-tree overlays. This reproduces the published Git state instead of changing the evidence digest or weakening the oracle.

## Native JSONL transport defect

The clean run 20261013T093903Z-a0439beb passed the unchanged live oracle, but the publication producer refused it before model dispatch: Codex 0.162.1 emitted duplicate item.id keys in native web_search records 15 and 16. No record is normalized or discarded. The complete original run is retained byte-for-byte as a declared local diagnostic input; diagnostics/20261013T093903Z-a0439beb.json pins every file and the negative oracle proves those records remain rejected.

For the final live-methodology run, native web search is explicitly disabled in a task-local Codex launcher. The fixture supplies the input task. The CLI remains 0.162.1, the requested model remains Astra, and the benchmark/oracle source and thresholds are unchanged. Strict JSONL validation runs before the machine/reviewer pipeline. This is a transport repair, not a Graph measurement or an independent-review retry.
