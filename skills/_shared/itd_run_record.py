#!/usr/bin/env python3
"""itd_run_record.py — запись прогона для itd_py.sh (COMPLETION-SUPERSEDE-1).

Включается только явно: `ITD_RUN_RECORD=1 sh skills/_shared/itd_py.sh <script> [args]`.
Обёрнутая команда исполняется тем же интерпретатором; содержимое её stdout и
stderr передаётся дальше без изменений (каждый поток через свой пайп: взаимный
порядок двух потоков и isatty не сохраняются), код выхода возвращается как есть. После её
завершения пишется запись `<каталог записей>/<id>.json`
{id, script, args, cwd, rc, isolated, python, lines} и одна строка `ITD-RUN <id>`
в stderr: по ней completion-хук привязывает запись к вызову, который сам
наблюдал, а по `lines` (хвост вывода прогона) проверяет, что весь наблюдённый
вывод вызова принадлежит этому прогону (docs/completion-gate.md, «Запись прогона»).

Запись best-effort: если её не удалось записать, строки `ITD-RUN` нет, и прогон
судится гейтом как без записи. Вложенные запуски раннера не записываются —
переменная снимается из окружения обёрнутой команды.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

KEEP_SECONDS = 7 * 24 * 3600  # несопоставленные записи старше недели удаляются
KEEP_BYTES = 256 * 1024       # хвост каждого потока, из которого берутся строки
KEEP_LINES = 400              # строк хвоста на поток


def records_dir() -> Path:
    override = os.environ.get("ITD_RUN_RECORD_DIR")
    if override:
        return Path(override)
    return Path.home() / ".local" / "state" / "itd" / "runs"


def script_identity(script: str, cwd: str) -> str:
    """Путь скрипта относительно каталога прогона; вне каталога — абсолютный."""
    real = os.path.realpath(script)
    rel = os.path.relpath(real, cwd)
    if rel == os.pardir or rel.startswith(os.pardir + os.sep):
        return real.replace(os.sep, "/")
    return rel.replace(os.sep, "/")


class Tail:
    """Хвост потока: последние KEEP_BYTES байт."""

    def __init__(self) -> None:
        self.data = bytearray()
        self.cut = False

    def feed(self, chunk: bytes) -> None:
        self.data += chunk
        if len(self.data) > 2 * KEEP_BYTES:
            del self.data[:-KEEP_BYTES]
            self.cut = True

    def lines(self) -> list:
        rows = bytes(self.data[-KEEP_BYTES:]).decode("utf-8", "replace").splitlines()
        self.cut = self.cut or len(self.data) > KEEP_BYTES
        if self.cut:
            rows = rows[1:]  # первая строка обрезанного хвоста неполная
        return [row for row in rows if row][-KEEP_LINES:]


def pump(src, dst, tail: Tail) -> None:
    """Передаёт поток дальше без изменений и копит его хвост."""
    fd = src.fileno()
    while True:
        try:
            chunk = os.read(fd, 65536)
        except OSError:
            break
        if not chunk:
            break
        tail.feed(chunk)
        try:
            dst.write(chunk)
            dst.flush()
        except Exception:
            # Получатель закрыл поток (`| head`): закрываем чтение, чтобы
            # обёрнутая команда получила тот же обрыв, что и без записи.
            try:
                src.close()
            except Exception:
                pass
            break


def write_record(args: list, rc: int, isolated: bool, lines: list) -> str:
    """Пишет запись и возвращает её id; '' — если прогон не записывается."""
    if not args:
        return ""
    if not os.path.isfile(args[0]):
        return ""  # -c / -m / stdin: у прогона нет скрипта-идентичности
    cwd = os.path.realpath(os.getcwd())
    run_id = uuid.uuid4().hex
    record = {"id": run_id, "script": script_identity(args[0], cwd), "args": args[1:],
              "cwd": cwd, "rc": rc, "isolated": isolated,
              "python": os.path.realpath(sys.executable), "lines": lines}
    directory = records_dir()
    directory.mkdir(parents=True, exist_ok=True)
    os.chmod(directory, 0o700)  # в записи аргументы и хвост вывода: только владельцу
    cutoff = time.time() - KEEP_SECONDS
    for old in directory.glob("*.json"):
        try:
            if old.stat().st_mtime < cutoff:
                old.unlink()
        except OSError:
            pass
    path = directory / (run_id + ".json")
    tmp = directory / (run_id + ".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(record))
    os.replace(tmp, path)
    return run_id


def main(argv: list) -> int:
    args = argv[1:]
    isolated = bool(args) and args[0] == "--itd-isolated"
    if isolated:
        args = args[1:]
    env = dict(os.environ)
    env.pop("ITD_RUN_RECORD", None)
    command = [sys.executable] + (["-I"] if isolated else []) + args
    proc = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def forward(signum, _frame) -> None:
        try:
            proc.send_signal(signum)
        except Exception:
            pass

    # Завершение раннера не должно оставлять обёрнутую команду сиротой. SIGINT
    # терминал доставляет всей группе сам — раннеру достаточно его пережить.
    for name, handler in (("SIGTERM", forward), ("SIGHUP", forward),
                          ("SIGINT", lambda _signum, _frame: None)):
        signum = getattr(signal, name, None)
        if signum is not None:
            try:
                signal.signal(signum, handler)
            except Exception:
                pass

    out_tail, err_tail = Tail(), Tail()
    threads = [
        threading.Thread(target=pump, args=(proc.stdout, sys.stdout.buffer, out_tail)),
        threading.Thread(target=pump, args=(proc.stderr, sys.stderr.buffer, err_tail)),
    ]
    for thread in threads:
        thread.start()
    rc = proc.wait()
    for thread in threads:
        thread.join()
    if rc < 0:
        rc = 128 - rc  # убит сигналом N: как у шелла, 128 + N
    try:
        run_id = write_record(args, rc, isolated, out_tail.lines() + err_tail.lines())
    except Exception:
        run_id = ""
    if run_id:
        try:
            sys.stderr.write("ITD-RUN %s\n" % run_id)
            sys.stderr.flush()
        except Exception:
            pass
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
