# Task Contract — COMPLETION-SUPERSEDE-1 completion gate: a red superseded by a later green record

- **Root cause:** the completion gate knows a run only by the text of its Bash call. `_layer_status`
  keeps the latest run PER COMMAND TEXT, so the red of a one-off call (a RED-first run in a scratch
  copy, a `/test` Step 5.5 mutation run, the same oracle behind another pipe) is never overwritten by
  a later green run of the same oracle under another text; the strict path
  (`runtime_evidence_status`) counts every red of the session. The runner `skills/_shared/itd_py.sh`
  ends in `exec` and leaves no trace of what ran, where and with which exit code. COMPLETION_BYPASS
  was needed on every commit of COMPLETION-FALSE-RED-1 (48a4431, 354e8f9, 2b782f8, d910535) and on
  four of five commits of TIER-WORDING-2 and STOPRULE-STUB-1 (BACKLOG P2 2026-10-01 item b).
- **Fix (owner decision A/B of 2026-10-02, criterion approved by the owner 2026-10-02):** execution
  evidence instead of parsing the command text.
  - Runner: opt-in `ITD_RUN_RECORD=1 sh skills/_shared/itd_py.sh <script> [args]` goes through
    `skills/_shared/itd_run_record.py`. It runs the same command with the same interpreter and
    the content of stdout and stderr passed on unchanged (each stream through its own pipe: the
    relative order of the two streams and isatty are not kept), returns its exit code, forwards SIGTERM/SIGHUP, writes
    `<records dir>/<id>.json` `{id, script, args, cwd, rc, isolated, python, lines}` (script = path
    relative to the run directory, lines = the tail of the run's own output) and adds one stderr
    line `ITD-RUN <id>`. Without the variable the launch is the previous `exec`. The variable is
    removed from the environment of the wrapped command (nested runner calls are not recorded). A
    record that cannot be written means no `ITD-RUN` line.
  - Hook (`hooks/completion_lib.py`): `match_run_record` attaches the record to the signal only when
    exactly one `ITD-RUN <id>` line is in the output the hook observed, the record file exists and is
    well-formed, and EVERY observed line is a line of the recorded run (no more often than the run
    printed it) or one exit echo equal to the recorded code - order-free, because stdout and stderr
    of a call arrive separately; the output of any other command of the same call, before or after
    the run, unbinds the record (/review r1 finding 2). The record file is deleted on the match (a replayed id finds nothing). The signal outcome is computed
    as before.
  - Judgement: `counted_signals` drops a red signal with a record (`rc != 0`) when the LATEST recorded
    signal of the same invocation (script, args, isolated mode, interpreter, layer - /review r1
    findings 1 and 3) is a pass with `rc == 0` that ran in the project root on the
    current HEAD; a run id repeated inside the ledger is not a second record. `compute_verdict` and
    the strict path of `hooks/completion-gate.sh` judge the counted signals. Superseding only removes
    a red: the pass of the layer is the pass signal of the green run itself.
- **Accepted residual (owner, 2026-10-02):** a deliberately forged record (the file and the output
  forged together). The gate catches a mistake, not intent; forging a record equals a bypass without
  a reason and is not a review blocker.
- **Stated limits:** a command of the same call that prints nothing is invisible to the gate before
  and after the fix; the environment variables of a call are not part of the invocation identity; an
  output cut by characters (`cut -c`) or down to the `ITD-RUN` line alone (`| tail -1`) does not bind
  or does not give a pass - the safe side; so does an uncut output longer than 400 lines per stream
  and `ITD_RUN_RECORD_DIR` set for the Bash call only. Binding is by membership of lines, not by
  equality of the output: a foreign command that prints exactly a line of the run is not told apart.
  Rule of use: one recorded run per Bash call. /review r2 PASSED_WITH_WARNINGS (5 minor, fixed).
- **Sol s1 BLOCKED (4 findings, fixed):** the superseding green must name the current HEAD and the
  project must have one (no fail-open on a missing HEAD); the records directory is 0700 and a record
  0600; a record is consumed by the first call that shows its id even when the binding fails; lines
  are compared character for character (only exactly empty lines are skipped).
- **Sol s3 BLOCKED (4 findings, fixed; s2 had no verdict - the producer died with the session):**
  the exit echo is at most three digits, so a long digit run never reaches `int()`; empty lines stay
  skipped on purpose (the host joins stdout and stderr with a newline), pinned by a check, and a
  command that prints only empty lines equals a silent one; the oracle now checks that both records
  of a two-id call are consumed and covers corrupted record files and every missing or mistyped field.
- **Verification Standards:** the unit verificationCommand exits 0; the new oracle
  `tests/verify_completion_supersede.py` is RED on the pre-fix code (21 failed, 62 passed; log
  `.itd-memory/verification-loop/reports/COMPLETION-SUPERSEDE-1-red-first.log`) and GREEN after (83
  passed); `--mutations` kills every mutant; `tests/verify_completion_gate.py`,
  `tests/verify_completion_adversarial_corpus.py` and `tests/verify_completion_false_red.py` stay
  green; high route - `/review`, full independent checker, Sol pre-PR.
- **Exclusions:** `outcome_from` and its regexes, every veto of the gate, `strip_expected_exit`, the
  signals hook, the default (unrecorded) launch of the runner, `docs/templates/itd/itd_hygiene.py`
  (the session close does not read records - BACKLOG), any judgement from the command text.
