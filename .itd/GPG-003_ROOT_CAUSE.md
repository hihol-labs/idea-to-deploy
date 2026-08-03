# GPG-003 root cause — split and substitutable independent-review paths

## Symptom

A project session following Idea to Deploy reported external cross-review as
`UNAVAILABLE` solely because `OPENAI_API_KEY` was absent, then offered the user
a choice to publish from local review anyway. That contradicted the approved
method: an independent fresh model must review the exact candidate before PR,
without requiring a paid API key and without a caller bypass.

## Root cause

The methodology currently exposes three conflicting contracts:

1. `itd_free_reviewer_producer.py` implements a strong isolated ChatGPT
   subscription route, but only for one OpenAI transport.
2. `/cross-review` still describes the paid Responses API as the automated
   adapter and declares local use advisory/fail-open.
3. `/review` and Verification Loop require fresh evidence but do not name one
   ordered host-neutral producer, so a host can substitute a same-context local
   review or stop at missing `OPENAI_API_KEY`.

The defect is therefore orchestration ambiguity, not the absence of a capable
free OpenAI reviewer.

## Minimal durable correction

Make the existing keyless producer the single mandatory pre-PR workflow and
extend it with ordered subscription-auth transports: fresh different OpenAI
model/session, Anthropic, then Gemini. Only typed transport unavailability may
advance the route. Findings, unverified output and identity/isolation failures
stop fail-closed. All three skills/contracts consume the same producer outcome;
paid API review remains separately named and never an automatic fallback. Each
pinned fallback transport must also prove that its installed CLI advertises the
exact invoked isolation and provenance arguments before it can review.

## Trust boundary

The honest host orchestrator may copy only validated subscription/OAuth
material into a private ephemeral transport home. The model receives only the
scrubbed exact candidate packet and has no tools, repository access, inherited
history or environment access. Receipts prove integrity/process and real
host-observed provenance; they do not claim cryptographic model identity or
same-principal Byzantine resistance.

The phase-one receipt binds the complete closed attempt ledger into its signed
payload. The ledger must be the exact prefix of `OpenAI -> Anthropic -> Gemini`:
every preceding entry is typed `UNAVAILABLE`, the final entry is `PASSED`, and
the final provider equals the signed reviewer provider. Missing, reordered,
skipped, duplicated, foreign, or differently typed entries are `UNVERIFIED`.
The broker independently revalidates this signed ledger before it may request
App authentication or authorize publication evidence.

The first route-ledger repair review exposed a second orchestration gap:
Verification Loop could mint a generic checker receipt from an independently
narrated JSON report, and the local publication doctor accepted the resulting
adjudication without proving that the mandatory producer ran. The durable
bridge now binds the producer-emitted phase-one v2 receipt, exact prompt,
canonical report, trusted producer keyring, candidate, provenance, and machine
receipt into checker evidence. Generic checker receipts remain useful for
non-publication diagnostics, but local-submission validation explicitly
requires the mandatory route and fails closed before guarded push. The same
repair closes the verdict object instead of defaulting a missing `unverified`
field and corrects the deployed broker keyring example to its actual
three-provider `reviewerModels` schema.

Native Windows parity then exposed one final representation defect: the same
temporary evidence root could be returned under both its long Unicode user
name and a DOS 8.3 alias. Lexical containment therefore rejected authentic
phase-one dependencies. The correction accepts that alias only after an
existing ancestor has the exact filesystem identity of the trusted evidence
root, rejects symlink/reparse traversal before reconciliation, and rebuilds
the accepted path under the trusted spelling. Producer artifacts are written
as byte-exact UTF-8 on both hosts so signed prompt hashes do not acquire a
Windows-only CRLF transformation.

The first real post-repair producer invocation also showed that ordinary
developer hosts without an HTTP proxy were classified as `UNAVAILABLE` before
the subscription CLI could run. Proxy absence is now an explicit closed
transport state: both proxy variables must be absent and that absence is bound
by the SHA-256 of the empty pair. A partial, additional, or changed proxy
configuration remains `UNVERIFIED`; the isolated native subscription CLI is
the only network-capable process and the reviewing model still has no tools.

That live invocation returned a genuine `BLOCKED` verdict and exposed an
evidence-availability flaw: the route raised its typed stop before writing the
reviewer's actionable findings. A valid negative report now travels only as
typed diagnostic evidence, persists its exact prompt/report plus observed
reviewer and attempt prefix, and still cannot be signed as phase one. Malformed
or transport-level failures remain non-persistable and fail closed.

The recovered independent report then found that local mandatory-route
validation compared the phase-one diff only when `baseCommit` happened to
equal `parentCommit`. A correctly signed but substituted base could therefore
skip exact-range comparison. The consumer now proves base-to-parent ancestry,
reconstructs the full binary diff from that signed base to the exact staged or
committed candidate, and compares both SHA-256 and byte count before accepting
checker evidence.

The next exact Terra review found that adapters still copied requested model
arguments into reviewer provenance. A provider/CLI fallback could therefore
be signed as the intended different model. Each route now derives the model
only from pinned runtime telemetry and requires it to match the requested
approved model or closed Claude alias. Codex writes one rollout inside a fresh
temporary auth home solely so the producer can bind its `session_meta` and
`turn_context.model`; that home is destroyed immediately afterward. Claude
uses its single `modelUsage` key and Gemini its init-event model. Missing model
telemetry is `UNAVAILABLE`; multiple, foreign, or changed values are terminal
`UNVERIFIED`.

## Publication follow-up

The first guarded update of an amended Draft exposed a separate availability
defect: `create_draft_pr` imposed a fixed 300-second timeout on `git push`, but
the pre-push hook intentionally reruns the full machine contract and can take
longer. The completed preflight was green, the push process was terminated at
that fixed boundary, and the remote SHA remained unchanged. The correction
passes the existing positive `itd pr create --timeout` value into the guarded
push, bounded to 300..3600 seconds. It does not remove, shorten, or bypass any
hook validation.

The retry exposed a second publication ambiguity: `pr_view` mapped every
nonzero `gh pr view` result, including TLS/auth/GraphQL failures, to "no PR".
That selected an ordinary non-fast-forward push for an existing amended Draft,
so Git supplied no valid update stream and the pre-push hook blocked it. The
closed correction recognizes only the exact CLI no-PR diagnostic; every other
lookup failure stops before choosing a push mode.

The installed GitHub CLI also requires an explicit branch argument whenever
`gh pr view` is combined with `--repo`. Omitting it produced a usage error that
the old ambiguity had hidden. The lookup now derives the current symbolic Git
branch, validates it, and binds both branch and repository in argv before it
may classify the result.

The first review of that binding found that the accepted no-PR diagnostic was
still branch-agnostic and whitespace-normalized. It is now compared to the
exact validated branch, rejects quotes in that coordinate, forbids surrounding
whitespace, and permits only no line terminator, LF, or CRLF.
