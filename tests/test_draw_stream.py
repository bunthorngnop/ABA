"""Lottery draw stream docking with fake browser windows (no browser is ever started by these tests)."""

from datetime import datetime, timedelta
from pathlib import Path

from app.draw_stream import (
    CAMBODIAN_STREAM_URL,
    CHROME_PROFILE_NAME,
    DRAW_STREAM_URL,
    LIVE_RELOAD_SECONDS,
    RETRY_SECONDS,
    DrawStreamController,
    active_draw_window,
    browser_command,
    draw_window_at,
    shows_live_draw,
)
from app.exchange_rates import CAMBODIA_TIMEZONE

RECT = (690, 1300, 670, 500)


def at(hour, minute, second=0, day=21):
    return datetime(2026, 11, day, hour, minute, second, tzinfo=CAMBODIA_TIMEZONE)


class FakeDesktop:
    """Browser windows on screen; the user's own Chrome window 1 is open all along."""

    def __init__(self, now, stream_appears=True):
        self.now = now
        self.windows = {1}
        self.stream_appears = stream_appears
        self.launches, self.placed, self.closed = [], [], []
        self.controller = DrawStreamController(
            Path("edge-profile"), lambda: self.now,
            launcher=self.launch,
            command=lambda url, rect, profile: ["chrome.exe", f"--app={url}"],
            list_windows=lambda: set(self.windows),
            exists=lambda hwnd: hwnd in self.windows,
            place=lambda hwnd, rect: self.placed.append((hwnd, rect)),
            close=self.close,
            title=lambda hwnd: self.titles.get(hwnd, "XSMB Minh Ngọc - Trực tiếp"),
            ensure_autoplay=self.allow_autoplay,
            resolve=self.lookup,
            background=lambda work: work(),  # run the lookup at once (no threads in tests)
            player_page=lambda video_id: f"http://127.0.0.1:1/player?v={video_id}",
        )
        self.autoplay_calls = 0
        self.live = {}  # channel url -> LiveVideo; a channel missing here fails like a network error
        self.lookups = []
        self.titles = {1: "Inbox - Google Chrome"}

    def lookup(self, url):
        self.lookups.append(url)
        if url not in self.live:
            raise OSError("no network in tests")
        return self.live[url]

    def allow_autoplay(self):
        self.autoplay_calls += 1
        return True

    def launch(self, args):
        self.launches.append(args)
        if self.stream_appears:
            self.windows.add(100 + len(self.launches))

    def close(self, hwnd):
        self.closed.append(hwnd)
        self.windows.discard(hwnd)


def test_draw_windows_are_1605_to_1640_and_1805_to_1840():
    assert active_draw_window(at(16, 4)) is None
    assert active_draw_window(at(16, 5)) == "16:05-16:40"
    assert active_draw_window(at(16, 39)) == "16:05-16:40"
    assert active_draw_window(at(16, 40)) is None
    assert active_draw_window(at(18, 5)) == "18:05-18:40"


def test_vietnamese_channel_at_16_and_18_cambodian_channel_at_10_13_and_19():
    """Owner decision 2026-11-22."""
    expected = {
        (10, 15): ("10:15-10:45", CAMBODIAN_STREAM_URL), (13, 15): ("13:15-13:45", CAMBODIAN_STREAM_URL),
        (16, 5): ("16:05-16:40", DRAW_STREAM_URL), (18, 5): ("18:05-18:40", DRAW_STREAM_URL),
        (19, 15): ("19:15-19:45", CAMBODIAN_STREAM_URL),
    }
    for (hour, minute), (label, url) in expected.items():
        window = draw_window_at(at(hour, minute))
        assert (window.label, window.url) == (label, url)
    for hour, minute in ((10, 14), (10, 45), (13, 45), (17, 15), (19, 45), (8, 30), (20, 30)):
        assert draw_window_at(at(hour, minute)) is None
    assert CAMBODIAN_STREAM_URL == "https://www.youtube.com/channel/UC1SVFPlK1ljQk-jdHgXB6qA/live"


def test_tuesday_and_thursday_results_five_minutes_early_are_inside_every_window():
    for day in (24, 26):  # Tuesday 24 and Thursday 26 November 2026
        assert at(10, 25, day=day).weekday() in (1, 3)
        for hour in (10, 13, 16, 18, 19):
            assert draw_window_at(at(hour, 25, day=day)) is not None  # results about 5 minutes early
            assert draw_window_at(at(hour, 30, day=day)) is not None  # usual time


