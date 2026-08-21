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

The supported Claude transport has a separate boundary: its native `Skill`
tool forks without the non-interactive product brief. The prompt therefore
requires direct main-session execution of the same local skill/reference with
built-in Write/Edit; runner preflight and a second fixture mutation pin it.
The live replay then exposed the transport root: the multiline product prompt
was truncated by the Windows `.CMD` positional-argument path. Claude now reads
that prompt from stdin; a direct `run_candidate` test pins stdin bytes and the
absence of the prompt from argv.

The first stdin run created all required outputs and exposed the final host
boundary: `verify_snapshot.py` printed a Unicode failure marker through cp1251
and crashed before returning its content verdict. Live and immutable reverify
paths now share one oracle helper with `PYTHONUTF8=1`, explicit UTF-8 decoding
and replacement-safe diagnostics.

With diagnostics visible, Opus missed the case-sensitive content contract by
capitalizing the only one-line occurrence and line-wrapping the lowercase
phrase elsewhere. The fixture and runner preflight now pin one exact lowercase
single-line `unique-cardinality exhaustion` occurrence in the guide.
