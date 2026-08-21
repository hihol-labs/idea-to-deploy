# PRG-003 root cause — incomplete installed runtime closure

## Incident

The native-Windows source-tree doctor accepted the reviewed v1.100.1 release
candidate as `LOCAL_REVIEWED`, while the installed runtime and pre-push hook
returned `UNVERIFIED` and blocked publication.

## Root cause

`scripts/itd_install_runtime.py` enumerated entry points, manifests and all
shared Python/policy files, but omitted the path-loaded exact-context closure:
`skills/review/scripts/itd_review_cache.py`, its review skill and both review
rubrics. The first repair imported the cache module but did not execute
`candidate_context`, so the missing methodology rubric surfaced only in the
installed doctor canary. The old test executed `itd --help` and a no-input
pre-push failure; neither path reconstructed candidate context.

## Corrective action

The complete path-loaded dependency set is explicit in the closed inventory
and therefore covered by the existing per-file and aggregate hashes. The
regression executes `candidate_context` from the installed verification loop
under `-I -B`; absence now fails on both WSL and native Windows before a
release can pass.
