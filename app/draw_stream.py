"""Lottery draw live stream docked over the right half of the dashboard (owner-approved 2026-11-18).

During each draw window ABA opens Microsoft Edge in app mode (no tabs, no address bar) with its
own profile, places that window exactly over the rates and private-rates cards, keeps it there on
top, and closes it when the window ends or ABA exits. Edge is a separate program, so a browser or
YouTube problem can never stop payment announcements. Only DRAW_STREAM_URL is ever opened.
"""

import ctypes
import logging
import subprocess
from ctypes import wintypes
from datetime import datetime, time
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

DRAW_STREAM_URL = "https://www.youtube.com/@xosominhngoc/live"
# (start, end) in Cambodia time, every day.
DRAW_WINDOWS = ((time(16, 5), time(16, 40)), (time(18, 5), time(18, 40)))
EDGE_PATHS = (
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
)

Rect = tuple[int, int, int, int]  # x, y, width, height in screen pixels


def active_draw_window(now: datetime) -> Optional[str]:
    """The draw window containing `now` as "HH:MM-HH:MM", or None."""
    current = now.time()
    for start, end in DRAW_WINDOWS:
        if start <= current < end:
            return f"{start:%H:%M}-{end:%H:%M}"
    return None


def find_edge() -> Optional[Path]:
    return next((path for path in EDGE_PATHS if path.is_file()), None)


# --- Windows helpers (ctypes) -------------------------------------------------------------------

_user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None
_kernel32 = ctypes.windll.kernel32 if hasattr(ctypes, "windll") else None
if _kernel32 is not None:
    _kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
_HWND_TOPMOST = wintypes.HWND(-1)
_SWP_NOACTIVATE, _SWP_SHOWWINDOW = 0x0010, 0x0040
_TH32CS_SNAPPROCESS = 0x00000002


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260),
    ]


def _process_tree(root_pid: int) -> set[int]:
    """root_pid and all of its descendants."""
    if _kernel32 is None:
        return {root_pid}
    snapshot = _kernel32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
    if not snapshot or snapshot == wintypes.HANDLE(-1).value:
        return {root_pid}
    parents: dict[int, int] = {}
    try:
        entry = _PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ok = _kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            parents[entry.th32ProcessID] = entry.th32ParentProcessID
            ok = _kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        _kernel32.CloseHandle(snapshot)
    tree = {root_pid}
    changed = True
    while changed:
        changed = False
        for pid, parent in parents.items():
            if parent in tree and pid not in tree:
                tree.add(pid)
                changed = True
    return tree


def _visible_windows_of(pids: set[int]) -> list[int]:
    if _user32 is None:
        return []
    found: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _lparam):
        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and _user32.IsWindowVisible(hwnd) and _user32.GetWindowTextLengthW(hwnd) > 0:
            found.append(hwnd)
        return True

    _user32.EnumWindows(callback, 0)
    return found


def _invisible_borders(hwnd: int) -> tuple[int, int, int, int]:
    """(left, top, right, bottom) invisible border widths around the visible window frame."""
    outer = wintypes.RECT()
    visible = wintypes.RECT()
    _user32.GetWindowRect(hwnd, ctypes.byref(outer))
    try:
        dwm = ctypes.windll.dwmapi
        if dwm.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(visible), ctypes.sizeof(visible)) != 0:  # 9 = EXTENDED_FRAME_BOUNDS
            return (0, 0, 0, 0)
    except (AttributeError, OSError):
        return (0, 0, 0, 0)
    return (visible.left - outer.left, visible.top - outer.top, outer.right - visible.right, outer.bottom - visible.bottom)


def _place_on_top(hwnd: int, rect: Rect) -> None:
    """Place the window so its *visible* frame covers exactly `rect`, above other windows."""
    x, y, width, height = rect
    left, top, right, bottom = _invisible_borders(hwnd)
    _user32.SetWindowPos(
        hwnd, _HWND_TOPMOST, x - left, y - top, width + left + right, height + top + bottom,
        _SWP_NOACTIVATE | _SWP_SHOWWINDOW,
    )


