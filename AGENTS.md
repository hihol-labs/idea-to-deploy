# Idea to Deploy — agent entry point

This repository is the canonical, model-neutral source of the Idea to Deploy
engineering harness. Do not treat a vendor-specific configuration file as the
methodology source of truth.

When working in this repository:

1. Read the applicable skill in `skills/<name>/SKILL.md` before executing that
   workflow. Shared rules live in `skills/_shared/`.
2. Treat `.itd/` contracts and `.itd-memory/` state as authoritative whenever
   they exist. Preserve WIP=1 and update state from evidence, not narration.
3. Use the native host adapter only as transport:
   - Codex: `.codex-plugin/plugin.json`, `hooks/hooks.json`, this `AGENTS.md`.
   - Claude Code: `.claude-plugin/plugin.json` and the Claude settings produced
     by `scripts/sync-to-active.sh` or `/adopt`.
4. Keep shared skills, hooks, contracts, rubrics, and tests vendor-neutral.
   Host-specific paths, tool names, payload translation, and installation
   instructions belong in an adapter boundary documented in
   `docs/HOST_ADAPTER_CONTRACT.md`.
5. Before claiming completion, run the relevant tests and report the real
   result. For adapter changes run `python3 tests/verify_host_adapters.py` and
   `bash tests/run-all.sh --quick` at minimum.
6. Use the shared Verification Loop for acceptance: low risk is machine-only,
   medium uses a targeted fresh-session checker, and high/unknown uses a full
   different-model/provider checker. Only an exact-candidate adjudication
   receipt may satisfy goal/review gates; local receipts assume an honest host
   orchestrator and do not claim same-principal cryptographic attestation.

For Codex-specific setup and known transport differences, read
`docs/CODEX_ADAPTER.md`.
