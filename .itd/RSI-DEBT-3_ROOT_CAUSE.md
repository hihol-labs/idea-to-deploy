# RSI-DEBT-3 Root Cause

Recorded: 2026-09-14

## Summary

`itd_goal_verify.py` executes a complete `A && B` verification command as one
opaque `sh -c` process and reduces the combined output to one decisive final
line. That discards both top-level command boundaries before unit and event
evidence are written. The shared 200-character evidence cap would also truncate
the required two-line summary even if those boundaries were recovered.

## Reproduction

Run the pre-fix regression suite:

```sh
sh skills/_shared/itd_py.sh tests/verify_goal_tools.py
```

On the merged `e97fc7c` implementation it reports `72 passed, 5 failed`. The
compound success stores only `exit 0: <B last line>`, and the compound failure
stores only `exit 7: <A last line>`.

## Evidence

- `cmd_verify` invokes the entire string through one
  `subprocess.run([sh, "-c", command])` call.
- `decisive_line(output)` selects only the last non-empty line.
- The result is formatted once as `exit <rc>: <last line>` and sliced to
  `EVIDENCE_MAX == 200` before it reaches the unit or terminal event.
- RED-first behavioural checks fail for ordered per-command evidence, exact
  terminal-event repetition, a quoted `&&`, same-shell state, and the executed
  command's failure summary. The existing single-command form and shell
  short-circuit checks remain green.

## Fix Hypothesis

Detect only unambiguous top-level `&&` boundaries, then run an instrumented
AND-list once in the same POSIX shell. Capture stdout, stderr, and exit status
for each executed top-level command without spawning one shell per leg. Format
compound evidence from those records with a separate bounded capacity while
leaving the legacy single-command path and its 200-character cap unchanged.
If the parser cannot prove the boundary shape, execute the original command by
the legacy path rather than guessing.

## Regression Test

`check_compound_verification_evidence` in `tests/verify_goal_tools.py` covers:

- exact ordered evidence and stdout digest for both successful commands;
- exact equality between unit evidence and the terminal event;
- the legacy single-command form and 200-character cap;
- quoted `&&` handling and same-shell variable state;
- `&&` short-circuiting and failure evidence for only the executed command.

## Constraints

- Preserve the sealed criterion and verification command.
- Preserve existing single-command output byte-for-byte.
- Do not execute a compound command twice or run each leg in a separate shell.
- Keep accepted historical evidence immutable.
- Run every mutation in a disposable worktree, one guarantee per mutation.

## Resolution (2026-09-15, measured)

The sections above describe the pre-fix state and are kept as history. What
shipped, with the numbers taken from runs rather than from the plan:

- `split_top_level_and` models exactly one shape - segments joined by
  top-level `&&`, with single/double quotes and backslash escapes tracked -
  and returns `None` for anything else at top level (`|`, `||`, `;`, a lone
  `&`, `(`, `)`, a backtick, `<<`, an unquoted `#`, a newline, an unterminated
  quote, a trailing backslash). The ONE `&` it accepts outside `&&` is a
  descriptor duplication `>&` / `<&` (`2>&1`), because refusing that pushed
  the most common real chain back to the one-line record. `None` keeps the
  legacy single-line path byte-for-byte. Refusing records less; guessing would
  put a command in the ledger nobody executed as written - and `#` is the
  measured case: an unquoted comment swallows an `&&` after it, so a split
  there would RUN and RECORD a leg the shell never executes.
- `compound_script` runs the whole chain in ONE `sh -c`, each command inside a
  `{ ...; }` group redirected to its own `N.out` / `N.err`, its status written
  to `N.rc`, and every following command nested in `if [ "$__itd_rc" -eq 0 ]`.
  Same shell, so `A && B` keeps whatever state A leaves; nesting, so `&&`
  short-circuits as it always did. Capture paths go through env vars as
  `Path(mkdtemp).resolve().as_posix()` - the resolved form for the Windows
  8.3 shape, the posix form for Git Bash redirects.
- `run_compound_verification` reads the records back in order. A command with
  a status file gets `<command>: exit <rc>, stdout sha256 <16 hex>, <last
  line>`; the last line is `decisive_line(stdout + stderr)` capped at
  `EVIDENCE_MAX`, because that is the only part of a line that can grow
  without bound. A non-zero status stops the walk - the rest never ran. A
  command WITHOUT a status file after a successful predecessor is one the
  shell started and did not finish: it is recorded with the shell's exit code
  (`124` and `timeout after Ns` on timeout, otherwise `shell exited <rc>
  before the command completed`) and the unit does not verify.
- `clamp_evidence` caps a single-line record at 200 as before and stores a
  multi-line record whole; both event writers use it instead of the raw slice.

### Defect found while proving it, not while planning it

The first version of the missing-status branch read `if not timed_out: break`
- "no status file and no timeout means the command never ran". Mutating that
guard SURVIVED, and the reason was not a weak test: the branch was dead. After
a failed command the walk already stops on `rc != 0`, so a missing status
file after a SUCCESSFUL predecessor can only mean the shell started the
command and went away before writing the status. In that case the old code
broke out of the loop with `rc` still `0` from the predecessor, and the unit
VERIFIED on a chain that never finished. The fixture `A && exit 3` reproduces
it deterministically (the group `exit` ends the shell before its `printf`) and
is now a RED check killed by M9.

