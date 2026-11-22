"""Lottery draw live stream docked over the right half of the dashboard (owner-approved 2026-11-18/21).

During each draw window ABA opens the channel's live page in Google Chrome app mode (no tabs, no
address bar) using the owner's own Chrome profile "Bunthorng" (signed in with YouTube Premium, so
there are no ads), places that window exactly over the rates and private-rates cards, keeps it on
top, and closes it when the window ends or ABA exits.

The owner's Chrome may already be open, so ABA never shuts Chrome down: it recognises only the new
window it opened (the browser windows present just before launching are remembered) and closes
that window alone, exactly like clicking its ✕. If the stream does not come up, ABA keeps trying
the same channel every 30 seconds until the draw window ends. If Chrome is not installed, Edge is
used instead. Only DRAW_STREAM_URL and CAMBODIAN_STREAM_URL are ever opened.

Two channels (owner decision 2026-11-22): the Vietnamese channel Xổ Số Minh Ngọc for the 16:00 and
18:00 draws, and the Cambodian channel ផ្ទះ ឆ្នោតយួន for the 10:00, 13:00 and 19:00 draws. Full
results are at half past the hour (about 5 minutes earlier on Tuesdays and Thursdays), so one window
from :15 to :45 covers every day. The Cambodian channel sometimes goes live late; while its page is
not showing that hour's live video, ABA reopens it every minute.
"""

import ctypes
import logging
import re
import subprocess
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

DRAW_STREAM_URL = "https://www.youtube.com/@xosominhngoc/live"  # Vietnamese channel Xổ Số Minh Ngọc
# Cambodian channel ផ្ទះ ឆ្នោតយួន (@ផ្ទះ_ឆ្នោតយួន), addressed by its channel ID to keep the URL plain ASCII.
CAMBODIAN_STREAM_URL = "https://www.youtube.com/channel/UC1SVFPlK1ljQk-jdHgXB6qA/live"


@dataclass(frozen=True)
class DrawWindow:
    start: time
    end: time
    url: str
    draw_hour: int  # hour of the draw (results at about :30)
    reload_until_live: bool = False  # channel whose live can start late: reopen until it shows

    @property
    def label(self) -> str:
        return f"{self.start:%H:%M}-{self.end:%H:%M}"


# Cambodia time, every day.
DRAW_WINDOWS = (
    DrawWindow(time(10, 15), time(10, 45), CAMBODIAN_STREAM_URL, 10, True),
    DrawWindow(time(13, 15), time(13, 45), CAMBODIAN_STREAM_URL, 13, True),
    DrawWindow(time(16, 5), time(16, 40), DRAW_STREAM_URL, 16),
    DrawWindow(time(18, 5), time(18, 40), DRAW_STREAM_URL, 18),
    DrawWindow(time(19, 15), time(19, 45), CAMBODIAN_STREAM_URL, 19, True),
)
LIVE_RELOAD_SECONDS = 60  # how often to reopen a page that is not showing the live video yet
CHROME_PROFILE_NAME = "Bunthorng"  # the owner's Chrome profile with YouTube Premium
CHROME_PATHS = (
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
)
EDGE_PATHS = (
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
)
WINDOW_APPEAR_SECONDS = 25  # how long to wait for the stream window after launching
RETRY_SECONDS = 30  # if it did not come up, try again this often until the draw window ends
BROWSER_WINDOW_CLASS = "Chrome_WidgetWin_1"  # top-level class used by both Chrome and Edge

Rect = tuple[int, int, int, int]  # x, y, width, height in screen pixels


def draw_window_at(now: datetime) -> Optional[DrawWindow]:
    """The draw window containing `now`, or None."""
    current = now.time()
    for window in DRAW_WINDOWS:
        if window.start <= current < window.end:
            return window
    return None


def active_draw_window(now: datetime) -> Optional[str]:
    """The draw window containing `now` as "HH:MM-HH:MM", or None."""
    window = draw_window_at(now)
    return window.label if window else None


_HOUR_IN_TITLE = re.compile(r"ម៉ោង\s*(\d{1,2})\s*[:.]\s*\d{2}")


def shows_live_draw(title: str, draw_hour: int) -> bool:
    """Whether the Cambodian channel's page title is that hour's live result video.

    Its videos are titled like "🔴LIVE ! លទ្ធផលឆ្នោតយួន | ម៉ោង 07:30 នាទី | ..." with a 12-hour time;
    the channel home page (shown when nothing is live) is titled with the channel name only.
    """
    if "LIVE" not in title.upper() and "លទ្ធផល" not in title:
        return False
    match = _HOUR_IN_TITLE.search(title)
    if match is None:
        return True  # a live video without an hour in its title: accept it
    return int(match.group(1)) % 12 == draw_hour % 12


