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
import threading
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


# --- Player-only page (owner-approved 2026-11-24) -------------------------------------------------
# ABA looks up the channel's current live video and opens YouTube's player-only (embed) page, so
# the window shows just the video: no comments, titles or suggestions. If the lookup fails, the
# normal /live page is opened instead.

@dataclass(frozen=True)
class LiveVideo:
    video_id: str
    title: str
    live_now: bool


_CANONICAL = re.compile(r'<link rel="canonical" href="https://www\.youtube\.com/watch\?v=([\w-]{11})"')
_META_TITLE = re.compile(r'<meta name="title" content="([^"]*)"')


def parse_live_page(page: str) -> Optional[LiveVideo]:
    """The video a channel's /live page points at, or None when it shows the channel instead."""
    import html

    match = _CANONICAL.search(page)
    if match is None:
        return None
    title = _META_TITLE.search(page)
    return LiveVideo(match.group(1), html.unescape(title.group(1)) if title else "", '"isLiveNow":true' in page)


def fetch_live_video(channel_url: str, timeout: float = 15.0) -> Optional[LiveVideo]:
    """Read the channel's /live page (public, no sign-in). Raises OSError on network problems."""
    import urllib.request

    request = urllib.request.Request(channel_url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept-Language": "en"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        page = response.read(6_000_000).decode("utf-8", "ignore")
    return parse_live_page(page)


def player_url(video_id: str) -> str:
    return f"https://www.youtube.com/embed/{video_id}?autoplay=1&rel=0&playsinline=1"


# YouTube refuses its player page when it is opened directly ("Error 153", no referring page), so
# ABA serves a tiny page on this PC only (127.0.0.1, random port) that holds just the player.
_VIDEO_ID = re.compile(r"[\w-]{11}")


# Stream volume in percent (owner, 2026-11-24). The player window keeps its own YouTube volume,
# separate from youtube.com, so the page sets it through YouTube's IFrame Player API on every open.
DRAW_STREAM_VOLUME = 20


def player_page_html(video_id: str, volume: int = DRAW_STREAM_VOLUME) -> bytes:
    """Page holding only the YouTube player, unmuted at `volume` %; the title reports the volume."""
    if not _VIDEO_ID.fullmatch(video_id):
        raise ValueError("not a YouTube video id")
    volume = max(0, min(100, int(volume)))
    return (
        '<!doctype html><html><head><meta charset="utf-8"><title>Draw stream</title>'
        "<style>html,body,#player{margin:0;width:100%;height:100%;background:#000;overflow:hidden}"
        "iframe{border:0;width:100%;height:100%}</style></head><body><div id=\"player\"></div>"
        '<script src="https://www.youtube.com/iframe_api"></script><script>'
        f"var VOLUME={volume},applied=false;"
        "function setVolume(p){p.unMute();p.setVolume(VOLUME);"
        "setTimeout(function(){document.title='Draw stream - volume '+p.getVolume();},500);}"
        "function onYouTubeIframeAPIReady(){new YT.Player('player',{"
        f"videoId:'{video_id}',width:'100%',height:'100%',"
        "playerVars:{autoplay:1,rel:0,playsinline:1,origin:location.origin},"
        "events:{onReady:function(e){setVolume(e.target);e.target.playVideo();},"
        "onStateChange:function(e){if(e.data===1&&!applied){applied=true;setVolume(e.target);}}}});}"
        "</script></body></html>"
    ).encode("utf-8")


class PlayerPageServer:
    """Serves GET /player?v=<video id> on 127.0.0.1 only; anything else is 404."""

    def __init__(self):
        self._server = None
        self._lock = threading.Lock()

    def url(self, video_id: str) -> str:
        if not _VIDEO_ID.fullmatch(video_id):
            raise ValueError("not a YouTube video id")
        with self._lock:
            if self._server is None:
                self._server = self._start()
            port = self._server.server_address[1]
        return f"http://127.0.0.1:{port}/player?v={video_id}"

    @staticmethod
    def _start():
        import http.server
        from urllib.parse import parse_qs, urlsplit

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                parts = urlsplit(self.path)
                video_id = parse_qs(parts.query).get("v", [""])[0]
                if parts.path != "/player" or not _VIDEO_ID.fullmatch(video_id):
                    self.send_error(404)
                    return
                body = player_page_html(video_id)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, name="draw-stream-page", daemon=True).start()
        return server

    def stop(self) -> None:
        with self._lock:
            server, self._server = self._server, None
        if server is not None:
            server.shutdown()
            server.server_close()


PLAYER_PAGES = PlayerPageServer()


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


# --- Chrome autoplay (owner-approved option A, 2026-11-24) ---------------------------------------
# The owner's Chrome is usually already running, and a running Chrome ignores the
# --autoplay-policy flag of a new window, so the stream waited for a click on Play. Chrome's
# per-user policy AutoplayAllowlist lets only YouTube play with sound by itself; every other site
# keeps Chrome's normal rules. Chrome then shows "Managed by your organization" in its menu.
CHROME_POLICY_KEY = r"Software\Policies\Google\Chrome\AutoplayAllowlist"
AUTOPLAY_SITE = "[*.]youtube.com"


def _allowlist_has_youtube(winreg, root) -> bool:
    try:
        with winreg.OpenKey(root, CHROME_POLICY_KEY, 0, winreg.KEY_READ) as key:
            index = 0
            while True:
                try:
                    _name, value, _kind = winreg.EnumValue(key, index)
                except OSError:
                    return False
                if value == AUTOPLAY_SITE:
                    return True
                index += 1
    except OSError:
        return False


