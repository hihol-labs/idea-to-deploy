#!/usr/bin/env python3
"""U16: pre-deploy independent review gate — ADR-008 shipment-scoped receipt gate.

The gate is the mechanical half of `/deploy` Step 0: a GATED candidate (data-
sensitive / irreversible / monetary) may not run a recognised deploy transport
unless a Verification Loop adjudication receipt was recorded for the EXACT
current candidate. Redesign 2026-08-12 (ADR-008): the hook no longer parses the
shipment FORM. Statically proving an arbitrary shell command "ships only the
reviewed artifact and executes nothing else" is undecidable and drove an
unbounded review arms race (r53–r89). The tractable, closeable contract is:

  * a gated candidate running a recognised transport (rsync/scp/ssh/tar-non-
    read-only/curl/wget/aws/docker-push/kubectl/terraform/…) or a statically
    OPAQUE command that could HIDE a transport (command/process substitution,
    eval/source/./xargs, case/select, non-lexable) is DENIED without a valid
    current pass;
  * a valid current pass — earned through the adjudication receipt bound to the
    exact candidate digest — ALLOWS the reviewed deploy regardless of the
    transport command's exact shape;
  * ordinary local code execution (interpreters, build/test/task runners,
    scripts, custom executables) and local file operations (rm/mv/editors) are
    OUT OF SCOPE: undecidable to prove they ship nothing, covered by /careful,
    the completion gate and human deploy review — NOT by this hook.

Mutation-tested both directions. Direction 1 (gate must block): the deny cases
and the registration-execution assertions go red if the gate stops blocking a
gated transport or stops being wired into /deploy Step 0. Direction 2 (gate
must not over-block): the routine negative control and the local-execution
allow cases go red if the gate starts demanding a receipt for a routine deploy
or for ordinary dev commands. Receipt-core internals (MAC authentication,
clock-skew tolerance, exact-digest + deploy-input binding, dirty-worktree
invalidation) are proved against the real gate module.

Fixture shape (r53): the trust anchor is NOT HOME-derived, so the hook under
test runs via a generated RUNNER that loads the real hook bytes and repoints
its `INSTALLED_GATE_SCRIPT` global at a fixture install; that fixture install
is a generated WRAPPER that loads the real gate-module bytes and repoints its
`GATE_MAC_KEY_PATH` at a fixture key. Only the two trust-anchor globals differ
from production; every judged byte is the real one.

Run: python3 tests/verify_predeploy_independent_review.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks" / "check-predeploy-gate.sh"
GATE_SCRIPT = ROOT / "skills" / "deploy" / "scripts" / "itd_predeploy_gate.py"
HOOKS_JSON = ROOT / "hooks" / "hooks.json"
DISPATCH = ROOT / "hooks" / "codex-dispatch.py"
SKILL_PATH = ROOT / "skills" / "deploy" / "SKILL.md"

# Fixture destinations are assembled from parts and point at an RFC 2606
# .invalid host, so the repository's own secret scrubber never mistakes a test
# string for a real deploy target.
REMOTE = "deployer@" + "example.invalid"
DEPLOY_CMD = "rsync -az ./ " + REMOTE + ":/srv/app"
ARTIFACT_CMD = "rsync -az .itd-memory/deploy-input.tar " + REMOTE + ":/srv/app"

DATA_SENSITIVE_CLAUDE_MD = "# Fixture project\n\nitd-domain: data-sensitive\n"

LOADER_PRELUDE = """\
import sys
from pathlib import Path
from importlib.machinery import SourceFileLoader
from importlib.util import spec_from_loader, module_from_spec


def _load(name, path):
    loader = SourceFileLoader(name, path)
    spec = spec_from_loader(name, loader)
    module = module_from_spec(spec)
    loader.exec_module(module)
    return module