def _alive(pid: int) -> bool:
    handle = _kernel32.OpenProcess(0x1000, False, pid) if _kernel32 is not None else 0  # QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    try:
        code = wintypes.DWORD()
        return bool(_kernel32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259  # STILL_ACTIVE
    finally:
        _kernel32.CloseHandle(handle)


# --- Controller ---------------------------------------------------------------------------------

class DrawStreamController:
    """Opens, docks and closes the Edge draw window. Call tick() regularly from the Tk thread."""

    def __init__(
        self,
        profile_dir: Path,
        clock: Callable[[], datetime],
        launcher: Callable[[list[str]], subprocess.Popen] = lambda args: subprocess.Popen(args),
        edge_path: Optional[Path] = None,
    ):
        self.profile_dir = Path(profile_dir)
        self.clock = clock
        self.launcher = launcher
        self.edge_path = edge_path if edge_path is not None else find_edge()
        self._process: Optional[subprocess.Popen] = None
        self._opened_windows: set[str] = set()  # "YYYY-MM-DD HH:MM-HH:MM" opened today
        self._test_until: Optional[datetime] = None

    def _edge_pids(self) -> set[int]:
        """Live processes started by our Edge launch (the launcher itself may already have exited)."""
        if self._process is None:
            return set()
        tree = _process_tree(self._process.pid)
        alive = {pid for pid in tree if pid != self._process.pid and _alive(pid)}
        if self._process.poll() is None:
            alive.add(self._process.pid)
        return alive

    @property
    def is_open(self) -> bool:
        if self._process is None:
            return False
        if _kernel32 is None:
            return self._process.poll() is None
        return bool(self._edge_pids())

    def open_test(self, until: datetime) -> None:
        """Open now (for the Operations test button) until the given time."""
        self._test_until = until

    def tick(self, rect: Optional[Rect]) -> None:
        now = self.clock()
        window = active_draw_window(now)
        testing = self._test_until is not None and now < self._test_until
        if self._test_until is not None and not testing:
            self._test_until = None
        if window is None and not testing:
            self.close()
            return
        if rect is None or rect[2] < 200 or rect[3] < 150:
            return  # the dashboard is not laid out (or is minimised); try again on the next tick
        key = f"{now:%Y-%m-%d} {window}" if window else None
        if not self.is_open:
            if self._process is not None:
                # Someone closed the stream during this window: do not reopen it until the next one.
                self._process = None
                return
            if key is not None and key in self._opened_windows and not testing:
                return
            self._open(rect)
            if key is not None:
                self._opened_windows.add(key)
            return
        self._dock(rect)

    def _open(self, rect: Rect) -> None:
        if self.edge_path is None:
            logger.warning("Draw stream skipped: Microsoft Edge was not found")
            return
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        x, y, width, height = rect
        args = [
            str(self.edge_path),
            f"--app={DRAW_STREAM_URL}",
            f"--user-data-dir={self.profile_dir}",
            f"--window-position={x},{y}",
            f"--window-size={width},{height}",
            "--autoplay-policy=no-user-gesture-required",
            "--no-first-run",
            "--no-default-browser-check",
        ]
        try:
            self._process = self.launcher(args)
            logger.info("Draw stream opened")
        except OSError as exc:
            logger.warning("Draw stream could not be opened (%s)", type(exc).__name__)
            self._process = None

    def _dock(self, rect: Rect) -> None:
        if self._process is None or _user32 is None:
            return
        try:
            for hwnd in _visible_windows_of(self._edge_pids()):
                _place_on_top(hwnd, rect)
        except Exception as exc:  # never let window placement affect the dashboard
            logger.warning("Draw stream could not be positioned (%s)", type(exc).__name__)

    def close(self) -> None:
        if self._process is None:
            return
        pids = self._edge_pids() if _kernel32 is not None else ({self._process.pid} if self._process.poll() is None else set())
        self._process = None
        if not pids:
            return
        args = ["taskkill", "/F", "/T"]
        for pid in sorted(pids):
            args += ["/PID", str(pid)]
        try:
            subprocess.run(args, capture_output=True, timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            logger.info("Draw stream closed")
        except (OSError, subprocess.SubprocessError) as exc:
            logger.warning("Draw stream could not be closed (%s)", type(exc).__name__)
