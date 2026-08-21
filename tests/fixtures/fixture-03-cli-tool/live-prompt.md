Use the repository-local Idea to Deploy plugin and execute
`$idea-to-deploy:blueprint --full` for the project below. This is a
non-interactive benchmark: the product decisions, MoSCoW priorities, and the
obvious single-process architecture are pre-approved, so do not pause for
questions or confirmation. Follow the actual workflow in
`.itd-plugin/skills/blueprint/SKILL.md`, including its referenced document
template, and write the resulting project documents in the current project
root. Do not implement product code.

When the candidate transport is Codex, create and edit the documents with the
native `apply_patch` file-edit tool. Do not substitute multi-statement
PowerShell write commands. A command-safety rejection of a shell inspection
does not prove that the workspace is read-only; report a read-only blocker only
if the native file-edit tool itself returns a write denial.

The adversarial (Devil's Advocate) review is NOT part of this session: the
external harness runs the real `devils-advocate` agent definition in a
separate fresh session after this one and validates its artifact. Do not
perform an inline self-critique in place of that review, do not write
`DEVILS_ADVOCATE_REVIEW.md` yourself, and do not claim that any adversarial
or independent reviewer ran inside this session. Do not report artifact
hashes or exact validation counts in chat: the external harness computes
hashes and validates the final files only after the process exits.

Project: a local Python 3.11 CLI for DevOps/SRE engineers that streams nginx
access logs and reports top-10 IPs, top-10 URLs by 4xx/5xx errors, hourly
request distribution, and the share of unique User-Agents. Default output is
colored terminal text; `--json` and `--csv` are supported for pipelines.

Constraints and approved decisions:

- No authentication, database, HTTP API, server, cloud, or Kubernetes.
- Stateless streaming processing; target 1 GB under 30 seconds on a laptop.
- Stack: Python 3.11, Click, Rich, dataclasses; installable through pip.
- Budget $0, open source, one-weekend delivery.
- Relevant alternatives: GoAccess, Logstash/Elastic/Kibana, AWStats, grep/awk.
- In `PROJECT_ARCHITECTURE.md`, use the literal decision statement
  **"no database — stateless streaming processing; no HTTP API — CLI-only
  tool"** and justify why both constraints are correct here.
- In `PROJECT_ARCHITECTURE.md`, place the commands, options, inputs, outputs,
  and exit-code contract under the exact second-level heading
  `## CLI Interface`.
- Include at least three user stories and a 4–10 step implementation plan.
- In `PRD.md`, place the user stories under the exact second-level heading
  `## User Stories` so the documented contract is explicit and replayable.
- Define hourly request distribution as a percentage using the literal formula
  `100 × hourly_request_count / total_valid_requests`; do not describe it as an
  unscaled fraction.
- Use the complete exit-code contract `0/1/2/3/4` in every implementation guide;
  code `4` means unique-cardinality exhaustion. Do not omit or remap code 4.

Before ending, verify that all six required files exist in the project root:

- `STRATEGIC_PLAN.md`
- `PROJECT_ARCHITECTURE.md`
- `PRD.md`
- `IMPLEMENTATION_PLAN.md`
- `CLAUDE_CODE_GUIDE.md`
- `CLAUDE.md`

If any required file is missing, continue the same `$idea-to-deploy:blueprint
--full` workflow and create it before reporting completion. Do not substitute a
README, summary, or chat response for any required file.

At the end, report which Idea to Deploy skill and reference file you actually
read and followed. Do not claim completion unless the documents exist.
