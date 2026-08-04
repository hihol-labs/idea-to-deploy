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

Make the existing keyless producer the single mandatory pre-PR workflow for
medium/high/unknown risk: exactly one fresh opposite OpenAI model/session,
`Sol -> Terra` or `Terra -> Sol`. `BLOCKED`, `UNVERIFIED`, and `UNAVAILABLE`
all stop publication. Anthropic, GitHub Copilot, and Antigravity remain optional
manually selected tools and are never automatic fallbacks or quorum members.
Low-risk work remains machine-only. All three skills/contracts consume the same
producer outcome; paid API review remains separately named and is never an
automatic fallback.

## Trust boundary

The honest host orchestrator may copy only validated subscription/OAuth
material into a private ephemeral transport home. The model receives only the
scrubbed exact candidate packet and has no tools, repository access, inherited
history or environment access. Receipts prove integrity/process and real
host-observed provenance; they do not claim cryptographic model identity or
same-principal Byzantine resistance.

The phase-one receipt binds the complete closed attempt ledger into its signed
payload. The mandatory ledger contains exactly one `openai-subscription` entry.
It is `PASSED` only for a fresh opposite Sol/Terra identity; `UNAVAILABLE`,
`BLOCKED` and `UNVERIFIED` stop publication without an automatic fallback.
Missing, duplicated, foreign or differently typed entries are `UNVERIFIED`.
The broker independently revalidates the selected ledger state machine before
it may request App authentication or authorize publication evidence.

The first route-ledger repair review exposed a second orchestration gap:
Verification Loop could mint a generic checker receipt from an independently
narrated JSON report, and the local publication doctor accepted the resulting
adjudication without proving that the mandatory producer ran. The durable
bridge now binds the producer-emitted phase-one v2 receipt, exact prompt,
canonical report, trusted producer keyring, candidate, provenance, and machine
receipt into checker evidence. Generic checker receipts remain useful for
non-publication diagnostics, but local-submission validation explicitly
requires the mandatory route and fails closed before guarded push. The same
historical repair closed the verdict object instead of defaulting a missing
`unverified` field and corrected the then-deployed broker keyring example to
its then-current three-provider `reviewerModels` schema. ADR-006 supersedes
that route with the single opposite-GPT model pair.

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
uses its single `modelUsage` key and Antigravity its JSONL runtime model. Missing model
telemetry is `UNAVAILABLE`; multiple, foreign, or changed values are terminal
`UNVERIFIED`.

The final exact candidate then exposed a recurrence of the earlier transparent
evidence boundary in the new keyless path. The required live-model benchmark
stores its sanitized transcript as `transcript.jsonl.gz`; the central broker
already had a strict logical representation for that format, but the local
producer rejected every Git binary patch before invoking the independent
model. The correction reuses the broker's frozen policy and canonical diff
algorithm for that one suffix. It enumerates the complete staged base/index
object set with renames disabled, verifies each raw Git blob SHA, binds modes,
sizes, logical hashes and the complete raw-diff hash/byte count, then reviews
strictly decoded JSONL. Generic binaries, multiple/incomplete gzip members,
invalid UTF-8/JSONL, duplicate keys, non-standard constants, empty records,
oversize input and scrub findings remain terminal. Phase one also recomputes
the prompt from the frozen packet before signing, preventing caller-side prompt
substitution.

The first review of that correction reported that an empty non-`PASSED`
verdict could be signed. The claim was refuted against the exact producer:
`_clean_report` already rejects every verdict other than `PASSED` after its
closed-schema check. Dedicated mutation cases now pin empty `BLOCKED`,
`PASSED_WITH_WARNINGS`, and the invalid `UNVERIFIED` verdict so this invariant
is visible and executable rather than dependent on reviewer interpretation.

The next exact review found a genuine alias gap: independence compared raw
model strings, while the Claude transport intentionally accepts a configured
family alias such as `opus` and records runtime telemetry such as
`claude-opus-4-6`. An Anthropic maker recorded as `opus` could therefore reach
the same family through the Anthropic fallback. Provider/model identities are
now canonicalized conservatively at live routing, phase-one minting, and
phase-one verification; mutation tests also re-sign the alias form to prove
the consumer rejects it.

