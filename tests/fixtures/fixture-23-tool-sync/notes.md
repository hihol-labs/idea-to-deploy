# Manual verification — fixture 23 (/tool-sync)

`/tool-sync` is an **explicit-invocation, external-write** skill that mirrors
idea-to-deploy artifacts to external planning/doc tools (GitHub, Linear, Notion,
Google Drive, Obsidian). This fixture regressionally fixes the
ask-before-live-write contract, the reconcile-not-overwrite rule, the no-secrets
guard, and the export-only fallback.

## Fixture status

`pending` — **deferred**, same bucket as `fixture-15-advisor` (external connector
+ stdout). For now: manual checklist below. The stub satisfies
`check-skill-completeness.sh`. Note: `/tool-sync` sets
`metadata.explicit_invocation: true` — invoked explicitly, exempt from the M-C11
trigger-drift check but still ships trigger phrases + a hook reminder (same
pattern as `/deploy`, `/migrate-prod`).

## /tool-sync — Scenario A: mirror plan to Notion (happy path)

User pastes the prompt from `idea.md`: sync LAUNCH_PLAN.md + BACKLOG.md status to
Notion; don't clobber the team's existing edits.

### Source + target
- [ ] Source artifacts identified (`LAUNCH_PLAN.md`, `BACKLOG.md`, `STATE.json`)
- [ ] Target connector + live-access availability assessed

### Reconcile, don't clobber
- [ ] Connector-native READ of Notion happens BEFORE any write
- [ ] External user edits preserved (reconcile, not blind overwrite)

### Guard rails
- [ ] NO secrets / private customer data / credentials synced
- [ ] `LAUNCH_PLAN.md` / `BACKLOG.md` stay canonical unless user makes the tool authoritative
- [ ] Live writes happen only on explicit request

### Output shape (stdout)
- [ ] Contains SYNC TARGET, SOURCE ARTIFACTS, MODE (live|export-only|read-only),
      CHANGES, UNSYNCED ITEMS, NEXT ACTION

## /tool-sync — Scenario B: live access unavailable (export-only)

Notion connector not available / not approved.

- [ ] MODE = export-only
- [ ] Payload written to `.itd-integrations/notion.json`
- [ ] States clearly that live sync was not performed

## /tool-sync — Scenario C: Obsidian target

User asks to sync to an Obsidian vault.

- [ ] Prefers `/obsidian-export` for the actual vault export
- [ ] Treats `.itd-integrations/obsidian/` as generated output (canonical edits
      stay in source idea-to-deploy docs)

## Cross-reference with `check-skill-completeness.sh`

1. ✅ `skills/tool-sync/references/` exists (tool-sync-checklist.md)
2. ✅ `hooks/check-skills.sh` contains trigger phrases for `/tool-sync`
3. ✅ `tests/fixtures/fixture-23-tool-sync/` exists with `idea.md`, `notes.md`,
   `expected-files.txt`, `expected-snapshot.json`

## Run manually

1. `cd tests/fixtures/fixture-23-tool-sync/`
2. `mkdir -p output && cd output`
3. Start Claude Code, paste `idea.md` content, invoke `/tool-sync`
4. Verify the checklist above; confirm no external edits were clobbered
5. `cd .. && python3 ../../verify_snapshot.py .` — expected: `⏸️ fixture-23-tool-sync: PENDING`

## Failures (fill in if any)

(empty unless the fixture fails — especially any external user edit clobbered, or
a secret synced into a planning tool)