"""


def gate_module():
    spec = importlib.util.spec_from_file_location("itd_predeploy_gate",
                                                  GATE_SCRIPT)
    if spec is None or spec.loader is None:
        raise SystemExit("unable to load the installed pre-deploy gate script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_gate_wrapper(home: Path) -> tuple[Path, Path]:
    """Fixture "installed" gate script: real bytes, fixture MAC key."""
    key_path = home / ".config" / "itd" / "deploy-gate.key"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    wrapper = (home / ".claude" / "skills" / "deploy" / "scripts"
               / "itd_predeploy_gate.py")
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    wrapper.write_text(
        LOADER_PRELUDE
        + f"module = _load('itd_predeploy_gate', {str(GATE_SCRIPT)!r})\n"
        + f"module.GATE_MAC_KEY_PATH = Path({str(key_path)!r})\n"
        + "sys.exit(module.main(sys.argv[1:]))\n",
        encoding="utf-8")
    return wrapper, key_path


def write_hook_runner(home: Path, installed_gate: Path) -> Path:
    """Runner that executes the real hook bytes against the fixture install."""
    runner = home / "run-hook-under-fixture.py"
    runner.write_text(
        LOADER_PRELUDE
        + f"module = _load('check_predeploy_gate', {str(HOOK)!r})\n"
        + f"module.INSTALLED_GATE_SCRIPT = Path({str(installed_gate)!r})\n"
        + "sys.exit(module.main())\n",
        encoding="utf-8")
    return runner


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True,
                   capture_output=True, text=True, timeout=60)


def make_candidate(base: Path, name: str, data_sensitive: bool) -> Path:
    cwd = base / name
    cwd.mkdir(parents=True)
    git(cwd, "init", "-q")
    git(cwd, "config", "user.email", "predeploy-fixture")
    git(cwd, "config", "user.name", "Predeploy Fixture")
    (cwd / "CLAUDE.md").write_text(
        DATA_SENSITIVE_CLAUDE_MD if data_sensitive else "# Fixture project\n",
        encoding="utf-8")
    (cwd / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    git(cwd, "add", "-A")
    git(cwd, "commit", "-qm", "candidate")
    return cwd


def bash(command: str) -> dict:
    return {"hook_event_name": "PreToolUse", "tool_name": "Bash",
            "tool_input": {"command": command, "description": ""}}


def invoke(cwd: Path, payload: dict, home: Path, entry: Path) -> int:
    env = os.environ.copy()
    env.update({
        "HOME": str(home), "USERPROFILE": str(home), "PYTHONUTF8": "1",
        "ITD_HOST": "claude", "PLUGIN_ROOT": str(ROOT),
        "CLAUDE_SESSION_ID": f"predeploy-{uuid.uuid4().hex[:10]}",
    })
    proc = subprocess.run(
        [sys.executable, str(entry)],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(cwd), env=env, timeout=120)
    return proc.returncode


def run_cli(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE_SCRIPT), *argv],
        capture_output=True, text=True, timeout=120,
        env={**os.environ, "ITD_DEPLOY_MONETARY": ""})


def main() -> int:
    passed = failed = 0

    def check(name: str, condition: bool, detail: str = "") -> None:
        nonlocal passed, failed
        print(("PASS  " if condition else "FAIL  ") + name
              + (f"  [{detail}]" if detail and not condition else ""))
        if condition:
            passed += 1
        else:
            failed += 1

    m = gate_module()

    # ------------------------------------------------------------------ #
    # SECTION 1 — registration / wiring (mutation control, both directions)
    # ------------------------------------------------------------------ #
    check("PreToolUse deploy hook exists", HOOK.is_file())
    check("SKILL.md wires the gate into /deploy Step 0",
          SKILL_PATH.is_file()
          and "itd_predeploy_gate" in SKILL_PATH.read_text(encoding="utf-8"))
    hooks_json = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    bash_hooks = [h for h in hooks_json["hooks"]["PreToolUse"]
                  if h.get("matcher") == "Bash"][0]["hooks"]
    registered = [c.get("command", "") for c in bash_hooks
                  if "check-predeploy-gate" in c.get("command", "")]
    check("deploy hook is registered on the Bash PreToolUse matcher",
          bool(registered))

    if registered:
        # r72: NEVER shell-evaluate the candidate-owned registration string —
        # shlex-split it, expand only PLUGIN_ROOT, allow-list the exact
        # dispatcher argv shape, then execute WITHOUT a shell.
        command = registered[0]
        argv_raw = shlex.split(command)
        argv = [os.path.expandvars(tok) if tok == "$PLUGIN_ROOT"
                else tok.replace("$PLUGIN_ROOT", str(ROOT))
                for tok in argv_raw]
        shape_ok = (
            len(argv) == 4
            and Path(argv[0]).name in ("python3", "python", "py")
            and Path(argv[1]).name == "codex-dispatch.py"
            and DISPATCH.resolve() == Path(argv[1]).resolve()
            and argv[2] == "--script"
            and argv[3] == "check-predeploy-gate.sh")
        check("the registration is EXACTLY the expected dispatcher argv "
              "(parsed, never shell-evaluated — r72)", shape_ok)

        if shape_ok:
            with tempfile.TemporaryDirectory(prefix="itd-u16-disp-") as td:
                base = Path(td)
                gated = make_candidate(base, "gated-disp", data_sensitive=True)
                routine = make_candidate(base, "routine-disp",
                                         data_sensitive=False)
                disp_env = dict(os.environ, PLUGIN_ROOT=str(ROOT))

                def dispatched(cwd: Path) -> subprocess.CompletedProcess:
                    return subprocess.run(
                        [sys.executable, argv[1], argv[2], argv[3]],
                        input=json.dumps({"tool_name": "Bash",
                                          "tool_input": {"command": DEPLOY_CMD}}),
                        capture_output=True, text=True, timeout=180,
                        cwd=str(cwd), env=disp_env)

                d_gated = dispatched(gated)
                check("the registered dispatcher argv DENIES a gated shipping "
                      "command — routing proved by execution (r60/r72)",
                      d_gated.returncode == 2 and '"deny"' in d_gated.stdout,
                      f"rc={d_gated.returncode}")
                d_routine = dispatched(routine)
                # r83: the deny direction alone is met by a default-deny
                # dispatcher; the SAME argv must ALLOW on a routine checkout.
                check("the SAME dispatcher argv ALLOWS that command on a "
                      "ROUTINE checkout — real routing, not default-deny (r83)",
                      d_routine.returncode == 0, f"rc={d_routine.returncode}")

    # ------------------------------------------------------------------ #
    # SECTION 2 — ADR-008 behavioural matrix + receipt-core internals
    # ------------------------------------------------------------------ #
    with tempfile.TemporaryDirectory(prefix="itd-u16-") as td:
        base = Path(td)
        home = base / "home"
        home.mkdir()
        installed_gate, key_path = write_gate_wrapper(home)
        runner = write_hook_runner(home, installed_gate)
        m.GATE_MAC_KEY_PATH = key_path
        hook_repo = make_candidate(base, "gated", data_sensitive=True)
        routine_repo = make_candidate(base, "routine", data_sensitive=False)

        def hook(cmd: str, cwd: Path = hook_repo) -> int:
            return invoke(cwd, bash(cmd), home, entry=runner)

        # --- direction 1: gated + recognised transport, no pass → deny ---
        transport_deny = [
            DEPLOY_CMD,
            "scp build.tar " + REMOTE + ":/srv/",
            "ssh host 'systemctl restart app'",
            "tar -czf build.tgz ./dist",
            "curl -T build.tar https://" + "example.invalid/up",
            "aws s3 cp build.tar s3://bucket/app",
            "terraform apply -auto-approve",
            "docker push registry/image:tag",
            "/usr/bin/rsync -a ./ " + REMOTE + ":/srv/",
        ]
        for cmd in transport_deny:
            check(f"gated + transport, no pass → deny: {cmd[:42]!r}",
                  hook(cmd) == 2)

        # wrapper option operands must not mask the transport head
        for wrapped in ("sudo -u root rsync -a ./ " + REMOTE + ":/srv/",
                        "env -C /tmp docker push registry/image",
                        "timeout 5s kubectl apply -f deploy.yaml",
                        "nice -n 10 scp file " + REMOTE + ":/srv/"):
            check(f"wrapper options do not mask the transport: {wrapped[:38]!r}",
                  hook(wrapped) == 2)

        # --- direction 1: gated + opaque/dynamic (could hide a transport) ---
        for cmd in ('eval "$DEPLOY"',
                    "rsync $(printf %s deployer)@host:/srv/ ./",
                    "echo `id`"):
            check(f"gated + dynamic/opaque, no pass → deny: {cmd[:38]!r}",
                  hook(cmd) == 2)
        check("gated + chained read-only;transport, no pass → deny "
              "(per-invocation)", hook("docker ps; docker push registry/i") == 2)
        # statically opaque forms that could hide a transport are gated: a shell
        # FUNCTION definition (both syntaxes), a `sudo`/`env` mode that spawns a
        # shell or runs an embedded string, a tar option that EXECUTES a command,
        # `eval`, and `case`/`select` compounds.
        opaque = [
            "function deploy { curl -T f " + REMOTE + ":/srv; }; deploy",
            "deploy () { rsync a " + REMOTE + ":/srv; }; deploy",
            "sudo -s",
            "sudo -i rsync a " + REMOTE + ":/srv",
            "env -S 'rsync a " + REMOTE + ":/srv'",
            "env --split-string='rsync a " + REMOTE + ":/srv'",
            "tar --checkpoint-action=exec=sh -cf a.tar d",
            "case $x in *) rsync a " + REMOTE + ":/srv;; esac",
        ]
        for cmd in opaque:
            check(f"gated + opaque (could hide a transport), no pass → deny: "
                  f"{cmd[:34]!r}", hook(cmd) == 2)
        # cd-escape guard (r65, retained under ADR-008): a content-shipping
        # command that changes to a STATICALLY UNRESOLVABLE directory cannot
        # prove which checkout the transport runs in — it may reach a gated one
        # from a routine cwd (`cd "$GATED" && rsync …`) — so it is fail-closed
        # DENIED regardless of the launch candidate's class. Routine candidates
        # are otherwise never gated (the plain-transport routine allow above);
        # this is the one narrow exception, and it is a security guard, not an
        # over-block. A LITERAL cd target stays resolvable and is classified.
        cd_escape = 'cd "$DIR" && rsync -az ./ ' + REMOTE + ":/srv"
        check("routine + transport that cd's to an unresolvable dir → deny "
              "(cd-escape guard, r65 — the one routine exception)",
              hook(cd_escape, routine_repo) == 2)
        check("gated + the same unresolvable-cd transport → deny",
              hook(cd_escape) == 2)

        # --- direction 2: ADR-008 out-of-scope local execution → allow ---
        rm_cmd = "rm -" + "rf ./build"  # assembled so /careful never fires here
        local_allow = [
            "python3 -m pytest",
            "make test",
            "npm run build",
            "bash build.sh",
            rm_cmd,
            "git status --short",
            "vim app.py",
            "/tmp/custom-deploy-tool --go",
        ]
        for cmd in local_allow:
            check(f"gated + local execution (out of scope) → allow: {cmd[:34]!r}",
                  hook(cmd) == 0)

        # a `$(…)`/backtick inside an unquoted shell COMMENT never executes, so
        # it must not be treated as opaque dynamic execution (false-block fix):
        # only a whitespace/line-start `#` is a comment — a mid-word `#` still
        # runs the substitution and stays gated.
        sub = "$(" + "rsync -a . " + REMOTE + ":/srv)"
        for cmd in ("echo harmless # " + sub, "make test # runs $(nproc) jobs"):
            check(f"gated + commented substitution is inert → allow: {cmd[:30]!r}",
                  hook(cmd) == 0)
        check("gated + a mid-word '#' does NOT start a comment, so the "
              "substitution still gates", hook("echo foo#" + sub) == 2)
        # an inert transport in an unquoted comment must not create a spurious
        # gated segment when the operator splitter runs (`;`/`|` inside it):
        for cmd in ("echo ok # inert; " + DEPLOY_CMD,
                    "echo ok # note | rsync x " + REMOTE + ":/srv"):
            check(f"gated + commented operator+transport is inert → allow: "
                  f"{cmd[:30]!r}", hook(cmd) == 0)
        # ...but a real transport on the NEXT line (past the comment's newline)
        # stays gated — the comment must not swallow the following command.
        check("gated + real transport on the line AFTER a comment → deny",
              hook("echo a # c\n" + DEPLOY_CMD) == 2)

        # SECURITY (ADR-008): a recognized transport with a Windows executable
        # suffix must not bypass the gate — `.exe`/`.cmd` is stripped before
        # table matching, path-qualified included.
        for cmd in ("/usr/bin/rsync.exe -a ./ " + REMOTE + ":/srv",
                    "rsync.exe -a ./ " + REMOTE + ":/srv",
                    "docker.exe push registry/image",
                    "bash.exe -c 'rsync -a x " + REMOTE + ":/srv'"):
            check(f"gated + .exe transport does NOT bypass the gate → deny: "
                  f"{cmd[:32]!r}", hook(cmd) == 2)
        for cmd in ("mytool.exe --go", "make.exe test"):
            check(f"gated + a custom/runner .exe (not a transport) → allow: "
                  f"{cmd!r}", hook(cmd) == 0)

        # read-only client calls stay open on a gated candidate
        for cmd in ("docker ps", "tar -tf build.tgz", "kubectl get pods"):
            check(f"gated + read-only client → allow: {cmd!r}", hook(cmd) == 0)

        # non-shipping / non-Bash are untouched
        check("gated + non-shipping Bash command is untouched",
              hook("grep -r TODO .") == 0)

        # --- SECURITY regression 2026-08-12-d (R8 + consolidated parser audit):
        # a leading REDIRECTION is not the command word. `>/tmp/log rsync …`
        # put `>/tmp/log` (or a bare fd number from `2>&1 …`) in head position;
        # the peel stopped at the "path-qualified head" and classified the
        # segment safe while the transport ran ungated (fail-open). Leading
        # redirects — bare (`> f rsync …`), fd-numbered (`2>… `), fd-dup
        # (`2>&1 …`), bash `&>`/clobber `>|`, input (`<in scp …`) — are peeled
        # everywhere a command word is located.
        redirect_hidden = [
            ">/tmp/log " + DEPLOY_CMD,
            "2>/tmp/log " + DEPLOY_CMD,
            "2>&1 " + DEPLOY_CMD,
            "&>/tmp/log " + DEPLOY_CMD,
            ">|/tmp/log " + DEPLOY_CMD,
            "<in.txt scp x " + REMOTE + ":/srv",
        ]
        for cmd in redirect_hidden:
            check(f"gated + leading redirect does NOT hide the transport → deny: "
                  f"{cmd[:34]!r}", hook(cmd) == 2)
        # a redirect GLUED to the command word (`rsync>/tmp/log …`) still runs
        # `rsync`: the pre-redirect prefix is the command word.
        for cmd in ("rsync>/tmp/log -a ./ " + REMOTE + ":/srv",
                    "rsync>log -a ./ " + REMOTE + ":/srv"):
            check(f"gated + redirect glued to the transport word → deny: "
                  f"{cmd[:34]!r}", hook(cmd) == 2)
        # a redirect before the shell `-c` flag must not defeat payload lexing.
        check("gated + `bash >log -c '<transport>'` → deny (payload still lexed)",
              hook("bash >/tmp/log -c 'rsync -a x " + REMOTE + ":/srv'") == 2)
        # a BARE interpreter runs its program from stdin the matcher cannot see
        # (`printf 'rsync …' | bash`, `sh <deploy.sh`) — unresolvable → gate.
        for cmd in ("bash", "sh -x", "sh <deploy.sh"):
            check(f"gated + bare shell reads stdin (computed program) → deny: "
                  f"{cmd!r}", hook(cmd) == 2)
        # `exec -a NAME prog` sets argv[0]; `-a` must consume NAME so `prog`
        # (the real transport) is judged, not NAME.
        check("gated + `exec -a NAME <transport>` → deny (argv[0] mask peeled)",
              hook("exec -a x /usr/bin/rsync -a ./ " + REMOTE + ":/srv") == 2)
        # `chroot NEWROOT cmd` is a transparent prefix runner: peel NEWROOT and
        # judge the wrapped command.
        check("gated + `chroot NEWROOT <transport>` → deny (wrapper peeled)",
              hook("chroot /newroot rsync -a ./ " + REMOTE + ":/srv") == 2)
        # a leading redirect must not hide a directory change from candidate-root
        # classification: `>log cd "$DIR" && rsync …` from a ROUTINE cwd reaches
        # an unresolvable checkout — the cd-escape guard must still fire.
        check("routine + leading-redirect-hidden unresolvable cd + transport → "
              "deny (cd-escape guard survives the redirect)",
              hook(">/tmp/log " + cd_escape, routine_repo) == 2)
        # POSITIVE controls: the redirect peeling must NOT over-block ordinary
        # local execution (ADR-008 out of scope) that merely redirects output.
        for cmd in (">/tmp/out make test", "pytest > out.log",
                    "python3 build.py 2>&1"):
            check(f"gated + local execution with a redirect stays allowed: "
                  f"{cmd!r}", hook(cmd) == 0)

        # --- SECURITY regression (producer round 2026-08-12-e) ----------------
        # 1. An expansion INSIDE the command word keeps a literal-looking head
        #    that the shell rewrites before exec: `r${EMPTY}sync …` (EMPTY
        #    unset) and the brace form run rsync while the matcher saw a
        #    harmless name. Any expansion metacharacter in the command word is
        #    now unresolvable → gated.
        for cmd in ("r${EMPTY}sync -a ./ " + REMOTE + ":/srv",
                    "r{sync} -a ./ " + REMOTE + ":/srv",
                    "rsy*c -a ./ " + REMOTE + ":/srv",
                    "~/bin/rsync -a ./ " + REMOTE + ":/srv"):
            check(f"gated + expansion in the COMMAND WORD → deny: {cmd[:30]!r}",
                  hook(cmd) == 2)
        # positive control: an expansion in an ARGUMENT is untouched — only the
        # command word is judged, so ordinary local work is not over-blocked.
        for cmd in ("grep $PATTERN app.py", "make test BUILD=${CI}"):
            check(f"gated + expansion in an ARGUMENT stays allowed: {cmd!r}",
                  hook(cmd) == 0)
        # 2. A shell payload reached THROUGH a prefix wrapper hid its `cd` from
        #    candidate-root analysis: `sudo bash -c 'cd /gated && rsync …'` was
        #    judged against the routine launch cwd. The payload's directory
        #    changes are now seen, so an unresolvable one denies from a routine
        #    cwd exactly like the top-level form.
        nested_escape = ("sudo bash -c 'cd \"$DIR\" && rsync -az ./ "
                         + REMOTE + ":/srv'")
        check("routine + `sudo bash -c 'cd $VAR && <transport>'` → deny "
              "(nested payload's cd is analysed after the wrapper peel)",
              hook(nested_escape, routine_repo) == 2)
        check("gated + the same nested-wrapper transport → deny",
              hook(nested_escape) == 2)

        # --- direction 2: routine candidate is never gated ---
        check("routine + transport → allow (record not consulted)",
              hook(DEPLOY_CMD, routine_repo) == 0)

        # --- ADR-008 CORE: a valid current pass allows any shipment form ---
        current = m.derive_candidate_digest(hook_repo)
        deploy_input = m.current_deploy_input_sha256(hook_repo)
        check("current deploy input digest is derivable",
              isinstance(deploy_input, str) and len(deploy_input) == 64)
        check("gate pass is recorded for the exact candidate digest",
              m.record_gate_pass(hook_repo, current, m.RISK_DATA_SENSITIVE,
                                 deploy_input) is True)
        for cmd in (DEPLOY_CMD, "ssh host 'systemctl restart app'",
                    "scp anything.tar " + REMOTE + ":/srv/"):
            check("ADR-008: a valid current pass authorises the reviewed deploy "
                  f"regardless of form: {cmd[:34]!r}", hook(cmd) == 0)
        # The pass is bound to the EXACT candidate digest + deploy input, so a
        # valid pass means THIS candidate's deploy was independently reviewed;
        # the hook then authorises it whatever the transport shape. Shipment-
        # form re-analysis is out of scope (see module docstring). The digest/
        # artifact binding that keeps the pass honest is proved next.

        # ----- receipt-core internals (real gate module) ------------------
        foreign = m.gate_ledger_path(hook_repo, current)
        foreign_record = {
            "kind": "itd-predeploy-gate-pass-v1",
            "candidateDigest": "f" * 64, "riskClass": m.RISK_DATA_SENSITIVE,
            "deployInputSha256": "0" * 64, "recordedAt": 4102444800}
        foreign_record["mac"] = m._gate_record_mac(
            foreign_record, m._gate_mac_key(create=True))
        foreign.write_text(json.dumps(foreign_record), encoding="utf-8")
        check("a record naming another candidate digest is refused",
              m.gate_pass_is_current(hook_repo) is False)
        foreign.write_text("{ not json", encoding="utf-8")
        check("an unparseable gate-pass record is fail-closed",
              m.gate_pass_is_current(hook_repo) is False)

        def rewrite_pass(**overrides) -> None:
            record = {"kind": "itd-predeploy-gate-pass-v1",
                      "candidateDigest": m.derive_candidate_digest(hook_repo),
                      "riskClass": m.RISK_DATA_SENSITIVE,
                      "deployInputSha256": m.current_deploy_input_sha256(
                          hook_repo),
                      "recordedAt": int(time.time())}
            record.update(overrides)
            record["mac"] = m._gate_record_mac(record,
                                               m._gate_mac_key(create=True))
            m.gate_ledger_path(hook_repo, record["candidateDigest"]).write_text(
                json.dumps(record), encoding="utf-8")

        rewrite_pass()
        check("a record bound to the current candidate AND its deploy input is "
              "accepted — positive control", m.gate_pass_is_current(hook_repo))
        # recorded_deploy_input_path rejects an unauthenticated / mis-bound
        # record before it can supply a path (the fully-current POSITIVE control
        # is after the emit-artifact block below, where a real pass + artifact
        # exist — a stale/dirty/non-gated record supplies nothing, r86 + r-r7).
        _dig = m.derive_candidate_digest(hook_repo)
        _art = {"kind": "itd-predeploy-gate-pass-v1", "candidateDigest": _dig,
                "riskClass": m.RISK_DATA_SENSITIVE,
                "deployInputSha256": m.current_deploy_input_sha256(hook_repo),
                "deployInputPath": ".itd-memory/deploy-input.tar",
                "recordedAt": int(time.time())}
        m.gate_ledger_path(hook_repo, _dig).write_text(
            json.dumps(dict(_art, deployInputPath="/tmp/attacker.tar",
                            mac="00" * 32)), encoding="utf-8")
        check("recorded_deploy_input_path rejects an invalid MAC — no "
              "unauthenticated artifact path reaches classify (r86)",
              m.recorded_deploy_input_path(hook_repo) is None)
        _foreign = dict(_art, candidateDigest="f" * 64,
                        deployInputPath="/tmp/foreign.tar")
        _foreign["mac"] = m._gate_record_mac(_foreign, m._gate_mac_key())
        m.gate_ledger_path(hook_repo, _dig).write_text(json.dumps(_foreign),
                                                       encoding="utf-8")
        check("recorded_deploy_input_path rejects a MAC-valid record bound to "
              "ANOTHER candidate digest — exact-candidate binding (r88)",
              m.recorded_deploy_input_path(hook_repo) is None)

        # clock-skew tolerance (r79 non-monotone wall clock)
        rewrite_pass(recordedAt=int(time.time())
                     + m.GATE_CLOCK_SKEW_TOLERANCE_SECONDS - 30)
        check("a pass within the clock-skew tolerance (clock stepped back) is "
              "still current — r79", m.gate_pass_is_current(hook_repo))
        rewrite_pass(recordedAt=int(time.time())
                     + m.GATE_CLOCK_SKEW_TOLERANCE_SECONDS + 3600)
        check("a pass dated absurdly far in the future (beyond skew) is refused",
              m.gate_pass_is_current(hook_repo) is False)
        rewrite_pass(deployInputSha256="0" * 64)
        check("a record whose deploy input digest does not match the current "
              "artifact is refused", m.gate_pass_is_current(hook_repo) is False)
        rewrite_pass(riskClass=m.RISK_ROUTINE)
        check("a record claiming a non-gated risk class is refused",
              m.gate_pass_is_current(hook_repo) is False)
        rewrite_pass(deployInputSha256=None)
        check("a record without a deploy input digest is fail-closed",
              m.gate_pass_is_current(hook_repo) is False)

        # a genuine pass must not survive a working-tree change
        rewrite_pass()
        tracked = hook_repo / "CLAUDE.md"
        original = tracked.read_text(encoding="utf-8")
        tracked.write_text(original + "\ndrift after the pass\n",
                           encoding="utf-8")
        check("a dirty worktree invalidates an otherwise valid gate pass",
              m.gate_pass_is_current(hook_repo) is False)
        check("the hook denies again once the candidate drifted from the "
              "reviewed commit", hook(DEPLOY_CMD) == 2)
        tracked.write_text(original, encoding="utf-8")
        subprocess.run(["git", "-C", str(hook_repo), "update-index",
                        "--refresh"], capture_output=True, timeout=60,
                       check=False)
        check("restoring the reviewed content restores the pass — content-"
              "bound, not a one-way latch", m.gate_pass_is_current(hook_repo))

        # security regression: a TRACKED file committed under the ledger
        # directory, modified after a valid pass, MUST invalidate the pass — the
        # directory-wide clean-worktree exemption used to ignore it, letting a
        # pass survive an edit to committed, deployable content (untracked-only
        # exemption fix).
        led = make_candidate(base, "ledger-tracked", data_sensitive=True)
        led_tracked = led / ".itd-memory" / "deploy-gate" / "tracked.txt"
        led_tracked.parent.mkdir(parents=True, exist_ok=True)
        led_tracked.write_text("reviewed\n", encoding="utf-8")
        git(led, "add", "-A")
        git(led, "commit", "-qm", "track a file under the ledger dir")
        m.record_gate_pass(led, m.derive_candidate_digest(led),
                           m.RISK_DATA_SENSITIVE,
                           m.current_deploy_input_sha256(led))
        check("a pass holds while the tracked ledger-dir file is unmodified",
              m.gate_pass_is_current(led) is True)
        led_tracked.write_text("modified after the pass\n", encoding="utf-8")
        check("modifying a TRACKED file inside the ledger directory invalidates "
              "the pass — the exemption is untracked-only, not a hole",
              m.gate_pass_is_current(led) is False)

        # the gate's OWN emitted artifact must not invalidate the pass, and an
        # out-of-checkout deploy input is refused
        artifact = hook_repo / ".itd-memory" / "deploy-input.tar"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        emitted = m.emit_deploy_input(hook_repo, artifact)
        check("the documented --emit-deploy-input artifact is produced",
              isinstance(emitted, str))
        check("a pass produced together with its deploy-input artifact is "
              "usable — the artifact is not counted as drift",
              m.record_gate_pass(hook_repo, m.derive_candidate_digest(
                  hook_repo), m.RISK_DATA_SENSITIVE, str(emitted),
                  deploy_input_path=artifact) is True
              and m.gate_pass_is_current(hook_repo))
        check("recorded_deploy_input_path returns the artifact path from that "
              "fully-current MAC-valid pass — positive control (r86 + r-r7 "
              "freshness/clean/gated/digest)",
              m.recorded_deploy_input_path(hook_repo)
              == ".itd-memory/deploy-input.tar")
        check("the documented gate flow actually unlocks the hook",
              hook(ARTIFACT_CMD) == 0)
        outside = base / "outside-input.tar"
        outside_cli = run_cli("check", "--root", str(hook_repo),
                              "--emit-deploy-input", str(outside))
        check("an out-of-checkout deploy input is refused",
              outside_cli.returncode == 2)

        # ----- receipt-validation delegation (check --receipt) --------------
        # The gate must DELEGATE receipt validation to the Verification Loop
        # and gate on its result: a regression that stops delegating, accepts
        # an invalid receipt, or misbinds candidate coordinates must be caught.
        # `validate_receipt` returns missing|invalid|valid from the delegated
        # checker (argv injectable for a deterministic test); `evaluate_gate`
        # turns that into the allow/deny decision.
        rcpt = hook_repo / ".itd-memory" / "adjudication.json"
        rcpt.parent.mkdir(parents=True, exist_ok=True)
        rcpt.write_text("{}", encoding="utf-8")

        def stub_validator(code: int) -> list[str]:
            s = base / f"stub-validator-{code}.sh"
            s.write_text(f"#!/bin/sh\nexit {code}\n", encoding="utf-8")
            os.chmod(s, 0o755)
            return [str(s)]

        check("validate_receipt: a missing receipt file is 'missing' "
              "(fail-closed, no delegation needed)",
              m.validate_receipt(hook_repo, base / "no-such.json",
                                 "U16:general-review", "high") == "missing")
        check("validate_receipt: a nonzero delegated checker is 'invalid'",
              m.validate_receipt(hook_repo, rcpt, "U16:general-review", "high",
                                 validator_argv=stub_validator(1)) == "invalid")
        check("validate_receipt: a zero-exit delegated checker is 'valid' — "
              "the gate really delegates to the Verification Loop check",
              m.validate_receipt(hook_repo, rcpt, "U16:general-review", "high",
                                 validator_argv=stub_validator(0)) == "valid")
        _dg = m.derive_candidate_digest(hook_repo)
        check("evaluate_gate: gated + valid receipt → allow (review evidence)",
              m.evaluate_gate(m.RISK_DATA_SENSITIVE, "valid", None, _dg)
              .get("allowed") is True)
        for bad in ("missing", "invalid"):
            check(f"evaluate_gate: gated + {bad} receipt → deny (fail-closed)",
                  m.evaluate_gate(m.RISK_DATA_SENSITIVE, bad, None, _dg)
                  .get("allowed") is False)
        check("evaluate_gate: routine + missing receipt → allow (risk-tiered)",
              m.evaluate_gate(m.RISK_ROUTINE, "missing", None, _dg)
              .get("allowed") is True)
        # end-to-end: the real `check --receipt` CLI refuses a missing / garbage
        # receipt on a gated candidate and records NO pass. A valid signed
        # adjudication receipt → allow is exercised by this unit's own live
        # producer→adjudicate→check chain (minting one needs the full
        # Verification Loop — out of a single verifier's scope; stated boundary).
        rr = make_candidate(base, "receipt-gated", data_sensitive=True)
        garbage = base / "garbage-receipt.json"
        garbage.write_text("{ not a receipt", encoding="utf-8")
        for label, arg in (("missing", str(base / "nope.json")),
                           ("garbage", str(garbage))):
            cli = run_cli("check", "--root", str(rr),
                          "--unit-id", "U16:general-review", "--receipt", arg)
            check(f"check --receipt ({label}) on a gated candidate → deny "
                  f"(exit 2, real delegation)", cli.returncode == 2)
        check("a refused receipt records NO gate pass (fail-closed end-to-end)",
              m.gate_pass_is_current(rr) is False)

        # end-to-end POSITIVE: `check --receipt <valid>` DELEGATES to the
        # Verification Loop validator (resolved from the INSTALLED anchor, r81
        # — never a flag), and on a 'valid' result records a usable pass that
        # then authorizes the deploy. A deterministic unit test injects a
        # fixture validator at the installed anchor: the gate's own contract is
        # "delegate to the loop and act on its result", which this exercises
        # both directions. The loop's cryptographic receipt validation is the
        # loop's own suite; the real signed-receipt end-to-end is exercised by
        # THIS unit's live producer→adjudicate→check chain. This closes the
        # "successful CLI validation-to-pass-recording path is untested" gap
        # without a non-deterministic external producer.
        stub_loop = (home / ".claude" / "skills" / "_shared"
                     / "itd_verification_loop.py")
        stub_loop.parent.mkdir(parents=True, exist_ok=True)
        # Producer round 2026-08-12-e (test-coverage finding): the stub used to
        # accept purely on the receipt TEXT and recorded nothing, so it could
        # not detect a regression that delegates without binding the exact
        # candidate. It now RECORDS its argv, and the assertions below prove the
        # gate→validator interface carries the exact candidate digest, the
        # deploy-input digest and path, the unit id and the risk tier.
        argv_log = base / "validator-argv.json"
        stub_loop.write_text(
            "import json, sys\n"
            f"open({str(argv_log)!r}, 'w').write(json.dumps(sys.argv[1:]))\n"
            "try:\n"
            "    body = open(sys.argv[sys.argv.index('--receipt') + 1]).read()\n"
            "except Exception:\n"
            "    sys.exit(1)\n"
            "sys.exit(0 if 'FIXTURE_VALID_RECEIPT' in body else 1)\n",
            encoding="utf-8")
        m.INSTALLED_ROOT_DEFAULT = home / ".claude"

        def gate_check(receipt_body: str):
            repo = make_candidate(base, "chk-" + uuid.uuid4().hex[:8],
                                  data_sensitive=True)
            rcp = base / ("receipt-" + uuid.uuid4().hex[:8] + ".json")
            rcp.write_text(receipt_body, encoding="utf-8")
            # the gate requires the emitted artifact INSIDE the checkout
            art = repo / ".itd-memory" / "deploy-input.tar"
            code = m.main(["check", "--root", str(repo), "--unit-id",
                           "U16:general-review", "--receipt", str(rcp),
                           "--emit-deploy-input", str(art)])
            return repo, code

        pos_repo, pos_code = gate_check("FIXTURE_VALID_RECEIPT ok")
        check("check --receipt (validator says valid) records a pass → exit 0 "
              "(CLI validation→pass-recording path, end-to-end)", pos_code == 0)
        check("that recorded pass is current for the exact candidate",
              m.gate_pass_is_current(pos_repo) is True)
        check("with the recorded pass the hook authorizes the deploy transport",
              hook(DEPLOY_CMD, pos_repo) == 0)
        # EXACT-CANDIDATE BINDING across the gate→validator interface: assert on
        # the RECORDED argv, not on the stub's verdict (producer round -e).
        recorded_argv = json.loads(argv_log.read_text(encoding="utf-8"))
        argv_blob = " ".join(recorded_argv)
        # The binding is DELEGATED, not copied: the gate hands the validator the
        # candidate ROOT plus `--candidate-mode committed-head`, and the
        # validator derives the exact tree from it. Asserting the argv pins that
        # contract — a regression that dropped --root, judged another checkout,
        # or asked "is this receipt valid at all?" (no candidate mode / no
        # mandatory route) now fails here.
        def argv_value(flag: str) -> str | None:
            return (recorded_argv[recorded_argv.index(flag) + 1]
                    if flag in recorded_argv
                    and recorded_argv.index(flag) + 1 < len(recorded_argv)
                    else None)
        check("validator argv binds THIS candidate checkout via --root "
              "(delegation is candidate-bound, not a bare 'is this receipt ok?')",
              argv_value("--root") == str(pos_repo))
        check("validator argv pins the exact-tree mode (--candidate-mode "
              "committed-head), so the receipt must match THIS tree",
              argv_value("--candidate-mode") == "committed-head")
        check("validator argv opts into the ADR-007 adjudicated route only "
              "(never a weaker mode): --accept-adjudicated-route present",
              "--accept-adjudicated-route" in recorded_argv)
        # Route strength is not an argv flag here — for a high risk tier the
        # validator demands an ADJUDICATION receipt by itself: a machine-only
        # receipt is rejected ("expected adjudication receipt version 1"), so a
        # gate that delegates with exactly this argv cannot be satisfied by
        # machine evidence alone. Verified live against the real validator.
        check("delegated argv omits no strength: the risk tier passed is the "
              "candidate's own gated tier", argv_value("--risk-tier") == "high")
        check("validator argv carries the unit id and the risk tier",
              argv_value("--unit-id") == "U16:general-review"
              and argv_value("--risk-tier") == "high")
        check("validator argv names the receipt under validation",
              argv_value("--receipt") is not None)
        # …and the deploy-input artifact IS bound — by the gate itself, in the
        # recorded pass (not via the validator argv): the recorded pass must
        # carry this candidate's current deploy-input digest.
        check("the recorded pass binds THIS candidate's deploy-input digest",
              m.current_deploy_input_sha256(pos_repo) is not None
              and m.gate_pass_is_current(pos_repo) is True)
        neg_repo, neg_code = gate_check("some rejected receipt body")
        check("check --receipt (validator rejects) → deny (exit 2), no pass "
              "recorded — the gate really gates on the delegated result",
              neg_code == 2 and m.gate_pass_is_current(neg_repo) is False)

        # ----- override path: cannotWeaken (U16:general-review-2) ------------
        # The only bypass class, HUMAN_OVERRIDE_NO_INDEPENDENT_REVIEW, requires a
        # recorded reason AND a signature; no signed minting channel exists yet,
        # so the gate refuses EVERY override for EVERY gated class, never PASSES
        # it and never counts it as review evidence. A hand-written record is not
        # a pass (its authentication is a host-owned MAC/signature it lacks).
        for risk in (m.RISK_DATA_SENSITIVE, m.RISK_MONETARY, m.RISK_IRREVERSIBLE):
            decision = m.evaluate_gate(risk, "missing",
                                       {"outcome": m.OVERRIDE_OUTCOME}, _dg)
            check(f"evaluate_gate: an override record is REFUSED for a {risk} "
                  "candidate (no signed channel) — never allowed, never review "
                  "evidence", decision.get("allowed") is False
                  and decision.get("reviewEvidence") is False)
        bad_override = base / "override-unsigned.json"
        bad_override.write_text(json.dumps({
            "outcome": m.OVERRIDE_OUTCOME, "candidateDigest": _dg,
            "confirmedBy": "someone", "reason": "no independent reviewer"}),
            encoding="utf-8")
        check("load_override: an unsigned/unauthenticated override record is "
              "rejected (None), never trusted",
              m.load_override(bad_override, _dg, home / ".claude") is None)
        ov_repo = make_candidate(base, "override-gated", data_sensitive=True)
        ov_art = ov_repo / ".itd-memory" / "deploy-input.tar"
        ov_cli = run_cli("check", "--root", str(ov_repo), "--unit-id",
                         "U16:general-review", "--override", str(bad_override),
                         "--emit-deploy-input", str(ov_art))
        check("check --override (unsigned) on a gated candidate → deny (exit 2) "
              "and records no pass — the bypass cannot weaken the gate",
              ov_cli.returncode == 2 and m.gate_pass_is_current(ov_repo) is False)

    # ------------------------------------------------------------------ #
    # SECTION 3 — trust anchor is the installed methodology, not the env
    # ------------------------------------------------------------------ #
    with tempfile.TemporaryDirectory(prefix="itd-u16-anchor-") as td:
        base = Path(td)
        evil_home = base / "evil-home"
        fake = (evil_home / ".claude" / "skills" / "deploy" / "scripts"
                / "itd_predeploy_gate.py")
        fake.parent.mkdir(parents=True, exist_ok=True)
        fake.write_text(
            "import json\n"
            "print(json.dumps({'riskClass': 'routine', 'gated': False,\n"
            "                  'gatePassRecorded': False}))\n",
            encoding="utf-8")
        fresh = make_candidate(base, "evil-case", data_sensitive=True)
        # POSITIVE CONTROL (finding 2, 2026-08-12-d): a bare `== 2` proves only
        # "fail-closed", which a broken hook or a failed account lookup also
        # satisfies. To prove the deny comes from the ANCHOR ignoring evil_home,
        # show the mechanism is live: if the fake evil-HOME gate WERE the trust
        # anchor, its `routine` verdict WOULD flip this exact candidate to
        # allow. Run the hook with the fake explicitly installed as the anchor
        # and confirm it allows (0) — the fake can and does flip the verdict.
        fake_anchor_runner = write_hook_runner(evil_home, fake)
        check("finding 2 control: the fake gate, WHEN trusted as the anchor, "
              "does flip the gated candidate to allow (0) — the flip is live",
              invoke(fresh, bash(DEPLOY_CMD), evil_home,
                     entry=fake_anchor_runner) == 0)
        # the REAL hook (no runner override): the account-database anchor must
        # resolve away from evil_home, so the gated candidate stays denied. With
        # the control above, this deny is specifically the anchor rejecting
        # evil_home, NOT a generic fail-closed.
        check("r53: HOME pointing at a permissive fake install does not flip "
              "the verdict — the anchor is not environment-derived",
              invoke(fresh, bash(DEPLOY_CMD), evil_home, entry=HOOK) == 2)

    print(f"\n{passed} passed, {failed} failed")
    if not failed:
        print("verify_predeploy_independent_review: PASSED")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
