# Fixture 30 — `/cross-review` contract

`/cross-review` is the explicit entry point to the same mandatory independent
pre-PR route used by `/review`. It must not implement another router.

## Contract

- Freeze and scrub the exact staged candidate.
- Use `skills/_shared/itd_free_reviewer_producer.py`.
- Preserve `OpenAI -> Anthropic -> Gemini`.
- Advance only on typed `UNAVAILABLE`; stop on `BLOCKED` or `UNVERIFIED`.
- Use installed user/subscription authentication and remove provider API keys.
- Require a fresh reviewer model/session and record actual provenance.
- Provide no caller bypass.
- Accept success only through a current Verification Loop adjudication receipt.
- Keep WSL credentials/transports in WSL and Windows credentials/transports on
  native Windows.

The skill may write only ignored Verification Loop evidence under
`.itd-memory`; it must not modify candidate source files or grant merge/deploy
permissions.
