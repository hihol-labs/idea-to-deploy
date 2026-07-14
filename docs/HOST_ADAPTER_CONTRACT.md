# Host adapter contract

Idea to Deploy has one methodology core and multiple runtime adapters. A host
adapter may translate transport details; it must not fork contracts, completion
criteria, risk policy, skill semantics, or persistent project state.

## Canonical core

- `skills/` contains workflows and shared operating rules.
- `docs/templates/itd/` contains project and verification contracts.
- `docs/templates/itd-memory/` defines persistent execution state.
- `hooks/` contains deterministic policy and telemetry checks.
- `tests/` defines observable behavior.

The machine-readable registry is `docs/host-adapters.json`.

## Adapter responsibilities

An adapter owns only:

- plugin packaging and discovery;
- the project guidance entry file;
- hook registration, event and tool-name normalization;
- host-specific installation, trust, and writable-data locations;
- translation from a host's subagent mechanism to the roles in `agents/`.

An adapter must preserve hook exit status and deny decisions. When a host cannot
represent a capability, the adapter must declare the degradation and provide a
fallback based on shared contracts or structured output. Silent false parity is
not allowed.

## Parity rule

A change to shared methodology behavior is complete only when:

1. the shared test passes;
2. both adapter manifests remain valid;
3. the adapter registry still maps the affected capability;
4. any intentionally unavailable transport feature is documented.

Claude Code and Codex may expose different tools, but a project must converge
to the same `.itd/` contracts, `.itd-memory/` state, review verdict schema, and
verification evidence.