def chrome_profile_directory(profile_name: str = CHROME_PROFILE_NAME) -> Optional[str]:
    """Chrome's folder name (e.g. "Profile 2") for the profile shown as `profile_name`."""
    import json
    import os

    local_state = Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data" / "Local State"
    try:
        info = json.loads(local_state.read_text(encoding="utf-8"))["profile"]["info_cache"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    for directory, details in info.items():
        if isinstance(details, dict) and details.get("name") == profile_name:
            return directory
    return None


def browser_command(url: str, rect: Rect, edge_profile_dir: Path) -> Optional[list[str]]:
    """Chrome (owner's profile) when installed, otherwise Edge with ABA's own profile."""
    x, y, width, height = rect
    common = [f"--app={url}", f"--window-position={x},{y}", f"--window-size={width},{height}",
              "--autoplay-policy=no-user-gesture-required", "--no-first-run", "--no-default-browser-check"]
    chrome = next((path for path in CHROME_PATHS if path.is_file()), None)
    if chrome is not None:
        profile = chrome_profile_directory()
        return [str(chrome), *common, *([f"--profile-directory={profile}"] if profile else [])]
    edge = next((path for path in EDGE_PATHS if path.is_file()), None)
    if edge is not None:
        return [str(edge), *common, f"--user-data-dir={edge_profile_dir}"]
    return None


# --- Windows helpers (ctypes) -------------------------------------------------------------------

_user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None
_HWND_TOPMOST = wintypes.HWND(-1)
_SWP_NOACTIVATE, _SWP_SHOWWINDOW = 0x0010, 0x0040
_WM_CLOSE = 0x0010


def browser_windows() -> set[int]:
    """Visible, titled top-level Chrome/Edge windows."""
    if _user32 is None:
        return set()
    found: set[int] = set()
    class_name = ctypes.create_unicode_buffer(64)

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _lparam):
        if _user32.IsWindowVisible(hwnd) and _user32.GetWindowTextLengthW(hwnd) > 0:
            _user32.GetClassNameW(hwnd, class_name, 64)
            if class_name.value == BROWSER_WINDOW_CLASS:
                found.add(int(hwnd))
        return True

    _user32.EnumWindows(callback, 0)
    return found


def window_title(hwnd: int) -> str:
    if _user32 is None:
        return ""
    length = _user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    _user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def is_app_window_title(title: str) -> bool:
    """App-mode windows have no browser suffix; normal Chrome/Edge windows end with the browser name."""
    return not (title.endswith("Google Chrome") or "Microsoft" in title and "Edge" in title)


def window_exists(hwnd: int) -> bool:
    return bool(_user32 and _user32.IsWindow(hwnd) and _user32.IsWindowVisible(hwnd))


def _invisible_borders(hwnd: int) -> tuple[int, int, int, int]:
    """(left, top, right, bottom) invisible border widths around the visible window frame."""
    outer, visible = wintypes.RECT(), wintypes.RECT()
    _user32.GetWindowRect(hwnd, ctypes.byref(outer))
    try:
        if ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(visible), ctypes.sizeof(visible)) != 0:
            return (0, 0, 0, 0)
    except (AttributeError, OSError):
        return (0, 0, 0, 0)
    return (visible.left - outer.left, visible.top - outer.top, outer.right - visible.right, outer.bottom - visible.bottom)


def place_on_top(hwnd: int, rect: Rect) -> None:
    """Place the window so its *visible* frame covers exactly `rect`, above other windows."""
    x, y, width, height = rect
    left, top, right, bottom = _invisible_borders(hwnd)
    _user32.SetWindowPos(hwnd, _HWND_TOPMOST, x - left, y - top, width + left + right, height + top + bottom,
                         _SWP_NOACTIVATE | _SWP_SHOWWINDOW)


def close_window(hwnd: int) -> None:
    """Close one window, exactly like clicking its ✕ (the rest of the browser keeps running)."""
    if _user32 is not None:
        _user32.PostMessageW(hwnd, _WM_CLOSE, 0, 0)


# --- Controller ---------------------------------------------------------------------------------

