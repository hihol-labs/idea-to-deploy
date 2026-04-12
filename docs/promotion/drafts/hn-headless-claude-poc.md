# Show HN: Running Claude Code headless for automated methodology testing

- **Platform:** Hacker News (Show HN)
- **Target length:** ~1500 words
- **Tags:** N/A (HN has no tags)
- **Hook:** We built a self-improving methodology plugin for Claude Code and needed to test it without a human in the loop. Here's what we learned about `claude -p` and headless LLM testing.
- **CTA:** The plugin is MIT-licensed at https://github.com/HiH-DimaN/idea-to-deploy -- feedback welcome, especially from anyone else doing headless Claude Code automation.

---

## Show HN: Running Claude Code headless for automated methodology testing

We built a self-improving methodology plugin for Claude Code and needed to test it without a human in the loop. Here is what we learned about `claude -p` and headless LLM testing.

### Background

idea-to-deploy is a Claude Code plugin (19 skills, 7 subagents) that turns Claude Code into a structured development pipeline: idea to architecture to code to tests to deploy. We have a three-tier testing system: structural meta-review (Python, runs in CI), snapshot validation (deterministic checks on generated output), and behavioural execution (actually running skills end-to-end).

The first two tiers are straightforward. The third is where things get interesting, because you need Claude Code to run non-interactively, produce files, and exit -- so you can validate the output programmatically.

### The `claude -p` flag

Claude Code supports a `-p` / `--print` flag for non-interactive mode. You pipe in a prompt, it runs, prints the response, and exits. Simple in theory.

In practice, there is a constellation of related flags that interact in non-obvious ways:

```bash
claude -p \
  --input-format stream-json \
  --output-format stream-json \
  --verbose \
  --no-session-persistence \
  --model sonnet \
  --dangerously-skip-permissions \
  --add-dir ./output \
  --max-budget-usd 10.00 \
  < fixture.jsonl
```

Let me walk through what each flag does and the gotchas we hit.

### `--input-format stream-json`

This is the key to multi-message input. Our skills (like `/kickstart`) ask clarifying questions before generating output. In interactive mode, a human types answers. In headless mode, you need to pre-seed those answers.

The input format is JSONL -- one JSON object per line:

```json
{"type":"user","message":{"role":"user","content":"/blueprint Build a Telegram bot for appointment booking\n\nPre-emptive clarifications:\n1. Users: patients and clinic staff\n2. Auth: Telegram built-in\n...\n\nIMPORTANT: do NOT ask further clarifying questions."}}
```

**Gotcha #1:** If you use `--input-format stream-json`, you must also use `--output-format stream-json`. Using `--output-format json` with stream-json input silently changes the output format anyway. We wasted an hour on this.

**Gotcha #2:** The `"type":"user"` wrapper is required. Sending raw `{"role":"user","content":"..."}` without the type envelope produces a parse error with no useful message.

### `--output-format stream-json`

The output is a stream of JSON objects, one per line, with different `type` fields:

- `init` -- session metadata, model info
- `assistant` -- the model's text response chunks
- `user` -- tool results (file writes, bash output)
- `result` -- final summary with token counts and cost
- `rate_limit_event` -- when you hit rate limits

**Gotcha #3:** `--output-format stream-json` requires `--verbose`. Without it, you get a cryptic error about incompatible flags. The documentation does not make this dependency obvious.

**Gotcha #4:** The `result` event contains a `total_cost_usd` field that reports the equivalent pay-as-you-go price even if you are on a Pro subscription (where actual cost is $0 for the API call). This is useful for budgeting CI runs but confusing if you think you are being charged.

### `--dangerously-skip-permissions`

In interactive mode, Claude Code asks for permission before writing files, running bash commands, etc. In headless mode, there is no human to approve. This flag skips all permission checks.

The name is deliberately scary, and rightfully so. We run it only in disposable output directories that get wiped after each test.

**Gotcha #5:** Without this flag, the headless run hangs indefinitely waiting for permission approval that will never come. There is no timeout -- it just sits there. We expected a timeout or error; instead we got a zombie process.

### `--max-budget-usd`

Hard budget cap per invocation. When exceeded, the run terminates with a `budget_exceeded` reason in the result event.

This is essential for CI. A single `/kickstart` run on Opus can cost $8-25 in equivalent tokens. Without a cap, a runaway generation loop could burn through significant budget.

**Observed costs (Sonnet equivalent pricing):**

