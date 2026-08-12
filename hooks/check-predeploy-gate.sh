#!/usr/bin/env python3
"""PreToolUse deploy gate: mutating deploy commands need a passed gate.

Route finding r32 (2026-08-10): the pre-deploy independent review gate was
only a `/deploy` Step 0 instruction, so skipping the step skipped the gate
entirely — the "fail-closed" claim held for the gate script but not for the
skill. This hook makes it mechanical: for a GATED candidate (data-sensitive,
irreversible or monetary), a mutating deploy command is denied unless the
installed gate recorded a pass bound to the EXACT current candidate digest.

Redesign r53/S1 (2026-08-11): eleven review rounds (r36–r53) kept finding new
bypass classes in the previous DENY-matcher — chained commands, `eval`/`$cmd`,
function bodies, heredocs, option operands, `cd` targets, descriptor
redirects, and finally a path-qualified transport inside a command
substitution. Enumerating shipping shapes of a Turing-complete shell is a
losing game, so the matcher is now an ALLOW-LIST over a closed grammar:

  * a command is safe (fast path, no classification) only when every
    invocation is fully statically resolved — lexable, a literal command
    word, wrapper options from known tables, NO command/process substitution
    outside single quotes (unconditional: the old "only when a transport word
    is visible" condition was itself the r53 bypass), and no content
    transport in command position;
  * for a GATED candidate everything else is deny-by-default; the only
    allowed transport forms are the read-only client calls from a closed
    table and — with a valid current pass — shipping EXACTLY the recorded
    artifact under closed per-transport flag tables (an unknown flag denies:
    an incomplete table now fails closed instead of open).

Routine candidates are never touched — the record is not even consulted.

Route finding r41 removed the "degrade to allow when the classifier is
missing" escape; a classifier that cannot run is a DENY carrying the repair
command. Route finding r53 removed the HOME-derived trust anchor: the
installed-methodology path is resolved from the OS account database
(`pwd`/shell32), never from the HOME/USERPROFILE environment an attacker can
launch the host with.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path


def _host_home() -> Path | None:
    """User home from the OS account database, never from the environment.

    Route finding r53: `Path.home()` reads HOME/USERPROFILE, which are ambient
    launch-time state — starting the host with HOME pointing at an
    attacker-owned tree substituted the entire installed methodology (and the
    gate's MAC key) in one move. The passwd entry (POSIX) or the shell32
    profile-folder API (Windows) answers the same question from the account
    database, which an attacker without host-level control cannot edit.
    None means "cannot resolve" and the caller stays fail-closed.
    """
    try:
        import pwd
        entry = pwd.getpwuid(os.getuid()).pw_dir
        if entry:
            return Path(entry)
    except (ImportError, KeyError, OSError):
        pass
    if sys.platform == "win32":
        try:
            import ctypes
            buffer = ctypes.create_unicode_buffer(260)
            # CSIDL_PROFILE = 40; SHGetFolderPathW resolves the profile
            # directory from the user token, not from the environment.
            if ctypes.windll.shell32.SHGetFolderPathW(
                    None, 40, None, 0, buffer) == 0 and buffer.value:
                return Path(buffer.value)
        except (OSError, AttributeError, ImportError):
            pass
    return None


GATE_SCRIPT_RELATIVE = Path("skills") / "deploy" / "scripts" / (
    "itd_predeploy_gate.py")
# The INSTALLED methodology is the only trust anchor. Route finding r50: when
# the hook preferred the copy sitting beside it, a deploy candidate could ship
# its own `itd_predeploy_gate.py` that reports every candidate as routine —
# candidate-supplied code gating itself, which the gate module already forbids
# for the receipt validator. The sibling copy is used ONLY when it is not
# inside the checkout being judged (a hook running from the methodology repo
# itself), and a classifier that resolves nowhere denies (route finding r41).
_HOST_HOME = _host_home()
INSTALLED_GATE_SCRIPT = (
    _HOST_HOME / ".claude" / GATE_SCRIPT_RELATIVE
    if _HOST_HOME is not None else None)
SIBLING_GATE_SCRIPT = Path(__file__).resolve().parents[1] / GATE_SCRIPT_RELATIVE


def resolve_gate_script(root: Path) -> Path | None:
    if INSTALLED_GATE_SCRIPT is not None and INSTALLED_GATE_SCRIPT.is_file():
        return INSTALLED_GATE_SCRIPT
    try:
        inside_candidate = SIBLING_GATE_SCRIPT.resolve().is_relative_to(
            Path(root).resolve())
    except (OSError, ValueError, RuntimeError):
        inside_candidate = True
    if not inside_candidate and SIBLING_GATE_SCRIPT.is_file():
        return SIBLING_GATE_SCRIPT
    return None


# Content-shipping commands only. `git push` is covered by its own guarded
# pre-push chain and is not a deploy transport.
MUTATING_COMMANDS = frozenset({
    "ssh", "scp", "rsync", "docker", "docker-compose", "podman", "tar",
    "kubectl", "helm",
})
# Read-only subcommands of the container/cluster clients. The exemption is
# decided PER INVOCATION, never over the whole shell string: route finding r36
# (2026-08-11) showed that a whole-string exemption let `docker ps; docker push
# image` through — the read-only head vouched for the shipping tail.
READ_ONLY_SUBCOMMANDS = frozenset({
    "ps", "images", "logs", "version", "info", "inspect", "get", "describe",
    "status", "list", "history",
})
READ_ONLY_CLIENTS = frozenset({"docker", "podman", "kubectl", "helm"})
# Global client options BEFORE the subcommand. Closed tables (r53/S1): a flag
# outside them makes the call not-read-only, because an unrecognised flag may
# consume the next token and turn the visible "subcommand" into an operand —
# exactly the r50 class, now failing closed instead of needing enumeration.
# Route finding r84: `--kubeconfig`/`--context`/`--kube-context`/`--config`
# select the configuration a Kubernetes/container client loads, and a
# kubeconfig can carry an `exec` credential plugin that runs an ARBITRARY
# local program during even `kubectl get`/`describe`. Trusting them on the
# read-only fast path let `kubectl --kubeconfig /tmp/evil get …` execute code
# on a gated checkout while `_is_read_only_client_call` reported `safe`,
# bypassing classification and receipt enforcement. They are removed from the
# read-only global table: their presence now makes the call NOT read-only
# (unknown global flag → fail-closed), so a gated candidate denies. A genuine
# read-only call against the default in-checkout config needs none of them.
CLIENT_GLOBAL_WITH_OPERAND = frozenset({
    "--namespace", "-n", "--host",
    "-H", "--log-level", "--tlscacert", "--tlscert", "--tlskey", "--server",
    "--user", "--cluster", "--token", "--as",
})
CLIENT_GLOBAL_NO_OPERAND = frozenset({"--debug", "-D", "--tls", "--tlsverify"})
# `tar -tf archive.tar` lists an archive and ships nothing (route finding r41).
TAR_READ_ONLY_FLAGS = frozenset({"-t", "--list"})
# Route finding r72: tar options that EXECUTE arbitrary commands even in list
# mode. Their presence makes an invocation not-read-only regardless of mode.
TAR_EXEC_OPTIONS = frozenset({
    "--checkpoint-action", "--to-command", "-I", "--use-compress-program",
    "--rmt-command", "--rsh-command", "-F", "--info-script",
    "--new-volume-script", "--rsh", "-e",
    # Route finding r85: `-T`/`--files-from` reads a list file whose entries
    # GNU tar interprets as OPTIONS unless verbatim mode is forced, so the
    # list can smuggle an execution-capable directive
    # (`--checkpoint-action=exec=…`) into an otherwise read-only `tar -t`.
    # The gate cannot vouch for the list's contents, so a files-from list is
    # execution-capable and never read-only.
    "-T", "--files-from",
})
TAR_EXEC_CLUSTER_LETTERS = frozenset("IFeT")
# Closed tar flag tables, used ONLY by _is_read_only_tar to decide whether a
# `tar` invocation lists (read-only, safe) or may create/extract/execute
# (transport → gate). ADR-008 removed the post-pass shipment-form allow-list,
# so the rsync/scp entries no longer gate any shipping form; they are retained
# for the tar key's operand/flag arity and left intact rather than pruned to a
# tar-only dict to keep the read-only-tar arity table stable.
TRANSPORT_WITH_OPERAND = {
    # Route finding r82: operand flags whose VALUE runs a program are removed
    # from the post-pass allow-list — a valid pass authorizes shipping the exact
    # recorded artifact, never arbitrary command execution through a transport
    # option. Dropped: rsync `-e`/`--rsh` (remote shell command),
    # `--rsync-path` (program run on the remote), `-M`/`--remote-option` (can
    # smuggle `--rsync-path=…` to the remote); scp `-o` (ProxyCommand/
    # LocalCommand) and `-S` (transport program); tar `-I`/
    # `--use-compress-program` (external filter program). They fail closed:
    # a deploy ships the artifact over the default transport or is denied.
    "rsync": frozenset({
        "--exclude", "--exclude-from", "--include", "--include-from",
        "--files-from", "--filter", "--log-file", "--out-format", "--temp-dir",
        "--partial-dir", "--backup-dir", "--compare-dest", "--copy-dest",
        "--link-dest", "--password-file", "--write-batch", "--read-batch",
        "--sockopts", "--suffix", "--max-size", "--min-size", "--block-size",
        "--bwlimit", "--timeout", "--contimeout", "--port", "--chmod",
        "--chown", "--usermap", "--groupmap", "-T", "-B",
        "--info", "--debug",
    }),
    # Route finding r86: `-F` loads a caller-chosen OpenSSH config that can set
    # ProxyCommand/LocalCommand and execute an arbitrary local program while an
    # otherwise exact-artifact scp still passes — a pass authorizes shipment,
    # never command execution (r82 invariant). `-F` removed (fails closed).
    "scp": frozenset({"-i", "-P", "-c", "-l", "-J"}),
    "tar": frozenset({
        "-f", "--file", "-C", "--directory", "-X", "--exclude-from",
        "--transform", "-H", "--format",
        "--exclude",
    }),
}
TRANSPORT_NO_OPERAND = {
    "rsync": frozenset({
        "--archive", "--recursive", "--links", "--perms", "--times",
        "--group", "--owner", "--devices", "--specials", "--verbose",
        "--quiet", "--compress", "--checksum", "--dry-run", "--delete",
        "--delete-after", "--delete-before", "--delete-during", "--partial",
        "--progress", "--sparse", "--hard-links", "--acls", "--xattrs",
        "--update", "--inplace", "--whole-file", "--ignore-existing",
        "--ignore-times", "--one-file-system", "--relative", "--stats",
        "--human-readable", "--itemize-changes",
    }),
    "scp": frozenset({"-r", "-p", "-q", "-C", "-4", "-6", "-v", "-B", "-T"}),
    "tar": frozenset({"--create", "--extract", "--gzip", "--bzip2", "--xz",
                      "--zstd", "--verbose"}),
}
# Wrappers that carry the real invocation in a later argument. `-c` shells are
# recursed into; the rest are transparent prefixes.
SHELL_WRAPPERS = frozenset({"bash", "sh", "zsh", "dash", "ksh"})
# `xargs` is deliberately NOT here: it is an interpreter of other commands, so
# peeling it produced an empty invocation that nothing then judged (route
# finding r42 — `printf 'rsync …' | xargs` slipped through).
PREFIX_WRAPPERS = frozenset({
    "sudo", "doas", "env", "nohup", "time", "command", "builtin", "exec",
    "nice", "ionice", "stdbuf", "setsid", "timeout", "chroot",
})
# Route finding r79: transparent pass-through wrappers that simply run the
# words after them (and their own dash-options) as a command, with no chdir or
# shell-spawn semantics of their own. `_dir_change_targets` must peel these
# before judging a `cd`/`pushd`/`popd` head, or `builtin cd /gated && rsync …`
# and `command cd /gated && …` hide the directory change from candidate-root
# classification. env/sudo/doas/timeout are deliberately EXCLUDED — they carry
# their own chdir (`env -C`) or shell-spawn (`sudo -s`) handling below.
PASSTHROUGH_WRAPPERS = frozenset({
    "command", "builtin", "exec", "nohup", "nice", "ionice", "stdbuf",
    "setsid",
})
# Compound-statement keywords that precede the real command word. `case` is
# deliberately NOT peelable: its arms live inside ONE segment behind
# `pattern)` prefixes this lexer cannot resolve, so peeling the keyword left
# the pattern word as a "safe" head while the arm executed a transport
# (route finding r60) — `case`/`select` are unresolvable constructs instead.
SHELL_KEYWORDS = frozenset({
    "if", "then", "else", "elif", "fi", "do", "done", "while", "until", "for",
    "esac", "{", "}", "!", "in",
})
UNRESOLVABLE_COMPOUNDS = frozenset({"case", "select"})
# `function deploy { … }` / `function deploy() { … }` — the `function` keyword
# is followed by the NAME, and neither is a command (route finding r45).
FUNCTION_KEYWORD = "function"
ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# `deploy(){ rsync . host:/srv; }` — the definition head is not a command, and
# leaving it as the head hid the body's transport entirely (route finding r44).
FUNCTION_DEF_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\(\)\s*\{?$")
NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# Wrapper options that consume the NEXT token. Route finding r38 (2026-08-11):
# skipping every flag AND every following word made `sudo -u root rsync …` look
# like the command `root`, so normal sudo usage walked past the gate. An
# UNKNOWN wrapper flag is assumed operand-free on purpose: that direction
# leaves the following tokens (and any transport among them) visible to the
# matcher, so a table gap surfaces as a judged transport, never a hidden one.
WRAPPER_OPTIONS_WITH_OPERAND = {
    "sudo": {"-u", "-g", "-p", "-C", "-h", "-D", "-R", "-U", "-T", "-r", "-t"},
    "doas": {"-u", "-C"},
    "env": {"-u", "-C", "-S", "--unset", "--chdir", "--split-string"},
    "timeout": {"-s", "-k", "--signal", "--kill-after"},
    "nice": {"-n", "--adjustment"},
    "ionice": {"-c", "-n", "-p", "-t", "--class", "--classdata"},
    "stdbuf": {"-i", "-o", "-e", "--input", "--output", "--error"},
    # Route finding R8-audit (2026-08-12-d): `exec -a NAME prog` sets argv[0]
    # and then runs `prog`; without `-a` in the operand table the peel read
    # `NAME` as the command word and the real transport (`exec -a x
    # /usr/bin/rsync . h:`) ran ungated.
    "exec": {"-a"},
}
# `timeout 5s cmd` / `nice 10 cmd`: one bare duration/priority operand.
# `chroot NEWROOT cmd`: the new-root path operand precedes the command.
DURATION_RE = re.compile(r"^\d+(\.\d+)?[smhd]?$")
WRAPPER_LEADING_OPERAND = {"timeout": DURATION_RE, "nice": DURATION_RE,
                           "chroot": re.compile(r"^[^-]\S*$")}
# POSIX allows any number of REDIRECTIONS before the command word, and the
# operators self-delimit even glued to a word. Route finding R8 (2026-08-12-d):
# `>/tmp/log rsync -a . host:/srv` put `>/tmp/log` in head position, the peel
# stopped at the "path-qualified head", `_command_head` judged `log`, and the
# transport ran UNGATED — fail-open. Leading redirect tokens are now peeled
# everywhere a command word is being located (head position, wrapper option
# scans, the `-c` payload finder, and directory-change scans); a bare operator
# consumes the following operand token, an attached form (`>file`, `2>&1`,
# `<<EOF`) is one token. fd-number (`2>`), fd-dup (`>&1`), bash `&>`/`&>>`,
# clobber (`>|`), here-doc/-string (`<<`/`<<-`/`<<<`) and open-rw (`<>`)
# forms are all redirections, never command words.
REDIRECT_TOKEN_RE = re.compile(r"^(\d*|&)(>>|>\||>&|<&|<<<|<<-?|<>|>|<)(.*)$")
# `rsync>/tmp/log -a . host:/srv`: the redirect glues to the command word and
# the shell still executes `rsync` — the pre-operator prefix IS the command
# word, so it replaces the token before head classification.
GLUED_REDIRECT_HEAD_RE = re.compile(r"^([^<>]+)[<>]")


def _skip_redirect(words: list[str], position: int) -> int | None:
    """Position past the redirect token at `position`, or None if not one."""
    match = REDIRECT_TOKEN_RE.match(words[position])
    if not match:
        return None
    return position + (1 if match.group(3) else 2)
# Constructs whose expansion this matcher cannot resolve statically. Route
# finding r38 (critical): `eval 'rsync …'`, `cmd=rsync; $cmd …` and
# `bash -c "$cmd"` all executed a transport that token matching never saw.
COMMAND_POSITION_INDIRECTION_RE = re.compile(r"^[\"']?(\$|`)")
# Producer round 2026-08-12-e: the leading-character test above only caught an
# expansion that STARTS the command word. `r${EMPTY}sync -a . host:/srv` (with
# EMPTY unset) and the brace form `r{sync}` keep a literal-looking head that
# `_command_head` resolved to a non-transport name, classified `safe` — and the
# shell then expanded it back to `rsync`, running the transport ungated on a
# gated checkout. Any expansion/glob metacharacter ANYWHERE in the command word
# makes the executed program statically unknowable, so the invocation is
# unresolvable (fail-closed) exactly like `$(…)`. Arguments are unaffected:
# only the command word is tested, so `grep $PATTERN file` stays safe.
COMMAND_WORD_EXPANSION_RE = re.compile(r"[$`{}*?\[\]~]")
INDIRECTION_COMMANDS = frozenset({"eval", "source", ".", "xargs"})
# Route finding r65: well-known network/content-movement clients ship bytes
# the gate cannot bind to the recorded file artifact — `curl --upload-file`,
# `wget --post-file`, `nc < data`, object-store CLIs, backup tools. They are
# recognised transports: gated on a gated candidate, allowed with a valid
# current pass (ADR-008). Honest limit, unchanged and stated: a truly custom-
# named deploy client is not enumerable and falls to the out-of-scope default
# (local execution) — /deploy Step 0 drives real deploys through the
# recognised transports here.
NETWORK_CONTENT_CLIENTS = frozenset({
    "curl", "wget", "nc", "ncat", "socat", "telnet", "ftp", "sftp", "lftp",
    "rclone", "aws", "gcloud", "gsutil", "az", "s3cmd", "mc", "restic",
    "borg", "rdiff-backup", "duplicity", "wormhole", "croc",
    # Route finding r68 (A-plus): named deploy/IaC/PaaS clients ship
    # content/state the pass cannot bind to the file artifact. Recognising
    # them by name shrinks the "unknown bare executable" residual to a
    # TRULY custom-named client, which stays the ADR-007-adjudicated honest
    # limit rather than a blanket block on every unknown command.
    "terraform", "tofu", "pulumi", "cdk", "cdktf", "sam", "serverless", "sls",
    "flyctl", "fly", "vercel", "netlify", "heroku", "wrangler", "kamal",
    "dokku", "caprover", "eb", "gcloud-app", "flatpak-builder", "skaffold",
    "kustomize", "kapp", "argocd", "flux", "nomad", "waypoint", "packer",
    "ansible-pull", "salt", "salt-call", "chef-client", "knife", "juju",
})


# A `#` starts a shell comment when it begins a WORD — that is, at the start of
# the input, after whitespace, or after a control operator (`;`, `&`, `|`, and
# the subshell parentheses), because an operator ends the previous word too.
# Producer round 2026-08-12-e (round 2): only whitespace was accepted here, so
# `echo ok;# $(rsync …)` — an inert comment the shell never executes — was read
# as live dynamic execution and a gated candidate was falsely DENIED. A mid-word
# `#` (`foo#$(bar)`) still runs the substitution and stays scanned.
COMMENT_START_BEFORE = " \t\r\n;&|()"


def _has_dynamic_execution(text: str) -> bool:
    """Command/process substitution outside single quotes, unconditionally.

    Route finding r53: the previous guard only fired when a transport word was
    visible in the raw text, and `echo $(/usr/bin/rsync -a . host:/srv)` kept
    the word out of the detector's boundary rules. A `$(…)`, backtick or
    `<(…)`/`>(…)` EXECUTES whatever it contains before the visible command
    runs, and a static matcher cannot see what — so under the allow-list it is
    never part of a safe command. Single-quoted text is literal and stays
    exempt; a payload handed to `sh -c` is rescanned at its own level.
    """
    quote: str | None = None
    escaped = False
    index = 0
    while index < len(text):
        char = text[index]
        if escaped:
            escaped = False
        elif char == "\\" and quote != "'":
            escaped = True
        elif quote == "'":
            if char == "'":
                quote = None
        elif quote == '"':
            if char == '"':
                quote = None
            elif char == "$" and text[index + 1:index + 2] == "(":
                return True
            elif char == "`":
                return True
        elif char == "#" and (index == 0
                              or text[index - 1] in COMMENT_START_BEFORE):
            # Unquoted shell comment (word-start `#`): the rest of the line does
            # not execute, so a `$(…)`/backtick inside it is inert — treating it
            # as dynamic falsely blocked `echo x # $(rsync …)` and `make test
            # # $(nproc)` on a gated candidate (ADR-008: ordinary local
            # execution is out of scope). Only a whitespace/line-start `#` is a
            # comment; a mid-word `#` (`foo#$(bar)`) still runs the substitution
            # and stays scanned (fail-closed).
            newline = text.find("\n", index + 1)
            if newline == -1:
                break
            index = newline
        elif char in "'\"":
            quote = char
        elif char == "$" and text[index + 1:index + 2] == "(":
            return True
        elif char == "`":
            return True
        elif char in "<>" and text[index + 1:index + 2] == "(":
            return True
        index += 1
    return False


def _split_segments_with_operators(command: str) -> list[tuple[str, str]]:
    """[(operator_before_segment, segment_text)], operators outside quotes.

    The operator matters for stdin provenance: only an UNQUOTED `|` feeds one
    command's output into the next. Route finding r46: matching `|` as a raw
    substring made `ssh host 'journalctl | tail'` look like local shipping.
    """
    segments: list[tuple[str, str]] = []
    current: list[str] = []
    operator = ""
    quote: str | None = None
    escaped = False
    index = 0
    while index < len(command):
        char = command[index]
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\" and quote != "'":
            current.append(char)
            escaped = True
        elif quote:
            current.append(char)
            if char == quote:
                quote = None
        elif char in "'\"":
            current.append(char)
            quote = char
        elif char == "#" and (index == 0
                              or command[index - 1] in COMMENT_START_BEFORE):
            # Unquoted word-start comment: consume to end-of-line WITHOUT
            # splitting on operators inside it — an inert `;`/`|`/transport in a
            # comment must not create a spurious segment (`echo ok # x; rsync …`
            # never runs the rsync). shlex(comments=True) strips it downstream.
            # The newline itself still separates, so a real transport on the
            # NEXT line stays classified (fail-closed). Consistent with
            # `_has_dynamic_execution`.
            newline = command.find("\n", index)
            if newline == -1:
                current.append(command[index:])
                index = len(command)
            else:
                current.append(command[index:newline])
                index = newline - 1
        elif (char == "&" and (command[index - 1:index] in ("<", ">")
                               or command[index + 1:index + 2] == ">")) or (
                char == "|" and command[index - 1:index] == ">"):
            # Route finding R8/S1-c: `2>&1`, `>&2`, `&>file`, `>|file` are
            # REDIRECTIONS, not control operators. Splitting `2>&1 rsync …`
            # at the `&` made `1 rsync …` its own segment whose head `1` was
            # safe — the transport ran ungated as that segment's argv. An
            # `&`/`|` adjacent to a redirect character stays in the segment.
            current.append(char)
        elif char in ";\n|&":
            segments.append((operator, "".join(current)))
            current = []
            pair = command[index:index + 2]
            if pair in ("&&", "||"):
                operator = pair
                index += 1
            else:
                operator = char
        else:
            current.append(char)
        index += 1
    segments.append((operator, "".join(current)))
    return [(op, text) for op, text in
            ((op, seg.strip().strip("()").strip()) for op, seg in segments)
            if text]


def _split_segments(command: str) -> list[str]:
    """Split on shell operators that are OUTSIDE quotes.

    Route finding r38: splitting first and lexing second tore
    `printf 'docker push; note'` in half, and the unlexable remainder was then
    conservatively denied — a false block on a command that ships nothing.
    """
    return [text for _, text in _split_segments_with_operators(command)]


# Windows/Git Bash executable suffixes. Security (ADR-008): `/usr/bin/rsync.exe`
# (or `docker.exe`, `bash.exe`) is the real transport/wrapper — matching its
# extensionless name kept it out of the recognised tables, classified it `safe`,
# and let it BYPASS the gate on Windows. The suffix is stripped before every
# head/table match so a `.exe` transport is gated exactly like its bare name.
WINDOWS_EXECUTABLE_SUFFIXES = frozenset({".exe", ".com", ".bat", ".cmd"})


def _command_head(token: str) -> str:
    """Basename with a Windows executable suffix stripped.

    Route finding R8 (2026-08-12-d): a redirect glued to the command word —
    `rsync>/tmp/log` — must resolve to the executed program `rsync`, not the
    whole token. The shell splits the redirect off; the prefix before the
    first unquoted `<`/`>` is the command word.
    """
    glued = GLUED_REDIRECT_HEAD_RE.match(token)
    if glued:
        token = glued.group(1)
    name = Path(token).name
    stem, dot, ext = name.rpartition(".")
    if dot and ("." + ext.lower()) in WINDOWS_EXECUTABLE_SUFFIXES:
        return stem
    return name


def _peel_wrappers(tokens: list[str]) -> list[list[str]]:
    """Peel sudo/env/... prefixes; expand `sh -c '<cmd>'` into sub-commands.

    Only BARE wrapper heads are peeled (r56): `/tmp/sudo rsync …` is not sudo
    — it is an arbitrary executable that receives `rsync …` as mere argv, so
    peeling it would judge an invocation that never runs. A path-qualified
    head stops the peel and is classified as opaque by _invocation_class.
    """
    while tokens:
        # Route finding R8 (2026-08-12-d): peel any LEADING redirect tokens.
        # POSIX permits redirections before the command word; `>/tmp/log rsync
        # …`, `2>&1 rsync …`, `<in.txt scp …` all put a redirect in head
        # position, and without this peel the "path-qualified head" break (or a
        # bare fd number) misclassified the segment as safe while the transport
        # ran. A bare operator (`> file`) also consumes its operand token.
        peeled_redirect = False
        while tokens:
            after = _skip_redirect(tokens, 0)
            if after is None:
                break
            tokens = tokens[after:]
            peeled_redirect = True
        if peeled_redirect:
            continue
        # Route finding r42: `DEPLOY=1 rsync …` and `if rsync …; then` put a
        # non-command word first, so the transport was never the head.
        # Route finding r61: a function DEFINITION is no longer peeled into
        # its body — peeling judged the body while the later invocation of
        # the defined NAME passed as a safe bare command
        # (`function deploy { curl … }; deploy`). A definition anywhere makes
        # the whole command unresolvable: the sentinel below propagates
        # through needs_gate and the pass branch alike, so both the
        # definition and its same-string invocation are denied on a gated
        # candidate without any name-tracking.
        # Route finding r61: `function deploy { … }` / `deploy(){ … }`.
        # Route finding r65: `deploy () { … }` with whitespace before the
        # parenthesis lexes as `deploy`, `()`, `{` — the name and `()` are
        # separate tokens, so the def-regex on token[0] alone missed it.
        if (tokens[0] == FUNCTION_KEYWORD or FUNCTION_DEF_RE.match(tokens[0])
                or (len(tokens) >= 2
                    and NAME_RE.match(tokens[0])
                    and tokens[1] in ("()", "("))):
            return [["\0dynamic"]]
        if ASSIGNMENT_RE.match(tokens[0]) or tokens[0] in SHELL_KEYWORDS:
            tokens = tokens[1:]
            continue
        if "/" in tokens[0]:
            break                          # path-qualified head: never peeled
        head = _command_head(tokens[0])    # strip .exe/.cmd/… before matching
        if head in SHELL_WRAPPERS:
            payload = _shell_command_payload(tokens[1:])
            if payload is not None:
                return _split_invocations(payload)
            # No `-c` payload. A positional token is a SCRIPT FILE
            # (`bash deploy.sh`) — out-of-scope local execution (ADR-008),
            # safe. But a BARE interpreter with no script file — `bash`,
            # `sh <in.sh` (the redirect is peeled first), `printf 'rsync …' |
            # sh` — executes commands from stdin the matcher cannot read (route
            # finding R8-audit): that is a computed/embedded command, so it is
            # unresolvable and gated exactly like eval/`$(…)`.
            if not _has_script_file_argument(tokens[1:]):
                return [["\0dynamic"]]
            break
        if head not in PREFIX_WRAPPERS:
            break
        # Route finding r62: wrapper modes that EXECUTE something the peel
        # cannot see are unresolvable, not skippable options — `env -S
        # 'rsync …'` runs the embedded string, `sudo -s`/`-i` spawns a shell
        # outside PreToolUse interception. Judged in the option region only
        # (the scan stops at the first positional, which is the wrapped
        # command whose own flags are not the wrapper's).
        if head in ("sudo", "doas"):
            for wrapper_word in tokens[1:]:
                if not wrapper_word.startswith("-"):
                    break
                if wrapper_word in ("--shell", "--login"):
                    return [["\0dynamic"]]
                # Route finding r66: a short-option CLUSTER containing `s`
                # or `i` (`sudo -is`, `sudo -si`) spawns a shell too — the
                # r62 exact-token check missed it.
                if (not wrapper_word.startswith("--")
                        and ("s" in wrapper_word[1:]
                             or "i" in wrapper_word[1:])):
                    return [["\0dynamic"]]
        if head == "env":
            for wrapper_word in tokens[1:]:
                if not wrapper_word.startswith("-"):
                    break
                if wrapper_word.split("=", 1)[0] == "--split-string" or (
                        not wrapper_word.startswith("--")
                        and "S" in wrapper_word[1:]):
                    return [["\0dynamic"]]
        with_operand = WRAPPER_OPTIONS_WITH_OPERAND.get(head, set())
        rest = tokens[1:]
        seen_leading_operand = False
        while rest:
            word = rest[0]
            if "=" in word and not word.startswith("-"):
                rest = rest[1:]           # env NAME=value
                continue
            if word.startswith("-"):
                takes = word.split("=", 1)[0] in with_operand and "=" not in word
                rest = rest[2:] if (takes and len(rest) > 1) else rest[1:]
                continue
            leading_re = WRAPPER_LEADING_OPERAND.get(head)
            if (leading_re is not None and not seen_leading_operand
                    and leading_re.match(word)):
                seen_leading_operand = True
                rest = rest[1:]
                continue
            break
        tokens = rest
    return [tokens] if tokens else []


def _shell_command_payload(rest: list[str]) -> str | None:
    """The `-c` command string of a shell invocation, or None.

    Route finding r59 (critical): searching for a literal `-c` ANYWHERE in
    the arguments let `bash -- deploy.sh -c 'echo safe'` reduce to the safe
    `echo safe` — but the shell actually executes `deploy.sh`, and `-c`
    there is a mere script argument. `-c` counts only inside the LEADING
    option region: before any `--` terminator and before the first
    positional token (which is a script file). `-o <opt>` consumes its
    operand; a single-dash cluster containing `c` (`bash -ec '…'`) is the
    command-string form too.
    """
    index = 0
    while index < len(rest):
        # Route finding R8: a redirect before `-c` (`bash >log -c 'rsync …'`)
        # is not the command-string flag and not a script file — skip it so
        # the `-c` payload is still lexed and its transport gated.
        after_redirect = _skip_redirect(rest, index)
        if after_redirect is not None:
            index = after_redirect
            continue
        word = rest[index]
        if word == "--":
            return None                    # what follows is a script file
        if word == "-o" or word == "+o":
            index += 2                     # set -o/+o option name operand
            continue
        if word.startswith("-") and len(word) > 1:
            if "c" in word[1:]:
                return rest[index + 1] if index + 1 < len(rest) else None
            index += 1
            continue
        return None                        # positional word: a script file
    return None


def _has_script_file_argument(rest: list[str]) -> bool:
    """True when a shell invocation has a positional SCRIPT FILE argument.

    Used only after `_shell_command_payload` returned None (no `-c` string):
    `bash deploy.sh` runs a file (out-of-scope local execution under ADR-008),
    but a bare `bash`/`sh` with only options reads its program from stdin,
    which the matcher cannot see and must gate. Mirrors the option-region walk
    of `_shell_command_payload`: `-o <opt>` consumes an operand, `--`
    terminates the option region, the first bare word is the script file.
    """
    index = 0
    while index < len(rest):
        after_redirect = _skip_redirect(rest, index)
        if after_redirect is not None:
            index = after_redirect         # R8: a redirect is not a script file
            continue
        word = rest[index]
        if word == "--":
            return index + 1 < len(rest)
        if word in ("-o", "+o"):
            index += 2
            continue
        if word.startswith("-") and len(word) > 1:
            index += 1
            continue
        return True
    return False


def _split_invocations(command: str) -> list[list[str]]:
    """Every command invocation in the string, as token lists.

    Emits the sentinel ``["\\0dynamic"]`` when THIS level of the string
    contains command/process substitution outside single quotes — the scan is
    repeated per recursion level, so a substitution hidden inside a quoted
    `sh -c` payload is caught when that payload is expanded (r53/S1).
    """
    invocations: list[list[str]] = []
    if _has_dynamic_execution(command):
        invocations.append(["\0dynamic"])
    for segment in _split_segments(command):
        try:
            tokens = shlex.split(segment, comments=True)
        except ValueError:
            # Unlexable even after quote-aware splitting: hand the raw text to
            # the caller, which treats it as unresolvable (fail-closed).
            invocations.append(["\0raw", segment])
            continue
        invocations.extend(_peel_wrappers(tokens))
    return invocations


UNRESOLVED_SENTINELS = frozenset({"\0raw", "\0dynamic"})


def _is_read_only_client_call(head: str, tokens: list[str]) -> bool:
    if head == "tar":
        return _is_read_only_tar(tokens)
    if head not in READ_ONLY_CLIENTS:
        return False
    # Route finding r50: `docker --config ps push image` made `ps` — the
    # OPERAND of a global option — look like the subcommand while `push` ran.
    # r53/S1: the tables are CLOSED — an unknown flag before the subcommand
    # makes the call not-read-only instead of being guessed around.
    rest = tokens[1:]
    index = 0
    while index < len(rest):
        word = rest[index]
        if word.startswith("-"):
            base = word.split("=", 1)[0]
            if base in CLIENT_GLOBAL_WITH_OPERAND:
                index += 1 if "=" in word else 2
                continue
            if word in CLIENT_GLOBAL_NO_OPERAND:
                index += 1
                continue
            return False
        return word in READ_ONLY_SUBCOMMANDS
    return False


def _is_read_only_tar(tokens: list[str]) -> bool:
    """`tar -tf a.tar` / `tar tf a.tar` list; anything else may write.

    Route finding r50: an option OPERAND (`tar --file list -c files`) was read
    as a bundled mode cluster, so an archive-creating command looked read-only.
    r53/S1: only flags from tar's own closed table are stepped over; an
    unknown flag before the mode token makes the call not-read-only.
    """
    # Route finding r72: returning True on the first `-t`/`--list` ignored
    # later options — GNU tar can EXECUTE code from `--checkpoint-action=exec`,
    # `--to-command`, `-I`/`--use-compress-program`, `--rmt-command`,
    # `--info-script`, … even in list mode. Read-only recognition now scans
    # the WHOLE argument list: it is read-only ONLY if a list mode is present
    # AND no option is execution-capable, a write mode, or unknown
    # (fail-closed). `-f`/`-C`/… operands are skipped; a create/extract mode
    # anywhere makes it not-read-only.
    with_operand = TRANSPORT_WITH_OPERAND["tar"]
    no_operand = TRANSPORT_NO_OPERAND["tar"]
    write_modes = ("--create", "--extract", "--append", "--update",
                   "--delete", "--concatenate", "--catenate")
    saw_list = False
    skip_next = False
    for argument in tokens[1:]:
        if skip_next:
            skip_next = False
            continue
        if not argument.startswith("-"):
            if saw_list:
                continue                   # file operands after a known mode
            if argument and all(c.isalpha() for c in argument):
                if any(c in "cxru" for c in argument):
                    return False           # bundled write mode
                if any(c in TAR_EXEC_CLUSTER_LETTERS for c in argument):
                    return False           # bundled exec option
                if "t" in argument:
                    saw_list = True
                    if argument.endswith("f") or "f" in argument:
                        skip_next = True
                    continue
                return False               # unknown bundled mode word
            return False
        base = argument.split("=", 1)[0]
        if base in TAR_EXEC_OPTIONS:
            return False                   # execution-capable: never safe
        if argument in TAR_READ_ONLY_FLAGS:
            saw_list = True
            continue
        if argument.startswith("--"):
            if argument in write_modes:
                return False
            if argument in no_operand or base in with_operand:
                skip_next = base in with_operand and "=" not in argument
                continue
            return False                   # unknown long flag: fail closed
        cluster = argument[1:]
        if not cluster or not all(c.isalpha() for c in cluster):
            return False
        if any(c in "cxru" for c in cluster):
            return False                   # short write mode in the cluster
        if any(c in TAR_EXEC_CLUSTER_LETTERS for c in cluster):
            return False                   # -I / -F etc. in the cluster
        if "t" in cluster:
            saw_list = True
        if "f" in cluster:
            skip_next = True
    return saw_list


def _invocation_class(tokens: list[str]) -> str:
    """'safe' | 'transport' | 'unresolvable' under the ADR-008 shipment scope.

    Redesign (2026-08-12, ADR-008): U16 gates a gated candidate's deploy at
    exactly one seam — a command whose COMMAND WORD is a recognised content/
    deploy transport (judged via the pass), or one whose command word is
    statically OPAQUE in a way that could HIDE such a transport (a command/
    process substitution, an interpreter of a COMPUTED command — eval/source/
    ./xargs, a case/select branch the splitter cannot enter, or a non-lexable
    segment). Everything else — ordinary local code execution (interpreters,
    build/test/task runners, script files), file operations (rm/mv/editors)
    and custom-named executables — is OUT OF SCOPE: statically proving such a
    command "ships nothing" is undecidable, and the r53–r89 review rounds
    proved the parse unwinnable. That residual is covered by /careful, the
    completion gate and human deploy review, not by this hook. A recognised
    transport is still gated wherever its word appears, path-qualified
    included (`/usr/bin/rsync` is judged as rsync — fail-closed on the visible
    word; the pass, when present, authorised the reviewed deploy).

    'transport' and 'unresolvable' both mean "not provably safe → gate"; the
    two labels are kept only for readability (main() treats them identically).
    """
    if tokens[0] in UNRESOLVED_SENTINELS:
        return "unresolvable"        # dynamic split sentinel ($()/backtick/def)
    if COMMAND_POSITION_INDIRECTION_RE.search(tokens[0]):
        return "unresolvable"        # substitution/backtick in command position
    if COMMAND_WORD_EXPANSION_RE.search(tokens[0]):
        # parameter/brace/glob/tilde expansion INSIDE the command word: the
        # program the shell will actually run is not this token (r${EMPTY}sync)
        return "unresolvable"
    head = _command_head(tokens[0])  # basename, .exe/.cmd/… stripped, judged by
    if head in INDIRECTION_COMMANDS:  # its visible word (path-qualified included)
        return "unresolvable"        # eval/source/./xargs run a COMPUTED command
    if head in UNRESOLVABLE_COMPOUNDS:
        # r60: `case x in x) rsync …;; esac` hides the transport behind a
        # pattern word inside one segment — statically unparseable here
        return "unresolvable"
    if head in MUTATING_COMMANDS:
        if _is_read_only_client_call(head, tokens):
            return "safe"
        return "transport"
    if head in NETWORK_CONTENT_CLIENTS:
        return "transport"           # recognised content/deploy mover
    # ADR-008 out-of-scope: local code execution (interpreters, runners,
    # scripts, path-qualified/custom executables) and local file operations
    # are NOT gated — undecidable to prove they ship nothing, covered by
    # /careful + the completion gate + human deploy review instead. /deploy
    # Step 0 drives real deploys through the recognised transport paths above.
    return "safe"


def needs_gate(command: str) -> bool:
    """True when the command is NOT provably safe under the closed grammar.

    The safe fast path (no classification at all) is an allow-list: every
    invocation lexes, has a literal bare command word, contains no
    substitution at any level, no interpreter of other commands, no script or
    task runner, and no content transport beyond the read-only client calls.
    Everything else is judged against the candidate's risk class — and for a
    gated candidate, denied unless it is one of the exactly-allowed forms.
    """
    for tokens in _split_invocations(command):
        if not tokens:
            continue
        if _invocation_class(tokens) != "safe":
            return True
    return False


SUBPROCESS_RETRY_ATTEMPTS = 3
SUBPROCESS_RETRY_BACKOFF_SECONDS = 0.05


def _run_read(argv: list[str], *, timeout: int):
    """Run an idempotent read-only subprocess with a bounded retry (S2/r77).

    Under isolation/full-suite load a fork/exec hiccup or a transient
    non-zero exit made the gate classify a legitimate candidate as
    unclassifiable and DENY it — fail-closed, but a spurious block of a valid
    deploy. Every call here reads the exact candidate, so retrying is safe; a
    genuine failure still exhausts the attempts and stays fail-closed. Returns
    the zero-exit CompletedProcess or None.
    """
    import time
    for attempt in range(SUBPROCESS_RETRY_ATTEMPTS):
        try:
            completed = subprocess.run(
                argv, capture_output=True, text=True, timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            completed = None
        if completed is not None and completed.returncode == 0:
            return completed
        if attempt + 1 < SUBPROCESS_RETRY_ATTEMPTS:
            time.sleep(SUBPROCESS_RETRY_BACKOFF_SECONDS * (attempt + 1))
    return None


def classify(root: Path) -> dict | None:
    """Read-only risk classification via the gate script itself.

    None means "could not classify" — the caller denies, it never allows.
    A transient classify failure retries (S2/r77) so it does not become a
    spurious deny; only a persistent failure stays None.
    """
    script = resolve_gate_script(root)
    if script is None:
        return None
    completed = _run_read(
        [sys.executable, str(script), "classify", "--root", str(root)],
        timeout=60)
    if completed is None or not completed.stdout.strip():
        return None
    try:
        value = json.loads(completed.stdout.strip().splitlines()[-1])
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def in_git_repository(root: Path) -> bool:
    """Outside a git checkout there is no deploy candidate to gate at all."""
    return _run_read(
        ["git", "-C", str(root), "rev-parse", "--git-dir"],
        timeout=30) is not None


def _deny(msg: str) -> None:
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": msg,
        }
    }, ensure_ascii=False))
    sys.stderr.write(msg)
    raise SystemExit(2)


def emit_deny(risk_class: str) -> None:
    _deny(
        f"[PRE-DEPLOY GATE] Мутирующая deploy-команда заблокирована: "
        f"кандидат класса `{risk_class}` не проходил pre-deploy гейт.\n\n"
        f"WHY: для data-sensitive / irreversible / monetary кандидата нужен "
        f"свежий adjudication receipt и артефакт, произведённый самим "
        f"гейтом; записи о прохождении для ТЕКУЩЕГО candidate digest нет "
        f"(отсутствует, просрочена или относится к другому кандидату).\n"
        f"FIX: прогони /deploy Step 0 (якорь — из учётной БД ОС, не $HOME):\n"
        f"  ITD_HOME=\"$(getent passwd \"$(id -u)\" | cut -d: -f6)\"\n"
        f"  G=\"$ITD_HOME/.claude/skills/deploy/scripts/itd_predeploy_gate.py\"\n"
        f"  python3 \"$G\" check --root \"$(git rev-parse --show-toplevel)\" \\\n"
        f"    --receipt <свежая квитанция> \\\n"
        f"    --emit-deploy-input .itd-memory/deploy-input.tar\n"
        f"и деплой именно этот артефакт.\n"
    )


def emit_deny_unclassifiable() -> None:
    _deny(
        "[PRE-DEPLOY GATE] Команда заблокирована: классификатор риска "
        "недоступен.\n\n"
        "WHY: хук не смог выполнить `itd_predeploy_gate.py classify`, поэтому "
        "он НЕ ЗНАЕТ, является ли кандидат data-sensitive / irreversible / "
        "monetary. Раньше эта ветка молча разрешала команду — и любой хук без "
        "своего гейт-скрипта переставал быть гейтом (route finding r41).\n"
        "FIX: восстанови установку методологии "
        "(`~/.claude/skills/deploy/scripts/itd_predeploy_gate.py`) или запусти "
        "команду из чекаута, где этот файл на месте.\n"
    )


def emit_deny_unresolvable_root() -> None:
    _deny(
        "[PRE-DEPLOY GATE] Команда заблокирована: цель `cd` нераскрываема "
        "статически.\n\n"
        "WHY: хук классифицирует риск КАЖДОГО чекаута, в котором может "
        "выполниться транспорт (route finding r45). Цель `cd` с подстановкой, "
        "переменной или тильдой он разрешить не может, значит не может и "
        "доказать, что команда не отгружает содержимое gated-кандидата "
        "(allow-list S1: недоказуемое — запрещено).\n"
        "FIX: используй литеральный путь в `cd` (без `$VAR`, `~`, "
        "подстановок) или запусти транспорт отдельной командой из нужного "
        "каталога.\n"
    )


ENV_CHDIR_OPTIONS = frozenset({"-C", "--chdir"})


def _dir_change_targets(command: str, _depth: int = 0) -> list[str | None]:
    """Directory-change targets in command order, judged in COMMAND position.

    Covers `cd`/`pushd` operands, `popd` (None — runtime-stack target the
    matcher cannot know), and `env -C DIR`/`--chdir DIR`/`--chdir=DIR` (route
    finding r70: `env --chdir /gated rsync …` moves the transport's directory
    but env is peeled as a wrapper, so the chdir was invisible). Only the
    LEADING command/wrapper region of each segment is scanned, so a `cd`/`env`
    appearing as an ARGUMENT (`grep cd file`) is never mistaken for a
    directory change. A None entry marks an unresolvable movement.
    """
    targets: list[str | None] = []
    for segment in _split_segments(command):
        try:
            tokens = shlex.split(segment, comments=True)
        except ValueError:
            continue
        index = 0
        # peel leading redirects / assignments / keywords / function-def heads.
        # Route finding R8: `>log cd /gated && rsync …` hid the `cd` behind a
        # leading redirect, so the gated checkout never entered candidate_roots
        # and the transport was judged against the routine launch cwd.
        while index < len(tokens):
            after_redirect = _skip_redirect(tokens, index)
            if after_redirect is not None:
                index = after_redirect
                continue
            lead = tokens[index]
            if (ASSIGNMENT_RE.match(lead) or lead in SHELL_KEYWORDS
                    or FUNCTION_DEF_RE.match(lead) or lead == FUNCTION_KEYWORD
                    or lead in ("()", "(")):
                index += 1
                continue
            break
        # Route finding r79: peel transparent pass-through wrappers (and their
        # dash-options) so a directory change hidden behind them —
        # `builtin cd /gated`, `command cd /gated`, `exec cd …` — is still
        # judged in command position. BARE heads only (r56/r73: a
        # path-qualified `/tmp/command` is an opaque executable, never peeled).
        while (index < len(tokens) and "/" not in tokens[index]
               and tokens[index] in PASSTHROUGH_WRAPPERS):
            index += 1
            while index < len(tokens) and tokens[index].startswith("-"):
                index += 1
        if index >= len(tokens):
            continue
        # Route finding r73: a path-qualified head (`/tmp/env`, `/tmp/cd`) is
        # an arbitrary executable, NOT a trusted wrapper/builtin — recognising
        # it as env/cd would add a bogus gated root (r56: path-qualified heads
        # are never peeled/trusted). Only BARE heads are directory changes.
        if "/" in tokens[index]:
            continue
        head = tokens[index]
        if head == "popd":
            targets.append(None)
            continue
        if head in ("cd", "pushd"):
            targets.append(tokens[index + 1]
                           if index + 1 < len(tokens) else None)
            continue
        # Route finding r81: a directory change nested inside a shell `-c`
        # payload (`bash -c 'cd /gated && rsync …'`) was invisible here, so
        # candidate_roots classified against the routine OUTER cwd while the
        # transport ran in the gated checkout. Recurse into the payload so the
        # nested cd/pushd/env-C is seen exactly as at the top level; a dynamic
        # nested target surfaces as None (unresolvable → denied by
        # has_unresolvable_cd). Bounded depth; at the limit a present payload is
        # treated as unresolvable rather than trusted.
        if head in SHELL_WRAPPERS:
            payload = _shell_command_payload(tokens[index + 1:])
            if payload is not None:
                if _depth < 3:
                    targets.extend(_dir_change_targets(payload, _depth + 1))
                else:
                    targets.append(None)
            continue
        # walk a leading wrapper chain (sudo/env/...) capturing env -C/--chdir
        while index < len(tokens):
            if "/" in tokens[index]:
                break                      # path-qualified: not a wrapper
            head = tokens[index]
            if head not in PREFIX_WRAPPERS:
                break
            cursor = index + 1
            found_command = False
            while cursor < len(tokens):
                word = tokens[cursor]
                if word == "--":
                    cursor += 1
                    found_command = True
                    break
                base = word.split("=", 1)[0]
                # Route finding r83: the ATTACHED short form `env -C/gated …`
                # (value glued to `-C`, no space and no `=`) changes directory
                # too, but was neither matched here nor peeled by
                # `_peel_wrappers`, so the transport was classified against the
                # launch cwd and a gated checkout escaped candidate-root
                # binding. `-C<DIR>` is a directory-change target.
                if (head == "env" and word.startswith("-C")
                        and not word.startswith("--") and len(word) > 2):
                    targets.append(word[2:])
                    cursor += 1
                    continue
                if head == "env" and base in ENV_CHDIR_OPTIONS:
                    if "=" in word:
                        targets.append(word.split("=", 1)[1])
                        cursor += 1
                    elif cursor + 1 < len(tokens):
                        targets.append(tokens[cursor + 1])
                        cursor += 2
                    else:
                        targets.append(None)
                        cursor += 1
                    continue
                if word.startswith("-"):
                    with_operand = WRAPPER_OPTIONS_WITH_OPERAND.get(head, set())
                    takes = base in with_operand and "=" not in word
                    cursor += 2 if (takes and cursor + 1 < len(tokens)) else 1
                    continue
                if "=" in word and head == "env":
                    cursor += 1            # env NAME=value
                    continue
                found_command = True
                break
            index = cursor if found_command else len(tokens)
            # Producer round 2026-08-12-e: a shell payload reached THROUGH a
            # prefix wrapper — `sudo bash -c 'cd /gated && rsync …'`,
            # `env bash -c '…'` — was never inspected here: the r81 recursion
            # above only fires when the shell is the FIRST head, and this
            # wrapper walk stopped at `bash` without reading its `-c` payload.
            # candidate_roots then held only the routine launch cwd while the
            # transport ran in the gated checkout with no pass. Recurse into
            # the payload exactly as at the top level (bounded depth; at the
            # limit an existing payload is unresolvable, never trusted).
            if (index < len(tokens) and "/" not in tokens[index]
                    and _command_head(tokens[index]) in SHELL_WRAPPERS):
                payload = _shell_command_payload(tokens[index + 1:])
                if payload is not None:
                    if _depth < 3:
                        targets.extend(
                            _dir_change_targets(payload, _depth + 1))
                    else:
                        targets.append(None)
    return targets


def candidate_roots(command: str, cwd: Path) -> list[Path]:
    """Every checkout the command could actually run its transport in.

    Route finding r45: classifying only `Path.cwd()` meant
    `cd /gated-repo && rsync …` from a routine parent was judged against the
    parent and allowed, while the transport ran in the gated checkout.
    """
    roots = [cwd]
    # Route finding r67: a chained `cd /a && cd ../b && rsync …` lands in
    # `/a/../b`, not `<cwd>/../b`. Each relative target is resolved against
    # the CURRENT simulated directory, updated left to right, not always the
    # launch cwd. (Unresolvable targets are handled by has_unresolvable_cd,
    # which denies the whole command before this matters.) r70: env --chdir
    # is a directory change too.
    current = cwd
    for target in _dir_change_targets(command):
        if target is None:
            continue                       # unresolvable — denied elsewhere
        try:
            path = Path(target)
            path = path if path.is_absolute() else current / path
            resolved = path.resolve()
        except (OSError, ValueError, RuntimeError):
            continue
        current = resolved
        if resolved not in roots:
            roots.append(resolved)
    return roots


def has_unresolvable_cd(command: str) -> bool:
    """A directory change this matcher cannot resolve to a literal path.

    r53/S1: an unresolvable `cd` target used to be silently skipped, so
    `cd $DIR && rsync …` was judged against the launch directory while the
    transport ran wherever `$DIR` pointed. r59 adds `pushd` (same movement)
    and `popd` (statically unknowable stack target) — and moves WHERE the
    deny fires: it is applied only for a candidate already classified GATED
    (see main), because denying before classification blocked routine
    checkouts, contrary to the routine-candidate exemption. Honest limit,
    stated: a variable `cd` FROM a routine checkout INTO a gated one is
    outside static reach — the boundary is classification of the resolvable
    roots plus this in-gated deny.
    """
    for target in _dir_change_targets(command):
        if target is None:
            return True                    # bare cd / popd / missing operand
        if target.startswith("-"):
            return True                    # `cd -` / pushd rotation flags
        if "$" in target or "`" in target or target.startswith("~"):
            return True
    return False


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if ((payload or {}).get("tool_name") or "") != "Bash":
        return 0
    command = ((payload or {}).get("tool_input") or {}).get("command") or ""
    if not needs_gate(command):
        return 0
    # Route finding r65 (REVERSES the r59 routine exemption): a command that
    # ships content AND changes to a statically unresolvable directory cannot
    # prove which checkout the transport runs in — it may be a gated one
    # reached from a routine cwd (`cd "$GATED" && rsync …`). Fail-closed wins
    # over the r59 "don't block routine" comfort: an unresolvable movement in
    # a content-shipping command is denied regardless of the launch cwd's
    # class. It stays narrow — needs_gate already required a transport or an
    # unresolvable invocation, so `cd "$VAR" && ls` never reaches here.
    if has_unresolvable_cd(command):
        emit_deny_unresolvable_root()
    cwd = Path.cwd()
    for root in candidate_roots(command, cwd):
        verdict = classify(root)
        if verdict is None:
            # Outside a git checkout there is no candidate to gate; anywhere
            # else an unusable classifier is a broken gate, not a permit.
            if not in_git_repository(root):
                continue
            emit_deny_unclassifiable()
        if not verdict.get("gated"):
            continue
        if verdict.get("gatePassRecorded") is not True:
            emit_deny(str(verdict.get("riskClass") or "gated"))
        # Redesign (2026-08-12, ADR-008): a VALID current pass means THIS exact
        # candidate's deploy was independently reviewed and its receipt
        # recorded by the gate. The hook no longer re-analyzes the shipment
        # command's shell FORM. Statically deciding whether an arbitrary shell
        # command "ships only the reviewed artifact and executes nothing else"
        # is undecidable, and the attempt drove an unbounded independent-review
        # arms race (rounds r53–r89: per-transport flag tables, redirect/
        # IO-number/heredoc parsing, upstream reader allow-lists, exec-capable
        # option operands, config-provenance exec, …). The tractable, closeable
        # contract is: a gated candidate may run a transport/unresolvable
        # command ONLY with a valid current pass (denied above otherwise); the
        # pass — earned through the Verification Loop adjudication receipt —
        # authorizes the reviewed deploy. Shipment-form minutiae and general
        # local mutation are OUT OF SCOPE (the latter is covered by /careful
        # and the completion gate). So: valid pass → allow.
        continue
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
