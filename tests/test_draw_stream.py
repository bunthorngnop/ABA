"""Lottery draw stream docking (fake Edge: no browser is ever started by these tests)."""

from datetime import datetime, timedelta
from pathlib import Path

from app import draw_stream as ds
from app.draw_stream import DRAW_STREAM_URL, DrawStreamController, active_draw_window
from app.exchange_rates import CAMBODIA_TIMEZONE


def at(hour, minute, day=18):
    return datetime(2026, 11, day, hour, minute, tzinfo=CAMBODIA_TIMEZONE)


class FakeProcess:
    pid = 4242

    def __init__(self):
        self.running = True

    def poll(self):
        return None if self.running else 0


class Harness:
    def __init__(self, tmp_path, monkeypatch, now):
        self.now = now
        self.launches = []
        self.killed = []
        self.process = None

        def launcher(args):
            self.launches.append(args)
            self.process = FakeProcess()
            return self.process

        monkeypatch.setattr(ds, "_kernel32", None)  # fake process: no real Windows process lookup
        monkeypatch.setattr(ds, "_dock_calls", [], raising=False)
        monkeypatch.setattr(ds.DrawStreamController, "_dock", lambda controller, rect: ds._dock_calls.append(rect))
        monkeypatch.setattr(ds.subprocess, "run", lambda args, **kwargs: self.killed.append(args))
        self.controller = DrawStreamController(
            tmp_path / "profile", lambda: self.now, launcher=launcher, edge_path=Path("msedge.exe"),
        )


RECT = (690, 1300, 670, 500)


def test_draw_windows_are_1605_to_1640_and_1805_to_1840():
    assert active_draw_window(at(16, 4)) is None
    assert active_draw_window(at(16, 5)) == "16:05-16:40"
    assert active_draw_window(at(16, 39)) == "16:05-16:40"
    assert active_draw_window(at(16, 40)) is None
    assert active_draw_window(at(18, 5)) == "18:05-18:40"
    assert active_draw_window(at(12, 0)) is None


def test_opens_docked_edge_app_window_with_sound_and_closes_after_the_draw(tmp_path, monkeypatch):
    h = Harness(tmp_path, monkeypatch, at(16, 6))
    h.controller.tick(RECT)
    args = h.launches[0]
    assert f"--app={DRAW_STREAM_URL}" in args and DRAW_STREAM_URL == "https://www.youtube.com/@xosominhngoc/live"
    assert "--window-position=690,1300" in args and "--window-size=670,500" in args
    assert "--autoplay-policy=no-user-gesture-required" in args  # sound on, no click needed
    assert any(a.startswith("--user-data-dir=") for a in args)  # own profile, user's Edge untouched
    h.controller.tick(RECT)
    assert ds._dock_calls == [RECT]  # kept in place over the cards
    h.now = at(16, 40)
    h.controller.tick(RECT)
    assert h.killed and h.killed[0][0] == "taskkill" and "/PID" in h.killed[0]
    assert not h.controller.is_open


def test_opens_once_per_window_and_not_again_if_closed_by_hand(tmp_path, monkeypatch):
    h = Harness(tmp_path, monkeypatch, at(18, 10))
    h.controller.tick(RECT)
    h.process.running = False  # someone closed the stream
    h.controller.tick(RECT)
    h.controller.tick(RECT)
    assert len(h.launches) == 1
    h.now = at(16, 6, day=19)  # next day's window opens again
    h.controller.tick(RECT)
    assert len(h.launches) == 2


def test_waits_for_the_dashboard_and_never_opens_outside_a_window(tmp_path, monkeypatch):
    h = Harness(tmp_path, monkeypatch, at(16, 6))
    h.controller.tick(None)  # dashboard minimised or on another tab
    assert h.launches == []
    h.now = at(15, 0)
    h.controller.tick(RECT)
    assert h.launches == []


def test_test_button_opens_for_a_minute_outside_the_draw_window(tmp_path, monkeypatch):
    h = Harness(tmp_path, monkeypatch, at(11, 0))
    h.controller.open_test(h.now + timedelta(seconds=60))
    h.controller.tick(RECT)
    assert len(h.launches) == 1
    h.now = at(11, 2)
    h.controller.tick(RECT)
    assert h.killed


def test_missing_edge_is_skipped_quietly(tmp_path):
    controller = DrawStreamController(tmp_path, lambda: at(16, 6), launcher=lambda args: 1 / 0, edge_path=None)
    controller.edge_path = None
    controller.tick(RECT)
    assert not controller.is_open
