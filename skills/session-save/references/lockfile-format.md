# `.active-session.lock` — формат и примеры записи

Справочник к Step 4.5 скилла `/session-save`. Читается по необходимости —
правило (писать lockfile при каждом вызове, идемпотентная перезапись,
самоистечение 10 минут) живёт в SKILL.md; здесь — точный формат и код.

Format (JSON, one line is fine):

```json
{
  "timestamp": 1712845200.0,
  "pid": 12345,
  "branch": "feat/session-save-lockfile",
  "project": "/home/user/projects/example",
  "note": "Saved session 2026-04-11: implemented feature X, blocker on Y"
}
```

Fields:
- `timestamp` — Unix epoch seconds (`date +%s` or Python `time.time()`).
  `pre-flight-check.sh` treats locks older than 10 minutes as stale.
- `pid` — current shell pid (`$$` in bash, `os.getpid()` in Python).
- `branch` — current git branch from `git branch --show-current`.
- `project` — absolute path to the project (current `pwd`).
- `note` — one-line summary, same as the MEMORY.md index entry.

Bash example:

```bash
cat > "$MEM_DIR/.active-session.lock" <<EOF
{
  "timestamp": $(date +%s),
  "pid": $$,
  "branch": "$(git branch --show-current 2>/dev/null || echo unknown)",
  "project": "$(pwd)",
  "note": "$SUMMARY"
}
EOF
```

Python example (for skills that use python):

```python
import json, os, subprocess, time
lock = mem_dir / ".active-session.lock"
branch = subprocess.run(
    ["git", "branch", "--show-current"], capture_output=True, text=True
).stdout.strip() or "unknown"
lock.write_text(json.dumps({
    "timestamp": time.time(),
    "pid": os.getpid(),
    "branch": branch,
    "project": str(Path.cwd()),
    "note": summary,
}))
```
