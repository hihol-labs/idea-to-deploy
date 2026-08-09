# GPG-004 / U15 — A16 transport unreliability: root cause named

**Date:** 2026-08-08 (evening, WSL leg)
**Candidate:** staged tree `5ca3b8ae0642673cfdb6818d0072ca5b907e2eef`, base `4971a557e27dc33654d58abaf897671f1ba2e766`
**Binary:** pinned Codex `37e6f5953f191b04f7b62cb07dae90f51d0947ad89f0355665b421fbde28700b` (0.144.3, linux-x64 musl)
**Model:** `gpt-5.6-terra`, provider `openai-subscription`
**Method:** differential experiment per U15; raw `--json` stream captured for every call, classifier recorded but never aborting.

## Verdict (branch (a) of the U15 criterion — factor named, both directions shown by execution)

The isolated invocation is NOT less reliable than a plain one. The mandatory
route fails because of **amplification by structure plus a classifier that
discards recovered calls**:

1. The transport exhibits a transient `request timed out` + self-reconnect at
   an observed per-call rate of **2 in 15** (~13%) on ~100 KB prompts. The CLI
   retries internally (`Reconnecting... 2/5`), the call **recovers, completes
   the turn and emits a full, schema-valid verdict** (returncode 0,
   `turn.completed` with usage, intact `report.json`).
2. The producer's event-stream classifier (`run_codex_review` in
   `skills/_shared/itd_free_reviewer_producer.py`) treats **any**
   `{"type":"error"}` event as fatal (`raise_cli_failure` → route
   `UNAVAILABLE`), including a reconnect notice that the CLI itself already
   healed. The delivered verdict is thrown away.
3. The hierarchical route is 15 unit calls + 1 integration call = **16
   sequential live calls with no per-unit resume**. One discarded call types
   the whole route `UNAVAILABLE` and the next attempt restarts from zero.
   At 13%/call: P(route survives) ≈ 0.87^16 ≈ **11%**. Observed: 0 completed
   routes in 4 attempts (3 earlier UNAVAILABLE + this instrumented run,
   breakIndex 9).

Isolation factors are refuted as causes (steps 1–2 + burst, this session and
`session_2026-08-08_7.md`): full isolation shape with tiny and 114 198-byte
prompts, 6/6 single calls clean; in this run 13 of 15 isolated unit calls were
transport-clean, including the largest prompt.

## Evidence (raw, reproducible)

Experiment runner: `a16_step3.py` (session scratchpad `a16/`, described in
`.itd-memory/session_2026-08-08_8.md`). Packet frozen by the producer's own
`freeze_packet` on the exact candidate worktree; prompts built by the
producer's own `_hierarchical_units`/`_unit_review_prompt`; invocation shape
byte-for-byte `run_codex_review` (fresh temp dir, 0500 transport copy, fresh
auth-only `CODEX_HOME`, allowlist env, `cwd=work`, fresh session per call,
timeout 900 s, no retries). Plan: `unitCount=15`, `fullDiffBytes=947043`.

Per-call log `step3/progress.jsonl`; raw `call-NN-stdout.jsonl`,
`call-NN-stderr.txt`, `call-NN-report.json`, `call-NN-prompt.txt` per call.

| call | prompt bytes | rc | error events | verdict in report | route classifier |
|-----:|-------------:|---:|-------------:|-------------------|------------------|
| 01 | 88 812 | 0 | 0 | BLOCKED | pass |
| 02 | 109 096 | 0 | 0 | BLOCKED | pass |
| 03 | 58 110 | 0 | 0 | BLOCKED | pass |
| 04 | 97 905 | 0 | 0 | BLOCKED | pass |
| 05 | 111 521 | 0 | 0 | BLOCKED | pass |
| 06 | 114 198 | 0 | 0 | PASSED | pass |
| 07 | 112 139 | 0 | 0 | PASSED | pass |
| 08 | 109 751 | 0 | 0 | BLOCKED | pass |
| **09** | 105 816 | **0** | **1** | **BLOCKED (full valid report)** | **fatal → UNAVAILABLE** |
| 10 | 105 942 | 0 | 0 | PASSED | pass |
| 11 | 107 714 | 0 | 0 | PASSED | pass |
| **12** | 110 685 | **0** | **1** | **PASSED (full valid report)** | **fatal → UNAVAILABLE** |
| 13 | 110 316 | 0 | 0 | BLOCKED | pass |
| 14 | 98 100 | 0 | 0 | BLOCKED | pass |
| 15 | 61 147 | 0 | 0 | BLOCKED | pass |
| 16 (integration) | — | — | — | not run | route aborts at 9 |

