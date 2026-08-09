# Mandatory keyless reviewer transports

This reference describes the host adapters used only through
`skills/_shared/itd_free_reviewer_producer.py`. They are transports, not
independent policy implementations.

## Fixed route

`Sol -> Terra` and `Terra -> Sol`

The producer runs exactly one isolated OpenAI subscription session with the
opposite Sol/Terra model. `UNAVAILABLE`, `BLOCKED` and `UNVERIFIED` stop; there
is no automatic provider fallback, caller bypass or vote shopping. Anthropic
and GitHub Copilot adapters below are optional separately invoked transports.
After a CLI starts, only closed auth, quota, network/status, or timeout signals
may be classified `UNAVAILABLE`; unknown non-zero exits, unsupported arguments,
oversized error output, and malformed protocol failures are `UNVERIFIED`.

## Common contract

- freeze and scrub the exact candidate before any provider call;
- resolve and SHA-256-pin the active host's executable or launcher/runtime;
- expose only the minimum validated user/subscription auth boundary to a
  private temporary profile; OS-keyring credentials remain in the keyring;
- remove provider API keys and unrelated environment variables;
- start a fresh non-persistent session with no inherited development context;
- disable tools, repository access, user rules, slash commands, MCP servers,
  and repository mutation;
- require the closed JSON verdict schema and observed session provenance;
- reject tool events, malformed output, and same maker/reviewer identity.

## OpenAI subscription adapter

The Codex adapter uses ChatGPT subscription auth from a closed `auth.json`
schema in a private temporary `CODEX_HOME`, ignored user config/rules, read-only
sandbox, no inherited environment, disabled tool features, strict output
schema, and event telemetry. The pinned CLI's `--ephemeral` JSONL omits runtime
model telemetry, so the producer instead reads the single rollout inside that
temporary home and then deletes the entire home. This preserves both observed
model provenance and non-persistence. It does not use a provider API key or
paid API endpoint.

## Anthropic subscription adapter

The Claude adapter copies only validated `claudeAiOauth` subscription material
into a temporary config directory. It uses print mode, no session persistence,
no slash commands, strict empty MCP config, empty setting sources, empty tools,
`dontAsk`, JSON output, and a strict verdict schema. It also requires present
empty `permission_denials` plus valid turn telemetry before accepting a report.

## GitHub Copilot user-auth adapter

The Copilot adapter uses the official GitHub user session and a content-pinned
native `copilot` executable. It runs in an empty temporary project and
`COPILOT_HOME`, receives the complete packet only on stdin, forces free `auto`
mode with a 30-credit session cap, disables custom instructions, builtin MCP,
remote export/control, updates, Bash environment loading, experimental mode,
memory, all model tools, and logging. The JSONL stream must bind one allowed
runtime-selected model and one canonical session, the exact stdin content,
zero tool requests, zero file changes, and 0..1 included premium request per
call. Paid overage is never enabled. Any other
model, inherited non-builtin skill, mutation, malformed output, or missing
telemetry is terminal `UNVERIFIED`.

## Host boundary

WSL uses WSL-native installed transports and POSIX-private temporary files.
Native Windows uses Windows-native installed transports and private temporary
profiles. Do not bridge credential-bearing execution between hosts. Missing
native transport/auth is `UNAVAILABLE`; weak permissions, changed pins,
unexpected credential fields, or incomplete telemetry are `UNVERIFIED`.
