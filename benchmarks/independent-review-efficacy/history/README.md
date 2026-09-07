# Immutable efficacy history

`route-debts/accepted-base-5410818/` preserves the three accepted result files
byte for byte from protected base commit
`541081840d2f972e1b0c5aea16fa09a767f80b2c`. Their original SHA-256 and Git blob
anchors are checked by the efficacy verifier.

The `diagnostic-*` directories preserve real observations made during the
ROUTE-DEBTS repair. Each snapshot retains its original payload, producer hash,
sessions, observation time and signature. The manifest records exact file
hashes and identities. These measurements do not constitute candidate
acceptance or an empirical effectiveness result.

The U12 leg retains the frozen corpus's counterfactual maker-provider
classification. Its real calls are Sol reviews; it does not record an
Anthropic implementation run.

History is append-only. Add a new snapshot and manifest entry for a new
observation; do not edit, re-date or re-sign an existing snapshot. Keep the
failed invocation logs and signed checkpoint prefixes with the unit's
declared verification inputs.

The sibling `results/` directory presents the currently applicable
observations. Refresh those views only from newly generated, archived signed
results. The verifier checks both history integrity and the existing strict
current-producer, corpus, signature and host-parity requirements. An old
archive is not current-producer evidence.
