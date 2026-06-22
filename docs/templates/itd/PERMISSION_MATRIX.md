# Permission Matrix

Purpose: define who or what may read, write, execute, publish, and touch external systems.

Machine-readable source: `.itd/PERMISSION_MATRIX.json`.

| Capability | Default | Agent | User Approval Required | Evidence |
|---|---|---|---|---|
| Read project files | Allow | Claude | No | Referenced files in response/state |
| Write project files | Scoped | Claude | When outside `.itd/UNIT_CONTEXT_MANIFEST.json` | Diff plus manifest |
| Run local verification | Allow when declared | Claude | No | `.itd-memory/events.jsonl` and `verificationHistory` |
| Install dependencies | Block | Claude | Yes | Approval plus command log |
| Read secrets | Block | Claude | Yes | Approval plus reason |
| External API read | Scoped | Claude | When private/sensitive | Connector/tool event |
| External API write | Block | Claude | Yes | Approval plus event |
| Git commit | Scoped | Claude | When requested or approved | Commit hash/event |
| Git push | Block | Claude | Yes | Remote branch/event |
| Deploy or migrate production | Block | Claude | Yes | Rollback, checks, approval, event |

Rules:

- Project-local rules may tighten this matrix, but must not make production or external writes implicit.
- Any permission exception must be recorded in `.itd-memory/events.jsonl`.
- Dangerous routes must use the smallest approved command surface.
