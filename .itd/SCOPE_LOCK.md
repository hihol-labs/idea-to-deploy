# GRAPH-LITE-1-CLOSE record the closure of GRAPH-LITE-1 after PR #351

## Current Task

- GRAPH-LITE-1-CLOSE (records only, no goal unit): GRAPH-LITE-1 was merged on the owner's command as PR #351 -> `0a3e594`
  and rolled out on WSL and Windows. This candidate records the closure: the acceptance contract moves the
  GRAPH-LITE-1 follow-up to `closedFollowups` (no active unit), BACKLOG marks session 1 published and lists the six
  medium findings of review p9 as GRAPH-LITE-2, ADR-013 records the trust boundary the owner accepted on p9, and
  `.itd/DECISIONS.md` records the owner's adjudication. No code, no test, no skill change.

## Allowed Change Areas

- `.itd/ACCEPTANCE_CONTRACT.json` - only `activeFollowup` (set to none) and one appended `closedFollowups` entry.
- `BACKLOG.md` - the P2 Graph Lite section: the session 1 line and one new GRAPH-LITE-2 item.
- `docs/adr/ADR-013-graph-lite-measured-exception.md` - one Consequences bullet (trust boundary).
- `.itd/DECISIONS.md` - one entry appended at the end.
- `.itd/SCOPE_LOCK.md` (this file).

## Forbidden Change Areas

- Code, hooks, skills (including `skills/graph/`), tests, CI, ledgers (`.itd-memory/**`), any other acceptance criterion.
- The GRAPH-LITE-2 fixes themselves (a separate candidate) and session 2 of ADR-013.
- Merge only on the owner's command.

## Review Rule

Records only: machine receipt (`meta-review`) and the mandatory independent reviewer (Sol) on the committed head, as the
gate registry requires a signed route for `itd pr create`.
