# ADR-015: the methodology lives in the installation; a project holds only its data and a pointer

- **Status:** accepted (owner 2026-10-15: «да, делай юнит и релиз»; unit INSTALL-OWNED-1, release 1.108.0)
- **Amends:** the `/adopt` scaffold (Step 1 CLAUDE.md block, Step 3.5 `.itd` copy, Step 7 project hooks). Does not
  change ADR-012 (minimal path by default) or any gate.

## Context

On 2026-10-15 a scan of every project on the owner's machine (WSL and Windows) found the methodology frozen inside
projects at whatever version adopted them:

1. `/adopt` copied the `.itd` tools (`itd_hygiene.py`, `itd_progress.py`, `check_contract_drift.py`,
   `itd_init_validate.py`) into each project, and the skills ran that copy first. Copies drifted (neuroexpert,
   buying, 152-ФЗ) and there was no update channel: a stale copy on an unmerged branch (neuroexpert R-10) could
   only be refreshed by touching that branch.
2. `/adopt` for Claude Code pasted the v1.20 rules block (hard route, mandatory `/task` and `/review`) into the
   project `CLAUDE.md`; three projects still carried it after the owner made the minimal path the default.
3. Older adoptions registered the installed hooks again in the project `.claude/settings.json`: they fired twice
   and re-enabled hooks the owner had switched off in `~/.claude/itd-disabled-hooks.txt`.
4. Nothing reported such drift.

## Decision

1. Code and rules live in the installation (`~/.claude` for Claude Code, the plugin for Codex). A project holds only
   its own contracts (`.itd/*.json`, `*.md`), its state (`.itd-memory/`), profile markers and a short pointer block.
2. `skills/_shared/itd_tool.sh` runs the `.itd` tools from the installation: `$ITD_TEMPLATES_DIR`, then the source
   next to the helper (repository checkout, Codex plugin), then `~/.claude/templates/itd`; a legacy project copy
   runs only when nothing is installed, with a warning. `check_contract_drift.py` takes `--root`.
3. `/adopt` copies contracts without the `.py` tools, writes a pointer block (any `idea-to-deploy:begin` marker
   counts as adopted) and does not re-enable globally disabled hooks per project.
4. `skills/_shared/itd_projects_doctor.py` reports drift read-only: old rules blocks, unused tool copies, duplicate
   or project hooks, project skills that shadow installed ones. Fixing a project stays an explicit owner decision.

## Consequences

- One update of the installation (`/plugin update` + `scripts/sync-to-active.sh`, Codex plugin refresh) reaches every
  project; the question «when will that branch merge» no longer matters for methodology code.
- Old copies in projects are harmless leftovers; the doctor lists them, deletion is optional.
- A machine without the installation and with only a project copy still works (legacy fallback with a warning).
