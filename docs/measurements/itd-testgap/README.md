# TESTGAP pilot: records and tools

Evidence and tools of the pilot `docs/measurements/ITD-PILOT-TESTGAP-PROTOCOL.md` (sections 9-11). Measurement
tools only: nothing here is wired into a hook, a skill or `tests/run-all.sh`, and nothing here is a mandatory check
(ADR-012 item 5).

| Path | What it is |
|---|---|
| `runs/run-*.json` | one record per run of 2026-11-07 (answer, score, time, tokens, isolation audit, proxy summary) |
| `s13/run-*.json` | the two runs of session 13 (canary, first baseline), counted in the budget |
| `blind-list.md`, `blind-key.json`, `blind-marks.txt` | the owner's blind list of hit candidates, its sealed key and the marks written before unblinding |
| `blind-list-H.md`, `blind-key-H.json` | the same for the held-out case H (zero candidates) |
| `k0-mutants.txt`, `m2-adjudication.json` | the manual M2 check: four mutants of the K0 candidate survive its test; every blocker of every K0 block adjudicated against them |
| `manual-adjudication.json` | the one manually adjudicated `../` (K0 baseline r3): the `cd` and the relative path, re-derived from the transcript by `pilot_check.py` |
| `pilot_run.py` | the runner: case build, one headless run, transcript audit, score (`selftest`, `nsprobe`, `reaudit`) |
| `pilot_ns.py` | the OS-level isolation wrapper and the host allowlist proxy |
| `batch.py` | at most three runs at a time, budget ceilings checked before each start |
| `blind.py` | the blind list (`make`) and the unblinding (`reveal`) |
| `k0_mutants.py` | the K0 mutant runs behind `k0-mutants.txt` |
| `pilot_check.py` | machine leg: section 10 against the records, transcripts, proxy logs and marks; `--selftest`, `--diff-scope` |
| `closure_check.py` | machine leg: the REL-1.110.6 closure by the ADR-016 convention |
| `make_evidence.py` | copies the host-only evidence (transcripts, proxy logs, canary marker) into the git-ignored machine input |

The tools carry the host paths of the pilot run (`/home/hihol/...`); they document how the pilot was run and are not
meant to run elsewhere without editing those paths. Run transcripts and proxy logs stay on the host.

Versions. `batch.py` here reserves the worst case of every running run for runs and wall time (tokens: an estimate
from the largest recorded run), refuses duplicate or already recorded items and accounts for runner failures (a runner that fails without a
record leaves a persisted worst-case `runs/charge-*.json`) (review a3 of ITD-PILOT-TESTGAP); the pilot ran an earlier version without the reservation. In the pilot
every started run left a record (`pilot_check.py` checks each START of the batch log) and the ceilings stayed far
(26 of 30 runs, 2 h 44 min of 8 h, 20.7 of 40 million tokens). `pilot_run.py` writes `tmpPaths` for every variant;
the canary runs of the pilot ran before amendment 4 introduced the field.
