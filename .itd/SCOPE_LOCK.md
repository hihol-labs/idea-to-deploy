# Scope Lock — U-NTFS-DIRSIZE: directory st_size out of the guarded-fallback identity

## Current Task

Close unit U-NTFS-DIRSIZE: on NTFS the `st_size` of a *directory* is not a
stable observation, so the guarded plain-stat fallback of the Verification
Loop treated an unchanged tree as mutated. Two consecutive scans of the same
untouched checkout disagreed on 1964 of 1964 directories (observed values
4096 | 8192 | 12288 | 32768 collapsing to 0). The fix removes directory
`st_size` from the identity tuple in both plain-stat identity builders and
pins the behaviour with a regression test. Regular-file `st_size` stays in
the identity: only the directory component is unstable.

## Allowed zones

- `skills/_shared/itd_verification_loop.py` — `_plain_source_identities` and
  `_plain_ancestor_identities` only; directory entries drop `st_size` from
  their identity tuple, every other identity component is unchanged.
- `tests/verify_verification_loop.py` — one added regression case proving a
  directory-size-only change is not an identity change.
- `.itd/SCOPE_LOCK.md` (this contract, rewritten for the unit).
- `.itd/ACCEPTANCE_CONTRACT.json` — `activeFollowup.unitId`, plus this unit's
  own `U-NTFS-DIRSIZE-AC1..AC8` acceptance criteria appended to `criteria`, as
  every prior unit of this contract is shaped. The review policy, its
  `riskTier`, the required impact classes, the reviewer minimum, the 40
  GPG-001..GPG-004 criteria and `doneRule` are byte-identical.

Untracked/ignored local stores written alongside (not part of the git
candidate): `.itd-memory/verification-loop/*` receipts, prompts and reports.

## Acceptance (this unit)

1. Targeted oracle: `python3 tests/verify_verification_loop.py` exits 0 with
   83/83 cases, including the added directory-size regression case.
2. Repository oracle: `bash tests/run-all.sh` reports `DONE fails:none` — no
   suite that was green before the candidate is red after it.
3. Mutation proof (executed oracle `directory-size-mutation-proof`): restoring
   directory `st_size` into the identity makes the targeted suite fail — the
   test is bound to the defect, not to the implementation shape.
5. Every one of the 12 `requiredImpactClasses` is carried by a criterion whose
   `oracleIds` name real machine runs that exit 0 on the exact reviewed tree;
   the four unit-specific oracles (targeted suite, mutation proof, 2000-
   directory scale/performance scan, fixed-arity/integer identity probe) run
   entirely outside the reviewed checkout and mutate nothing in it.
4. The candidate touches no file outside the allowed zones, and the two code
   hunks change identity composition only — no traversal, ordering, hashing,
   guard, or error-handling behaviour is altered.

## Risk tier

high — inherited unchanged from `activeFollowup.reviewPolicy.riskTier`. The
edited module is the identity oracle of the Verification Loop itself: a
weakened identity would let a mutated tree pass as unchanged, so the unit
keeps the full evidence-first policy (one independent reviewer, the complete
required impact-class union, isolated-machine-oracle explorer, sealed-host-
union adjudicator). The tier is not lowered because the diff is small.

## Out of scope

Any other NTFS/host-parity difference; `st_mtime`/`st_ctime` granularity; the
guarded-fallback selection logic itself; the GPG-004 ladder units (its
criteria and `doneRule` stay untouched, and `activeFollowup` is temporarily
pointed at this unit); the gate registry `~/.config/itd/gates.json`; any
branch or checkout other than `fix/ntfs-directory-size-identity` in
`/tmp/itd-wt-ntfs`.