The following exact review questioned Gemini's empty `--prompt` value while
the packet is sent on stdin. This is the pinned CLI's documented transport,
not an empty review: `--prompt` selects headless mode and its value is appended
to stdin. The producer passes the complete UTF-8 packet as subprocess input.
A behavioral mutation now captures the actual child-process argv and stdin,
then proves both byte equality and SHA-256 equality before accepting the
adapter contract. The source contract is the official Gemini CLI
[`config.ts`](https://github.com/google-gemini/gemini-cli/blob/main/packages/cli/src/config/config.ts).

That conclusion later became obsolete for a different reason: on 2026-06-18
Google stopped serving individual Google AI Pro/Ultra/free accounts through
the legacy Gemini CLI backend and moved those users to Antigravity CLI. The
adapter remained internally correct for the retired protocol, so unit tests,
bundle pinning and argument smoke all passed while the real third route could
never become available. This was a methodology freshness defect: the oracle
proved implementation fidelity but had no release-blocking external service
liveness/freshness anchor for a mandatory provider.

The durable correction replaces only the mandatory Google route with the
official native Antigravity CLI. Its exact executable is content-bound; OAuth
stays in the OS keyring; review runs in an empty temporary project/home with
slash commands disabled, plan+sandbox enabled, explicit deny-all permissions,
telemetry disabled and `useG1Credits=false`. JSONL evidence must expose one
stable runtime model/session and zero attempted tool calls. A pinned help smoke
proves the invoked flags before review. The release oracle now treats provider
retirement/migration announcements as an external dependency change that
reopens the candidate and requires fresh WSL/Windows live transport proof.

That proposed correction also failed its required live gate. Authenticated
Antigravity 1.1.10 rejected the current account because the product is not
available in its location. A second apparent free fallback, GitHub Models, was
already fully retired on 2026-07-30 even though stale search results still
described its free API. Neither can remain mandatory merely because its local
adapter or old documentation passes.

The current correction uses official GitHub Copilot CLI, available on Copilot
Free, as the third transport. Native WSL and Windows 1.0.78 probes reused the
existing GitHub user session, accepted the exact prompt through stdin, selected
runtime `gpt-5-mini`, emitted distinct session UUIDs, attempted zero tools,
changed zero files and reported bounded included-quota usage (`premiumRequests`
0 or 0.33). The producer now pins the
native executable, forces `auto`, caps a session at 30 AI credits, disables
custom instructions, builtin MCP, remote control/export, updates, Bash env,
experiments, tools and logging, and accepts only the closed live auto-model
allowlist. Any model drift, prompt substitution, non-builtin inherited skill,
tool request, file mutation or usage above one premium request per call is
`UNVERIFIED`.

The next exact review exposed the consumer-side counterpart of the Anthropic
alias defect. The producer correctly signs runtime telemetry such as
`claude-opus-4-6`, but the broker enrollment authorizes the family as `opus`
and still used raw string membership before signature verification. A valid
Claude fallback was therefore mintable but not publishable. The broker now
canonicalizes both each enrolled model and the signed observed model through
the producer's same conservative identity function. A positive runtime-name
mutation and a negative unlisted-Sonnet mutation keep the authorization narrow.

The next live exact review failed before a verdict because the producer reused
the 2 MB review-input cap for Codex's private rollout. That rollout legitimately
contains the already-bounded packet plus runtime provenance/events, so the
container exceeded its input even though the model input remained valid. The
fix leaves the 2 MB packet and 1 MB captured-process-output limits unchanged
and gives only the ephemeral rollout a separate 16 MiB hard cap. A regression
fixture creates a rollout larger than the packet cap and proves session/model
provenance is still recovered; the temporary auth home is deleted afterward.

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

The blocked FX publication then exposed a portable-profile boundary defect.
The v2 `local-review` profile already had a current exact independent
adjudication, but doctor, `itd pr create`, and pre-push still ran the generic
adoption-contract machine preflight. That made an intentionally unadopted
product repository add methodology contracts to its product PR or remain
blocked. The correction selects the closed local profile first, requires the
registered checkout, maker provenance, exact committed `HEAD`, and valid local
adjudication, and skips only adoption/machine preflight for that profile.
App-backed and legacy profiles retain both controls; the claim remains
`LOCAL_REVIEWED`, never `PROTECTED`.

## Final acceptance replay: keyless packet exceeded the single-call model bound

The exact A25 candidate passed all 14 machine runs but its first fresh Terra
producer invocation ended `UNVERIFIED`: the CLI returned a nonzero
model-selection-class failure that was not typed transport unavailability. A
minimal isolated Terra probe passed with the same executable, subscription
auth, model, proxy pin, schema and sandbox, excluding login, executable pin and
basic model availability as the cause. The frozen exact prompt was 1,251,522
bytes and contained a 1,192,241-byte transparent review diff.

The incorrect assumption was that the producer's 2 MB byte cap also guaranteed
that one subscription-model request fit the reviewer's token/model-input
limit. The central broker already solves the same bounded-candidate problem
with a deterministic complete-file/UTF-8-line plan: direct units are at most
80 KB, at most 16 units cover the exact full diff, and a final integration
review is mandatory. The new keyless producer reused the broker's transparent
representation but discarded that hierarchical plan and sent the entire diff
in one call.

The correction must reuse the frozen broker plan for every oversized keyless
packet, run every bound unit through the same selected subscription provider,
run one integration review over the complete unit evidence, and sign a prompt
bundle that reconstructs all unit prompts/reports and the integration prompt.
Any missing/reordered unit, changed byte range, mixed runtime model, tool call,
typed failure or non-clean integration verdict remains fail-closed. The
regression test constructs an oversized transparent packet, proves all unit
byte ranges reconstruct the full diff, proves no model call receives the full
oversized prompt, and rejects prompt-bundle coverage mutations.

The first review of that binding found that the accepted no-PR diagnostic was
still branch-agnostic and whitespace-normalized. It is now compared to the
exact validated branch, rejects quotes in that coordinate, forbids surrounding
whitespace, and permits only no line terminator, LF, or CRLF.

## Methodology-wide effectiveness correction

The next Terra review exposed a host-aggregation defect: the producer returned
the integration report directly, so a clean integration response could erase a
blocking unit finding. The host now signs bundle v2 with the raw integration
report and derives the only final report by deterministic union of every unit
and integration finding/unverified contour.

A separate production incident demonstrated the larger false-confidence mode.
An independent model had seen the exact code and reported `PASSED`, but the
packet contained no executable default-period export bound, reconciliation by
transaction class, rounding-conservation oracle, clean generated-client
freshness check, or repository-hygiene gate. Later production inspection found
all of those gaps. The failure was not product-specific; it was an evidence
availability and review-efficacy defect.

ADR-005 therefore strengthens the existing nine points with evidence-first
coverage and measured deep review. Active criteria declare generic impact
classes and exact-tree oracle IDs; absent or failed coverage is `UNVERIFIED`
before model dispatch. ADR-006 later removes the mandatory quorum: medium,
high and unknown risk require one fresh opposite-GPT report in phase-one v2.
The host still preserves all machine, unit, integration and reviewer findings.
The frozen efficacy pack uses deterministic mutations only for evidence/union
mechanics; blocker recall and false-block calibration come from real no-tools
Terra reports over candidates whose expected faults are hidden from the model.
Prompt, producer, manifest, session, transport and runtime bindings require
fresh WSL and native-Windows results. GPG-003 remains open until exact
adjudication, merge/release and dual-host installed proof are recorded in
completion evidence.

The historical first quorum replay of that candidate (A37) exercised Copilot
fallback and stopped correctly because one assistant message was not strict
JSON. The parser was not at fault and remains closed: Markdown fences, prose
and partial extraction are never promoted to evidence. The prompt boundary was
weaker than the parser boundary, however: hierarchical unit prompts placed the
untrusted diff after the schema/output instruction, leaving candidate text as
the model's final context. The durable correction makes one trusted RFC 8259
output contract the final instruction for direct, unit and integration calls,
after every untrusted byte. Focused mutations require that placement and still
reject fenced or prose-prefixed JSON. A37 remains terminal and only the changed
candidate may receive a new route-bound review.

A38 then proved that passing regression counts were still not sufficient. The
review retained real blockers across units: stale Gemini operating state,
contradictory quorum wording, weak verdict semantics in efficacy scoring,
repository-controlled unsigned live evidence, incomplete whole-route
freshness, an unanchored local phase-one keyring, and two inconsistencies in
the generated live blueprint fixture. The correction is deliberately bounded
to those findings. Live efficacy/provider results are now host-derived signed
envelopes; high/critical recall requires a blocking verdict; freshness covers
all three ordered transports and records the deliberately unconfigured
Anthropic subscription as typed UNAVAILABLE; and the host-owned profile
registry pins the authorized phase-one keyring hash passed to the installed
validator. The benchmark prompt/oracle now require exit code 4 and percentage
semantics. The already-correct `_clean_report` PASSED check is evaluated before
its lists so a future reviewer cannot reasonably misread the gate order.
Public evidence signatures use lowercase fixed-width hex rather than base64url:
the Ed25519 payload and verification are unchanged, while the generic
high-entropy credential scrub can continue to reject every mixed-case token
without a dangerous field-name allowlist.

The bounded A41 and A42 cycles later repeated the same terminal Copilot
structured-output failure. That evidence showed the mandatory provider chain
and quorum were an availability defect, not additional protection against the
earlier missing-oracle incident. ADR-006 therefore selects one fresh opposite
GPT reviewer and leaves Anthropic, Copilot, Antigravity and paid API transports
optional. Exact-candidate machine evidence, strict output, re-review after any
amendment, route-bound adjudication, dual-host rollout and 9/9 completion
evidence remain unchanged.