The failing stream, verbatim head (call-09; call-12 identical in shape):

```
{"type":"thread.started","thread_id":"019fe2c9-36ee-7ad3-b2d7-819381d6329e"}
{"type":"turn.started"}
{"type":"error","message":"Reconnecting... 2/5 (request timed out)"}
{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"{\"findings\":[...],\"verdict\":\"BLOCKED\"}"}}
{"type":"turn.completed","usage":{"input_tokens":36642,"cached_input_tokens":7936,"output_tokens":1169,"reasoning_output_tokens":950}}
```

Both directions by execution:

- **Presence** of the factor (transient reconnect event in stream) → the
  route classifier raises `UNAVAILABLE` on a call that carries a valid
  verdict: calls 09 and 12, streams above.
- **Absence** of the factor → identical isolated shape, identical prompt
  class, verdict accepted: the other 13 calls of the same run, plus 6/6
  single calls in steps 1–2.

Non-fatal background noise, present on clean and failed calls alike:
`codex_models_manager: failed to refresh available models: timeout waiting
for child process to exit` (stderr), and the PATH-alias warning about /tmp —
neither correlates with the outcome.

## Why the efficacy runner survives the same conditions

`tests/run-independent-review-efficacy.py` checkpoints per case (commit
`4afbf8b`): a transient failure costs one case, resumed on the next
invocation. The mandatory route has no such checkpoint, so the same transport
costs the whole 16-call attempt.

## What this is NOT

- NOT a licence to raise `--max-transport-attempts`, add automatic retries to
  the mandatory route, or reclassify a genuinely failed call: a call that
  dies without a verdict must stay fatal (U15 cannotWeaken).
- NOT an isolation defect: H1 (environment), H2 (credential home), H3
  (disabled features), H4 (execution shape), H6 (DNS/TUN) are refuted by
  execution; H5 (rate/concurrency) is refuted as a *sufficient* cause — the
  reconnects appear mid-series and mid-single-call alike and self-heal.

## Sanctioned fix (agreed in advance, session_2026-08-08_7/8)

**Per-unit resumability of the hierarchical route**, modelled on the efficacy
runner's checkpoint: a failed unit call costs that unit only; a unit that
already produced a verdict is never re-run; every unit still must produce a
real verdict. RED-first with mutation proof in both directions. Cost
accepted: `skills/_shared` edits change the content-pinned tree → new live H4
run → new machine receipt → new route run.

## Open question for the human (NOT decided here)

Calls 09/12 delivered valid verdicts that the classifier discarded. Whether a
stream containing ONLY recovered reconnect notices (`error: Reconnecting...`
followed by `turn.completed` + valid report) may be accepted is a separate
security-control decision: accepting it reads as softening `UNAVAILABLE`
(forbidden by cannotWeaken as written), while rejecting it discards real
verdicts and keeps the per-call loss rate at ~13%. Resumability alone already
converts the 0.87^16 route into per-unit independent completion, so the
route becomes viable without touching the classifier. Recorded as a decision
point, not implemented.

## Content note for U8 (out of U15 scope)

The unit leg produced 9 BLOCKED unit verdicts on the current candidate,
including a concrete high-severity finding on
`tests/fixtures/live-model-evidence/runs/20260808T122710Z-02b15c7b/transcript.jsonl.gz`
(captured Blueprint run substitutes self-critique for the required Devil's
Advocate subagent). When the route completes after the fix, the integration
verdict will need real adjudication — the transport fix does not make the
candidate pass.
