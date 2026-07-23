# External outcome validation protocol

This package measures whether Idea to Deploy improves real engineering work. It
is opt-in and intentionally separate from internal fixtures and methodology
self-scores.

## Enrollment

1. A project operator explicitly consents to a 30+ day baseline/follow-up
   observation. Participation is never enabled by `/adopt` or a hook.
2. Locally derive pseudonyms: `proj_`/`op_` plus 12 lowercase hex characters.
   Do not submit names, emails, repository URLs/paths, prompts, source code,
   secrets or customer data.
3. Record at least the six schema metrics over comparable work units. Keep raw
   logs in the project; export only aggregates and SHA-256 provenance.
4. A second operator verifies each source hash. The verifier ID must differ
   from the record operator ID.
5. Compute `attestation.recordDigest` with
   `scripts/itd_external_outcomes.py digest-record` and opt in to the accuracy,
   independence and privacy attestations.

## Local paired-unit collection

The zero-dependency collector keeps raw observations in the pilot project and
exports only aggregates plus SHA-256 provenance. Generate pseudonymous IDs,
then initialize the ledger only after explicit consent:

```text
python scripts/itd_external_pilot.py new-id --kind project
python scripts/itd_external_pilot.py new-id --kind operator
python scripts/itd_external_pilot.py new-id --kind comparison
python scripts/itd_external_pilot.py init \
  --ledger .itd-pilot/units.jsonl \
  --project-id proj_<12hex> --operator-id op_<12hex> \
  --repository-class external_private --started-at <ISO-8601> --consent
```

For every pseudonymous `comparisonId`, record exactly one verified baseline
unit and one verified follow-up unit. `PILOT_UNIT_SCHEMA.json` defines the raw
fields and deterministic metric formulas. Do not put task names, repository
paths, prompts, code, people, email addresses, secrets or customer data in the
ledger.

```text
python scripts/itd_external_pilot.py append \
  --ledger .itd-pilot/units.jsonl --phase baseline \
  --comparison-id cmp_<12hex> --started-at <ISO-8601> --finished-at <ISO-8601> \
  --verified --defect-escapes 0 --false-completions 0 --token-units 0 \
  --friction-events 0 --critical-regressions 0
python scripts/itd_external_pilot.py aggregate \
  --ledger .itd-pilot/units.jsonl --out .itd-pilot/aggregate.json
```

A distinct operator independently replays the aggregate and verifies both the
aggregate digest and raw-ledger SHA-256 before producing a candidate record:

```text
python scripts/itd_external_pilot.py attest \
  --ledger .itd-pilot/units.jsonl --aggregate .itd-pilot/aggregate.json \
  --verified-by op_<different-12hex> --verified-at <ISO-8601> \
  --out .itd-pilot/record.json --consent --independent-operator \
  --not-author-affiliated --accurate
```

`record.json` is still only a candidate. Add it to the real index after the
human attestations are truthful and the frozen cohort thresholds are met.

## Evaluation and export

Place consented records in `docs/evidence/external-outcomes/INDEX.json`, then:

```text
python scripts/itd_external_outcomes.py evaluate \
  --index docs/evidence/external-outcomes/INDEX.json
python scripts/itd_external_outcomes.py export \
  --index docs/evidence/external-outcomes/INDEX.json --out external-outcomes.export.json
```

The evaluator fails closed unless the frozen policy is met: 3 independent
non-methodology projects, 2 operators, 30 comparable units, 30 days per
project, fresh post-freeze evidence, verifiable hashes, no prohibited fields,
no critical regression and at least one material primary-metric improvement.

The export contains only validated aggregates and digests. Publication or
sharing is a separate explicit human action. The tool does not contact pilots,
upload evidence, merge changes or create a passing `INDEX.json`.

Privacy-safe success and failure narratives may be derived only after this
evaluation workflow. Use `OPERATING_LOOP_STORIES.md` and the two
`docs/templates/itd/OPERATING_LOOP_*_STORY.json` templates. Story prose never
upgrades evidence: the indexed record and this evaluator remain authoritative.

## Evidence boundary

- Tests may construct in-memory examples to refute the evaluator. They are not
  external evidence and must never be copied into the real index.
- This methodology repository and its author-only self-report are ineligible.
- A missing/pending real index is a legitimate `PE5-008` blocker, not a reason
  to lower thresholds or label fixtures as outcomes.
