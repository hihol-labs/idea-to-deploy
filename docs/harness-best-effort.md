# Harness-native features — best-effort invariant (topic-док)

> Вынесено из глобального CLAUDE.md-блока (v1.74.0, retro 2026-07-10:
> SNR-сигнал 1/5 типов задач + A/B-паритет сжатия). Поведенческие правила
> остались в entry-блоке (`docs/templates/global-claude-md.md`); здесь —
> полный контракт и rationale. Enforced-by: `hooks/pii-egress-guard.sh`
> (egress-часть) + реестр `docs/instruction-registry.json`.

The CLI harness (Claude Code / codex / gemini) ships vendor-specific tools
(typed tool-calls, chips, artifacts, background agents, transcript search).
Standing rule for ALL of them:

- **Best-effort layer only.** A harness-native feature may TRANSPORT a
  methodology contract, never BE the contract. No gate, no `verified`
  transition, no handoff may depend on the presence of a specific tool-call —
  the contract stays vendor-neutral (text/JSON in the transcript, files in the
  repo), so it survives a vendor or version switch. A harness feature silently
  disappearing must degrade to the neutral path, not to a false "all green".
- **Egress + mutation guard.** Anything that leaves the machine (web publish,
  artifact upload, transcript mining to an external model) goes through the
  cross-review-grade secret scrubber AND explicit human confirmation. Anything
  that mutates durable state (prod data, `MEMORY.md`, ledgers) from a harness
  feature follows the data-sensitive gate: read-only diff → human approve →
  apply. Background/scheduled harness agents are read-only reporters; they
  never commit, push, or edit files unattended.

Связанные артефакты: реестр решений по харнесс-фичам —
`docs/FABLE5_FEATURE_LEDGER.md` (adopt/abstain per фича, ре-review абстенций —
`/retro` Step 1b); живой пример деградации — completion gate
(`docs/completion-gate.md`): нет леджера сигналов → advisory, не ложный green.
