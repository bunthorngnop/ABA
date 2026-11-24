"""Daily 07:30 close (the watchdog task starts ABA again)."""

from datetime import datetime, timedelta

from app.daily_restart import DailyRestart
from app.exchange_rates import CAMBODIA_TIMEZONE


def at(hour, minute, day=25):
    return datetime(2026, 11, day, hour, minute, tzinfo=CAMBODIA_TIMEZONE)


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


def test_closes_once_at_0730_when_idle():
    clock = Clock(at(7, 29))
    restart = DailyRestart(clock, lambda: True, started_at=at(18, 51, day=24))
    assert restart.due() is False
    clock.now = at(7, 30)
    assert restart.due() is True
    assert restart.due() is False  # only once


def test_waits_for_announcements_to_finish():
    clock = Clock(at(7, 30))
    busy = [True]
    restart = DailyRestart(clock, lambda: not busy[0], started_at=at(18, 0, day=24))
    assert restart.due() is False
    clock.now = at(7, 31)
    busy[0] = False
    assert restart.due() is True


def test_gives_up_for_the_day_if_still_busy_at_0800():
    clock = Clock(at(8, 0))
    restart = DailyRestart(clock, lambda: True, started_at=at(18, 0, day=24))
    assert restart.due() is False


def test_a_fresh_start_is_not_restarted_again():
    clock = Clock(at(7, 31))
    restart = DailyRestart(clock, lambda: True, started_at=at(7, 0))
    assert restart.due() is False  # started within the last hour (e.g. the watchdog just restarted it)
    clock.now = at(7, 31, day=26)
    assert restart.due() is True  # next morning


def test_never_outside_the_morning_window():
    clock = Clock(at(12, 0))
    restart = DailyRestart(clock, lambda: True, started_at=at(1, 0))
    for hour in (0, 6, 8, 12, 19, 23):
        clock.now = at(hour, 30)
        assert restart.due() is False
