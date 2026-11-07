#!/usr/bin/env python3
"""OS-level isolation of one TESTGAP pilot run (protocol section 7). Local tool, not shipped.

  pilot_ns.py proxy <socket> <log>   - host side: CONNECT proxy on a Unix socket, exact host allowlist, port 443
  pilot_ns.py stage1 <b64 config>    - inside `unshare -r -m -n -p -f --mount-proc`: tmpfs over /mnt, /home, /tmp,
                                       /run/WSL; bound-back allowlist; then nested `unshare -U` to uid 1000
  pilot_ns.py stage2 <b64 config>    - uid 1000 inside: loopback forwarder 127.0.0.1:18443 -> proxy socket, run cmd
  pilot_ns.py probe <b64 args>       - wrapper self-test payload (no model): tries every leak path, prints JSON
"""
from __future__ import annotations

import base64
import json
import os
import socket
import socketserver
import subprocess
import sys
import threading
import time

ALLOW = {"api.anthropic.com", "console.anthropic.com", "platform.claude.com"}
FWD_PORT = 18443
SOCK_IN = "/tmp/pilot/.proxy/proxy.sock"


def pipe(a: socket.socket, b: socket.socket) -> None:
    def one(src, dst):
        try:
            while True:
                data = src.recv(65536)
                if not data:
                    break
                dst.sendall(data)
        except OSError:
            pass
        finally:
            try:
                dst.shutdown(socket.SHUT_WR)
            except OSError:
                pass
    t = threading.Thread(target=one, args=(b, a), daemon=True)
    t.start()
    one(a, b)
    t.join()
    a.close()
    b.close()


