#!/usr/bin/env python3
"""Tests of the ITD simplification baseline tools (ADR-016, plan session 2).

Run: python3 -I -B docs/measurements/itd-simplify/test_measure_tools.py
Self-contained: temporary transcripts, homes and projects; no real hook, transcript or runtime is touched.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import egress_acceptance_probe as probe  # noqa: E402
import hook_bench  # noqa: E402
import runtime_digest  # noqa: E402
import summarize_rounds  # noqa: E402


def line(**record) -> str:
    return json.dumps(record) + "\n"


class TranscriptStatsTest(unittest.TestCase):
    def run_stats(self, lines: list[str], *more: list[str]) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            for index, session in enumerate((lines, *more), 1):
                Path(tmp, f"s{index}.jsonl").write_text("".join(session), encoding="utf-8")
            (Path(tmp) / "sub").mkdir()
            Path(tmp, "sub", "agent.jsonl").write_text(lines[0], encoding="utf-8")  # subagent dir is not read
            done = subprocess.run([sys.executable, "-I", "-B", str(HERE / "transcript_stats.py"), tmp,
                                   "--since", "2000-01-01"], capture_output=True, text=True, check=True)
        return json.loads(done.stdout)

    def test_lower_bound_context_and_session_save(self) -> None:
        tool = {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "ls"}}
        skill = {"type": "tool_use", "id": "t2", "name": "Skill", "input": {"skill": "idea-to-deploy:session-save"}}
        lines = [
            line(type="user", uuid="u1", timestamp="2026-10-21T10:00:00Z", message={"content": "do it"}),
            # two records of one UserPromptSubmit event (chained through attachments) are summed: 3 + 4 bytes
            line(type="attachment", uuid="a1", parentUuid="u1",
                 attachment={"type": "hook_additional_context", "hookEvent": "UserPromptSubmit", "content": ["abc"]}),
            line(type="attachment", uuid="a2", parentUuid="a1",
                 attachment={"type": "hook_additional_context", "hookEvent": "UserPromptSubmit", "content": ["дд"]}),
            line(type="attachment", attachment={"type": "hook_success", "hookEvent": "SessionStart",
                                                 "stdout": "x" * 50}),
            line(type="assistant", timestamp="2026-10-21T10:00:05Z", message={"content": [tool]}),
            line(type="attachment", attachment={"type": "hook_success", "hookEvent": "PreToolUse", "toolUseID": "t1",
                                                 "durationMs": 100, "command": "~/.claude/hooks/a.sh"}),
            line(type="attachment", attachment={"type": "hook_success", "hookEvent": "PreToolUse", "toolUseID": "t1",
                                                 "durationMs": 300, "command": '"C:/x/python.exe" "C:/h/b.sh"'}),
            line(type="assistant", timestamp="2026-10-21T10:01:00Z", message={"content": [skill]}),
            line(type="assistant", timestamp="2026-10-21T10:02:00Z", message={"content": [{"type": "text"}]}),
            line(type="user", timestamp="2026-10-21T10:02:30Z",
                 message={"content": [{"type": "tool_result", "tool_use_id": "t2"}]}),
            line(type="assistant", timestamp="2026-10-21T10:03:00Z", message={"content": [{"type": "text"}]}),
            line(type="user", uuid="u2", timestamp="2026-10-21T10:09:00Z", message={"content": "next"}),
            line(type="attachment", uuid="a3", parentUuid="u2",
                 attachment={"type": "hook_additional_context", "hookEvent": "UserPromptSubmit", "content": ["xyz"]}),
        ]
        stats = self.run_stats(lines)
        self.assertEqual(stats["files"], 1)
        self.assertEqual(stats["hooks"]["Bash:PreToolUse"], {"calls": 1, "lowerBoundWallMsMedian": 300})
        self.assertEqual(stats["perCommandMedianMs"]["Bash:PreToolUse:b.sh"], {"n": 1, "median": 300})
        # events u1 (3 + 4 UTF-8 bytes) and u2 (3); the SessionStart stdout is not counted a second time.
        self.assertEqual(stats["context"]["prompts"], 2)
        self.assertEqual(stats["context"]["perPromptBytesMedian"], 5)
        self.assertEqual(stats["context"]["perPromptBytesMax"], 7)
        self.assertEqual(stats["context"]["perSessionBytesMedian"], 10)
        # 10:01:00 -> 10:03:00: a tool result is not a human prompt; the run ends before 10:09:00.
        self.assertEqual(stats["sessionSave"], {"runs": 1, "secondsMedian": 120, "secondsMin": 120,
                                                "secondsMax": 120})

    def test_per_command_name_is_the_script_token(self) -> None:
        tool = {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "ls"}}
        hooks = [("bash ~/.claude/hooks/a.sh --project /home/u/proj", 100),
                 ('"C:/Program Files/nodejs/node.exe" "C:/p/hooks/pre.mjs" pre C:\\Users\\u\\x', 200),
                 ("~/.claude/hooks/a.sh", 300)]
        lines = [line(type="assistant", timestamp="2026-10-21T10:00:05Z", message={"content": [tool]})]
        lines += [line(type="attachment", attachment={"type": "hook_success", "hookEvent": "PreToolUse",
                                                      "toolUseID": "t1", "durationMs": ms, "command": command})
                  for command, ms in hooks]
        per_command = self.run_stats(lines)["perCommandMedianMs"]
        # arguments after the script (paths above all) neither rename nor split a hook's statistics
        self.assertEqual(per_command, {"Bash:PreToolUse:a.sh": {"n": 2, "median": 200.0},
                                       "Bash:PreToolUse:pre.mjs": {"n": 1, "median": 200}})

    def test_event_median_counts_sessions_without_the_event(self) -> None:
        def ctx(uuid: str, event: str, text: str) -> str:
            return line(type="attachment", uuid=uuid, parentUuid="u",
                        attachment={"type": "hook_additional_context", "hookEvent": event, "content": [text]})
        user = line(type="user", uuid="u", timestamp="2026-10-21T10:00:00Z", message={"content": "go"})
        stats = self.run_stats([user, ctx("a", "SessionStart", "x" * 10), ctx("b", "UserPromptSubmit", "ab")],
                               [user, ctx("c", "UserPromptSubmit", "abcd")])
        by_event = stats["context"]["perSessionBytesByEventMedian"]
        self.assertEqual(stats["sessions"], 2)
        self.assertEqual(by_event["SessionStart"], 5)  # median of [10, 0], not of [10]
        self.assertEqual(by_event["UserPromptSubmit"], 3)
        self.assertEqual(by_event["PreToolUse"], 0)

    def test_prompts_and_sessions_without_context_count_as_zero(self) -> None:
        prompt = line(type="user", uuid="p1", timestamp="2026-10-21T10:00:00Z", message={"content": "one"})
        bare = line(type="user", uuid="p2", timestamp="2026-10-21T10:05:00Z", message={"content": "two"})
        ups = line(type="attachment", uuid="a1", parentUuid="p1",
                   attachment={"type": "hook_additional_context", "hookEvent": "UserPromptSubmit", "content": ["abcdef"]})
        silent = line(type="user", uuid="q1", timestamp="2026-10-21T11:00:00Z", message={"content": "quiet"})
        note = line(type="user", uuid="n1", timestamp="2026-10-21T11:01:00Z",
                    message={"content": "<task-notification>done</task-notification>"})  # not a person's prompt
        stats = self.run_stats([prompt, ups, bare], [silent, note])
        self.assertEqual(stats["sessions"], 2)  # the silent transcript is a session too
        self.assertEqual(stats["context"]["prompts"], 3)  # p1 (6 bytes), p2 and q1 (0 bytes)
        self.assertEqual(stats["context"]["perPromptBytesMedian"], 0)
        self.assertEqual(stats["context"]["perSessionBytesMedian"], 3)  # median of [6, 0]

    def test_meta_counts_modes_models_and_versions(self) -> None:
        def rec(**fields) -> str:
            return line(timestamp="2026-10-21T10:00:00Z", **fields)
        stats = self.run_stats([rec(type="user", uuid="u", permissionMode="bypassPermissions", version="2.1.1",
                                    message={"content": "hi"}),
                                rec(type="assistant", version="2.1.2", message={"model": "m-a", "content": []}),
                                rec(type="assistant", version="2.1.2", message={"model": "m-b", "content": []}),
                                rec(type="user", uuid="v", permissionMode="default", message={"content": "x"})])
        meta = stats["meta"]
        self.assertEqual(meta["permissionModes"], {"bypassPermissions": 1, "default": 1})
        self.assertEqual(meta["models"], {"m-a": 1, "m-b": 1})
        self.assertEqual(meta["versions"], {"2.1.2": 2, "2.1.1": 1})
        self.assertEqual(meta["newestTranscriptVersion"], "2.1.2")


class HookBenchTest(unittest.TestCase):
    def test_matcher_semantics(self) -> None:
        self.assertTrue(hook_bench.matches(None, "Bash"))
        self.assertTrue(hook_bench.matches("", "Read"))
        self.assertTrue(hook_bench.matches("*", "Edit"))
        self.assertTrue(hook_bench.matches("Bash|PowerShell", "Bash"))
        self.assertFalse(hook_bench.matches("Edit", "MultiEdit"))
        self.assertFalse(hook_bench.matches("Write|Edit", "Read"))
        self.assertTrue(hook_bench.matches("mcp__", "mcp__") and not hook_bench.matches("mcp__", "Bash"))

    def test_command_labels_name_the_script_and_stay_unique(self) -> None:
        self.assertEqual(hook_bench.command_label('"C:/P/python.exe" -X utf8 "C:/Users/u/.claude/hooks/careful.sh"'),
                         "careful.sh")
        self.assertEqual(hook_bench.command_label('node "/p/hooks/pretooluse.mjs" --flag x'), "pretooluse.mjs")
        self.assertEqual(hook_bench.command_label("cat > /dev/null; exit 3"), "cat > /dev/null; exit 3")
        self.assertEqual(hook_bench.command_labels([("Pre", "user", "~/.claude/hooks/a.sh"),
                                                    ("Pre", "user", "/other/a.sh --x"),
                                                    ("Post", "user", "~/.claude/hooks/a.sh")]),
                         ["Pre:user:a.sh", "Pre:user:a.sh#2", "Post:user:a.sh"])

    def test_sources_and_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home, project = Path(tmp, "home"), Path(tmp, "proj")
            plugin = home / "plugins" / "cache" / "mk" / "plug" / "1.0.0" / "hooks"
            plugin.mkdir(parents=True)
            (project / ".claude").mkdir(parents=True)
            (home / "settings.json").write_text(json.dumps({
                "enabledPlugins": {"plug@mk": True, "off@mk": False},
                "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "u1"}]},
                                         {"matcher": "*", "hooks": [{"type": "command", "command": "u2"}]}]}}),
                encoding="utf-8")
            (project / ".claude" / "settings.json").write_text(json.dumps({
                "hooks": {"PostToolUse": [{"matcher": "Write", "hooks": [{"type": "command", "command": "p1"}]}]}}),
                encoding="utf-8")
            (plugin / "hooks.json").write_text(json.dumps({
                "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
                    {"type": "command", "command": 'node "${CLAUDE_PLUGIN_ROOT}/hooks/pre.mjs"'}]}]}}),
                encoding="utf-8")
            sources = hook_bench.hook_sources(home, project)
            self.assertEqual([label for label, _, _ in sources],
                             ["user", "project/settings.json", "plugin/plug@mk"])
            pre_bash = [command for _, command, _ in hook_bench.commands(sources, "PreToolUse", "Bash")]
            root = str(plugin.parent).replace("\\", "/")
            self.assertEqual(pre_bash, ["u1", "u2", f'node "{root}/hooks/pre.mjs"'])
            self.assertEqual([c for _, c, _ in hook_bench.commands(sources, "PreToolUse", "Read")], ["u2"])
            self.assertEqual(hook_bench.commands(sources, "PostToolUse", "Bash"), [])

    def test_plugin_root_follows_the_host(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            cache = home / "plugins" / "cache" / "mk" / "plug"
            for version in ("1.9.0", "1.10.0", "1.2.0"):
                (cache / version).mkdir(parents=True)
            # without installed_plugins.json: the highest version in numeric order, not lexicographic
            self.assertEqual(hook_bench.plugin_root(home, "plug@mk"), cache / "1.10.0")
            (home / "plugins" / "installed_plugins.json").write_text(json.dumps({"version": 2, "plugins": {
                "plug@mk": [{"scope": "user", "installPath": str(cache / "1.2.0"), "version": "1.2.0"}]}}),
                encoding="utf-8")
            self.assertEqual(hook_bench.plugin_root(home, "plug@mk"), cache / "1.2.0")
            self.assertIsNone(hook_bench.plugin_root(home, "absent@mk"))

    @unittest.skipIf(os.name == "nt", "the bench run uses /bin/bash")
    def test_bench_runs_every_matching_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home, project, marks = Path(tmp, "home"), Path(tmp, "proj"), Path(tmp, "marks")
            home.mkdir(), project.mkdir(), marks.mkdir()
            hook = f'cat > "{marks}/$(date +%s%N)-$$"'
            (home / "settings.json").write_text(json.dumps({"hooks": {
                "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": hook}] * 2}],
                "PostToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": hook}]}]}}),
                encoding="utf-8")
            done = subprocess.run([sys.executable, "-I", "-B", str(HERE / "hook_bench.py"), "--home", str(home),
                                   "--project", str(project), "--runs", "2"], capture_output=True, text=True,
                                  check=True)
            rows = [json.loads(x) for x in done.stdout.splitlines()]
            bash = next(r for r in rows if r.get("tool") == "Bash")
            self.assertEqual(bash["processes"], {"pre": 2, "post": 1, "total": 3})
            self.assertEqual(next(r for r in rows if r.get("tool") == "Read")["processes"]["total"], 1)
            # (1 warm-up + 2 runs) x (Bash 3 + Edit 1 + Read 1) commands, each fed its JSON payload.
            payloads = [json.loads(p.read_text(encoding="utf-8")) for p in marks.iterdir()]
            self.assertEqual(len(payloads), 15)
            self.assertEqual({p["session_id"] for p in payloads}, {"itd-baseline-bench"})
            self.assertTrue(all("tool_response" in p for p in payloads if p["hook_event_name"] == "PostToolUse"))
            self.assertEqual(bash["nonzeroExits"], {})

    @unittest.skipIf(os.name == "nt", "the bench run uses /bin/bash")
    def test_bench_fails_on_a_crashing_hook_and_bad_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home, project = Path(tmp, "home"), Path(tmp, "proj")
            home.mkdir(), project.mkdir()
            (home / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [
                {"matcher": "Bash", "hooks": [{"type": "command", "command": "cat > /dev/null; exit 3"}]}]}}),
                encoding="utf-8")
            argv = [sys.executable, "-I", "-B", str(HERE / "hook_bench.py"), "--home", str(home),
                    "--project", str(project)]
            done = subprocess.run(argv + ["--runs", "1"], capture_output=True, text=True)
            self.assertEqual(done.returncode, 1)
            bash = next(json.loads(x) for x in done.stdout.splitlines() if '"tool": "Bash"' in x)
            self.assertEqual(bash["nonzeroExits"], {"Pre:user:cat > /dev/null; exit 3": 2})  # warm-up + 1 call
            for bad in ("0", "-1"):
                self.assertEqual(subprocess.run(argv + ["--runs", bad], capture_output=True).returncode, 2)


class DigestAndProbeTest(unittest.TestCase):
    def test_runtime_digest_is_content_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("a", "b"):
                Path(tmp, name, "skills").mkdir(parents=True)
                Path(tmp, name, "skills", "x.py").write_bytes(b"print(1)\n")
                Path(tmp, name, "y.txt").write_bytes(b"y")
            first, second = runtime_digest.tree_digest(str(Path(tmp, "a"))), runtime_digest.tree_digest(str(Path(tmp, "b")))
            self.assertEqual(first, second)
            self.assertEqual(first[0], 2)
            Path(tmp, "b", "y.txt").write_bytes(b"z")
            self.assertNotEqual(first[1], runtime_digest.tree_digest(str(Path(tmp, "b")))[1])
            Path(tmp, "empty").mkdir()
            for root in (Path(tmp, "missing"), Path(tmp, "empty"), Path(tmp, "a", "y.txt")):
                with self.assertRaises(SystemExit):
                    runtime_digest.tree_digest(str(root))
            script = [sys.executable, "-I", "-B", str(HERE / "runtime_digest.py")]
            # a call without roots is a usage error, never an empty successful measurement
            bare = subprocess.run(script, capture_output=True, text=True)
            self.assertEqual((bare.returncode, bare.stdout), (2, ""))
            self.assertIn("usage", bare.stderr)
            done = subprocess.run([*script, str(Path(tmp, "a"))], capture_output=True, text=True)
            self.assertEqual(done.returncode, 0)
            self.assertEqual(done.stdout.split()[1:], [str(first[0]), first[1]])

    def test_rounds_summary_is_the_median_of_round_medians(self) -> None:
        def record(tool: str, split: tuple[int, int], chain: int, pre: int, post: int, exits: dict | None = None):
            return line(tool=tool, processes={"pre": split[0], "post": split[1], "total": sum(split)},
                        preWallMs={"median": pre}, postWallMs={"median": post}, chainWallMs={"median": chain},
                        nonzeroExits=exits or {})

        def log(tmp: str, phase: str, entry: str) -> None:
            with Path(tmp, f"meta-{phase}.txt").open("a", encoding="utf-8") as meta:
                meta.write(entry + "\n")

        def write_round(tmp: str, phase: str, combo: str, index: int, chain: int, pre: int, post: int,
                        tools=summarize_rounds.TOOLS, split=(9, 3)) -> None:
            Path(tmp, f"bench-{phase}-{combo}-r{index}.jsonl").write_text(
                line(home="h") + "".join(record(tool, split, chain, pre, post) for tool in tools))
            log(tmp, phase, f"{combo} r{index} exit=0 load_after=1.0")

        script = [sys.executable, "-I", "-B", str(HERE / "summarize_rounds.py")]
        with tempfile.TemporaryDirectory() as tmp:
            for combo in summarize_rounds.COMBOS:
                for index, (chain, pre, post) in enumerate(((900, 500, 400), (500, 300, 200), (700, 450, 250)), 1):
                    write_round(tmp, "after", combo, index, chain, pre, post)
            write_round(tmp, "before", "wsl-itd", 1, 1, 1, 1)  # another phase is not read
            lines, problems = summarize_rounds.summary(Path(tmp), "after")
            self.assertEqual(lines[3], "| wsl-itd | Bash | 12 (9+3) | 700 | 900 / 500 / 700 | 450 / 250 |")
            self.assertEqual((len(lines), problems), (3 + 4 * 3, []))
            self.assertEqual(subprocess.run([*script, tmp, "after"], capture_output=True).returncode, 0)
            # an empty directory, a misspelled phase, a missing combination: never a successful summary
            with tempfile.TemporaryDirectory() as empty:
                self.assertEqual(subprocess.run([*script, empty, "after"], capture_output=True).returncode, 1)
            self.assertEqual(subprocess.run([*script, tmp, "afterr"], capture_output=True).returncode, 1)
            self.assertEqual(len(summarize_rounds.summary(Path(tmp), "before")[1]), 4)  # 3 combos absent + counts
            # a round without one tool, a split that moves at the same total, a crashing hook, a broken line
            write_round(tmp, "after", "win-itd", 4, 600, 300, 300, tools=("Bash", "Edit"), split=(8, 4))
            Path(tmp, "bench-after-win-itd-r4.jsonl").write_text(
                Path(tmp, "bench-after-win-itd-r4.jsonl").read_text()
                + record("Read", (2, 1), 1, 1, 1, {"Pre:user:a.sh": 1}) + "not json\n")
            lines, problems = summarize_rounds.summary(Path(tmp), "after")
            self.assertIn("VARIES [(8, 4, 12), (9, 3, 12)]", [l for l in lines if "| win-itd | Bash |" in l][0])
            self.assertTrue(any("round counts differ" in p for p in problems))
            self.assertTrue(any("nonzeroExits" in p for p in problems))
            self.assertTrue(any("not json" in p for p in problems))
            write_round(tmp, "after", "win-itd", 4, 600, 300, 300, tools=("Bash", "Edit"))
            self.assertIn("win-itd: bench-after-win-itd-r4.jsonl: 0 Read records, expected 1",
                          summarize_rounds.summary(Path(tmp), "after")[1])
            # a duplicate in one round and a gap in another do not cancel out
            Path(tmp, "bench-after-win-itd-r4.jsonl").unlink()
            write_round(tmp, "after", "win-itd", 2, 500, 300, 200, tools=("Bash", "Edit", "Read", "Read"))
            write_round(tmp, "after", "win-itd", 3, 700, 450, 250, tools=("Bash", "Edit"))
            problems = summarize_rounds.summary(Path(tmp), "after")[1]
            self.assertIn("win-itd: bench-after-win-itd-r2.jsonl: 2 Read records, expected 1", problems)
            self.assertIn("win-itd: bench-after-win-itd-r3.jsonl: 0 Read records, expected 1", problems)
            self.assertEqual(subprocess.run([*script, tmp], capture_output=True).returncode, 2)

    def test_rounds_summary_requires_a_clean_run_log(self) -> None:
        one = line(home="h") + "".join(
            line(tool=tool, processes={"pre": 9, "post": 3, "total": 12}, preWallMs={"median": 1},
                 postWallMs={"median": 1}, chainWallMs={"median": 2}, nonzeroExits={})
            for tool in summarize_rounds.TOOLS)
        clean = [f"{combo} r1 exit=0 load_after=1.0" for combo in summarize_rounds.COMBOS]
        cases = {
            "clean log": (clean, 0),
            "no run log": (None, 1),
            "a failed bench step": ([*clean[:3], "win-itd r1 exit=1 load_after=1.0"], 2),
            "a failed transcript step": ([*clean, "transcripts-wsl-itd exit=2"], 1),
            "a skipped round under load": ([*clean, "wsl-itd r2 load_timeout load=4.2 at t"], 1),
            "a round file without its exit record": (clean[:3], 1),
        }
        for label, (meta, expected) in cases.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                for combo in summarize_rounds.COMBOS:
                    Path(tmp, f"bench-after-{combo}-r1.jsonl").write_text(one)
                if meta is not None:
                    Path(tmp, "meta-after.txt").write_text("".join(entry + "\n" for entry in meta))
                problems = summarize_rounds.summary(Path(tmp), "after")[1]
                self.assertEqual(len(problems), expected, problems)

    def test_run_rounds_stops_when_the_windows_copy_cannot_be_refreshed(self) -> None:
        def run(win_src: Path, tmp: Path) -> subprocess.CompletedProcess:
            env = {**os.environ, "HOME": str(tmp), "RAW": str(tmp / "raw"), "WIN_SRC": str(win_src)}
            return subprocess.run(["bash", str(HERE / "run_rounds.sh"), "after", "0"], env=env,
                                  capture_output=True, text=True, timeout=60)
        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp = Path(raw_tmp)
            (tmp / "blocker").write_text("a file where the copy directory should be\n")
            occupied = tmp / "occupied"
            (occupied / "hook_bench.py").mkdir(parents=True)  # any user, root and Windows included: cp lands inside
            (occupied / "hook_bench.py" / "keep").write_text("stale\n")
            cases = {"the copy directory cannot be created": tmp / "blocker" / "baseline",
                     "the copy path is a directory": occupied}
            if os.name != "nt" and os.geteuid() != 0:  # root writes into a read-only directory
                stale = tmp / "stale"
                stale.mkdir()
                (stale / "hook_bench.py").write_text("# stale copy\n")
                (stale / "hook_bench.py").chmod(0o444)
                stale.chmod(0o555)
                cases["a stale copy cannot be overwritten"] = stale
            try:
                for label, win_src in cases.items():
                    with self.subTest(label):
                        result = run(win_src, tmp)
                        self.assertEqual(result.returncode, 1, result.stderr)
                        self.assertIn("cannot refresh", result.stderr)
                        self.assertFalse((tmp / "raw" / "meta-after.txt").exists(), "a round log was started")
                if "a stale copy cannot be overwritten" in cases:
                    self.assertEqual((tmp / "stale" / "hook_bench.py").read_text(), "# stale copy\n")
            finally:
                if (tmp / "stale").exists():
                    (tmp / "stale").chmod(0o755)

    def test_probe_helpers(self) -> None:
        if os.name != "nt":
            self.assertEqual(probe.to_wsl('"C:/P/python.exe" -X utf8 "C:/h/g.sh"'),
                             '"/mnt/c/P/python.exe" -X utf8 "C:/h/g.sh"')
        self.assertEqual(probe.to_wsl("~/.claude/hooks/g.sh"), "~/.claude/hooks/g.sh")
        self.assertEqual(probe.decision('{"hookSpecificOutput": {"permissionDecision": "ask"}}'), "ask")
        self.assertEqual(probe.decision(""), "none")
        self.assertEqual(probe.decision("not json"), "unparsed")
        self.assertTrue(probe.matches({"none"}, 0, "none"))
        self.assertFalse(probe.matches({"none"}, 2, "none"))  # a crashing hook is not a pass
        self.assertFalse(probe.matches({"none"}, 0, "unparsed"))
        self.assertTrue(probe.matches({"ask", "deny"}, 2, "deny"))
        self.assertFalse(probe.matches({"ask", "deny"}, 0, "none"))  # an external POST must not pass silently


if __name__ == "__main__":
    unittest.main(verbosity=1)