### Mutation table (final run, disposable worktree, baseline 83/0, 42/0)

Each mutation edits one point and is quoted with the checks it killed; the
file is restored from the pristine candidate after each run, and the worktree
status is compared with the live tree at the end (`identical`). Twelve
lethal, none surviving; M10 is listed because it was run, and removed.

| # | Guarantee attacked | Result | Killed |
|---|---|---|---|
| M1 | event writer stores a multi-line record whole | LETHAL 81/2 | terminal event repeats unit evidence; unfinished leg |
| M2 | splitter tracks quotes | LETHAL 76/7 | one line per command; terminal event; quoted `&&`; failure names executed command; tail cap; unfinished leg; `2>&1` |
| M3 | commands share one shell (`( )` instead of `{ }`) | LETHAL 81/2 | same-shell state; unfinished leg |
| M4 | walk stops after a failed command | LETHAL 82/1 | failure evidence names only the executed command |
| M5 | shell chain short-circuits | LETHAL 82/1 | `&&` short-circuiting |
| M6 | a single command keeps the legacy form | LETHAL 81/2 | legacy form; legacy 200 cap |
| M7 | a compound line caps its last output line | LETHAL 82/1 | tail cap |
| M8 | unmodelled operators are refused, not split | LETHAL 82/1 | legacy form kept for a pipe |
| M9 | an unfinished leg cannot inherit a zero | LETHAL 82/1 | unfinished leg is not verified |
| M10 | shell exit code re-applied after the walk | SURVIVED 80/0 (earlier run) | removed as redundant, see below |
| M11 | an unquoted `#` is refused | LETHAL 82/1 | commented leg never runs, legacy form kept |
| M12 | `>&` is a redirection, not a control operator | LETHAL 82/1 | `2>&1` chain records two lines |
| M13 | a trailing backslash is refused | LETHAL 82/1 | legacy form kept instead of a split |

M10 survived because the block was redundant: every case where the shell's
exit code is non-zero already yields the same `rc` through the failed
command's own status or through the missing-status branch (M9). The block was
REMOVED, not kept as prose. The one window it would have covered - the shell
dying after the last status file is written and before its own `exit` - has
no deterministic fixture and is declared as a limit in the code comment.

### Independent review (in-house, code-reviewer subagent, whole unit vs main)

Verdict `PASSED`, two minor findings, four unverified items - recorded as
returned, then measured:

- Minor 1: a multi-line record has no explicit byte ceiling. Correct as
  stated; the bound is by construction (sealed command text + one capped line
  per leg), and it is the declared design above rather than an omission.
- Minor 2: `{}`/`exit`-containing legs were read, not executed, by the
  reviewer. `exit` IS executed by the `A && exit 3` fixture (M9). An unquoted
  `}` inside a leg is an ordinary argument to the shell unless it stands in
  command position, which a leg without `;` or newline cannot reach.
- Unverified 1-4 (records vs code, scope-lock forbidden areas, the exact check
  list, live `{}`/`exit` runs): the first three are what the cross-vendor
  producer run over the whole unit is for; the fourth is covered by M9's
  fixture. The reviewer's own question "can any input be split wrongly" was
  then answered by hand: the `#` case above was a real hole and is closed
  RED-first-by-mutation (M11); `2>&1` was a false refusal (M12).
- The review took three resumptions to produce a report (turn limit), the
  same route defect as in the ROUTE-REPAIR-2 session.

### Mirror, attributed

Candidate before the map regeneration: `DONE fails:
verify_verification_profiles verify_reviewer_provider_freshness
verify_ledger_reconciliation verify_mandatory_keyless_review`. Pristine
`e97fc7c` in a separate clean worktree: `DONE fails:
verify_reviewer_provider_freshness verify_ledger_reconciliation
verify_mandatory_keyless_review blocked: verify_independent_review_efficacy`.
The difference is one suite, `verify_verification_profiles`, whose failing
check reads `the committed map is fresh against the tracked tree (regenerate
to fix)`: `.itd/IMPACT_GRAPH.json` drifted when `tests/verify_goal_tools.py`
changed. Regenerated with `tests/build_impact_graph.py` (`FRESH`). Final
candidate mirror: `DONE fails: verify_reviewer_provider_freshness
verify_ledger_reconciliation verify_mandatory_keyless_review` - the pristine
set and nothing else.

### Declared limits

- The post-status race above.
- `.resolve()` on the capture root is only exercised on native Windows; no
  local oracle and no mutation can see it, the `windows-verify` CI leg is the
  only witness (two occurrences in ROUTE-REPAIR-2 made this a class).
- The splitter is not a shell parser. A `verificationCommand` that needs
  `;`, `|`, `#`, subshells or substitutions keeps the legacy one-line
  evidence, by design; making that command's legs visible means rewriting it
  as a plain `&&` chain, not extending the parser. `2>&1` is the one
  redirection form accepted because it is measured to be common; `&>` is
  bash-only and stays refused.
