# Q6 CMP preregistration and instrument

This stdlib instrument implements freeze, validate, reconcile, sealed owner labels and guarded read-only scoring. It does not implement the D3 statistical decision or connect scores to policy, reward, routing or self-modification. Synthetic tests establish software behavior only. The empirical ITD proxy is an unvalidated adaptation inspired by [HGM descendant outcomes](https://arxiv.org/html/2510.21614v3), not a causal claim or a reproduction of its theorem.

`PROTOCOL.json` freezes the formula, population, window, missing/tie rules, owner rubric, budgets and future statistical algorithms. CMP is the fraction of unique explicitly linked descendant lifecycle cycles whose **first** valid published primary machine-verification receipt passed. The root's own outcome, retry count and number of tests do not contribute. A later passing retry never replaces an earlier failed receipt. The producer's explicit `shell=unavailable` marker is missing oracle evidence, not a business failure; reconciliation stops rather than counting zero or selecting a later success. Numeric exit codes alone cannot distinguish infrastructure from a deliberately failing oracle. This archival parser validates sealed structure and internal semantics; it does not revalidate a 90-day-old receipt against today's host shell or admission freshness window.

## Start after accepted merge

From a clean source checkout whose HEAD is merged into origin/main, create an ignored local CONTEXT.json containing explicit current operating context, for example:

```json
{"vendor":"openai","model":"gpt-6-astra","harnessMajor":"1","promptPolicyDigest":"<actual SHA-256 of the fixed prompting policy>"}
```

The example is a schema illustration, not an assertion about installed defaults. Record the actual controlling model/vendor; WSL may be only the execution transport. Recheck all four context fields on every use. Do not infer a current default from a past receipt.

```sh
sh skills/_shared/itd_py.sh benchmarks/cmp/cmp_protocol.py freeze --root . --output .itd-memory/experiments/q6-cmp --context .itd-memory/experiments/q6-cmp/CONTEXT.json
sh skills/_shared/itd_py.sh benchmarks/cmp/cmp_protocol.py validate --campaign .itd-memory/experiments/q6-cmp/CAMPAIGN.json --current-context .itd-memory/experiments/q6-cmp/CONTEXT.json
```

Freeze obtains real UTC and Git HEAD itself, checks the actual adjacent source files against the clean tracked commit and exclusively publishes CAMPAIGN.json. Existing output directories may contain CONTEXT.json; an existing campaign can never be replaced. There is no backdated timestamp or alternate-instrument CLI option. The frozen observation window is 90 days; use stops after the 180-day data timeout. A context or instrument/protocol change makes the campaign stale and requires a fresh freeze/window. Checksums assume an honest local operator; they are not cryptographic owner attestations.

## Collect prospective lineage without occupying WIP

For every participating normal work unit, before its **first** machine oracle, materialize a small lineage descriptor. Use actual event identity, including ledger and activation event id:

```json
{"schemaVersion":1,"identity":["idea-to-deploy","GOAL.json","U-example","actual-activation-event-id"],"parents":[]}
```

Parents are full identities of attributable prospective experimental ancestors. They do not mean all Git ancestors, software dependencies or the pre-freeze baseline. A root has no attributable prospective parent. Never infer lineage from timestamps or scores.

Bind the descriptor by staging it in the actual machine candidate, or supplying its ignored project-local file/directory with the existing machine producer's `--input`. The unchanged producer records kinds `file` or `directory`; there is no special CMP declared-input kind. Preserve those exact source bytes. Missing provenance does not block ordinary engineering, but makes the experiment incomplete rather than providing an invented exposure. Q6 setup and its future Q6-DECISION unit are excluded.

At window completion, prepare a dedicated local source directory with complete source receipt files, relevant lifecycle event JSONL and declared-input snapshots in their original project-relative paths. It must contain no .git database, links, secrets or raw model transcripts. Receipts are recognized by content even if their extension is not .json. Byte-identical producerRunId copies deduplicate; conflicting copies fail. Lifecycle events retain their actual id/at/actor/type/name/decision/evidence/ledger fields. Do not omit failed primary attempts or eligible lifecycle cycles.

Store the snapshot **outside** that source directory:

```json
{"sourceInventory":[{"path":"events.jsonl","sha256":"<actual bytes hash>"},{"path":"receipts/first.receipt","sha256":"<actual bytes hash>"},{"path":"inputs/U-example/lineage.json","sha256":"<actual bytes hash>"}],"units":[{"project":"idea-to-deploy","ledger":"GOAL.json","unitId":"U-example","activationEventId":"actual-activation-event-id","eventsPath":"events.jsonl","lineagePath":"inputs/U-example/lineage.json"}]}
```

Enumerate and hash every file in the directory, not merely the abbreviated illustration. All prospective closed or end-censored lifecycle cycles must be represented. When lineage is a tracked Git blob, include `repositoryPath` naming an available Git root from the frozen repository aliases; its reviewedTree must still be available. Caller path strings alone do not prove lineage. The source directory is a declared evidence scope, not a proof that a dishonest operator supplied every file existing elsewhere.

`reconcile --campaign ... --current-context ... --snapshot ... --source-root ...` verifies source hashes, receipts, actual event cycles, first-outcome selection and the acyclic explicit lineage graph. The fixed cohort comprises the first20 verified roots activated after freeze and closed inside the window, ordered by closure then identity, before examining outcomes/exposures. Zero exposure never causes substitution with a later root. Overlapping clades reject dependence. Reconciliation reports the source/receipt/cycle census and every excluded cycle; scoring additionally classifies each cycle, including later roots outside the fixed first20. Incomplete provenance fails visibly; insufficient cohort/exposure yields INSUFFICIENT_DATA. Unclosed or late-closed descendants are censored rather than counted as successes or failures.

## Blind owner labels, then numeric disclosure

After maturity, reconcile the complete snapshot and keep it unchanged. A collector prepares the owner's worksheet using only the allowlist/rubric in PROTOCOL.json. Shuffle presentation with Python random.Random(20260905).shuffle over initially identity-sorted roots. Keep the machine receipts, scores/components/counts and model/provider labels out of the worksheet. Maintain the blind-id to identity mapping separately; an honest operator maps the completed owner ratings back only after the owner finishes. Recognition of a change can weaken practical blinding and must be reported at decision time.

The owner supplies a complete ordinal integer rating 0..4 for every fixed-cohort root; missing is distinct from zero. Create an input JSON object `{"ratings":[{"root":["idea-to-deploy","GOAL.json","U-example","actual-activation-event-id"],"rating":2}, ...]}` with all20 identities, then run:

```sh
sh skills/_shared/itd_py.sh benchmarks/cmp/cmp_protocol.py seal-labels --campaign CAMPAIGN.json --current-context CONTEXT.json --snapshot SNAPSHOT.json --source-root SOURCES --labels OWNER.json
sh skills/_shared/itd_py.sh benchmarks/cmp/cmp_protocol.py score --campaign CAMPAIGN.json --current-context CONTEXT.json --snapshot SNAPSHOT.json --source-root SOURCES
```

Sealing validates the complete cohort/ratings and exclusively writes fixed LABELS.json alongside the campaign, bound to the full snapshot and campaign. Score uses that fixed seal and rejects early disclosure, absent/invalid ratings or changed evidence. It emits UNVALIDATED, operationalSignal=false and d3Verdict=NOT_RUN. The pure `score()` function exists for synthetic testing; importing it is not a supported way to bypass the owner workflow. No automatic statistics or D3 PASS is provided.

The future separate decision unit must persist its one-attempt intent before numeric reveal, implement the already frozen rho/permutation/bootstrap design and consume the unchanged instrument. N=20 and rho>=.6 alone do not demonstrate significance; [SciPy documents the small-sample permutation caveat](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.spearmanr.html). Ties use average ranks; constant vectors are undefined. Do not tune the formula, labels, window or cohort after observing scores.

Baseline is zero prospective CMP pairs;37 prior verified engineering units are not a forecast of eligible clades. Budgets:16 setup hours,1 operator hour/month,90 observation days,180-day timeout. Benefit30min/month and six-month payback are unmeasured hypotheses. Stop/archive the campaign to roll back; original ledgers and production behavior are unchanged. Keep raw traces local for90 days under the advisory retention policy; aggregates without text can be retained. Scrub before original evidence is sealed, never modify a sealed receipt to conceal data.
