# GPG-002 root cause — Windows doctor timeout on WSL UNC checkout

## Summary

`validate_local_adjudication()` imposed one unconditional 30-second outer
timeout. A native Windows Python cold-start plus the bounded committed-head Git
probes over `\\wsl.localhost\...` can legitimately exceed that outer budget, so
the parent killed a valid fail-closed validator and reported `UNAVAILABLE`.

## Reproduction

- Checkout: `\\wsl.localhost\Ubuntu-24.04\home\hihol\projects\idea-to-deploy`.
- Runtime: native Windows bundled Python with the required dependencies.
- Command: `itd gate doctor` against a temporary local-review registry.
- Result before the fix: exit 1 after 54.32 seconds overall; doctor drift was
  `local review: UNAVAILABLE: local adjudication validator is unavailable`.

## Evidence

- The outer subprocess timeout is hard-coded as 30 seconds in
  `skills/_shared/itd_gate_control.py`.
- The invoked Verification Loop performs several separately bounded repository
  and exact-candidate probes; it remains fail-closed on timeout or mismatch.
- A WSL-produced receipt is intentionally foreign to a Windows repository path;
  the fix must not weaken that path binding or reinterpret invalid evidence.

## Fix hypothesis

Retain the 30-second default for local/native checkouts, but use a bounded
180-second outer budget only when native Windows validates a UNC checkout,
including the extended `\\?\UNC\server\share` form. Extended local/device
paths such as `\\?\C:\repo` retain 30 seconds. The receipt, candidate, path,
risk, return-code and output-size checks remain unchanged.

## Regression test

`tests/verify_gate_profile_doctor.py` records the timeout passed to the child:
Windows UNC must receive exactly 180 seconds, while a normal POSIX checkout
must retain 30 seconds. Standard and extended UNC shares receive 180 seconds;
native drive, device/extended-local and incomplete UNC paths retain 30 seconds.
Existing stale/foreign receipt canaries must stay green.

## Verified outcome

- Focused WSL and native-Windows tests pass 25/25; profile registry tests pass
  18/18.
- The implementation merged in PR #180 as `ed33169e8cc48f6a5da314586548ee0c5e2389cd`.
- Patch release 1.95.1 merged in PR #181 as
  `1422c94d28f7a6821f0038a766437b7618cc22f1` and was installed on both
  WSL and Windows Codex/Claude hosts.
- A Windows-native high-risk machine/checker/adjudication chain bound to the
  UNC repository path passed. The installed native doctor returned
  `LOCAL_REVIEWED` with `drift=[]`, `protected=0`, version 1.95.1, and elapsed
  time 32.57 seconds.
- Clone-durable evidence is indexed by
  `.itd/GPG-002_COMPLETION_EVIDENCE.json`.