# ---------------------------------------------------------------- host proxy
def proxy(sock_path: str, log_path: str) -> None:
    lock = threading.Lock()

    def log(rec):
        rec["t"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with lock, open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")

    class H(socketserver.BaseRequestHandler):
        def handle(self):
            c = self.request
            buf = b""
            while b"\r\n\r\n" not in buf and len(buf) < 16384:
                part = c.recv(4096)
                if not part:
                    return
                buf += part
            head, _, rest = buf.partition(b"\r\n\r\n")
            line = head.split(b"\r\n", 1)[0].decode("latin-1", "replace")
            parts = line.split()
            method = parts[0].upper() if parts else ""
            target = parts[1] if len(parts) > 1 else ""
            host, _, port = target.rpartition(":")
            if method != "CONNECT" or host.lower() not in ALLOW or port != "443":
                log({"decision": "deny", "method": method, "target": target[:200]})
                c.sendall(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
                c.close()
                return
            try:
                up = socket.create_connection((host.lower(), 443), timeout=30)
                up.settimeout(None)
            except OSError as exc:
                log({"decision": "allow-failed", "target": target, "error": str(exc)[:200]})
                c.sendall(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
                c.close()
                return
            log({"decision": "allow", "target": target})
            c.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
            if rest:
                up.sendall(rest)
            pipe(c, up)

    log_path = os.path.abspath(log_path)
    os.chdir(os.path.dirname(os.path.abspath(sock_path)))  # AF_UNIX paths are limited to 108 bytes
    sock_path = os.path.basename(sock_path)
    if os.path.exists(sock_path):
        os.unlink(sock_path)
    srv = socketserver.ThreadingUnixStreamServer(sock_path, H)
    srv.daemon_threads = True
    srv.serve_forever()


# ---------------------------------------------------------------- namespace stages
def sh(*args):
    subprocess.run(list(args), check=True)


def stage1(cfg: dict) -> int:
    home = cfg["home"]
    stage = "/mnt/.stage"
    sh("ip", "link", "set", "lo", "up")
    sh("mount", "-t", "tmpfs", "-o", "mode=755", "pilot-mnt", "/mnt")
    os.makedirs(stage)
    sh("mount", "--rbind", home, stage)
    sh("mount", "-t", "tmpfs", "-o", "mode=755", "pilot-home", "/home")
    os.makedirs(home, mode=0o755)
    sh("mount", "-t", "tmpfs", "-o", "mode=1777", "pilot-tmp", "/tmp")
    if os.path.isdir("/run/WSL"):
        sh("mount", "-t", "tmpfs", "-o", "mode=755", "pilot-wsl", "/run/WSL")

    def bind(src_rel_or_abs: str, dst: str, ro: bool):
        src = src_rel_or_abs if src_rel_or_abs.startswith("/") else os.path.join(stage, src_rel_or_abs)
        if not os.path.lexists(src):
            return
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.isdir(src):
            os.makedirs(dst, exist_ok=True)
        else:
            open(dst, "a").close()
        sh("mount", "--bind", src, dst)
        if ro:
            sh("mount", "-o", "remount,bind,ro", dst)

    for rel in cfg["ro"]:
        bind(rel, os.path.join(home, rel), True)
    for rel in cfg["rw"]:
        bind(rel, os.path.join(home, rel), False)
    for src_rel, dst in cfg["extra"]:
        bind(src_rel, dst, False)
    with open(os.path.join(home, ".claude.json"), "w", encoding="utf-8") as fh:
        json.dump({"hasCompletedOnboarding": True, "numStartups": 1, "autoUpdates": False}, fh)
    for d in cfg.get("mkdirs", []):
        os.makedirs(d, exist_ok=True)
    sh("umount", "-l", stage)
    os.rmdir(stage)
    os.chown(home, 0, 0)
    blob = base64.b64encode(json.dumps(cfg).encode()).decode()
    return subprocess.run(["unshare", "-U", "--map-user=1000", "--map-group=1000", "--", sys.executable,
                           os.path.join(cfg["nsdir_in"], "pilot_ns.py"), "stage2", blob]).returncode


def forwarder() -> None:
    class F(socketserver.BaseRequestHandler):
        def handle(self):
            up = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                up.connect(SOCK_IN)
            except OSError:
                self.request.close()
                return
            pipe(self.request, up)

    socketserver.ThreadingTCPServer.allow_reuse_address = True
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", FWD_PORT), F)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()


def stage2(cfg: dict) -> int:
    forwarder()
    env = dict(cfg["env"])
    return subprocess.run(cfg["cmd"], cwd=cfg["cwd"], env=env, stdin=subprocess.DEVNULL).returncode


# ---------------------------------------------------------------- self-test payload
def probe(args: dict) -> int:
    out = {"uid": os.getuid(), "gid": os.getgid()}
    secret, marker = args["secret"], args["marker"]

    def read(label, path):
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                data = fh.read(4096)
            out[label] = "LEAK" if marker in data else f"read-no-marker:{len(data)}"
        except OSError as exc:
            out[label] = f"blocked:{exc.__class__.__name__}"

    read("direct", secret)
    read("proc_self_root", "/proc/self/root" + secret)
    read("proc_host_pid_root", f"/proc/{args['hostpid']}/root" + secret)
    read("proc_1_root", "/proc/1/root" + secret)
    link = os.path.join(args["cwd"], ".probe-link")
    try:
        os.symlink(secret, link)
        read("symlink", link)
    finally:
        if os.path.lexists(link):
            os.unlink(link)
    for label, path in (("mnt_c", "/mnt/c"), ("projects", os.path.expanduser("~/projects")),
                        ("claude_projects", os.path.expanduser("~/.claude/projects")), ("run_wsl", "/run/WSL")):
        try:
            out[label] = sorted(os.listdir(path))[:10]
        except OSError as exc:
            out[label] = f"blocked:{exc.__class__.__name__}"
    for label, path in (("settings_ro", os.path.expanduser("~/.claude/settings.json")),):
        try:
            with open(path, "a"):
                pass
            out[label] = "WRITABLE"
        except OSError as exc:
            out[label] = f"ro:{exc.__class__.__name__}"
    try:
        socket.create_connection(("140.82.121.3", 443), timeout=5).close()
        out["direct_tcp_github"] = "CONNECTED"
    except OSError as exc:
        out["direct_tcp_github"] = f"blocked:{exc.__class__.__name__}"
    try:
        socket.getaddrinfo("github.com", 443)
        out["dns"] = "RESOLVED"
    except OSError as exc:
        out["dns"] = f"blocked:{exc.__class__.__name__}"

    def via_proxy(host):
        try:
            s = socket.create_connection(("127.0.0.1", FWD_PORT), timeout=10)
            s.sendall(f"CONNECT {host}:443 HTTP/1.1\r\nHost: {host}:443\r\n\r\n".encode())
            line = s.recv(200).split(b"\r\n", 1)[0].decode()
            s.close()
            return line
        except OSError as exc:
            return f"error:{exc}"

    out["proxy_github"] = via_proxy("github.com")
    out["proxy_raw_github"] = via_proxy("raw.githubusercontent.com")
    out["proxy_api"] = via_proxy("api.anthropic.com")
    try:
        import urllib.request
        urllib.request.urlopen("https://github.com/hihol-labs/idea-to-deploy", timeout=10).read(100)
        out["urllib_github"] = "LEAK"
    except Exception as exc:  # noqa: BLE001
        out["urllib_github"] = f"blocked:{str(exc)[:80]}"
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "proxy":
        proxy(sys.argv[2], sys.argv[3])
    else:
        payload = json.loads(base64.b64decode(sys.argv[2]))
        sys.exit({"stage1": stage1, "stage2": stage2, "probe": probe}[mode](payload))
