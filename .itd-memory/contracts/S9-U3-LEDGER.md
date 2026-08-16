# S9-U3-LEDGER — agent-delegation telemetry fails the strict completion ledger

**Unit:** `S9-U3-LEDGER` · riskTier **medium** · branch `fix/s9-harness-debts`
**Impact classes:** correctness, error-handling, repository-hygiene

## Root cause

Two hooks append to the same ledger `.claude/completion/signals.jsonl`, but only
one of them signs its rows.

- `hooks/completion-signals.sh:94` stamps `sig["producer"] =
  "itd-completion-signals"` before calling `completion_lib.append_signal`.
- `hooks/record-agent-skill.sh` (`record_agent_signal`) builds its row with
  `completion_lib.agent_result_signal` and appends it **without** a `producer`.
  `append_signal` (`hooks/completion_lib.py`) adds `session` and `unit`, never a
  producer, so the omission survives to disk.

The strict evaluator then reads every row of the session and requires
`producer` on all of them:

- `hooks/completion-gate.sh` → `signal_schema_error` — a missing field aborts
  the parse of the WHOLE ledger with `runtime ledger line N: runtime signal is
  missing fields: producer`, and the commit is denied.
- `docs/templates/itd/itd_hygiene.py` → the same check in the explicit-close
  path, so `/session-save --close` goes red for the same reason.

Observed row (`.claude/completion/signals.jsonl:1130`):

```json
{"ts": "2026-08-14T20:46:45+00:00", "kind": "agent", "layer": 0,
 "class": "delegation", "command": "agent:general-purpose",
 "outcome": "empty", "evidence": "пустой финал субагента",
 "session": "7371d4aa-3bdf-4bc9-adbf-9c1f90a4b0dd"}
```

So merely delegating to a subagent could make a later commit or session close
fail closed for a reason that has nothing to do with the work being judged.

## Scope

Writer and evaluators, plus their oracles:

- `hooks/record-agent-skill.sh` — stamp the row with its OWN provenance,
  `itd-record-agent-skill`. Signing it as `itd-completion-signals` would be a
  forged provenance and is not done.
- `hooks/completion-gate.sh` — a layer-0 row is delegation ACCOUNTING, not a
  completion layer: `runtime_evidence_status` only reads the layers declared in
  `policy.runtimeLayers`, so a layer-0 row can never change a verdict. It is
  therefore checked for shape (`ts`, `kind`, `layer`, `outcome`, valid
  timestamp, valid layer) and exempted from provenance and runtime-field
  checks — but ONLY while the policy has not declared layer 0 a runtime layer.
  If it has, the row is judged strictly as before.
- `docs/templates/itd/itd_hygiene.py` — the identical relaxation on the
  explicit-close path. Fixing only the commit gate would leave the same defect
  live in the session-close evaluator, which reads the same ledger with the
  same rule.
- `tests/verify_completion_gate.py`, `tests/verify_strict_completion_policy.py`
  — behavioural coverage of both paths.

## Exclusions

- **`.claude/completion/signals.jsonl` is NOT edited.** The ledger is the
  evidence this defect was diagnosed from; repairing history would destroy the
  reproduction and is forbidden by `.itd/SCOPE_LOCK.md`.
- **`append_signal` does not gain a default producer.** A default would stamp
  someone else's provenance onto any writer that forgot to sign, which is
  exactly the property the evaluator exists to check. Each writer signs itself.
- **The relaxation is not "skip non-runtime layers".** It is limited to
  layer 0 and is conditional on the policy. Layer 1 keeps full strict
  validation even though it is not in the default `runtimeLayers`, so the
  change cannot silently widen into the completion layers.

## Verification standards

- RED-first: the two new gate assertions and the close assertion fail before
  the fix with the exact production error (`missing fields: producer`).
- Mutation: neutralizing the layer-0 exemption in either evaluator turns
  exactly the corresponding assertion red; neutralizing the writer's stamp
  turns the writer assertion red. Restoring returns both suites to green.
- No weakening: assertions prove that a layer-2 row without `producer`, a
  layer-2 row with a foreign `producer`, and a layer-0 row under a policy that
  declares layer 0 a runtime layer are all still denied.