def test_live_title_check_uses_the_12_hour_time_in_the_cambodian_titles():
    title = "🔴LIVE ! លទ្ធផលឆ្នោតយួន | ម៉ោង 07:30 នាទី | ថ្ងៃទី 21/11/2026 | ផ្ទះ ឆ្នោតយួន - YouTube"
    assert shows_live_draw(title, 19)
    assert not shows_live_draw(title, 13)  # another hour's stream
    assert shows_live_draw(title.replace("07:30", "01:25"), 13)  # Tue/Thu minutes may differ
    assert shows_live_draw(title.replace("07:30", "10:30"), 10)
    assert not shows_live_draw("ផ្ទះ ឆ្នោតយួន - YouTube", 10)  # channel home page: nothing live
    assert not shows_live_draw("YouTube", 10)


def test_cambodian_channel_is_reopened_every_minute_until_its_live_shows():
    desk = FakeDesktop(at(19, 15))
    desk.titles[101] = "ផ្ទះ ឆ្នោតយួន - YouTube"  # not live yet
    desk.controller.tick(RECT)  # launch
    assert f"--app={CAMBODIAN_STREAM_URL}" in desk.launches[0]
    desk.controller.tick(RECT)  # docked
    desk.now += timedelta(seconds=LIVE_RELOAD_SECONDS - 2)
    desk.controller.tick(RECT)
    assert desk.closed == []  # give the page a minute
    desk.now += timedelta(seconds=2)
    desk.controller.tick(RECT)
    assert desk.closed == [101]  # reopened, not treated as closed by hand
    desk.titles[102] = "🔴LIVE ! លទ្ធផលឆ្នោតយួន | ម៉ោង 07:30 នាទី | ផ្ទះ ឆ្នោតយួន - YouTube"
    desk.controller.tick(RECT)  # relaunch
    desk.controller.tick(RECT)  # docked
    assert len(desk.launches) == 2 and desk.placed[-1][0] == 102
    desk.now += timedelta(seconds=5 * LIVE_RELOAD_SECONDS)
    desk.controller.tick(RECT)
    assert desk.closed == [101]  # live now: left alone
    desk.now = at(19, 45)
    desk.controller.tick(RECT)
    assert desk.closed == [101, 102]


def test_vietnamese_channel_is_never_reopened_for_its_title():
    desk = FakeDesktop(at(16, 6))
    desk.controller.tick(RECT)
    desk.controller.tick(RECT)
    desk.now += timedelta(seconds=10 * LIVE_RELOAD_SECONDS)
    desk.controller.tick(RECT)
    assert desk.closed == [] and len(desk.launches) == 1
    assert f"--app={DRAW_STREAM_URL}" in desk.launches[0]


def test_chrome_command_uses_the_owners_profile_and_app_mode(monkeypatch):
    import app.draw_stream as ds

    monkeypatch.setattr(ds, "CHROME_PATHS", (Path(__file__),))  # any existing file stands in for chrome.exe
    monkeypatch.setattr(ds, "chrome_profile_directory", lambda name=CHROME_PROFILE_NAME: "Profile 2")
    args = browser_command(DRAW_STREAM_URL, RECT, Path("edge-profile"))
    assert f"--app={DRAW_STREAM_URL}" in args and "--profile-directory=Profile 2" in args
    assert "--window-position=690,1300" in args and "--window-size=670,500" in args
    assert not any(a.startswith("--user-data-dir") for a in args)  # the owner's signed-in Chrome, not a new profile
    assert CHROME_PROFILE_NAME == "Bunthorng" and DRAW_STREAM_URL == "https://www.youtube.com/@xosominhngoc/live"


def test_docks_only_the_new_window_and_closes_only_that_window():
    desk = FakeDesktop(at(16, 6))
    desk.controller.tick(RECT)  # launch
    desk.controller.tick(RECT)  # the new window is found and docked
    assert desk.placed == [(101, RECT)]
    desk.now = at(16, 40)
    desk.controller.tick(RECT)
    assert desk.closed == [101]  # the user's own Chrome window 1 is never touched
    assert desk.windows == {1}


