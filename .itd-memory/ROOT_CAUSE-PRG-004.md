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
phrase elsewhere. The fixture and runner preflight now require at least one
exact lowercase `unique-cardinality exhaustion` occurrence on a physical line
in the guide; additional correct occurrences remain allowed.

That repair passed the content oracle and exposed an ambient user plugin trace
during the advocate phase. A first name-only exclusion was rejected by Terra:
the untrusted model could forge the same path. The snapshot remains complete;
Claude instead loads only project settings with strict MCP configuration, so
the ambient user plugin is absent before either model phase starts.

The isolated replay reached the content oracle and exposed a formatting gap:
six semantic user stories were prose lines, while the frozen counter accepts
lines beginning `- As a `. The fixture and runner preflight now pin at least
three exact case-sensitive single-line prefixes.

The exact synthetic candidate `ad204c4` then produced live Opus PASS
`20260821T212314Z-f8630276`: all content contracts passed, the fresh advocate
completed, and strict project-only settings produced no ambient trace drift.

The authority scrubber then rejected the transparent PASS transcript on 13
opaque high-entropy tokens. Capture sanitization now redacts only mixed-case,
digit-bearing tokens of at least 48 characters whose Shannon entropy is >=4.2;
lowercase SHA/digest material remains unchanged and hash-pinnable.

Exact synthetic candidate `8a3b48b` produced the accepted replacement live
run `20260821T214723Z-163dccac`: deterministic content oracle and advocate both
passed, and the authority scrubber reports no high-entropy, residual-credential
or high-confidence-secret material in the retained transcript.

Terra r15 found the first entropy token alphabet incomplete: base64 `+/=` and
dotted opaque tokens could split below the length threshold. The closed
alphabet now covers URL-safe, base64 and dotted forms under the same
mixed-case+digit+entropy rule; runtime-built mutations keep those test tokens
out of the reviewer diff itself.

Terra r16 found that the Claude native plugin manifest failed validation
(`agents: Invalid input`). The benchmark no longer claims native plugin loading
or passes `--plugin-dir`; the prompt requires direct reads of the same
repository-local skill/reference files in the main session, which the retained
transcript can substantiate.

The expanded sanitizer was re-recorded on exact synthetic candidate `fada93b`.
Live Opus PASS `20260821T222606Z-06a059a7` passed the content oracle and
advocate, and the authority scrubber again found no high-entropy, residual or
secret material in the retained transcript.

Exact synthetic candidate `35cff8b` produced the accepted direct-file live
Opus PASS `20260821T224723Z-7c5db8da`: content oracle and advocate both passed,
and authority screening found no high-entropy, residual or secret material.
