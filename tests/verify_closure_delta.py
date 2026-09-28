#!/usr/bin/env python3
"""verify_closure_delta.py — CLOSURE-DELTA-1: only closure records change after verification.

REL-1.106.0 route (goal approved 2026-09-27): after the goal harness verifies a unit on the
reviewed tree, the tree that is committed or merged later differs by the harness transition and
the ledger-close records. "Nothing else changed" was checked by eye. The tool
`scripts/itd_closure_delta.py` reads the verified tree from a PASSED adjudication receipt
(`candidate.reviewedTree`), replays the verify transition with the goal harness OF THAT TREE in a
temporary copy, and exits non-zero when the candidate's ledger differs from what the harness
wrote (owner decision 2026-09-29: the etalon comes from the harness, not from a list of shapes).

Contract of this oracle (all in a temporary git repository, never the live one):

  1. Producer-first: the fixture tree carries the harness and the ledger validator of this
     checkout; the base transition is written by the real goal harness (`--activate`, then
     verify) - the reviewed tree is taken after the activation, the closure tree carries what the
     harness wrote to GOAL/STATE/events. Other scenarios (a medium unit with its receipt, a STATE
     unit written by /task, a finished goal, a foreign followup, a red validator) are variants of
     that reviewed tree.
  2. Accepted, silent exit 0: the same tree; the harness transition alone; the full closure
     (harness transition + followup move + an entry appended to DECISIONS + a line inserted into a
     BACKLOG section); the full closure named by a commit; a medium unit bound to this receipt;
     the harness STATE projection over a /task unit; a goal closed by /goal Step 3 with every unit
     verified or skipped; a reviewed tree without a validator.
  3. Rejected, exit 1 with `<path>: WHY` and `FIX:` on stderr, one case per rule, each naming the
     path of the exercised rule: foreign paths and modes, text rules of DECISIONS and BACKLOG,
     journal structure, every appended event beyond the harness transition (a failed attempt
     before the green one, a hook line before or after it, a wrong decision or order), every GOAL
     and STATE difference from the harness transition (normalized fields still checked for
     shape), the receipt binding, the followup move, ledger records for an unverified unit, a red
     validator of the reviewed tree.
  4. Input errors exit 2: receipt not PASSED, not an adjudication, without receiptSha256, not
     JSON, unknown verified tree, a bad --tree, --receipt without --tree, a reviewed tree without
     STATE.json or with an unreadable one, a working-deadline unit and a sealed (bounded) unit
     (refused by the tool itself before the command is substituted, with its own message), a
     harness of the reviewed tree that does not finish within `ITD_CLOSURE_DELTA_TIMEOUT` seconds
     (a value that is not ASCII digits > 0 is ignored, the default applies). No arguments - quiet
     exit 0.
  5. The oracle is registered in tests/run-all.sh.

RED on the pre-fix tree (ed47135): the tool does not exist, every behavioural check fails.
Run: sh skills/_shared/itd_py.sh tests/verify_closure_delta.py
"""
from __future__ import annotations

import calendar
import copy
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "scripts" / "itd_closure_delta.py"
PY = sys.executable
UNIT = "U-1"
PASS_CMD = f'"{PY}" -c "print(chr(111)+chr(107))"'
RECEIPT_SHA = "a" * 64

GOAL = ".itd-memory/GOAL.json"
STATE = ".itd-memory/STATE.json"
EVENTS = ".itd-memory/events.jsonl"
ACCEPTANCE = ".itd/ACCEPTANCE_CONTRACT.json"
DECISIONS = ".itd/DECISIONS.md"
BACKLOG = "BACKLOG.md"
SCOPE = ".itd/SCOPE_LOCK.md"
VALIDATOR = "scripts/validate_state.py"
HARNESS = "skills/goal/scripts/itd_goal_verify.py"

fails: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"PASS  {name}")
    else:
        fails.append(name)
        print(f"FAIL  {name}" + (f"  — {detail}" if detail else ""))


def clean_env(extra: dict | None = None) -> dict:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("GIT_") and k not in ("CLAUDE_PROJECT_DIR",)}
    env.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_AUTHOR_NAME": "Oracle", "GIT_AUTHOR_EMAIL": "oracle@example.com",
                "GIT_COMMITTER_NAME": "Oracle", "GIT_COMMITTER_EMAIL": "oracle@example.com",
                "PYTHONUTF8": "1"})
    env.update(extra or {})
    return env


def git(repo: Path, *args: str, stdin: bytes | None = None, env: dict | None = None) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args], input=stdin, capture_output=True,
                          env=clean_env(env), timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(f"git {args}: {proc.stderr.decode('utf-8', 'replace')}")
    return proc.stdout.decode("utf-8", "replace").strip()


def git_blob(repo: Path, tree: str, rel: str) -> bytes:
    proc = subprocess.run(["git", "-C", str(repo), "cat-file", "blob", f"{tree}:{rel}"],
                          capture_output=True, env=clean_env(), timeout=60)
    return proc.stdout


def tree_with(repo: Path, base: str, changes: dict, modes: dict | None = None) -> str:
    """A tree = `base` with `changes` (path -> bytes, or None to delete), built in a scratch index."""
    env = {"GIT_INDEX_FILE": str(repo.parent / "scratch.index")}
    git(repo, "read-tree", base, env=env)
    for path, data in changes.items():
        if data is None:
            git(repo, "update-index", "--force-remove", path, env=env)
            continue
        sha = git(repo, "hash-object", "-w", "--stdin", stdin=data)
        mode = (modes or {}).get(path, "100644")
        git(repo, "update-index", "--add", "--cacheinfo", f"{mode},{sha},{path}", env=env)
    return git(repo, "write-tree", env=env)


def run_tool(repo: Path, *args: str, env: dict | None = None) -> tuple[int, str, str]:
    proc = subprocess.run([PY, str(TOOL), "--repo", str(repo), *args], capture_output=True,
                          encoding="utf-8", errors="replace", env=clean_env(env), timeout=300)
    return proc.returncode, proc.stdout, proc.stderr


FIXTURE_EVENT_PREFIX = "evt-fixture-"  # the fixture harness stamps its events differently


def run_harness(repo: Path, *args: str) -> subprocess.CompletedProcess:
    """The harness OF THE FIXTURE TREE, not the checkout's: the tool must replay that one."""
    harness = repo / HARNESS
    return subprocess.run([PY, str(harness), *args], cwd=str(repo), capture_output=True,
                          encoding="utf-8", errors="replace", env=clean_env(), timeout=120)


def dump(obj: object) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def edit(data: bytes, fn) -> bytes:
    obj = json.loads(data)
    fn(obj)
    return dump(obj)


def target(goal: dict) -> dict:
    return next(u for u in goal["units"] if u["id"] == UNIT)


def unit_edit(data: bytes, **fields) -> bytes:
    def apply(goal: dict) -> None:
        for key, value in fields.items():
            if value is None:
                target(goal).pop(key, None)
            else:
                target(goal)[key] = value
    return edit(data, apply)


