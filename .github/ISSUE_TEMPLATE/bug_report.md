---
name: Bug report
about: Report a bug in idea-to-deploy methodology, a skill, a hook, or the meta-rubric
title: "[BUG] "
labels: bug
assignees: ''
---

## Environment

- **Claude Code version:** (run `claude --version`)
- **Plugin version:** (from `plugin.json` or the README badge, e.g. `1.8.0`)
- **Model in use:** (Haiku / Sonnet / Opus + version, e.g. `claude-sonnet-4-6`)
- **OS:** (macOS / Linux / WSL / Windows)
- **Installation method:** (`/plugin install`, manual clone, other)

## What happened?

Describe the unexpected behavior. Be specific.

## What did you expect to happen?

Describe the behavior you expected.

## How to reproduce

Exact steps, including the prompt text you used:

```
1.
2.
3.
```

If the bug is in a specific skill, mention which one (`/bugfix`, `/kickstart`, `/infra`, etc.).

## Minimal reproduction (optional but appreciated)

If you can reduce the bug to a minimal fixture:

- What files / code are needed
- Where they should live (e.g. `tests/fixtures/my-repro/`)
- The exact skill invocation

## Logs / output

Paste any error messages, stack traces, or meta-review output. Use code blocks.

```

```

## Did you run the meta-review?

- [ ] `python3 tests/meta_review.py --verbose` — result: (PASSED / PASSED_WITH_WARNINGS / BLOCKED / didn't run)
- [ ] `python3 tests/verify_triggers.py` — result: (0 drift / N drift / didn't run)

If you saw drift or failures in these, paste the output above.

## Additional context

Anything else that might help — related PRs, recent CHANGELOG entries, your local setup peculiarities.
