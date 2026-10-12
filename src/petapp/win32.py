"""Win32 glue. The spike in ``spikes/win32_spike.py`` proved these two are the only forms that work."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
kernel32.GetTickCount.restype = wintypes.UINT

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.UINT)]


def set_click_through(hwnd: int, enabled: bool) -> None:
    """Qt's own input-transparent window flags do not actually let clicks fall through."""
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    if enabled:
        style |= WS_EX_TRANSPARENT | WS_EX_LAYERED
    else:
        style &= ~WS_EX_TRANSPARENT
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)


def last_input_idle_seconds() -> float:
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    if not user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    return ((kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF) / 1000.0


# A named mutex, not a named pipe, is what actually means "one instance": the kernel owns the
# lifetime, so a process that is killed or crashes cannot leave a registration behind. Measured
# with two live processes on Qt 6.12, QLocalServer.listen() returned True for *both* under the same
# name, which is how two pets ended up on the desktop at once.
# GetLastError has to be read through a WinDLL(use_last_error=True) handle, because the plain
# windll accessor can pick up an error code from some intervening ctypes call.
_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.CreateMutexW.restype = wintypes.HANDLE
_k32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
_k32.CloseHandle.restype = wintypes.BOOL
_k32.CloseHandle.argtypes = [wintypes.HANDLE]

ERROR_ALREADY_EXISTS = 183


def acquire_named_mutex(name: str) -> tuple[str, int]:
    """('owned', handle) for the first caller, ('taken', 0) while a live process holds it.

    ``Local\\`` scopes the name to this session, which is the right boundary for something drawn on
    one desktop. ('error', 0) means the kernel refused outright and the caller must decide what to
    do without an exclusivity signal.
    """
    handle = _k32.CreateMutexW(None, False, name)
    err = ctypes.get_last_error()
    if not handle:
        return ("error", 0)
    if err == ERROR_ALREADY_EXISTS:
        _k32.CloseHandle(handle)
        return ("taken", 0)
    return ("owned", int(handle))
