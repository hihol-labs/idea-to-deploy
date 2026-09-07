"""Windows adapter for handle-relative ledger I/O (including UNC checkouts).

NtCreateFile RootDirectory and NtSetInformationFile keep each operation bound
to opened directories. No reconstructed pathname is used after traversal.
See docs/HOST_ADAPTER_CONTRACT.md for the transport boundary.
"""
from __future__ import annotations

import contextlib
import ctypes
import os
from pathlib import Path
import secrets
import stat


class _WindowsIO:
    def __init__(self):
        from ctypes import wintypes as w
        self.w = w
        class UnicodeString(ctypes.Structure):
            _fields_ = [('Length', w.USHORT), ('MaximumLength', w.USHORT), ('Buffer', w.LPWSTR)]
        class ObjectAttributes(ctypes.Structure):
            _fields_ = [('Length', w.ULONG), ('RootDirectory', w.HANDLE),
                        ('ObjectName', ctypes.POINTER(UnicodeString)), ('Attributes', w.ULONG),
                        ('SecurityDescriptor', w.LPVOID), ('SecurityQualityOfService', w.LPVOID)]
        class IOStatus(ctypes.Structure):
            _fields_ = [('Status', ctypes.c_void_p), ('Information', ctypes.c_size_t)]
        class FileInfo(ctypes.Structure):
            _fields_ = [('attributes', w.DWORD), ('creation', w.FILETIME), ('access', w.FILETIME),
                        ('write', w.FILETIME), ('volume', w.DWORD), ('sizeHigh', w.DWORD),
                        ('sizeLow', w.DWORD), ('links', w.DWORD), ('indexHigh', w.DWORD), ('indexLow', w.DWORD)]
        class RenameInfo(ctypes.Structure):
            _fields_ = [('replace', ctypes.c_ubyte), ('root', w.HANDLE),
                        ('length', w.ULONG), ('name', w.WCHAR * 1)]
        self.UnicodeString, self.ObjectAttributes, self.IOStatus = UnicodeString, ObjectAttributes, IOStatus
        self.FileInfo, self.RenameInfo = FileInfo, RenameInfo
        self.nt = ctypes.WinDLL('ntdll', use_last_error=True)
        self.k32 = ctypes.WinDLL('kernel32', use_last_error=True)
        self.nt.NtCreateFile.argtypes = [ctypes.POINTER(w.HANDLE), w.ULONG, ctypes.POINTER(ObjectAttributes),
            ctypes.POINTER(IOStatus), ctypes.c_void_p, w.ULONG, w.ULONG, w.ULONG, w.ULONG, ctypes.c_void_p, w.ULONG]
        self.nt.NtCreateFile.restype = ctypes.c_long
        self.nt.NtSetInformationFile.argtypes = [w.HANDLE, ctypes.POINTER(IOStatus), ctypes.c_void_p, w.ULONG, w.ULONG]
        self.nt.NtSetInformationFile.restype = ctypes.c_long
        self.nt.RtlNtStatusToDosError.argtypes = [ctypes.c_long]
        self.nt.RtlNtStatusToDosError.restype = w.ULONG
        self.k32.CloseHandle.argtypes = [w.HANDLE]
        self.k32.CloseHandle.restype = w.BOOL
        self.k32.GetFileInformationByHandle.argtypes = [w.HANDLE, ctypes.POINTER(FileInfo)]
        self.k32.GetFileInformationByHandle.restype = w.BOOL
        self.k32.GetFileType.argtypes = [w.HANDLE]
        self.k32.GetFileType.restype = w.DWORD

    def _check(self, status):
        if status < 0:
            raise ctypes.WinError(self.nt.RtlNtStatusToDosError(status))

    def _info(self, handle, *, directory=False, private=False):
        info = self.FileInfo()
        if not self.k32.GetFileInformationByHandle(handle, ctypes.byref(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        if (self.k32.GetFileType(handle) != 1 or info.attributes & 0x400
                or bool(info.attributes & 0x10) != directory
                or (private and info.links != 1)):
            raise RuntimeError('opened namespace object is not a safe directory/regular file')
        return info

    @staticmethod
    def _leaf(name):
        if not name or name in ('.', '..') or any(c in name for c in ('/', '\\', ':', '\0')):
            raise RuntimeError('namespace component is not a single ordinary name')
        return name

    def _open(self, parent, name, *, directory=False, create=False, exclusive=False, access=None,
              private=False):
        if parent is not None:
            self._leaf(name)
        buf = ctypes.create_unicode_buffer(name)
        length = len(name.encode('utf-16-le'))
        if length > 65532:
            raise RuntimeError('namespace name is too long')
        us = self.UnicodeString(length, length + 2, ctypes.cast(buf, self.w.LPWSTR))
        attrs = self.ObjectAttributes(ctypes.sizeof(self.ObjectAttributes), parent,
                                     ctypes.pointer(us), 0x40, None, None)
        handle, ios = self.w.HANDLE(), self.IOStatus()
        # SYNCHRONIZE + READ_ATTRIBUTES + TRAVERSE for directories; generic read for files.
        desired = access if access is not None else (0x1000A0 if directory else 0x80100000)
        disposition = 2 if exclusive else (3 if create else 1)
        options = 0x200000 | 0x20 | (1 if directory else 0x40)  # REPARSE, SYNC, DIR/NONDIR
        # Relative lookup and publication use the retained directory object,
        # even if its former pathname is concurrently renamed or redirected.
        sharing = 7
        self._check(self.nt.NtCreateFile(ctypes.byref(handle), desired, ctypes.byref(attrs),
            ctypes.byref(ios), None, 0x80, sharing, disposition, options, None, 0))
        try:
            self._info(handle, directory=directory, private=exclusive or private)
        except BaseException:
            self.k32.CloseHandle(handle)
            raise
        return handle

    @contextlib.contextmanager
    def _parent(self, path, *, create_after=None):
        path = Path(path).absolute()
        if not path.anchor or '..' in path.parts:
            raise RuntimeError('namespace requires an absolute non-traversing path')
        anchor = path.anchor
        if anchor.startswith('\\\\'):
            nt_root = '\\??\\UNC\\' + anchor[2:]
        else:
            nt_root = '\\??\\' + anchor
        handles = []
        try:
            handles.append(self._open(None, nt_root, directory=True))
            for index, part in enumerate(path.parts[1:-1], start=1):
                handles.append(self._open(handles[-1], part, directory=True,
                    create=create_after is not None and index >= create_after))
            yield handles[-1], self._leaf(path.name)
        finally:
            for handle in reversed(handles):
                self.k32.CloseHandle(handle)

    @contextlib.contextmanager
    def _fd(self, handle, flags):
        import msvcrt
        try:
            fd = msvcrt.open_osfhandle(handle.value, flags | os.O_BINARY)
        except BaseException:
            self.k32.CloseHandle(handle)
            raise
        try:
            yield fd
        finally:
            os.close(fd)

    def _rename(self, handle, parent, name, replace):
        raw = self._leaf(name).encode('utf-16-le')
        offset = self.RenameInfo.name.offset
        buf = ctypes.create_string_buffer(max(ctypes.sizeof(self.RenameInfo), offset + len(raw)))
        header = self.RenameInfo.from_buffer(buf)
        header.replace, header.root, header.length = int(replace), parent.value, len(raw)
        ctypes.memmove(ctypes.addressof(buf) + offset, raw, len(raw))
        ios = self.IOStatus()
        self._check(self.nt.NtSetInformationFile(handle, ctypes.byref(ios), buf, offset + len(raw), 10))

    def _delete(self, handle):
        flag, ios = ctypes.c_ubyte(1), self.IOStatus()
        self._check(self.nt.NtSetInformationFile(handle, ctypes.byref(ios), ctypes.byref(flag), 1, 13))

    @staticmethod
    def _write(fd, content):
        offset = 0
        while offset < len(content):
            written = os.write(fd, content[offset:])
            if written <= 0:
                raise OSError('durable write made no progress')
            offset += written
        os.fsync(fd)

    def _read(self, parent, name, max_bytes):
        handle = self._open(parent, name)
        with self._fd(handle, os.O_RDONLY) as fd:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_size > max_bytes:
                raise RuntimeError('namespace file is nonregular or oversized')
            parts, size = [], 0
            while True:
                chunk = os.read(fd, min(65536, max_bytes + 1 - size))
                if not chunk:
                    break
                parts.append(chunk); size += len(chunk)
                if size > max_bytes:
                    raise RuntimeError('namespace file exceeds read limit')
            after = os.fstat(fd)
            fields = lambda st: (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
            if fields(before) != fields(after) or size != after.st_size:
                raise RuntimeError('namespace file changed during read')
            return b''.join(parts)

    def read_regular_snapshot(self, path, max_bytes=4 * 1024 * 1024):
        with self._parent(path) as (parent, name):
            return self._read(parent, name, max_bytes)

    def _publish(self, parent, name, content, replace):
        handle = None
        for _ in range(32):
            temporary = f'.{name}.{secrets.token_hex(16)}.tmp'
            try:
                handle = self._open(parent, temporary, exclusive=True, access=0xC0110000)
                break
            except FileExistsError:
                continue
        if handle is None:
            raise RuntimeError('cannot create an exclusive namespace temporary')
        published = False
        with self._fd(handle, os.O_RDWR) as fd:
            try:
                self._write(fd, content)
                try:
                    self._rename(handle, parent, name, replace)
                except FileExistsError:
                    if replace:
                        raise
                    return 'existing-same' if self._read(parent, name, len(content) + 1) == content else 'collision'
                published = True
                return 'created'
            finally:
                if not published:
                    self._delete(handle)

    def atomic_replace_bytes(self, path, content):
        with self._parent(path) as (parent, name):
            self._publish(parent, name, content, True)

    def write_immutable_bytes(self, path, content, *, root):
        relative = Path(path)
        if relative.anchor or relative.drive or not relative.parts or '..' in relative.parts:
            raise RuntimeError('immutable child must be a contained relative path')
        root = Path(root).absolute()
        with self._parent(root / relative, create_after=len(root.parts)) as (parent, name):
            try:
                old = self._read(parent, name, max(len(content) + 1, 4 * 1024 * 1024))
            except FileNotFoundError:
                return self._publish(parent, name, content, False)
            return 'existing-same' if old == content else 'collision'

    def durable_append_bytes(self, path, content):
        with self._parent(path) as (parent, name):
            # A multi-link destination would redirect the trusted append.
            handle = self._open(parent, name, create=True, access=0x40100080, private=True)
            with self._fd(handle, os.O_WRONLY | os.O_APPEND) as fd:
                os.lseek(fd, 0, os.SEEK_END)
                self._write(fd, content)

    def durable_unlink(self, path):
        try:
            with self._parent(path) as (parent, name):
                handle = self._open(parent, name, access=0x110080)
                try:
                    self._delete(handle)
                finally:
                    self.k32.CloseHandle(handle)
        except FileNotFoundError:
            return


_INSTANCE = None


def backend():
    global _INSTANCE
    if os.name != 'nt':
        raise RuntimeError('Windows namespace adapter requires native Windows')
    if _INSTANCE is None:
        _INSTANCE = _WindowsIO()
    return _INSTANCE
