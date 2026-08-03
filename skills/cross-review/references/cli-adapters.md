# Mandatory keyless reviewer transports

This reference describes the host adapters used only through
`skills/_shared/itd_free_reviewer_producer.py`. They are transports, not
independent policy implementations.

## Fixed route

`OpenAI -> Anthropic -> Gemini`

The producer tries an isolated OpenAI subscription session first, an isolated
Anthropic subscription session second, and an isolated Gemini user-auth
session last. Only typed `UNAVAILABLE` advances. `BLOCKED` and `UNVERIFIED`
stop. Exhaustion remains `UNAVAILABLE`. There is no caller bypass.
After a CLI starts, only closed auth, quota, network/status, or timeout signals
may be classified `UNAVAILABLE`; unknown non-zero exits, unsupported arguments,
oversized error output, and malformed protocol failures are `UNVERIFIED`.

## Common contract

- freeze and scrub the exact candidate before any provider call;
- resolve and SHA-256-pin the active host's executable or launcher/runtime;
- copy only validated user/subscription auth into a private temporary profile;
- remove provider API keys and unrelated environment variables;
- start a fresh non-persistent session with no inherited development context;
- disable tools, repository access, user rules, slash commands, MCP servers,
  and repository mutation;
- require the closed JSON verdict schema and observed session provenance;
- reject tool events, malformed output, and same maker/reviewer identity.

## OpenAI subscription adapter

The Codex adapter uses ChatGPT subscription auth from a closed `auth.json`
schema, `codex exec --ephemeral`, ignored user config/rules, read-only sandbox,
no inherited environment, disabled tool features, strict output schema, and
event telemetry. It does not use a provider API key or paid API endpoint.

## Anthropic subscription adapter

The Claude adapter copies only validated `claudeAiOauth` subscription material
into a temporary config directory. It uses print mode, no session persistence,
no slash commands, strict empty MCP config, empty setting sources, empty tools,
`dontAsk`, JSON output, and a strict verdict schema.

## Gemini user-auth adapter

The Gemini adapter copies only validated personal OAuth material into a
temporary profile. It enforces personal OAuth settings, plan approval mode, a
deny-all tool policy, sandbox/trust isolation, a fresh UUID session, and JSONL
telemetry. The complete installed JavaScript bundle (all relative runtime
dependencies) and the native runtime are pinned separately; pinning only the
small launcher file is insufficient. Before dispatch, that exact pinned bundle
must pass a fail-closed CLI help smoke proving every invoked policy, plan,
sandbox, trust, stream-output, and fresh-session argument is available.

## Host boundary

WSL uses WSL-native installed transports and POSIX-private temporary files.
Native Windows uses Windows-native installed transports and private temporary
profiles. Do not bridge credential-bearing execution between hosts. Missing
native transport/auth is `UNAVAILABLE`; weak permissions, changed pins,
unexpected credential fields, or incomplete telemetry are `UNVERIFIED`.
