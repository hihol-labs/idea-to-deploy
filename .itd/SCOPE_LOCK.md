# WIN-TESTQUOTE-1

Current unit `WIN-TESTQUOTE-1`, low risk, activated by the goal harness on 2026-09-22 over
`origin/main` `97cc1290` (release v1.105.0). Opened because the Windows native canary of
`REL-1.105.0` (now `blocked`) failed on a test-only defect. The criterion and the
verificationCommand live ONLY in `.itd-memory/GOAL.json`; this file references them and does
not restate them. Review claim ids: `WIN-TESTQUOTE-1`, `WIN-TESTQUOTE-1:general-review`.

## In scope

- `tests/verify_verification_loop.py`: one helper `interpreter_oracle()` replacing the three
  `json.dumps(sys.executable)` oracle commands, plus the RED-first regression block
  (`WIN-TESTQUOTE-1` checks: fixed quoting green through the transport on an interpreter
  alias under a non-ASCII directory, old quoting red on it, static guard).
- `.itd/SCOPE_LOCK.md` (this file); canonical unit ledgers written by the goal harness.

## Required evidence

- The unit's verificationCommand exits 0 (suite green on WSL, zero `json.dumps(sys.executable)`
  sites).
- Mutation: restoring `json.dumps(sys.executable)` at any one site makes the suite red.
- Native Windows: the suite exits 0 in `C:\itd-src\idea-to-deploy` on this candidate tree,
  under the owner's interpreter `C:\Users\Дмитрий\...\python.exe` (the failing host).
- `sh skills/_shared/itd_py.sh tests/meta_review.py` exits 0; `bash tests/run-all.sh --quick`
  ends with `DONE fails:none`.

## Forbidden

- Any change under `skills/`, `hooks/`, `scripts/`, `agents/`; any other test file; the sealed
  oracles of `REL-1.105.0` or this unit; touching the release, the tag or the installed runtime.
- Continuing `REL-1.105.0` in this candidate: its ledger-close package is parked in the git
  stash and returns only after this unit is merged.
