# Operating-loop outcome stories

Success and failure stories are privacy-safe views over the existing external
outcome protocol. They explain observed effects; they do not create evidence,
change evaluator thresholds, or turn telemetry into adoption.

## Workflow

1. Obtain explicit pilot consent and collect comparable baseline/follow-up units
   with `scripts/itd_external_pilot.py` exactly as described in `PROTOCOL.md`.
2. Have a different pseudonymous operator attest the raw-ledger and aggregate
   hashes. Keep raw data inside the pilot project.
3. Add the consented aggregate record to
   `docs/evidence/external-outcomes/INDEX.json` and run the existing evaluator.
4. Copy the applicable success or failure JSON template. Populate only
   aggregates, pseudonymous IDs, hashes, limitations, and the accepted record
   digest. Never copy prompts, source, paths, people, or customer data.
5. Keep `evidenceStatus` as `UNVERIFIED` unless the linked record is accepted by
   the existing evaluator, the operator and verifier IDs differ, both paired
   outcomes exist, and the project is external and non-methodology-owned.
6. Run `python scripts/itd_external_outcomes.py validate-story --index
   docs/evidence/external-outcomes/INDEX.json --story <story.json>`. This command
   reruns the canonical cohort evaluator and binds the story to the matching
   accepted project record, digest, operators, metrics, and source hashes.
7. Publish or share a story only through a separate explicit human-approved
   action. A scheduler may report a candidate but cannot validate or publish it.

## Fail-closed evidence boundary

Stars, downloads, author self-report, synthetic fixtures, this methodology
repository, methodology-owned projects, missing before/after metrics, a single
operator, or an absent/failed index record remain `UNVERIFIED`. They may be
described as limitations but never relabeled as external outcomes.

Both success and failure stories must be retained. A failure story uses the
same provenance and privacy requirements; negative results are not silently
removed from the cohort. The canonical adoption decision remains the output of
`scripts/itd_external_outcomes.py evaluate`, not the story file or its prose.