def event_line(event: dict) -> bytes:
    return (json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8")


FOLLOWUP = {"unitId": UNIT, "status": "open", "openedAt": "2026-09-28",
            "selectedClaim": "LOCAL_REVIEWED",
            "reviewPolicy": {"mode": "evidence-first", "riskTier": "low"}}
DECISIONS_TEXT = ("# Decisions\n\n## 2026-09-26 Прошлое решение\n\nПричина: замер маршрута.\n\n"
                  "## 2026-09-27 Второе решение\n\nПричина: решение владельца.\n")
BACKLOG_TEXT = ("# BACKLOG\n\n## P1 - первая запись\n\nОписание первой записи.\n\n"
                "## P2 - вторая запись\n\nОписание второй записи.\n")


def base_files() -> dict:
    goal = {"version": 1, "goal": "Closure-delta fixture goal", "status": "active",
            "createdAt": "2026-09-28T00:00:00Z", "updatedAt": "2026-09-28T00:00:00Z",
            "currentUnitId": "",
            "units": [{"id": UNIT, "criterion": "U-1 passes", "verificationCommand": PASS_CMD,
                       "riskTier": "low", "status": "pending"},
                      {"id": "U-2", "criterion": "U-2 passes", "verificationCommand": PASS_CMD,
                       "riskTier": "low", "status": "pending"}]}
    acceptance = {"version": 2, "purpose": "fixture contract", "activeFollowup": FOLLOWUP,
                  "closedFollowups": [{"unitId": "U-0", "status": "closed",
                                       "closedAt": "2026-09-27T00:00:00Z",
                                       "closureEvidence": "earlier unit"}]}
    # The smallest STATE mirror that hooks/validate_state_core.py accepts (fail-closed fields).
    state = {"version": 1, "sessionState": "ACTIVE", "currentStage": "VERIFY", "intent": "fixture",
             "classification": {}, "architecture": {}, "existingProject": {}, "currentUnit": {},
             "gateResults": {"nextStepApproval": "pending"}, "verificationHistory": [], "decisionLog": [], "artifacts": [],
             "completedModules": [], "failedValidations": [], "blockers": [],
             "humanSteering": {"approvalStatus": "approved", "recommendedNextStep": "verify U-1"},
             "eventLog": {}, "nextAction": "verify U-1", "ledgerFiles": []}
    return {GOAL: dump(goal), STATE: dump(state),
            EVENTS: b'{"id":"e0","type":"note","note":"seed"}\n',
            ACCEPTANCE: dump(acceptance), DECISIONS: DECISIONS_TEXT.encode("utf-8"),
            BACKLOG: BACKLOG_TEXT.encode("utf-8"),
            SCOPE: b"# U-1\n\n## Current Task\n\n- U-1: fixture\n",
            "src/app.py": b"print('app')\n"}


class Scenario:
    """A verified tree, its receipt and the closure delta the oracle mutates."""

    def __init__(self, repo: Path, tmp: Path, name: str, base: str, closure: dict,
                 receipt_sha: str = RECEIPT_SHA, tier: str = "low") -> None:
        self.repo, self.base, self.closure = repo, base, closure
        # The harness records the receipt path relative to the project root, so the
        # receipt lives inside the repository (untracked: trees are built from the index).
        self.receipt = repo / "receipts" / f"{name}-adjudication.json"
        self.receipt.parent.mkdir(exist_ok=True)
        self.receipt_obj = {"version": 1, "kind": "adjudication", "unitId": UNIT,
                            "outcome": "PASSED", "receiptSha256": receipt_sha,
                            "candidate": {"reviewedTree": base, "riskTier": tier},
                            "dependencies": {"machine": {"path": f"receipts/{name}-machine.json",
                                                         "sha256": "e" * 64}}}
        self.receipt.write_text(json.dumps(self.receipt_obj), encoding="utf-8")

    def record(self) -> dict:
        """The verificationReceipt the harness derives from this receipt file."""
        return {"path": self.receipt.relative_to(self.repo).as_posix(),
                "sha256": hashlib.sha256(self.receipt.read_bytes()).hexdigest(),
                "receiptSha256": self.receipt_obj["receiptSha256"], "outcome": "PASSED",
                "machinePath": self.receipt_obj["dependencies"]["machine"]["path"],
                "machineSha256": self.receipt_obj["dependencies"]["machine"]["sha256"]}

    def tree(self, changes: dict | None = None, modes: dict | None = None) -> str:
        return tree_with(self.repo, self.base, {**self.closure, **(changes or {})}, modes)

    def run(self, tree: str, env: dict | None = None) -> tuple[int, str, str]:
        return run_tool(self.repo, "--receipt", str(self.receipt), "--tree", tree, env=env)

    def accept(self, name: str, changes: dict | None = None, tree: str = "",
               env: dict | None = None) -> None:
        rc, out, err = self.run(tree or self.tree(changes), env)
        check(name, rc == 0 and not out and not err, f"rc={rc} out={out!r} err={err[-400:]!r}")

    def reject(self, name: str, changes: dict, fragment: str, modes: dict | None = None,
               path: str = "") -> None:
        """The finding line is `<path>: <WHY>` for the path of the exercised rule."""
        rc, _out, err = self.run(self.tree(changes, modes))
        if path:
            paths = [path]
        elif modes:
            paths = list(modes)
        elif len(changes) == 1:
            paths = list(changes)
        elif ": " in fragment:
            paths = [fragment.split(": ", 1)[0]]
        else:
            paths = []  # the case must name the path of the rule it exercises
        rows = err.splitlines()
        located = any(fragment in row and any(row.startswith(f"{p}: ") for p in paths)
                      for row in rows)
        check(name, rc == 1 and located and "  FIX: " in err,
              f"rc={rc} expected `<path>: ...{fragment}` err={err[-400:]!r}")

    def input_error(self, name: str, changes: dict | None = None, fragment: str = "",
                    env: dict | None = None) -> None:
        # `fragment` pins the refusal to the tool's own message, not to a harness failure.
        rc, out, err = self.run(self.tree(changes), env)
        check(name, rc == 2 and not out and "itd_closure_delta:" in err and fragment in err
              and "Traceback" not in err,
              f"rc={rc} expected {fragment!r} err={err[-300:]!r}")


def main() -> int:
    if not TOOL.is_file():
        check("tool-exists", False, f"{TOOL} is missing")
    with tempfile.TemporaryDirectory(prefix="itd-closure-delta-") as tmp_name:
        tmp = Path(tmp_name)
        repo = tmp / "repo"
        repo.mkdir()
        git(repo, "init", "-q")
        base = base_files()
        for rel, data in base.items():
            (repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (repo / rel).write_bytes(data)
        # The tool replays the transition with the harness OF THE REVIEWED TREE, so the
        # fixture tree carries the harness and the ledger validator of this checkout.
        ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
        for part in ("skills/_shared", "skills/goal/scripts", "skills/task/scripts"):
            shutil.copytree(ROOT / part, repo / part, ignore=ignore)
        shutil.copytree(ROOT / "scripts", repo / "scripts", ignore=ignore)
        (repo / "hooks").mkdir()
        shutil.copy(ROOT / "hooks" / "validate_state_core.py", repo / "hooks" / "validate_state_core.py")
        # Make the reviewed tree's harness distinguishable from the checkout's: its event ids carry
        # another prefix. A tool that replayed the checkout harness would produce `evt-goal-` ids
        # and fail the etalon comparison against this fixture's transition.
        fixture_harness = repo / "skills" / "goal" / "scripts" / "itd_goal_verify.py"
        src = fixture_harness.read_text(encoding="utf-8")
        assert src.count('f"evt-goal-') == 2, "the harness event id prefix moved; update the fixture patch"
        fixture_harness.write_text(src.replace('f"evt-goal-', f'f"{FIXTURE_EVENT_PREFIX}'), encoding="utf-8")

        print("[1] producer-first: the real goal harness writes the transition")
        act = run_harness(repo, "--activate", UNIT)
        check("harness-activate", act.returncode == 0, (act.stdout + act.stderr)[-300:])
        git(repo, "add", "-A")
        reviewed = git(repo, "write-tree")
        ver = run_harness(repo, UNIT)
        check("harness-verify", ver.returncode == 0 and "VERIFIED" in ver.stdout,
              (ver.stdout + ver.stderr)[-300:])
        wrote = {rel: (repo / rel).read_bytes() for rel in (GOAL, STATE, EVENTS)}
        at_review = {rel: git_blob(repo, reviewed, rel) for rel in wrote}
        check("harness-wrote-ledger", all(wrote[rel] != at_review[rel] for rel in wrote),
              "the harness did not change GOAL, STATE and events")
        verified_unit = target(json.loads(wrote[GOAL]))
        check("harness-verified-unit", verified_unit["status"] == "verified")
        tail = wrote[EVENTS][len(at_review[EVENTS]):]
        real_event = json.loads(tail.decode("utf-8").strip().splitlines()[-1])
        check("harness-verified-event", real_event.get("decision") == "verified", repr(real_event)[:200])
        id_prefix = re.sub(r"\d+-[0-9a-f]{32}$", "", real_event["id"])
        check("fixture-harness-is-distinguishable", id_prefix == FIXTURE_EVENT_PREFIX, id_prefix)

        def harness_event(decision: str, evidence: str = "exit 1: boom", **over) -> dict:
            """A unit event in the exact shape the harness wrote, with fresh id/at/transaction."""
            event = dict(real_event)
            transaction = secrets.token_hex(16)
            event.update({"id": f"{id_prefix}{int(time.time())}-{transaction}",
                          "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                          "decision": decision, "evidence": evidence, "transaction": transaction})
            event.update(over)
            return event

        moved = edit(base[ACCEPTANCE], lambda a: (
            a["closedFollowups"].append({**a["activeFollowup"], "status": "closed",
                                         "closedAt": "2026-09-28T10:00:00Z",
                                         "closureEvidence": "Verified by the goal harness"}),
            a.__setitem__("activeFollowup", {"unitId": "", "status": "none",
                                             "note": "No active unit"})))
        appended = base[DECISIONS] + "\n## 2026-09-28 U-1 закрыт\n\nЦена маршрута.\n".encode()
        backlog = BACKLOG_TEXT.replace(
            "Описание первой записи.\n",
            "Описание первой записи.\n\nСтатус 2026-09-28: закрыто юнитом U-1.\n").encode("utf-8")
        closure = {**wrote, ACCEPTANCE: moved, DECISIONS: appended, BACKLOG: backlog}
        main_sc = Scenario(repo, tmp, "main", reviewed, closure)
        harness_only = Scenario(repo, tmp, "harness", reviewed, wrote)

        # A medium unit: verified with a verificationReceipt bound to its receipt.
        medium_sha = "b" * 64
        medium_base = tree_with(repo, reviewed, {
            GOAL: unit_edit(at_review[GOAL], riskTier="medium"),
            STATE: edit(at_review[STATE], lambda s: s["currentUnit"].__setitem__("riskTier", "medium"))})
        medium = Scenario(repo, tmp, "medium", medium_base, {}, receipt_sha=medium_sha, tier="medium")
        bound = medium.record()
        medium.closure = {
            **closure,
            GOAL: unit_edit(wrote[GOAL], riskTier="medium", verificationReceipt=bound),
            STATE: edit(wrote[STATE], lambda s: s["currentUnit"].__setitem__("riskTier", "medium"))}

        # A pre-existing, acknowledged handoff of an earlier unit: never a transition field here
        # (the harness writes handoffState only for working-deadline units), so it must survive
        # byte for byte - an acknowledgement rewritten after the review is not accepted.
        preacked = {"required": False, "unitId": UNIT, "requiredAt": "2026-09-27T09:00:00Z",
                    "acknowledgedAt": "2026-09-27T09:05:00Z", "acknowledgement": "owner turn"}
        handoff_base = tree_with(repo, reviewed, {GOAL: edit(at_review[GOAL], lambda x: x.__setitem__("handoffState", preacked))})
        handoff_goal = edit(wrote[GOAL], lambda x: x.__setitem__("handoffState", preacked))
        handoff = Scenario(repo, tmp, "handoff", handoff_base, {**closure, GOAL: handoff_goal})

        # A compound command `A && B`: the harness records one evidence row per segment.
        compound_cmd = PASS_CMD + " && " + PASS_CMD
        compound_rows = "\n".join(f"{seg}: exit 0, stdout sha256 {'1' * 16}, ok" for seg in (PASS_CMD, PASS_CMD))
        compound_base = tree_with(repo, reviewed, {GOAL: unit_edit(at_review[GOAL], verificationCommand=compound_cmd)})
        compound_goal = unit_edit(wrote[GOAL], verificationCommand=compound_cmd, evidence=compound_rows)
        compound_events = at_review[EVENTS] + event_line({**real_event, "evidence": compound_rows})
        compound = Scenario(repo, tmp, "compound", compound_base,
                            {**closure, GOAL: compound_goal, EVENTS: compound_events})

        # A STATE unit written by /task: the harness projection rewrites goal/riskTier/notes.
        task_state = edit(at_review[STATE], lambda s: s["currentUnit"].update(
            {"goal": "U-1: /task wording", "riskTier": "high", "riskTierForced": True}))
        projected = Scenario(repo, tmp, "projected",
                             tree_with(repo, reviewed, {STATE: task_state}), closure)

        # A finished goal: U-2 skipped in the verified tree, /goal Step 3 marks the goal done.
        skipped = {"status": "skipped", "skippedReason": "owner decision"}
        done_base = tree_with(repo, reviewed, {GOAL: edit(
            at_review[GOAL], lambda g: g["units"][1].update(skipped))})
        done = Scenario(repo, tmp, "done", done_base, {**closure, GOAL: edit(
            wrote[GOAL], lambda g: (g["units"][1].update(skipped),
                                    g.__setitem__("status", "done")))})

        # A followup of another unit; a journal / DECISIONS without a final newline.
        foreign_followup = edit(base[ACCEPTANCE], lambda a: a["activeFollowup"].__setitem__(
            "unitId", "U-2"))
        foreign = Scenario(repo, tmp, "foreign",
                           tree_with(repo, reviewed, {ACCEPTANCE: foreign_followup}),
                           {**closure, ACCEPTANCE: edit(foreign_followup, lambda a: (
                               a["closedFollowups"].append({**a["activeFollowup"],
                                                            "status": "closed", "closedAt": "x",
                                                            "closureEvidence": "y"}),
                               a.__setitem__("activeFollowup", {"unitId": "", "status": "none"})))})
        unterminated = at_review[EVENTS].rstrip(b"\n")
        decisions_open = base[DECISIONS].rstrip(b"\n")
        no_newline = Scenario(repo, tmp, "no-newline",
                              tree_with(repo, reviewed, {EVENTS: unterminated, DECISIONS: decisions_open}),
                              {**closure, EVENTS: unterminated + b"\n" + tail,
                               DECISIONS: decisions_open + b"\n\n## 2026-09-28 U-1\n"})

        # Reviewed trees the etalon cannot replay: no STATE, an unreadable STATE, a deadline unit.
        no_state = Scenario(repo, tmp, "no-state", tree_with(repo, reviewed, {STATE: None}),
                            {**closure, STATE: None})
        bad_state = Scenario(repo, tmp, "bad-state", tree_with(repo, reviewed, {STATE: b"{\n"}),
                             {**closure, STATE: b"{\n"})
        deadline = Scenario(repo, tmp, "deadline", tree_with(repo, reviewed, {GOAL: unit_edit(
            at_review[GOAL], deadlineState={"profile": "working_deadline", "stopReason": ""})}), closure)

        # The validator of the reviewed tree decides: a red one rejects, an absent one is skipped.
        red_validator = Scenario(repo, tmp, "red-validator", tree_with(repo, reviewed, {
            VALIDATOR: b"import sys\nprint('schema: red', file=sys.stderr)\nsys.exit(1)\n"}), closure)
        no_validator = Scenario(repo, tmp, "no-validator",
                                tree_with(repo, reviewed, {VALIDATOR: None}), closure)

        print("[2] accepted deltas")
        handoff.accept("accept-handoff-preexisting-unchanged")
        # WSL2 steps its clock backwards: a reviewed tree stamped up to 60 s AFTER the transition
        # times is still accepted (the broker's MAX_CLOCK_SKEW_SECONDS), beyond that it is not.
        for label, seconds, ok in (("within-skew", 30, True), ("beyond-skew", 120, False)):
            stamped = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(
                calendar.timegm(time.strptime(real_event["at"], "%Y-%m-%dT%H:%M:%SZ")) + seconds))
            skewed = Scenario(repo, tmp, f"clock-{label}", tree_with(repo, reviewed, {
                GOAL: edit(at_review[GOAL], lambda x, v=stamped: x.__setitem__("updatedAt", v))}), closure)
            if ok:
                skewed.accept(f"accept-clock-step-{label}")
            else:
                skewed.reject(f"reject-clock-step-{label}", {}, "earlier than the reviewed tree's updatedAt", path=GOAL)
        main_sc.accept("accept-same-tree", tree=reviewed)
        harness_only.accept("accept-harness-transition")
        main_sc.accept("accept-full-closure")
        commit = git(repo, "commit-tree", main_sc.tree(), "-m", "ledger-close")
        main_sc.accept("accept-commit-treeish", tree=commit)
        R = main_sc.reject
        R("reject-attempt-event-before-transition",
          {EVENTS: at_review[EVENTS] + event_line(harness_event("verification_failed")) + tail},
          "decision 'verification_failed' is not the harness 'verified' event", path=EVENTS)
        R("reject-hook-line-after-transition", {EVENTS: wrote[EVENTS] + (
            b'{"id":"b1","actor":"human-bypass","type":"completion_bypass",'
            b'"name":"COMPLETION_BYPASS","reason":"stale red signal"}\n')},
          "is not part of the harness transition", path=EVENTS)
        R("reject-status-line-after-transition",
          {EVENTS: wrote[EVENTS] + b'{"type":"status","actor":"harness","name":"U-1","status":"done"}\n'},
          "is not part of the harness transition", path=EVENTS)
        medium.accept("accept-medium-bound-receipt")
        projected.accept("accept-state-projection")
        done.accept("accept-goal-done")
        no_validator.accept("accept-no-validator-in-tree")
        compound.accept("accept-compound-evidence")

        print("[3] rejected mutations - one per rule")
        R = main_sc.reject
        g, s = wrote[GOAL], wrote[STATE]
        # paths, modes, append-only journals
        R("reject-foreign-path-modified", {"src/app.py": b"print('changed')\n"},
          "src/app.py: not a closure record")
        R("reject-foreign-path-added", {"docs/new.md": b"# new\n"}, "docs/new.md: not a closure record")
        R("reject-foreign-path-deleted", {"src/app.py": None}, "not a closure record (status D)",
          path="src/app.py")
        no_backlog = Scenario(repo, tmp, "no-backlog", tree_with(repo, reviewed, {BACKLOG: None}), closure)
        no_backlog.reject("reject-closure-path-added", {}, "status A, mode", path=BACKLOG)
        R("reject-scope-lock", {SCOPE: b"# U-2\n"}, f"{SCOPE}: not a closure record")
        R("reject-decisions-deleted", {DECISIONS: None}, f"{DECISIONS}: status D")
        R("reject-mode-change", {}, f"{DECISIONS}: status M, mode 100644 -> 100755",
          modes={DECISIONS: "100755"})
        R("reject-decisions-middle-edit",
          {DECISIONS: appended.replace("замер маршрута".encode(), "другое".encode())},
          f"{DECISIONS}: the old content is not a prefix")
        R("reject-decisions-insert-before-end",
          {DECISIONS: appended.replace(b"## 2026-09-27", "## 2026-09-28 Вставка\n\n## 2026-09-27".encode())},
          f"{DECISIONS}: the old content is not a prefix")
        R("reject-decisions-fragment", {DECISIONS: appended + b"tail"},
          "the appended part does not end with a newline", path=DECISIONS)
        R("reject-decisions-invalid-utf8", {DECISIONS: appended + b"\xff\n"},
          "the appended part is not UTF-8", path=DECISIONS)
        no_newline.reject("reject-decisions-old-unterminated", {},
                          f"{DECISIONS}: the old content does not end with a newline")
        R("reject-backlog-line-changed", {BACKLOG: backlog.replace("второй записи".encode(), "иначе".encode())},
          f"{BACKLOG}: old line")
        R("reject-backlog-line-removed", {BACKLOG: backlog.replace("## P2 - вторая запись\n".encode(), b"")},
          f"{BACKLOG}: old line")
        R("reject-backlog-fragment", {BACKLOG: backlog + "хвост без перевода".encode()},
          "does not end with a newline - a partial line", path=BACKLOG)
        R("reject-backlog-invalid-utf8", {BACKLOG: backlog + b"\xff\n"}, "is not UTF-8", path=BACKLOG)
        # journal structure
        R("reject-events-rewrite", {EVENTS: wrote[EVENTS].replace(b'"seed"', b'"reseed"')},
          f"{EVENTS}: the old content is not a prefix")
        R("reject-events-partial-line", {EVENTS: wrote[EVENTS] + b'{"id":"e9","type":"note"}'},
          f"{EVENTS}: the appended part does not end with a newline")
        R("reject-events-not-json", {EVENTS: wrote[EVENTS] + b"not json\n"}, "is not UTF-8 JSON")
        R("reject-events-invalid-utf8", {EVENTS: wrote[EVENTS] + b'{"type":"note","x":"\xff"}\n'},
          "is not UTF-8 JSON")
        R("reject-events-not-object", {EVENTS: wrote[EVENTS] + b"[1]\n"}, "is not a JSON object")
        R("reject-events-no-type", {EVENTS: wrote[EVENTS] + b'{"id":"e9"}\n'}, "has no type")
        no_newline.reject("reject-events-old-unterminated", {},
                          f"{EVENTS}: the old content does not end with a newline")
        # unit events the harness does not write at closure
        for name, raw in (("forged-unit", b'{"unitId":"U-2","decision":"verified","actor":"harness","type":"x"}'),
                          ("other-unit", b'{"type":"unit","actor":"harness","name":"U-2","decision":"verified"}'),
                          ("unit-scope", b'{"type":"unit-scope","actor":"harness","name":"U-1","decision":"verified"}'),
                          ("owner-route", b'{"type":"unit","actor":"human-owner","name":"U-1","decision":"verified"}'),
                          ("odd-decision", b'{"type":"unit","actor":"harness","name":"U-1","decision":"skipped"}'),
                          ("blocked-decision", b'{"type":"unit","actor":"harness","name":"U-1","decision":"blocked"}'),
                          ("decision-not-string", b'{"type":"unit","actor":"harness","name":"U-1","decision":["verified"]}')):
            R(f"reject-events-{name}", {EVENTS: wrote[EVENTS] + raw + b"\n"},
              "is not part of the harness transition", path=EVENTS)
        R("reject-events-forged-minimal",
          {EVENTS: at_review[EVENTS] + b'{"type":"unit","actor":"harness","name":"U-1","decision":"verified"}\n'},
          "does not have the harness event fields", path=EVENTS)
        R("reject-events-forged-then-real",
          {EVENTS: at_review[EVENTS] + b'{"type":"unit","actor":"harness","name":"U-1","decision":"verified"}\n' + tail},
          "does not have the harness event fields", path=EVENTS)
        R("reject-event-extra-field", {EVENTS: at_review[EVENTS] + event_line({**real_event, "extra": 1})},
          "does not have the harness event fields", path=EVENTS)
        R("reject-event-missing-field",
          {EVENTS: at_review[EVENTS] + event_line({k: v for k, v in real_event.items() if k != "ledger"})},
          "does not have the harness event fields", path=EVENTS)
        R("reject-event-bad-id", {EVENTS: at_review[EVENTS] + event_line({**real_event, "id": "evt-x"})},
          "is not the harness shape", path=EVENTS)
        R("reject-event-bad-id-prefix",
          {EVENTS: at_review[EVENTS] + event_line({**real_event, "id": "evt-unit-" + real_event["id"].split("-", 2)[2]})},
          "is not the harness shape", path=EVENTS)
        R("reject-event-id-transaction-mismatch",
          {EVENTS: at_review[EVENTS] + event_line({**real_event, "id": real_event["id"][:-32] + "0" * 32})},
          "is not the harness shape", path=EVENTS)
        R("reject-event-wrong-name", {EVENTS: at_review[EVENTS] + event_line({**real_event, "name": "U-2"})},
          "is not a harness unit event of 'U-1'", path=EVENTS)
        R("reject-event-wrong-actor", {EVENTS: at_review[EVENTS] + event_line({**real_event, "actor": "human-owner"})},
          "is not a harness unit event of 'U-1'", path=EVENTS)
        R("reject-event-bad-transaction",
          {EVENTS: at_review[EVENTS] + event_line({**real_event, "transaction": "zz"})},
          "transaction is not a harness transaction id", path=EVENTS)
        R("reject-event-at-not-iso", {EVENTS: at_review[EVENTS] + event_line({**real_event, "at": "yesterday"})},
          "at is not an ISO-8601 UTC timestamp", path=EVENTS)
        R("reject-event-at-earlier",
          {EVENTS: at_review[EVENTS] + event_line({**real_event, "at": "2000-01-01T00:00:00Z"})},
          "earlier than the reviewed tree's updatedAt", path=EVENTS)
        R("reject-event-evidence-mismatch",
          {EVENTS: at_review[EVENTS] + event_line({**real_event, "evidence": "exit 0: other"})},
          "evidence differs from the unit evidence", path=EVENTS)
        R("reject-event-other-ledger",
          {EVENTS: at_review[EVENTS] + event_line({**real_event, "ledger": "STATE"})},
          "ledger 'STATE' !=", path=EVENTS)
        for decision in ("verification_failed", "verification_unverified", "regressed", "activated"):
            R(f"reject-event-after-transition-{decision}",
              {EVENTS: wrote[EVENTS] + event_line(harness_event(decision))},
              "is not part of the harness transition", path=EVENTS)
        R("reject-partial-no-event", {EVENTS: at_review[EVENTS]},
          "the harness verified event of 'U-1' was not appended", path=EVENTS)
        R("reject-checkpoint-instead-of-verified",
          {EVENTS: at_review[EVENTS] + event_line(harness_event("working_deadline_checkpoint", "checkpoint"))},
          "decision 'working_deadline_checkpoint' is not the harness 'verified' event", path=EVENTS)
        R("reject-verified-event-goal-not-verified", {GOAL: at_review[GOAL], STATE: at_review[STATE]},
          "was not verified by the harness in this delta", path=EVENTS)
        R("reject-hook-line-without-transition",
          {GOAL: at_review[GOAL], STATE: at_review[STATE], EVENTS: at_review[EVENTS] + (
              b'{"id":"b1","actor":"human-bypass","type":"completion_bypass",'
              b'"name":"COMPLETION_BYPASS","reason":"stale red signal"}\n')},
          "was not verified by the harness in this delta", path=EVENTS)
        # GOAL against the harness transition
        R("reject-goal-not-object", {GOAL: b"[]\n"}, f"{GOAL}: not a JSON object")
        R("reject-goal-duplicate-key", {GOAL: g.replace(b'"version": 1,', b'"version": 1,\n  "version": 1,', 1)},
          f"{GOAL}: not valid JSON")
        R("reject-goal-top-level", {GOAL: edit(g, lambda x: x.__setitem__("goal", "other"))},
          "differs from the harness transition at goal", path=GOAL)
        R("reject-goal-current-unit", {GOAL: edit(g, lambda x: x.__setitem__("currentUnitId", "U-2"))},
          "at currentUnitId", path=GOAL)
        R("reject-current-unit-kept", {GOAL: edit(g, lambda x: x.__setitem__("currentUnitId", UNIT))},
          "at currentUnitId", path=GOAL)
        R("reject-goal-abandoned", {GOAL: edit(g, lambda x: x.__setitem__("status", "abandoned"))},
          "at status: candidate 'abandoned'", path=GOAL)
        R("reject-goal-done-with-pending", {GOAL: edit(g, lambda x: x.__setitem__("status", "done"))},
          "at status: candidate 'done'", path=GOAL)
        R("reject-goal-done-unit-status-not-string",
          {GOAL: edit(g, lambda x: (x["units"][1].__setitem__("status", ["skipped"]),
                                    x.__setitem__("status", "done")))},
          "at units[1].status", path=GOAL)
        R("reject-goal-updated-at-removed", {GOAL: edit(g, lambda x: x.pop("updatedAt"))},
          "missing ['updatedAt']", path=GOAL)
        R("reject-goal-updated-at-not-iso", {GOAL: edit(g, lambda x: x.__setitem__("updatedAt", "now"))},
          "updatedAt is not an ISO-8601 UTC timestamp", path=GOAL)
        pending = {"required": True, "unitId": UNIT, "requiredAt": "2026-09-28T10:00:00Z",
                   "acknowledgedAt": "", "acknowledgement": ""}
        R("reject-handoff-fabricated", {GOAL: edit(g, lambda x: x.__setitem__("handoffState", pending))},
          "extra ['handoffState']", path=GOAL)
        R("reject-handoff-fabricated-acked", {GOAL: edit(g, lambda x: x.__setitem__(
            "handoffState", {**pending, "required": False, "acknowledgedAt": "2026-09-28T10:05:00Z",
                             "acknowledgement": "new user turn"}))},
          "extra ['handoffState']", path=GOAL)
        for field_, value in (("acknowledgement", "rewritten after review"),
                              ("acknowledgedAt", "2026-09-28T10:05:00Z"), ("required", True)):
            handoff.reject(f"reject-handoff-preexisting-{field_}-changed",
                           {GOAL: edit(handoff_goal, lambda x, f=field_, v=value: x["handoffState"].__setitem__(f, v))},
                           f"at handoffState.{field_}", path=GOAL)
        R("reject-units-not-list", {GOAL: edit(g, lambda x: x.__setitem__("units", {}))},
          "not verified in the later GOAL.json", path=GOAL)
        R("reject-unit-not-object", {GOAL: edit(g, lambda x: x["units"].__setitem__(1, "U-2"))},
          "at units[1]", path=GOAL)
        R("reject-unit-list", {GOAL: edit(g, lambda x: x["units"].pop())}, "at units length", path=GOAL)
        R("reject-unit-reorder", {GOAL: edit(g, lambda x: x["units"].reverse())}, "at units[0]", path=GOAL)
        R("reject-foreign-unit", {GOAL: edit(g, lambda x: x["units"][1].__setitem__("status", "in_progress"))},
          "at units[1].status", path=GOAL)
        R("reject-unit-command-leg", {GOAL: unit_edit(g, verificationCommand=PASS_CMD + " && true")},
          "at units[0].verificationCommand", path=GOAL)
        R("reject-unit-criterion", {GOAL: unit_edit(g, criterion="weaker")}, "at units[0].criterion", path=GOAL)
        R("reject-unit-risk-tier", {GOAL: unit_edit(g, riskTier="none")}, "at units[0].riskTier", path=GOAL)
        R("reject-unit-extra-key", {GOAL: unit_edit(g, note="x")}, "units[0] keys: extra ['note']", path=GOAL)
        R("reject-unit-attempts-by-hand", {GOAL: unit_edit(g, attempts=[{"number": 1, "outcome": "verified"}])},
          "units[0] keys: extra ['attempts']", path=GOAL)
        R("reject-unit-not-verified", {GOAL: unit_edit(g, status="in_progress")},
          "not verified in the later GOAL.json", path=GOAL)
        R("reject-unit-no-verified-at", {GOAL: unit_edit(g, verifiedAt="")},
          "verifiedAt is not an ISO-8601 UTC timestamp", path=GOAL)
        R("reject-unit-verified-at-true", {GOAL: unit_edit(g, verifiedAt=True)},
          "verifiedAt is not an ISO-8601 UTC timestamp", path=GOAL)
        R("reject-unit-verified-at-earlier", {GOAL: unit_edit(g, verifiedAt="2000-01-01T00:00:00Z")},
          "earlier than the reviewed tree's updatedAt", path=GOAL)
        R("reject-unit-verified-at-future", {GOAL: unit_edit(g, verifiedAt="2099-12-31T23:59:59Z")},
          "lies in the future", path=GOAL)
        R("reject-unit-verified-at-impossible", {GOAL: unit_edit(g, verifiedAt="2026-13-45T99:99:99Z")},
          "is not a real UTC moment", path=GOAL)
        import datetime as _dt

        def shift(stamp: str, **delta) -> str:
            moment = _dt.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")
            return (moment + _dt.timedelta(**delta)).strftime("%Y-%m-%dT%H:%M:%SZ")

        # The harness reads the clock three times per transition (verifiedAt, updatedAt, event
        # at); the fixture verify may itself cross a second boundary, so every shifted stamp is
        # relative to the LAST real clock read, never to verifiedAt alone.
        real_at = real_event["at"]
        after_all = shift(real_at, seconds=1)
        far = shift(verified_unit["verifiedAt"], minutes=2)
        main_sc.accept("accept-second-boundary-in-transition", {
            GOAL: edit(g, lambda x: x.__setitem__("updatedAt", after_all)),
            STATE: edit(s, lambda x: x["currentUnit"].__setitem__("completedAt", after_all)),
            EVENTS: at_review[EVENTS] + event_line({**real_event, "at": after_all})})
        R("reject-verified-at-after-the-other-clocks", {GOAL: unit_edit(g, verifiedAt=after_all)},
          "is earlier than the unit verifiedAt", path=GOAL)
        R("reject-updated-at-far-after-verified-at", {GOAL: edit(g, lambda x: x.__setitem__("updatedAt", far))},
          "is more than 0:01:00 after the unit verifiedAt", path=GOAL)
        R("reject-state-completed-at-far-after",
          {STATE: edit(s, lambda x: x["currentUnit"].__setitem__("completedAt", far))},
          "completedAt", path=STATE)
        R("reject-event-at-before-updated-at",
          {GOAL: edit(g, lambda x: x.__setitem__("updatedAt", after_all))},
          "at", path=EVENTS)
        R("reject-event-at-differs-from-completed-at",
          {EVENTS: at_review[EVENTS] + event_line({**real_event, "at": after_all})},
          "at differs from currentUnit.completedAt", path=EVENTS)
        R("reject-evidence-prose", {GOAL: unit_edit(g, evidence="all good")},
          "evidence is not the harness `exit 0: <line>` record", path=GOAL)
        R("reject-evidence-compound-form-for-single", {GOAL: unit_edit(g, evidence="a: exit 0, x\nb: exit 0, y")},
          "evidence is not the harness `exit 0: <line>` record of a single command", path=GOAL)
        cg = compound.closure[GOAL]
        compound.reject("reject-compound-red-leg-with-exit0-tail", {GOAL: unit_edit(
            cg, evidence=f"{PASS_CMD}: exit 1, stdout sha256 {'1' * 16}, tail: exit 0, x\n" + compound_rows.split("\n")[1])},
            "evidence row 1 is not the harness record of segment", path=GOAL)
        compound.reject("reject-compound-wrong-segment", {GOAL: unit_edit(
            cg, evidence=compound_rows.replace(PASS_CMD + ": exit 0", "other: exit 0", 1))},
            "evidence row 1 is not the harness record of segment", path=GOAL)
        compound.reject("reject-compound-row-count", {GOAL: unit_edit(cg, evidence=compound_rows.split("\n")[0])},
                        "evidence has 1 rows for 2 command segments", path=GOAL)
        compound.reject("reject-compound-single-form", {GOAL: unit_edit(cg, evidence="exit 0: ok")},
                        "evidence has 1 rows for 2 command segments", path=GOAL)
        R("reject-receipt-foreign-digest", {GOAL: unit_edit(g, verificationReceipt={**bound, "receiptSha256": "d" * 64})},
          "verificationReceipt is not the record the harness writes", path=GOAL)
        R("reject-receipt-two-keys", {GOAL: unit_edit(g, verificationReceipt={"outcome": "PASSED", "receiptSha256": RECEIPT_SHA})},
          "verificationReceipt is not the record the harness writes", path=GOAL)
        main_record = main_sc.record()
        R("reject-receipt-forged-machine-sha", {GOAL: unit_edit(g, verificationReceipt={**main_record, "machineSha256": "f" * 64})},
          "verificationReceipt is not the record the harness writes", path=GOAL)
        R("reject-receipt-forged-path", {GOAL: unit_edit(g, verificationReceipt={**main_record, "path": "elsewhere.json"})},
          "verificationReceipt is not the record the harness writes", path=GOAL)
        R("reject-receipt-forged-file-sha", {GOAL: unit_edit(g, verificationReceipt={**main_record, "sha256": "f" * 64})},
          "verificationReceipt is not the record the harness writes", path=GOAL)
        reordered = {k: main_record[k] for k in reversed(list(main_record))}
        R("reject-receipt-key-order", {GOAL: unit_edit(g, verificationReceipt=reordered)},
          "verificationReceipt is not the record the harness writes", path=GOAL)
        main_sc.accept("accept-low-unit-with-derived-receipt", {GOAL: unit_edit(g, verificationReceipt=main_record)})
        medium.reject("reject-medium-without-receipt", {GOAL: unit_edit(
            medium.closure[GOAL], verificationReceipt=None)}, "is verified without a verificationReceipt",
            path=GOAL)
        medium.reject("reject-medium-receipt-not-passed", {GOAL: unit_edit(
            medium.closure[GOAL], verificationReceipt={**bound, "outcome": "BLOCKED"})},
            "verificationReceipt is not the record the harness writes", path=GOAL)
        R("reject-goal-record-unit-not-verified",
          {GOAL: edit(at_review[GOAL], lambda x: x.__setitem__("updatedAt", "2026-09-29T00:00:00Z")),
           STATE: at_review[STATE], EVENTS: at_review[EVENTS], ACCEPTANCE: base[ACCEPTANCE]},
          "not verified in the later GOAL.json", path=GOAL)
        red_validator.reject("reject-validator-red", {}, f"fails {VALIDATOR} of the reviewed tree", path=GOAL)
        # STATE against the harness projection
        R("reject-state-foreign-key", {STATE: edit(s, lambda x: x.__setitem__("notes", "x"))},
          "$ keys: extra ['notes']", path=STATE)
        R("reject-state-not-object", {STATE: edit(s, lambda x: x.__setitem__("currentUnit", []))},
          "at currentUnit", path=STATE)
        R("reject-state-other-unit", {STATE: edit(s, lambda x: x["currentUnit"].__setitem__("id", "U-2"))},
          "at currentUnit", path=STATE)
        R("reject-state-unit-extra-key", {STATE: edit(s, lambda x: x["currentUnit"].__setitem__("note", "x"))},
          "currentUnit keys: extra ['note']", path=STATE)
        R("reject-state-unit-not-verified",
          {STATE: edit(s, lambda x: x["currentUnit"].__setitem__("status", "in_progress"))},
          "at currentUnit.status", path=STATE)
        R("reject-state-completed-at-not-iso",
          {STATE: edit(s, lambda x: x["currentUnit"].__setitem__("completedAt", "later"))},
          "completedAt is not an ISO-8601 UTC timestamp", path=STATE)
        R("reject-partial-no-state", {STATE: at_review[STATE]}, "at currentUnit", path=STATE)
        R("reject-state-verified-goal-not-verified", {GOAL: at_review[GOAL], EVENTS: at_review[EVENTS]},
          "not verified in the later GOAL.json", path=STATE)
        projected.reject("reject-state-goal-not-projected",
                         {STATE: edit(s, lambda x: x["currentUnit"].__setitem__("goal", "rewritten"))},
                         "at currentUnit.goal", path=STATE)
        projected.reject("reject-state-note-kept-changed",
                         {STATE: edit(s, lambda x: x["currentUnit"].__setitem__("riskTierForced", False))},
                         "currentUnit keys: extra ['riskTierForced']", path=STATE)
        # ACCEPTANCE
        R("reject-acceptance-foreign-key", {ACCEPTANCE: edit(moved, lambda a: a.__setitem__("purpose", "changed"))},
          "key 'purpose' changed")
        foreign.reject("reject-followup-owner", {}, "activeFollowup belongs to 'U-2'", path=ACCEPTANCE)
        R("reject-acceptance-active-not-empty", {ACCEPTANCE: edit(moved, lambda a: a.__setitem__(
            "activeFollowup", {"unitId": "U-2", "status": "open"}))}, "new activeFollowup is not the empty record")
        R("reject-acceptance-empty-extra-key", {ACCEPTANCE: edit(moved, lambda a: a["activeFollowup"].__setitem__(
            "extra", 1))}, "new activeFollowup is not the empty record")
        R("reject-closed-prefix-changed", {ACCEPTANCE: edit(moved, lambda a: a["closedFollowups"][0].__setitem__(
            "closureEvidence", "rewritten"))}, "closedFollowups is not the old list plus one record")
        R("reject-moved-status", {ACCEPTANCE: edit(moved, lambda a: a["closedFollowups"][-1].__setitem__(
            "status", "open"))}, "moved followup status is 'open'")
        R("reject-moved-differs", {ACCEPTANCE: edit(moved, lambda a: a["closedFollowups"][-1]
                                                   ["reviewPolicy"].__setitem__("riskTier", "high"))},
          "moved followup key 'reviewPolicy' differs")
        R("reject-moved-no-evidence", {ACCEPTANCE: edit(moved, lambda a: a["closedFollowups"][-1].pop(
            "closureEvidence"))}, "moved followup closureEvidence is missing or empty")
        R("reject-moved-empty-closed-at", {ACCEPTANCE: edit(moved, lambda a: a["closedFollowups"][-1].__setitem__(
            "closedAt", " "))}, "moved followup closedAt is missing or empty")
        R("reject-acceptance-move-unit-not-verified",
          {GOAL: at_review[GOAL], STATE: at_review[STATE], EVENTS: at_review[EVENTS]},
          "a closure record changed while the unit 'U-1' is not verified", path=ACCEPTANCE)

        print("[4] input errors and the quiet no-op")
        closure_tree = main_sc.tree()

        def expect_input_error(name: str, *args: str, fragment: str = "") -> None:
            # `fragment` pins the refusal to ONE rule's message, so a neighbouring rule cannot cover for it.
            rc, out, err = run_tool(repo, *args)
            check(name, rc == 2 and not out and "itd_closure_delta:" in err and "Traceback" not in err
                  and fragment in err, f"rc={rc} expected {fragment!r} err={err[-300:]!r}")

        for name, patch, fragment in (
                ("input-receipt-blocked", {"outcome": "BLOCKED"}, "outcome is 'BLOCKED'"),
                ("input-receipt-machine", {"kind": "machine"}, "kind is 'machine'"),
                ("input-receipt-no-digest", {"receiptSha256": ""}, "receiptSha256 is missing"),
                ("input-unknown-tree", {"candidate": {"reviewedTree": "0" * 40, "riskTier": "low"}}, "is not in"),
                ("input-receipt-tier-mismatch", {"candidate": {"reviewedTree": reviewed, "riskTier": "high"}},
                 "candidate.riskTier 'high' is not the reviewed unit's riskTier 'low'"),
                ("input-receipt-tier-missing", {"candidate": {"reviewedTree": reviewed}}, "candidate.riskTier is missing"),
                # a TRUTHY non-object: `(deps or {}).get` would still pass for an empty list
                ("input-receipt-dependencies-not-object", {"dependencies": ["machine"]}, "dependencies.machine is missing")):
            # Inside the repository, so the refusal comes from the receipt content, not its path.
            bad = repo / "receipts" / f"{name}.json"
            bad.write_text(json.dumps({**copy.deepcopy(main_sc.receipt_obj), **patch}), encoding="utf-8")
            expect_input_error(name, "--receipt", str(bad), "--tree", closure_tree, fragment=fragment)
        outside = tmp / "outside-adjudication.json"
        outside.write_text(json.dumps(main_sc.receipt_obj), encoding="utf-8")
        expect_input_error("input-receipt-outside-repository", "--receipt", str(outside), "--tree", closure_tree)
        not_json = repo / "receipts" / "not-json.json"  # inside the repository: the JSON is what fails
        not_json.write_text("{", encoding="utf-8")
        expect_input_error("input-receipt-not-json", "--receipt", str(not_json), "--tree", closure_tree)
        expect_input_error("input-bad-tree", "--receipt", str(main_sc.receipt), "--tree", "no-such-ref")
        expect_input_error("input-receipt-without-tree", "--receipt", str(main_sc.receipt))
        no_state.input_error("input-no-state-in-reviewed-tree")
        bad_state.input_error("input-invalid-state-in-reviewed-tree")
        deadline.input_error("input-working-deadline-unit", fragment="cannot replay a working-deadline unit")
        sealed = Scenario(repo, tmp, "sealed", tree_with(repo, reviewed, {GOAL: edit(at_review[GOAL], lambda x: (
            x.__setitem__("runPolicy", {"mode": "bounded_autonomous", "maxAttemptsPerUnit": 3,
                                        "maxWallClockSecondsPerUnit": 14400, "maxTokensPerSession": 100000,
                                        "freezeVerification": True, "requireApproach": True,
                                        "requireIndependentReview": False, "enforceObservedTokens": False,
                                        "verificationStrategy": "adaptive", "maxCheckpointBytes": 4096,
                                        "sealedPolicy": {}, "sealedFingerprint": "0" * 64}),
            target(x).__setitem__("runState", {"startedAt": "2026-09-28T00:00:00Z",
                                               "verificationFingerprint": "0" * 64})))}), closure)
        sealed.input_error("input-sealed-bounded-unit", fragment="cannot replay a sealed (bounded) unit")
        # A harness of the reviewed tree that never returns: exit 2 after the timeout, no traceback.
        hanging = Scenario(repo, tmp, "hanging-harness", tree_with(repo, reviewed, {
            HARNESS: b"import time\ntime.sleep(30)\n"}), closure)
        hanging.input_error("input-harness-timeout", fragment="did not finish within 1s",
                            env={"ITD_CLOSURE_DELTA_TIMEOUT": "1"})
        # A validator of the reviewed tree that never returns is an input error too, not a pass.
        slow_validator = Scenario(repo, tmp, "hanging-validator", tree_with(repo, reviewed, {
            VALIDATOR: b"import time\ntime.sleep(30)\n"}), closure)
        slow_validator.input_error("input-validator-timeout", fragment=f"{VALIDATOR} of the reviewed tree did not finish",
                                   env={"ITD_CLOSURE_DELTA_TIMEOUT": "5"})
        # A reviewed tree the copy cannot hold (a path component over 255 bytes): the extraction
        # fails closed with exit 2 instead of a traceback (OSError contour).
        unholdable = Scenario(repo, tmp, "unholdable", tree_with(repo, reviewed, {
            "docs/" + "x" * 300 + ".md": b"too long for the copy\n"}), closure)
        unholdable.input_error("input-reviewed-tree-not-extractable", fragment="could not be extracted into a copy")
        # A timeout value that is not ASCII digits (a superscript two, a word) is ignored, not a
        # traceback: the default applies and the closure is accepted as usual.
        for label, raw in (("superscript", "\u00b2"), ("word", "soon"), ("zero", "0")):
            main_sc.accept(f"accept-timeout-knob-ignored-{label}", closure,
                           env={"ITD_CLOSURE_DELTA_TIMEOUT": raw})
        bare = subprocess.run([PY, str(TOOL)], cwd=str(repo), capture_output=True, encoding="utf-8",
                              errors="replace", env=clean_env(), timeout=60)
        check("noop-without-arguments", bare.returncode == 0 and not bare.stdout and not bare.stderr,
              f"rc={bare.returncode} out={bare.stdout!r} err={bare.stderr[-200:]!r}")

    print("[5] registration")
    runall = (ROOT / "tests" / "run-all.sh").read_text(encoding="utf-8")
    full = re.search(r'^FULL="([^"]*)"', runall, re.M)
    suites = full.group(1).replace("\\\n", " ").split() if full else []
    check("run-all-registered", "verify_closure_delta" in suites
          and re.search(r'^\s*for t in \$FULL; do run_py "\$t"; done', runall, re.M) is not None,
          "verify_closure_delta must be a token of FULL, which run-all executes")

    print(f"{'PASSED' if not fails else 'FAILED'}: {len(fails)} failed")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
