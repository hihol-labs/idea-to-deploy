# Idea to Deploy global router

Idea to Deploy is the default engineering methodology for non-trivial local
project work in this Codex installation.

- Use the enabled `idea-to-deploy` plugin and select the smallest applicable
  lifecycle skill before implementation.
- Project `AGENTS.md`, `.itd/` contracts, and `.itd-memory/` state take
  precedence over this global router.
- If a project is not adopted, use the plugin's `adopt` workflow: inspect
  first, show the bounded plan, and write only after the user's authorization.
- Preserve WIP=1 and require the evidence named by
  `.itd/VERIFICATION_CONTRACT.json` before claiming completion.
- For implementation or change work, use Verification Loop as the default
  acceptance protocol: freeze the exact staged candidate, run its machine
  oracle, and apply the risk-tier checker before accepting the result.
- Exclude undeclared ignored/untracked overlays from the oracle. When a
  non-Git input is necessary, declare it explicitly and bind its content hash.
- Accept completion only from a current, revalidated adjudication receipt;
  prose or a standalone `PASSED` verdict is not sufficient evidence.
- Keep work handoff-ready: tests recorded, state reconciled, and the next
  action explicit.

Product Factory OS is legacy on this machine. Do not load or auto-adopt it
unless the user explicitly asks for that methodology.
