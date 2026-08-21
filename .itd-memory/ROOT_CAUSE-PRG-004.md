# PRG-004 root cause — Codex live write-boundary ambiguity

## Incident

Current-tree live runs loaded the repository-local blueprint skill but created
none of the six required documents. Codex command-safety rejected several
multi-statement PowerShell commands; the models then narrated that the entire
workspace was read-only without a native file-edit denial.

## Root cause

The fixture required files to be written but did not name the Codex-native
write boundary. The model was free to substitute shell writes or infer global
filesystem state from a command-policy rejection. Recovery repeated the same
ambiguity, so two-attempt bounded runs correctly failed.

## Corrective action

The live prompt requires `apply_patch`, forbids PowerShell write substitution,
and defines the only acceptable read-only evidence. The runner rejects a
fixture that omits the directive before dispatch; a temporary-fixture mutation
executes that real preflight. Acceptance still requires a real current-tree
live PASS rather than prompt inspection alone.
