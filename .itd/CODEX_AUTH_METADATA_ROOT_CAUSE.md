# Codex subscription auth metadata compatibility

## Summary
The exact core-token key-set check rejects current legitimate Codex ChatGPT auth records because they add login_owner_id and oauth_provenance metadata.

## Reproduction
The unchanged installed1.110.0 producer returns UNVERIFIED: free reviewer requires closed ChatGPT subscription auth before any model invocation. A synthetic six-field ChatGPT record reproduces it; a legacy four-field record is accepted.

## Evidence
Read-only structural inspection found auth_mode=chatgpt, API-key field null, all four core strings valid, extra login_owner_id:str and oauth_provenance:{issuer:str,client_id:str}. No credential values were logged. The observed issuer matches canonical https://auth.openai.com. Aboutyou machine receipt a7 PASSED before the transport rejected the format.

## Fix Hypothesis
Keep two closed token shapes, legacy core-only and current core plus both bounded metadata fields. Reject incomplete/unknown metadata, noncanonical issuer and malformed values. Preserve core validation, no API key, private-home copy bytes and fresh opposite-model route.

## Regression Test
Extend the existing free-reviewer behavioral oracle with synthetic acceptance, byte-preserving ephemeral-home transport and malformed/unknown/API-mode rejection cases. It must fail on the unchanged validator and pass after the fix.

## Constraints
Do not project or strip real metadata, print credentials, run candidate code with actual reviewer auth, edit installed files in place or weaken review/egress gates.

Official guidance requires keeping each registration's issued client ID with its credentials and validated identity, and keeping tokens out of logs/source control: https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions . Exact local Codex field names above are observed runtime evidence rather than a claim that this page specifies auth.json.
