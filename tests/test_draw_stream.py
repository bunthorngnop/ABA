"""Lottery draw stream docking with fake browser windows (no browser is ever started by these tests)."""

from datetime import datetime, timedelta
from pathlib import Path

from app.draw_stream import (
    CHROME_PROFILE_NAME,
    DRAW_STREAM_URL,
    RETRY_SECONDS,
    DrawStreamController,
    active_draw_window,
    browser_command,
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
        )
        self.titles = {1: "Inbox - Google Chrome"}

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