def test_keeps_retrying_the_channel_until_the_stream_appears():
    desk = FakeDesktop(at(16, 6), stream_appears=False)
    desk.controller.tick(RECT)
    desk.now += timedelta(seconds=26)
    desk.controller.tick(RECT)  # gave up waiting; retry later
    assert len(desk.launches) == 1
    desk.now += timedelta(seconds=RETRY_SECONDS)
    desk.stream_appears = True
    desk.controller.tick(RECT)  # second attempt
    desk.controller.tick(RECT)
    assert len(desk.launches) == 2 and desk.placed and desk.placed[-1][0] == 102


def test_closed_by_hand_stays_closed_until_the_next_window():
    desk = FakeDesktop(at(18, 10))
    desk.controller.tick(RECT)
    desk.controller.tick(RECT)
    desk.windows.discard(101)  # the user clicked ✕
    for _ in range(3):
        desk.controller.tick(RECT)
    assert len(desk.launches) == 1
    desk.now = at(16, 6, day=22)
    desk.controller.tick(RECT)
    assert len(desk.launches) == 2


def test_waits_for_the_dashboard_and_never_opens_outside_a_window():
    desk = FakeDesktop(at(16, 6))
    desk.controller.tick(None)
    assert desk.launches == []
    desk.now = at(15, 0)
    desk.controller.tick(RECT)
    assert desk.launches == []


def test_test_button_opens_for_a_minute_outside_the_draw_window():
    desk = FakeDesktop(at(11, 0))
    desk.controller.open_test(desk.now + timedelta(seconds=60))
    desk.controller.tick(RECT)
    desk.controller.tick(RECT)
    assert desk.placed
    desk.now = at(11, 2)
    desk.controller.tick(RECT)
    assert desk.closed == [101]


def test_restored_normal_chrome_windows_are_never_mistaken_for_the_stream():
    desk = FakeDesktop(at(16, 6))
    desk.windows.add(50)  # Chrome restored a normal window while starting
    desk.titles[50] = "Gmail - Google Chrome"
    desk.controller._before = {1}
    desk.controller.tick(RECT)  # launch (snapshot now includes 50)
    desk.windows.add(60)
    desk.titles[60] = "News - Google Chrome"  # another restored window appears with the stream
    desk.controller.tick(RECT)
    assert desk.placed == [(101, RECT)]


class FakeRegistry:
    """Stands in for winreg (the real registry is never touched).

    `values` is this user's allowlist, `machine` the machine-wide one; `writable=False` behaves like
    a normal account, where Windows refuses writes under Software\\Policies.
    """

    HKEY_CURRENT_USER, HKEY_LOCAL_MACHINE, KEY_READ, KEY_SET_VALUE, REG_SZ = "HKCU", "HKLM", 1, 2, 1

    def __init__(self, values=None, machine=None, writable=True):
        self.values = dict(values or {})
        self.machine = machine
        self.writable = writable
        self.opened = []

    def _key(self, values):
        class Key:
            def __enter__(self): return values
            def __exit__(self, *exc): return False

        return Key()

    def OpenKey(self, root, path, reserved, access):
        values = self.machine if root == "HKLM" else (self.values or None)
        if values is None:
            raise FileNotFoundError(path)
        return self._key(values)

    def CreateKeyEx(self, root, path, reserved, access):
        if not self.writable:
            raise PermissionError(path)
        self.opened.append((root, path))
        return self._key(self.values)

    def EnumValue(self, key, index):
        items = list(key.items())
        if index >= len(items):
            raise OSError("no more values")
        name, value = items[index]
        return name, value, self.REG_SZ

    def SetValueEx(self, key, name, reserved, kind, value):
        key[name] = value


def test_autoplay_set_machine_wide_by_an_administrator_is_recognised():
    from app.draw_stream import ensure_youtube_autoplay

    registry = FakeRegistry(machine={"1": "[*.]youtube.com"}, writable=False)
    assert ensure_youtube_autoplay(registry) is True
    assert registry.values == {}  # nothing written


def test_autoplay_not_set_on_a_normal_account_reports_false_without_crashing():
    from app.draw_stream import ensure_youtube_autoplay

    assert ensure_youtube_autoplay(FakeRegistry(writable=False)) is False


