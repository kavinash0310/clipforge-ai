from __future__ import annotations

import ctypes
import json
import os
import tempfile
from ctypes import wintypes
from pathlib import Path
from typing import Any


class _DataBlob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]


class WindowsSecretStore:
    """Persist OAuth secrets as current-user DPAPI ciphertext on Windows."""

    def __init__(self, path: Path):
        if os.name != "nt":
            raise RuntimeError("YouTube OAuth requires Windows DPAPI for secure token storage.")
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _transform(value: bytes, *, protect: bool) -> bytes:
        if os.name != "nt":
            raise RuntimeError("Windows DPAPI is only available on Windows.")
        crypt32 = ctypes.WinDLL("Crypt32.dll", use_last_error=True)
        kernel32 = ctypes.WinDLL("Kernel32.dll", use_last_error=True)
        crypt32.CryptProtectData.argtypes = [
            ctypes.POINTER(_DataBlob), wintypes.LPCWSTR, ctypes.POINTER(_DataBlob),
            wintypes.LPVOID, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(_DataBlob),
        ]
        crypt32.CryptProtectData.restype = wintypes.BOOL
        crypt32.CryptUnprotectData.argtypes = [
            ctypes.POINTER(_DataBlob), ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(_DataBlob),
            wintypes.LPVOID, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(_DataBlob),
        ]
        crypt32.CryptUnprotectData.restype = wintypes.BOOL
        kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
        kernel32.LocalFree.restype = wintypes.HLOCAL

        input_buffer = ctypes.create_string_buffer(value, len(value))
        input_blob = _DataBlob(len(value), ctypes.cast(input_buffer, ctypes.POINTER(ctypes.c_ubyte)))
        output_blob = _DataBlob()
        if protect:
            succeeded = crypt32.CryptProtectData(
                ctypes.byref(input_blob), "ClipForge YouTube credentials", None, None, None, 0,
                ctypes.byref(output_blob),
            )
        else:
            succeeded = crypt32.CryptUnprotectData(
                ctypes.byref(input_blob), None, None, None, None, 0, ctypes.byref(output_blob)
            )
        if not succeeded:
            raise OSError(ctypes.get_last_error(), "Windows could not protect or unlock the YouTube credentials.")
        try:
            return ctypes.string_at(output_blob.data, output_blob.size)
        finally:
            kernel32.LocalFree(output_blob.data)

    def read(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"oauth": None, "upload_sessions": {}, "channel": None}
        try:
            cleartext = self._transform(self.path.read_bytes(), protect=False)
            value = json.loads(cleartext.decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError("Secret payload must be an object.")
            value.setdefault("oauth", None)
            value.setdefault("upload_sessions", {})
            value.setdefault("channel", None)
            return value
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
            raise RuntimeError("Saved YouTube credentials could not be unlocked. Reconnect the YouTube account.") from error

    def write(self, value: dict[str, Any]) -> None:
        ciphertext = self._transform(json.dumps(value, separators=(",", ":")).encode("utf-8"), protect=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix="youtube-", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(descriptor, "wb") as temporary_file:
                temporary_file.write(ciphertext)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            Path(temporary_name).replace(self.path)
        finally:
            Path(temporary_name).unlink(missing_ok=True)

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)