class DrawStreamController:
    """Opens, docks and closes the stream window. Call tick() regularly (every ~2 s) from the Tk thread."""

    def __init__(
        self,
        edge_profile_dir: Path,
        clock: Callable[[], datetime],
        launcher: Callable[[list[str]], object] = lambda args: subprocess.Popen(args),
        command: Callable[[str, Rect, Path], Optional[list[str]]] = browser_command,
        list_windows: Callable[[], set[int]] = browser_windows,
        exists: Callable[[int], bool] = window_exists,
        place: Callable[[int, Rect], None] = place_on_top,
        close: Callable[[int], None] = close_window,
        title: Callable[[int], str] = window_title,
    ):
        self.edge_profile_dir = Path(edge_profile_dir)
        self.clock = clock
        self.launcher, self.command = launcher, command
        self.list_windows, self.exists, self.place, self.close_one = list_windows, exists, place, close
        self.title = title
        self._hwnd: Optional[int] = None
        self._before: set[int] = set()
        self._launched_at: Optional[datetime] = None
        self._retry_at: Optional[datetime] = None
        self._shown_windows: set[str] = set()  # "YYYY-MM-DD HH:MM-HH:MM" in which the stream appeared
        self._test_until: Optional[datetime] = None
        self._url: Optional[str] = None  # channel of the open (or launching) stream window
        self._docked_at: Optional[datetime] = None

    @property
    def is_open(self) -> bool:
        return self._hwnd is not None and self.exists(self._hwnd)

    def open_test(self, until: datetime) -> None:
        """Open now (Operations test button) until the given time."""
        self._test_until = until
        self._retry_at = None

    def tick(self, rect: Optional[Rect]) -> None:
        now = self.clock()
        draw = draw_window_at(now)
        window = draw.label if draw else None
        testing = self._test_until is not None and now < self._test_until
        if self._test_until is not None and not testing:
            self._test_until = None
            if window is None:
                self.close()
        if window is None and not testing:
            self.close()
            self._retry_at = None
            return
        url = draw.url if draw else DRAW_STREAM_URL
        if self._url is not None and self._url != url and (self._hwnd is not None or self._launched_at is not None):
            self.close()  # a different channel's window is due now
            self._retry_at = None
        if rect is None or rect[2] < 200 or rect[3] < 150:
            return  # dashboard not laid out, minimised or on another tab; try again next tick
        key = f"{now:%Y-%m-%d} {window or 'test'}"
        if self._hwnd is not None:
            if self.exists(self._hwnd):
                if (draw is not None and draw.reload_until_live and self._docked_at is not None
                        and now - self._docked_at >= timedelta(seconds=LIVE_RELOAD_SECONDS)
                        and not shows_live_draw(self.title(self._hwnd), draw.draw_hour)):
                    # The channel is not live with this draw yet: reopen its live page.
                    logger.info("Draw stream not live yet; reopening the channel")
                    self.close()
                    self._shown_windows.discard(key)
                    self._retry_at = None
                    return
                self.place(self._hwnd, rect)
                return
            # The stream window was closed by hand: leave it closed until the next draw window.
            logger.info("Draw stream window was closed")
            self._hwnd = None
            return
        if self._launched_at is not None:
            new = sorted(self.list_windows() - self._before)
            # Prefer the app-mode window (Chrome may also restore other windows when it starts).
            apps = [hwnd for hwnd in new if is_app_window_title(self.title(hwnd))]
            if apps:
                self._hwnd = apps[-1]
                self._launched_at = None
                self._docked_at = now
                self._shown_windows.add(key)
                logger.info("Draw stream window found and docked")
                self.place(self._hwnd, rect)
                return
            if now - self._launched_at < timedelta(seconds=WINDOW_APPEAR_SECONDS):
                return  # still starting
            logger.warning("Draw stream did not appear; retrying in %s s", RETRY_SECONDS)
            self._launched_at = None
            self._retry_at = now + timedelta(seconds=RETRY_SECONDS)
            return
        if key in self._shown_windows and not testing:
            return  # already shown in this draw window (and then closed by hand)
        if self._retry_at is not None and now < self._retry_at:
            return
        self._launch(rect, now, url)

    def _launch(self, rect: Rect, now: datetime, url: str = DRAW_STREAM_URL) -> None:
        self._url = url
        args = self.command(url, rect, self.edge_profile_dir)
        if args is None:
            logger.warning("Draw stream skipped: neither Chrome nor Edge was found")
            self._retry_at = now + timedelta(seconds=RETRY_SECONDS)
            return
        self._before = self.list_windows()
        try:
            self.launcher(args)
            self._launched_at = now
            logger.info("Draw stream launching in %s", Path(args[0]).stem)
        except OSError as exc:
            logger.warning("Draw stream could not be launched (%s); retrying in %s s", type(exc).__name__, RETRY_SECONDS)
            self._retry_at = now + timedelta(seconds=RETRY_SECONDS)

    def close(self) -> None:
        hwnd, self._hwnd = self._hwnd, None
        self._launched_at = None
        self._docked_at = None
        if hwnd is not None and self.exists(hwnd):
            try:
                self.close_one(hwnd)
                logger.info("Draw stream window closed")
            except Exception as exc:
                logger.warning("Draw stream window could not be closed (%s)", type(exc).__name__)
