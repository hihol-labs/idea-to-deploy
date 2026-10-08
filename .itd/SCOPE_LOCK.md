# GRAPH-LITE-1 add the default-off /graph skill as the measured exception of ADR-012 (ADR-013)

## Current Task

- GRAPH-LITE-1 (no goal unit; owner decision 2026-10-07, variant A+B after the graph-engineering explainer by
  Greg Isenberg): ship Graph Lite - one explicit agent graph per task kept as files under
  `.itd-memory/graph-runs/<run-id>/`, default-off (`disable-model-invocation: true`), read-only nodes, the owner
  approves the exact graph digest, the human is the only terminal node - as the single measured exception to
  ADR-012 item 5 (ADR-013). Session 1 of 3: the skill, its run tool, its oracle, the ADR, the vocabulary map and
  the registration a new skill needs. The measurement itself (sessions 2-3) is out of scope.

## Allowed Change Areas

- `skills/graph/` (new) - `SKILL.md`, `scripts/itd_graph.py`, `agents/openai.yaml`.
- `tests/verify_graph_skill.py` (new) and `tests/fixtures/fixture-33-graph/` (new, contract fixture).
- `docs/adr/ADR-013-graph-lite-measured-exception.md` (new), `docs/graph-engineering.md` (new), the amended-by
  note in `docs/adr/ADR-012-minimal-path-default.md`.
- Registration of the 41st skill: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `README.md`,
  `README.ru.md`, `docs/templates/global-claude-md.md`, `docs/HARNESS_ENGINEERING_MAP.md`,
  `docs/HARNESS_DOCS_STATE.json` (inventory only), `docs/CONTRACTS.md`, count prose in `docs/**` and
  `docs/promotion/**`, `docs/adr/ADR-001-no-own-runtime.md` (count lines only),
  `docs/HARNESS_DEMO_ABSORPTION_CONTRACT.json` + `.sha256` and `tests/verify_harness_demo_absorption.py`
  (public skill baseline 41 + the name; the baseline-drift mutation moves to 42 so it stays non-vacuous).
- Wiring: `tests/run-all.sh`, `.github/workflows/windows-verify.yml`, `.itd/IMPACT_GRAPH.json` (regenerated).
- Records: `CHANGELOG.md` (Unreleased), `.itd/DECISIONS.md` (one entry appended), `BACKLOG.md` (one P2 entry and
  one P3 finding), `tests/fixtures/live-model-evidence/` (re-recorded on the new methodology tree),
  `.itd/SCOPE_LOCK.md` (this file).
- `.itd/ACCEPTANCE_CONTRACT.json` - only `activeFollowup` (GRAPH-LITE-1, medium, evidence-first) and the two
  criteria `GRAPH-LITE-1-1-run-tool` and `GRAPH-LITE-1-2-registration`; no other criterion changes.

## Forbidden Change Areas

- Hooks, gates and their policies (`hooks/**`, `skills/_shared/**` policies), any other criterion of
  `.itd/ACCEPTANCE_CONTRACT.json`, other skills, the minimal path of ADR-012 and its hooks opt-out list.
- Ledgers (`.itd-memory/GOAL.json`, `STATE.json`, `events.jsonl`); no goal unit is opened.
- Triggers for `/graph` in `hooks/check-skills.sh` (the skill is opt-in by ADR-013).
- A node declared as mutating (`purity` other than `read-only`); any `verified` minted by a graph; a graph runtime
  or scheduler owned by ITD. Read-only is a contract the run tool backs (Explore agent type, git-state check at
  `record`) without claiming a sandbox: ignored files, `.itd-memory/`, harness telemetry and network use are
  documented as not detected (ADR-013 item 3).
- The plugin version (stays 1.106.0; the release is a separate unit), `sync-to-active` before the merge, the merge
  itself (owner's command only).

## Recorded Evidence (not maker-authored)

`tests/fixtures/live-model-evidence/runs/20261008T122051Z-39d67a99/**` and `latest.json` are observations written by
`tests/run-live-model-benchmark.py` (the model under test produced `output/**`); the maker did not author or edit them.
Their reviewable properties are integrity and freshness, not content: `transcript.jsonl.gz` is gzip on disk (first
bytes `1f8b`, written by `gzip.open`) and the review packet shows it decompressed through the transparent JSONL
representation; `tests/verify_live_model_benchmark.py --require-evidence` (machine leg `live-evidence`) checks the
methodology tree pin, `transcriptGzipSha256` over the gzip bytes and the independent snapshot oracle.

## Review Rule

Minimal path of ADR-012 for the change itself (tests written and run). Publication follows the gate registry:
machine receipt on the committed head, the mandatory independent reviewer (Sol, opposite vendor) on the same
head, adjudication receipt registered for `itd pr create`.