| Fixture type | Duration | Cost |
|---|---|---|
| `/blueprint` Lite (6 docs) | ~10 min | $1.50-2.00 |
| `/kickstart` Full (7+ docs) | ~20 min | $5-8.00 |
| `/blueprint` no-DB edge case | ~8 min | $1.50 |

### `--no-session-persistence`

Each run creates a throwaway session. Without this flag, headless runs pollute your session picker with dozens of test sessions.

### `--add-dir`

Grants Claude Code access to an additional directory beyond the cwd. We use this to point at the output directory where generated files land.

**Gotcha #6:** The path must exist before the run starts. Claude Code does not create it. If it does not exist, you get a silent failure where no files are written but the run appears to succeed.

### Rate limits and fork behaviour

**Gotcha #7:** Rate limits in headless mode emit `rate_limit_event` objects in the stream but do not terminate the run. The process sleeps and retries automatically. This is good for reliability but means a rate-limited run can take 3-5x longer than expected. Our 10-minute fixture once took 45 minutes during a rate limit storm.

**Gotcha #8:** If you fork the Claude Code process (e.g., running multiple fixtures in parallel), each fork shares the same rate limit bucket tied to your account. Three parallel runs do not get 3x throughput -- they get the same throughput split three ways, with more rate limit events. Sequential execution is more predictable.

### The stream-json output parsing

Parsing the stream-json output requires handling interleaved event types. Here is the minimal viable parser logic:

```python
import json, sys

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    event = json.loads(line)
    if event["type"] == "result":
        cost = event.get("total_cost_usd", "unknown")
        reason = event.get("stop_reason", "unknown")
        print(f"Done. Cost: ${cost}, Reason: {reason}")
    elif event["type"] == "assistant":
        # Model text output -- usually not needed if you
        # care about generated files rather than chat text
        pass
```

**Gotcha #9:** The `result` event is not always the last line. Occasionally a final `rate_limit_event` or trailing newline follows it. Do not assume the stream ends cleanly after `result`.

### What we built with this

Our runner script (`tests/run-fixture-headless.sh`, ~160 lines of bash) wraps all of the above into a single command:

```bash
bash tests/run-fixture-headless.sh fixture-02-tg-bot --model sonnet --budget 10.00
```

It creates the output directory, pipes the fixture's `stream.jsonl` into `claude -p`, waits for completion, runs `verify_snapshot.py` against the output, and reports pass/fail. On pass, the output directory is cleaned up. On fail, it is preserved for debugging.

We have 3 active fixtures and 7 pending stubs. The active ones validate that `/kickstart` and `/blueprint` produce the right file structure, section headings, content markers, and count constraints (e.g., "at least 15 API endpoints for a 6-table SaaS").

### The self-improvement loop this enables

Having automated behavioural testing closes a loop: human finds a drift in the methodology, we add a meta-review gate (we now have 25+ such gates), and the behavioural test confirms the fix holds across realistic scenarios. In the v1.13.2 to v1.17.0 release series, 4 user observations produced 5 new gates, each catching a class of documentation drift that structural checks alone missed.

The headless runner is what makes this sustainable. Without it, testing a methodology change means manually running `/kickstart`, waiting 20 minutes, and eyeballing the output. With it, we run a command and get a pass/fail in 10 minutes.

### Limitations and open questions

1. **Non-determinism.** LLM output varies between runs. Our snapshot contracts are deliberately loose (section heading patterns, count minimums) rather than exact-match. This means some regressions slip through. We have not found a good solution to this yet.

2. **Cost at scale.** 10 fixtures at $2-8 each is $20-80 per full run. We run on release branches only, not every PR. At 4 releases/month, that is $80-320/month -- manageable but not free.

3. **No multi-turn yet.** Our `stream.jsonl` files contain a single user message with pre-seeded clarifications. True multi-turn testing (send message, parse response, send follow-up) is possible with stream-json but we have not implemented it.

4. **Model version pinning.** We pin `--model sonnet` but Anthropic updates the model behind that alias. A snapshot that passed on Sonnet 3.5 might fail on Sonnet 4 if output structure changes. We have no way to pin to a specific model checkpoint.

### The repo

idea-to-deploy is MIT-licensed: https://github.com/HiH-DimaN/idea-to-deploy

The headless runner, snapshot validator, and meta-review scripts are all in `tests/`. The methodology itself is 20 skills covering project creation, daily work (bugfix, refactor, test, perf, security audit, deps audit, migrate, harden, infra), product discovery, documentation, and session persistence.

If you are doing anything similar with headless Claude Code or automated LLM testing, I would be curious to hear your approach. The flag documentation is sparse and we found most of the above through experimentation.
