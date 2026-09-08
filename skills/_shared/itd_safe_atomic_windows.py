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
        self.k32.GetCurrentProcess.restype = w.HANDLE
        self.k32.LocalFree.argtypes = [w.HGLOBAL]
        self.k32.LocalFree.restype = w.HGLOBAL
        self.adv = ctypes.WinDLL('advapi32', use_last_error=True)
        self.adv.GetSecurityInfo.argtypes = [w.HANDLE, ctypes.c_int, w.DWORD,
            ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        self.adv.GetSecurityInfo.restype = w.DWORD
        self.adv.GetLengthSid.argtypes = [ctypes.c_void_p]
        self.adv.GetLengthSid.restype = w.DWORD
        self.adv.OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)]
        self.adv.OpenProcessToken.restype = w.BOOL
        self.adv.GetTokenInformation.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                                 w.DWORD, ctypes.POINTER(w.DWORD)]
        self.adv.GetTokenInformation.restype = w.BOOL
        self._owner_identities = None

    def _check(self, status):
        if status < 0:
            raise ctypes.WinError(self.nt.RtlNtStatusToDosError(status))

    def _sid_bytes(self, sid):
        length = self.adv.GetLengthSid(sid)
        if not length:
            raise ctypes.WinError(ctypes.get_last_error())
        return ctypes.string_at(sid, length)

    def _token_sid(self, token, information_class):
        size = self.w.DWORD()
        self.adv.GetTokenInformation(token, information_class, None, 0, ctypes.byref(size))
        if not size.value:
            raise ctypes.WinError(ctypes.get_last_error())
        buf = ctypes.create_string_buffer(size.value)
        if not self.adv.GetTokenInformation(token, information_class, buf, size.value,
                                            ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        # TOKEN_USER and TOKEN_OWNER both start with the SID pointer.
        return self._sid_bytes(ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p))[0])

    def owner_identities(self):
        """SIDs this token stamps on the objects it creates: user and owner.

        The POSIX rule is ``st_uid == os.getuid()``.  Windows has no single
        equivalent: an elevated token's default owner is a group (usually
        Administrators), and every object such a token creates carries that
        group instead of the user.  Both identities are therefore accepted,
        with the residual limitation named rather than hidden: on such a host
        an object owned by that group could have been created by another
        member of it.  The stricter user-only rule was tried and measured
        instead of argued (Sol-fa4 asked for it): it refuses every ledger
        write on an elevated host, and the Windows CI runner failed the whole
        Goal harness suite with 'foreign owner'.  On a host where the writer
        is a plain user, which is the deployment this methodology targets, the
        two identities coincide and the rule is exactly ``st_uid``.  A
        stronger guarantee needs the destination's DACL, not its owner, and is
        recorded as a separate debt.
        """
        if self._owner_identities is None:
            # Named ``process_handle`` and not ``token``: the review scrubber
            # redacts the value of any assignment whose name ends in ``token``,
            # which blinded an independent reviewer to this code path.
            process_handle = self.w.HANDLE()
            if not self.adv.OpenProcessToken(self.k32.GetCurrentProcess(), 0x8,
                                             ctypes.byref(process_handle)):
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                self._owner_identities = tuple(
                    {self._token_sid(process_handle, 1), self._token_sid(process_handle, 4)})
            finally:
                self.k32.CloseHandle(process_handle)
        return self._owner_identities

    def _owner_sid(self, handle):
        owner, descriptor = ctypes.c_void_p(), ctypes.c_void_p()
        # SE_FILE_OBJECT = 1, OWNER_SECURITY_INFORMATION = 1.
        status = self.adv.GetSecurityInfo(handle, 1, 1, ctypes.byref(owner), None, None, None,
                                          ctypes.byref(descriptor))
        if status:
            raise ctypes.WinError(status)
        try:
            return self._sid_bytes(owner)
        finally:
            self.k32.LocalFree(descriptor)

    def _info(self, handle, *, directory=False, private=False):
        info = self.FileInfo()
        if not self.k32.GetFileInformationByHandle(handle, ctypes.byref(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        if (self.k32.GetFileType(handle) != 1 or info.attributes & 0x400
                or bool(info.attributes & 0x10) != directory
                or (private and info.links != 1)):
            raise RuntimeError('opened namespace object is not a safe directory/regular file')
        # A single link proves nothing about who owns the destination: a
        # foreign-owned file planted at a ledger path would still accept a
        # trusted append (Sol-a13).  This is the POSIX st_uid rule's parity.
        if private and self._owner_sid(handle) not in self.owner_identities():
            raise RuntimeError('opened namespace object has a foreign owner')
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

    @contextlib.contextmanager
    def open_private_lock_fd(self, path):
        with self._parent(path) as (parent, name):
            # GENERIC_READ | GENERIC_WRITE | SYNCHRONIZE | FILE_READ_ATTRIBUTES.
            handle = self._open(parent, name, create=True, access=0xC0100080, private=True)
            with self._fd(handle, os.O_RDWR) as fd:
                yield fd

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
