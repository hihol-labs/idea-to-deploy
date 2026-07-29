# Forbidden Changes — GPG-001

These changes remain blocked unless the user explicitly changes the approved
scope:

- commit, log, prompt, persist, or install any API key or GitHub App private key;
- execute candidate code in a process that can read reviewer credentials;
- let an OAuth/CLI reviewer or an unbound same-name check satisfy the cloud gate;
- turn API outage, zero balance, missing provenance/oracle, stale SHA/base,
  oversized input, `neutral`, or `skipped` into success;
- silently truncate candidate evidence or accept caller-supplied cost/status;
- weaken WIP=1, exact-candidate binding, maker/checker separation, App-bound
  checks, human merge authority, or the Verification Loop;
- edit an installed plugin cache instead of releasing a new ITD version.