def test_youtube_autoplay_is_added_to_chromes_per_user_allowlist():
    from app.draw_stream import AUTOPLAY_SITE, CHROME_POLICY_KEY, ensure_youtube_autoplay

    registry = FakeRegistry()
    assert ensure_youtube_autoplay(registry) is True
    assert registry.values == {"1": "[*.]youtube.com"} == {"1": AUTOPLAY_SITE}
    assert registry.opened == [(registry.HKEY_CURRENT_USER, r"Software\Policies\Google\Chrome\AutoplayAllowlist")]
    assert CHROME_POLICY_KEY.startswith(r"Software\Policies\Google\Chrome")


def test_youtube_autoplay_keeps_other_entries_and_is_not_added_twice():
    from app.draw_stream import ensure_youtube_autoplay

    registry = FakeRegistry({"1": "https://example.org"})
    ensure_youtube_autoplay(registry)
    ensure_youtube_autoplay(registry)
    assert registry.values == {"1": "https://example.org", "2": "[*.]youtube.com"}


def test_autoplay_is_ensured_once_before_the_first_launch():
    desk = FakeDesktop(at(16, 6))
    desk.controller.tick(RECT)
    desk.controller.tick(RECT)
    desk.now = at(16, 40)
    desk.controller.tick(RECT)  # window ends: stream closed
    desk.now = at(18, 6)
    desk.controller.tick(RECT)
    assert desk.autoplay_calls == 1 and len(desk.launches) == 2


# --- Player-only page (owner-approved 2026-11-24) ---

MN_LIVE_PAGE = (
    '<html><head><link rel="canonical" href="https://www.youtube.com/watch?v=bWi0ebH0VB0">'
    '<meta name="title" content="XSMB Minh Ngọc - Trực tiếp Xổ Số Miền Bắc &amp; KQXS">'
    '</head><script>{"isLiveNow":true}</script></html>'
)


def live(video_id, title, live_now=True):
    from app.draw_stream import LiveVideo
    return LiveVideo(video_id, title, live_now)


def test_live_page_gives_the_video_id_title_and_live_status():
    from app.draw_stream import parse_live_page, player_url

    video = parse_live_page(MN_LIVE_PAGE)
    assert video.video_id == "bWi0ebH0VB0" and video.live_now is True
    assert video.title == "XSMB Minh Ngọc - Trực tiếp Xổ Số Miền Bắc & KQXS"
    assert parse_live_page(MN_LIVE_PAGE.replace('"isLiveNow":true', '')).live_now is False  # an ended stream
    assert parse_live_page('<link rel="canonical" href="https://www.youtube.com/channel/UC1">') is None
    assert player_url("bWi0ebH0VB0") == "https://www.youtube.com/embed/bWi0ebH0VB0?autoplay=1&rel=0&playsinline=1"


def test_opens_the_player_only_page_of_the_live_video():
    desk = FakeDesktop(at(16, 6))
    desk.live[DRAW_STREAM_URL] = live("bWi0ebH0VB0", "XSMN Minh Ngọc - Trực tiếp")
    desk.controller.tick(RECT)
    assert desk.launches == [["chrome.exe", "--app=http://127.0.0.1:1/player?v=bWi0ebH0VB0"]]
    desk.controller.tick(RECT)
    assert desk.placed == [(101, RECT)]


def test_falls_back_to_the_live_page_when_the_lookup_fails_or_nothing_is_live():
    desk = FakeDesktop(at(16, 6))  # lookup fails (no entry)
    desk.controller.tick(RECT)
    assert desk.launches[-1] == ["chrome.exe", f"--app={DRAW_STREAM_URL}"]
    desk = FakeDesktop(at(18, 6))
    desk.live[DRAW_STREAM_URL] = live("oldvideo123", "XSMB yesterday", live_now=False)
    desk.controller.tick(RECT)
    assert desk.launches[-1] == ["chrome.exe", f"--app={DRAW_STREAM_URL}"]


