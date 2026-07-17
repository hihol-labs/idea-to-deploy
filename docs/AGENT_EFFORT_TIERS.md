# Per-role effort tiers for the subagents (v1.52.0)

Each agent in `agents/*.md` carries an `effort` value in its frontmatter — the reasoning-budget dial, **orthogonal to `model`**. Before v1.52.0 most agents sat at `high` (8 of 10; `doc-writer` and `ux-reviewer` were already `medium`): little cost differentiation, and cheap gather/mechanical roles burned nearly the same budget as the hard verify/judge ones. Release B calibrates them by role class.

## The principle

- **`high`** — hard verify / judge / design / deep analysis. The output gates quality or requires holding a lot of structure in mind at once; a wrong answer is expensive downstream, so spend the budget.
- **`medium`** — gather / advise / review-with-evidence. Reads and synthesizes, but does not itself gate code or hold a whole design.
- **`low`** — mechanical transformation. The shape of the answer is largely determined by the input.

When in doubt, err one tier **up** for anything whose output feeds a gate (tests, security, review). `effort` is independent of `model`: a `haiku`+`low` role is cheap on both axes; an `opus`+`medium` role is a strong model on a bounded task.

## The table

| Agent | Role class | model | effort |
|---|---|---|---|
| `code-reviewer` | verify (gates quality) | sonnet | **high** |
| `security-reviewer` | verify (gates security) | opus | **high** |
| `devils-advocate` | judge (adversarial) | opus | **high** |
| `architect` | design (deep structure) | opus | **high** |
| `perf-analyzer` | deep analysis | sonnet | **high** |
| `test-generator` | generate (feeds a gate) | sonnet | **high** |
| `researcher` | gather / recommend | sonnet | medium |
| `business-analyst` | gather / advise | opus | medium |
| `ux-reviewer` | review-with-evidence | sonnet | medium |
| `doc-writer` | mechanical write | haiku | **low** |

Rationale for the v1.52.0 changes (the rest were already correct):

- `doc-writer` **medium → low** — writing shaped by the code it documents; the least open-ended role.
- `researcher` **high → medium** — gathers evidence and recommends; read-only, does not gate code.
- `business-analyst` **high → medium** — market/persona/competitor analysis; advisory, read-only.
- `test-generator` stays **high** on purpose — it is generative, but its output is the test suite that gates everything else, so under-thinking there is a false green.

## Per-call override

The frontmatter value is the sensible default. A per-call override may always move
effort upward. Automatic `effort=low` is narrower: it is valid only inside an active
low/medium-risk `working_deadline` unit for a bounded mechanical slice whose
description begins `[itd:mechanical]`. Protected review, security, root-cause,
architecture and gate-producing roles retain `high`; high-risk or unknown-risk work
fails out of the automatic low route. `hooks/model-policy.sh` emits a host-native ASK
instead of silently accepting a nonconforming downgrade.

Effort is orthogonal to verification: changing it cannot remove any required
evidence contour. Speed or credit multipliers are not a methodology contract;
calibration uses host-observed telemetry and a frozen A/B comparison.
