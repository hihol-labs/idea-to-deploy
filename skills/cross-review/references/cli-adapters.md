# Cross-review CLI adapters

Verified-shape, adapt-per-version recipes for shelling out to an external review
model from `/cross-review`. Exact flags vary by CLI version — always prefer the
non-interactive / "exec" / "-p prompt" mode and capture stdout. Treat any
non-zero exit, auth error, or quota/rate-limit message as "engine unavailable"
and move to the next link in the chain (codex → gemini → native Claude review).

## 0. The review prompt

Keep it focused so the external model returns actionable findings, not prose:

```
You are an INDEPENDENT second-opinion reviewer. The following diff was written
and already self-reviewed by a different AI. Find what that reviewer likely
MISSED: correctness bugs, security issues, missed edge cases, broken error
handling. Return a short ranked list: file:line + the concrete problem + a fix.
Be concise. If you find nothing real, say so.
--- DIFF (secrets/PII already redacted) ---
<scrubbed diff here>
```

## 1. Scrub secrets/PII BEFORE egress

A third-party CLI is an external service. Redact before sending. Minimal sed pass
(extend as needed; the `pii-egress-guard.sh` hook is the backstop, not a
substitute):

```bash
scrub() {
  sed -E \
    -e '/-----BEGIN [A-Z ]*PRIVATE KEY-----/,/-----END [A-Z ]*PRIVATE KEY-----/ s/.*/[REDACTED-PRIVATE-KEY]/' \
    -e 's/\b(AKIA|ASIA)[0-9A-Z]{16}\b/[REDACTED-AWS-KEY]/g' \
    -e 's/\bgh[pousr]_[A-Za-z0-9]{36,}\b/[REDACTED-GH-TOKEN]/g' \
    -e 's/\bxox[baprs]-[A-Za-z0-9-]{10,}/[REDACTED-SLACK-TOKEN]/g' \
    -e 's/\bAIza[0-9A-Za-z_-]{35}/[REDACTED-GOOGLE-KEY]/g' \
    -e 's/\b[rs]k_live_[A-Za-z0-9]{16,}/[REDACTED-STRIPE-KEY]/g' \
    -e 's/\bsk-ant-[A-Za-z0-9_-]{20,}/[REDACTED-ANTHROPIC-KEY]/g' \
    -e 's/\bsk-[A-Za-z0-9]{20,}/[REDACTED-KEY]/g' \
    -e 's/(authorization:\s*bearer\s+)[A-Za-z0-9._-]{20,}/\1[REDACTED]/Ig' \
    -e 's/\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b/[REDACTED-EMAIL]/g' \
    -e 's/(password|passwd|api[_-]?key|secret|token)(\s*[=:]\s*)[^ "'"'"'&]{6,}/\1\2[REDACTED]/Ig'
}
```

If a live credential remains after scrubbing, do NOT send the diff externally —
degrade to the native review and tell the user to rotate the credential.

## 2. Detect the engine

```bash
if command -v codex >/dev/null 2>&1; then ENGINE=codex
elif command -v gemini >/dev/null 2>&1; then ENGINE=gemini
else ENGINE=none; fi
```

## 3. OpenAI Codex CLI

Non-interactive "exec" mode reads the prompt and prints to stdout. Wrap in a
timeout; on non-zero exit, fall through.

```bash
PROMPT="$(build_prompt)"   # section 0 + scrubbed diff
if OUT="$(printf '%s' "$PROMPT" | timeout 120 codex exec - 2>/tmp/codex.err)"; then
  echo "engine: codex"; echo "$OUT"
else
  echo "codex unavailable (rc=$?, $(tail -1 /tmp/codex.err 2>/dev/null))" >&2
  # fall through to gemini
fi
```

If `codex exec -` (stdin) is not supported on the installed version, pass the
prompt as an argument: `timeout 120 codex exec "$PROMPT"` — but ONLY for small
diffs: an argument hits the OS `ARG_MAX` limit on large diffs ("Argument list
too long", rc=126, verified live on a ~3.7k-line diff 2026-07-02). For anything
big, keep stdin and redirect from a file instead of a variable:
`timeout 120 codex exec - < "$PROMPT_FILE"`.

Two more "unavailable" shapes seen in the wild (both = degrade, don't block):

- **Config error on startup** — e.g. `Error loading config.toml: unknown variant
  'priority', expected 'fast' or 'flex'` in `service_tier` after a CLI up/downgrade.
  Worth ONE retry with an inline override (`codex -c 'service_tier="flex"' exec …`);
  if that also fails, treat as unavailable and tell the user their
  `~/.codex/config.toml` needs fixing.
- **Cloud handshake timeout** — `timed out waiting for cloud requirements after 15s`
  (network/VPN). No retry loop; fall through the chain.

## 4. Google Gemini CLI

```bash
if OUT="$(printf '%s' "$PROMPT" | timeout 120 gemini -p - 2>/tmp/gemini.err)"; then
  echo "engine: gemini"; echo "$OUT"
else
  echo "gemini unavailable (rc=$?, $(tail -1 /tmp/gemini.err 2>/dev/null))" >&2
  # fall through to native
fi
```

If `-p -` (stdin) is unsupported, use `gemini -p "$PROMPT"`.

## 5. Native fallback (always available)

If `ENGINE=none` or both external calls failed, run a Claude red-team self-review
of the scrubbed diff in-session (a skeptical pass whose job is to REFUTE the
change), and state explicitly that the external second opinion was unavailable
and why. The base `/review` gate is still required regardless.

## Notes

- Never write `/tmp/claude-review-done-*` from this skill — that marker belongs to
  `/review`. Cross-review is additive and must not satisfy the commit gate.
- Always print which engine actually produced the findings (codex / gemini /
  native) so the provenance of the second opinion is explicit.
- Keep the external timeout modest (≈120s) so a hung CLI degrades quickly.