def test_cambodian_window_opens_only_when_that_hours_live_has_started():
    desk = FakeDesktop(at(19, 15))
    desk.live[CAMBODIAN_STREAM_URL] = live("xGxcf6tpEDQ", "🔴LIVE ! លទ្ធផលឆ្នោតយួន | ម៉ោង 06:30 នាទី", live_now=False)
    desk.controller.tick(RECT)
    assert desk.launches == []  # the last stream (18:30) has ended: wait
    desk.now += timedelta(seconds=LIVE_RELOAD_SECONDS - 1)
    desk.controller.tick(RECT)
    assert len(desk.lookups) == 1  # checks again only after a minute
    desk.now += timedelta(seconds=1)
    desk.live[CAMBODIAN_STREAM_URL] = live("Av6ez-UWyuQ", "🔴LIVE ! លទ្ធផលឆ្នោតយួន | ម៉ោង 07:30 នាទី")
    desk.controller.tick(RECT)
    assert desk.launches == [["chrome.exe", "--app=http://127.0.0.1:1/player?v=Av6ez-UWyuQ"]]
    desk.controller.tick(RECT)
    desk.titles[101] = "YouTube"  # the player page title is not checked: never reopened
    desk.now += timedelta(seconds=10 * LIVE_RELOAD_SECONDS)
    desk.controller.tick(RECT)
    assert desk.closed == [] and len(desk.launches) == 1


def test_a_lookup_answer_is_never_reused_for_a_later_window():
    desk = FakeDesktop(at(16, 6))
    desk.live[DRAW_STREAM_URL] = live("firstvideo1", "XSMN live")
    desk.controller.tick(RECT)
    desk.controller.tick(RECT)
    desk.now = at(16, 40)
    desk.controller.tick(RECT)
    desk.live[DRAW_STREAM_URL] = live("secondvideo", "XSMB live")
    desk.now = at(18, 6)
    desk.controller.tick(RECT)
    assert desk.launches[-1][1].endswith("player?v=secondvideo")


def test_local_player_page_holds_only_the_youtube_player_and_serves_nothing_else():
    import urllib.error
    import urllib.request

    from app.draw_stream import PlayerPageServer

    server = PlayerPageServer()
    try:
        url = server.url("bWi0ebH0VB0")
        assert url.startswith("http://127.0.0.1:") and url.endswith("/player?v=bWi0ebH0VB0")
        page = urllib.request.urlopen(url, timeout=5).read().decode("utf-8")
        assert '<script src="https://www.youtube.com/iframe_api"></script>' in page
        assert "videoId:'bWi0ebH0VB0'" in page and "VOLUME=20" in page
        base = url.split("/player")[0]
        for bad in ("/player?v=../../etc", "/player?v=%3Cscript%3E", "/", "/other?v=bWi0ebH0VB0"):
            try:
                urllib.request.urlopen(base + bad, timeout=5)
                raise AssertionError(f"served {bad}")
            except urllib.error.HTTPError as exc:
                assert exc.code == 404
    finally:
        server.stop()
    try:
        PlayerPageServer().url("not-an-id")
        raise AssertionError("accepted a bad id")
    except ValueError:
        pass


def test_falls_back_to_the_live_page_if_the_player_page_cannot_start():
    desk = FakeDesktop(at(16, 6))
    desk.live[DRAW_STREAM_URL] = live("bWi0ebH0VB0", "XSMN live")

    def broken(video_id):
        raise OSError("port unavailable")

    desk.controller.player_page = broken
    desk.controller.tick(RECT)
    assert desk.launches[-1] == ["chrome.exe", f"--app={DRAW_STREAM_URL}"]


def test_player_page_sets_the_stream_volume_to_20_percent_unmuted():
    from app.draw_stream import DRAW_STREAM_VOLUME, player_page_html

    assert DRAW_STREAM_VOLUME == 20  # owner, 2026-11-24
    page = player_page_html("bWi0ebH0VB0").decode("utf-8")
    assert "VOLUME=20" in page and "p.unMute();p.setVolume(VOLUME)" in page
    assert "onReady:function(e){setVolume(e.target)" in page  # set as soon as the player is ready
    assert "if(e.data===1&&!applied)" in page  # and again when it first starts playing
    assert "autoplay:1" in page and "origin:location.origin" in page
    assert "VOLUME=100" in player_page_html("bWi0ebH0VB0", 250).decode("utf-8")  # kept within 0-100
    try:
        player_page_html("bad'id</script>")
        raise AssertionError("accepted a bad id")
    except ValueError:
        pass
