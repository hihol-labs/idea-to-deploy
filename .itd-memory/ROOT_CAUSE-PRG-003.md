# PRG-003 root cause — incomplete installed runtime closure

## Incident

The native-Windows source-tree doctor accepted the reviewed v1.100.1 release
candidate as `LOCAL_REVIEWED`, while the installed runtime and pre-push hook
returned `UNVERIFIED` and blocked publication.

## Root cause

`scripts/itd_install_runtime.py` enumerated entry points, manifests and all
shared Python/policy files, but omitted
`skills/review/scripts/itd_review_cache.py`. The omission was invisible to the
old runtime test: it executed `itd --help` and a no-input pre-push failure, but
neither path called `itd_verification_loop._review_cache_module()`.

## Corrective action

The dependency is explicit in the closed inventory and therefore covered by
the existing per-file and aggregate hashes. The regression executes the
installed verification-loop loader under `-I -B`; absence now fails on both
WSL and native Windows before a release can pass.
