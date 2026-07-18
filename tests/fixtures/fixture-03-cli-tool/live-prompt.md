Use the repository-local Idea to Deploy plugin and execute
`$idea-to-deploy:blueprint --full` for the project below. This is a
non-interactive benchmark: the product decisions, MoSCoW priorities, and the
obvious single-process architecture are pre-approved, so do not pause for
questions or confirmation. Follow the actual workflow in
`.itd-plugin/skills/blueprint/SKILL.md`, including its referenced document
template, and write the resulting project documents in the current project
root. Do not implement product code.

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
- Include at least three user stories and a 4–10 step implementation plan.

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
