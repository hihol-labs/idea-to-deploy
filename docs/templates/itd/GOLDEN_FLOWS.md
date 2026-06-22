# Golden Flows

Golden flows are the smallest set of user journeys that prove the product still works.

| Flow | Entry Point | Expected Result | Verification | Browser Evidence |
|---|---|---|---|---|
| Replace me | Replace me | Replace me | automated/manual | `/browser-check` Playwright screenshot/log when browser-facing |

## Blocking Rule

If a task touches a golden flow, the flow must be verified before deployment. A golden flow with no verification evidence cannot be marked `passed` (see fail-closed verification in `docs/CONTRACTS.md`).