def ensure_youtube_autoplay(registry=None) -> bool:
    """True when YouTube is in Chrome's autoplay allowlist (machine-wide or this user's); adds it if possible.

    Windows lets only an administrator write Chrome policies, so on a normal account the owner sets
    it once (see README); ABA then only checks it.
    """
    try:
        winreg = registry
        if winreg is None:
            import winreg  # type: ignore[no-redef]
        if any(_allowlist_has_youtube(winreg, root) for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER)):
            return True
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, CHROME_POLICY_KEY, 0,
                                winreg.KEY_READ | winreg.KEY_SET_VALUE) as key:
            names, index = set(), 0
            while True:
                try:
                    name, value, _kind = winreg.EnumValue(key, index)
                except OSError:
                    break
                if value == AUTOPLAY_SITE:
                    return True
                names.add(name)
                index += 1
            slot = next(str(n) for n in range(1, len(names) + 2) if str(n) not in names)
            winreg.SetValueEx(key, slot, 0, winreg.REG_SZ, AUTOPLAY_SITE)
            logger.info("Chrome autoplay allowed for YouTube (per-user policy)")
            return True
    except (OSError, ImportError) as exc:
        logger.warning("Chrome autoplay for YouTube is not set (%s); an administrator must set it once "
                       "(README: Chrome autoplay); until then the stream may need a click on Play", type(exc).__name__)
        return False


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
        ensure_autoplay: Callable[[], bool] = ensure_youtube_autoplay,
        resolve: Callable[[str], Optional[LiveVideo]] = fetch_live_video,
        background: Callable[[Callable[[], None]], None] = lambda work: threading.Thread(
            target=work, name="draw-stream-lookup", daemon=True).start(),
        player_page: Callable[[str], str] = PLAYER_PAGES.url,
    ):
        self.player_page = player_page
        self.ensure_autoplay = ensure_autoplay
        self._autoplay_ok = False
        self.resolve, self.background = resolve, background
        self._lookup_pending = False
        self._lookup_result: Optional[tuple[str, str, Optional[LiveVideo]]] = None  # (channel, "ok"/"error", video)
        self._player_only = False  # the open window shows the player-only page
        self._lookup_at = clock()
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
                if (draw is not None and draw.reload_until_live and not self._player_only
                        and self._docked_at is not None
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
        target = self._target(draw, url, now)
        if target is not None:
            self._launch(rect, now, url, target)

    def _start_lookup(self, channel_url: str) -> None:
        self._lookup_pending = True

        def work() -> None:
            try:
                result = (channel_url, "ok", self.resolve(channel_url))
            except Exception as exc:
                logger.info("Live video lookup failed (%s); the normal live page will be used", type(exc).__name__)
                result = (channel_url, "error", None)
            self._lookup_result = result
            self._lookup_at = self.clock()
            self._lookup_pending = False

        self.background(work)

    def _target(self, draw: Optional[DrawWindow], channel_url: str, now: datetime) -> Optional[str]:
        """The page to open now, or None while looking up / waiting for the right live."""
        if self._lookup_pending:
            return None
        if self._lookup_result is not None and now - self._lookup_at > timedelta(seconds=LIVE_RELOAD_SECONDS):
            self._lookup_result = None  # too old (e.g. from an earlier draw window)
        if self._lookup_result is None or self._lookup_result[0] != channel_url:
            self._start_lookup(channel_url)
            if self._lookup_pending or self._lookup_result is None:
                return None  # answer arrives in the background
        _channel, status, video = self._lookup_result
        self._lookup_result = None  # look up afresh next time
        if status == "error":
            self._player_only = False
            return channel_url  # fallback: the normal live page
        reload = draw is not None and draw.reload_until_live
        if video is not None and video.live_now and (not reload or shows_live_draw(video.title, draw.draw_hour)):
            try:
                page = self.player_page(video.video_id)
            except Exception as exc:
                logger.warning("Player page unavailable (%s); the normal live page will be used", type(exc).__name__)
                self._player_only = False
                return channel_url
            self._player_only = True
            return page
        if reload:
            logger.info("Draw stream: that hour's live has not started yet; checking again in %s s", LIVE_RELOAD_SECONDS)
            self._retry_at = now + timedelta(seconds=LIVE_RELOAD_SECONDS)
            return None
        self._player_only = False
        return channel_url

    def _launch(self, rect: Rect, now: datetime, url: str = DRAW_STREAM_URL, target: Optional[str] = None) -> None:
        self._url = url
        if not self._autoplay_ok:
            self._autoplay_ok = True  # checked once per ABA run (it restarts daily at 07:30)
            try:
                self.ensure_autoplay()
            except Exception:
                logger.exception("Chrome autoplay check failed")
        args = self.command(target or url, rect, self.edge_profile_dir)
        if args is None:
            logger.warning("Draw stream skipped: neither Chrome nor Edge was found")
            self._retry_at = now + timedelta(seconds=RETRY_SECONDS)
            return
        self._before = self.list_windows()
        try:
            self.launcher(args)
            self._launched_at = now
            logger.info("Draw stream launching in %s (%s)", Path(args[0]).stem,
                        "player only" if target and target != url else "live page")
        except OSError as exc:
            logger.warning("Draw stream could not be launched (%s); retrying in %s s", type(exc).__name__, RETRY_SECONDS)
            self._retry_at = now + timedelta(seconds=RETRY_SECONDS)

    def close(self) -> None:
        hwnd, self._hwnd = self._hwnd, None
        self._launched_at = None
        self._docked_at = None
        self._player_only = False
        if hwnd is not None and self.exists(hwnd):
            try:
                self.close_one(hwnd)
                logger.info("Draw stream window closed")
            except Exception as exc:
                logger.warning("Draw stream window could not be closed (%s)", type(exc).__name__)
