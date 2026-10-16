# REL-1.108.0 (INSTALL-OWNED-1)

## Current Task

- REL-1.108.0: the methodology lives in the installation, a project holds only its data and a pointer
  (INSTALL-OWNED-1, ADR-015), shipped with #358-#360 as release 1.108.0 (owner 2026-10-15). Criteria:
  `.itd/ACCEPTANCE_CONTRACT.json` REL-1.108.0-AC1..AC4.

## Allowed Change Areas

- `skills/_shared/itd_tool.sh`, `skills/_shared/itd_projects_doctor.py` (new), `skills/_shared/itd_contract_dir.py` (new),
  `skills/_shared/itd_project_hooks.py`.
- `docs/templates/itd/check_contract_drift.py` (`--root`); usage hints in `docs/templates/itd/{itd_hygiene,itd_progress,
  itd_init_validate}.py`; `docs/templates/github/itd-hygiene.yml` (tools from a pinned release).
- `skills/{session-save,handoff,retro,review,task,kickstart,adopt}/SKILL.md`, `skills/review/references/review-checklist.md`,
  `skills/adopt/references/claude-md-template.md`, `skills/adopt/scripts/itd_adopt.py` - call sites and adopt scaffold.
- `hooks/pre-flight-check.sh` - message text and the helper path of its own installation.
- `tests/verify_install_owned_tools.py` (new), `tests/verify_hooks_autoinstall.py`, `tests/verify_session_hygiene_quality.py`,
  `tests/verify_operational_cold_start.py`, `tests/run-all.sh`, `.github/workflows/meta-review.yml`.
- `docs/adr/ADR-015-installation-owned-methodology.md` (new), `docs/CONTRACTS.md`, `docs/completion-gate.md`,
  `docs/templates/global-claude-md.md`, `README.md`, `README.ru.md`, `CHANGELOG.md`.
- Version files: `.claude-plugin/`, `.codex-plugin/`, `docs/HARNESS_CONFORMANCE_REPORT.md`, `docs/HARNESS_DOCS_STATE.json`,
  `docs/api-reviewer/RELEASE_CANDIDATE_CONTRACT.json`, `tests/verify_external_reviewer_release.py`.
- `tests/fixtures/live-model-evidence/` - re-recorded on the release tree.
- `scripts/itd_install_runtime.py` - declare the new shared doctor in the runtime inventory.
- `benchmarks/independent-review-efficacy/` (new append-only history groups, manifest entries, current result views) and
  the history pins in `tests/verify_independent_review_efficacy.py` - efficacy evidence for the producer of #360.
- `BACKLOG.md` - the line-anchoring item of the efficacy oracle and the SHD resolver item.
- `.itd/ACCEPTANCE_CONTRACT.json`, `.itd/DECISIONS.md`, `.itd/SCOPE_LOCK.md`, `.itd/IMPACT_GRAPH.json` - records.

## Forbidden Change Areas

- `HANDOFF.md`; any project outside this repository (the doctor only reads); gates and their thresholds.

## Review Rule

One independent checker (gpt-5.6-sol) on the exact committed candidate before `itd pr create`.
