import asyncio
from types import SimpleNamespace

import pytest
from telethon.errors import SessionRevokedError

from app import telegram_listener
from app.config import Settings
from app.system_alerts import (
    ALERT_DELAY_SECONDS,
    ALERT_REPEAT_SECONDS,
    ALERT_TEXTS,
    LOGIN,
    NETWORK,
    RECOVERED,
    PaymentHealthAlerts,
    alert_audio_path,
)


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def make(enabled=True):
    clock = Clock()
    played = []
    return PaymentHealthAlerts(played.append, enabled=enabled, clock=clock), clock, played


def test_alert_after_two_minutes_down_then_every_ten_minutes_then_recovered_once():
    alerts, clock, played = make()
    alerts.report(True)
    alerts.report(False, NETWORK)
    clock.t += ALERT_DELAY_SECONDS - 1
    assert alerts.check_once() is None
    clock.t += 1
    assert alerts.check_once() == NETWORK
    clock.t += ALERT_REPEAT_SECONDS - 1
    assert alerts.check_once() is None
    clock.t += 1
    assert alerts.check_once() == NETWORK
    alerts.report(True)
    alerts.report(True)
    assert played == [NETWORK, NETWORK, RECOVERED]


def test_short_drop_is_silent_and_no_recovery_message_without_an_alert():
    alerts, clock, played = make()
    alerts.report(True)
    alerts.report(False, NETWORK)
    clock.t += 60
    alerts.check_once()
    alerts.report(True)
    clock.t += 1000
    alerts.check_once()
    assert played == []


def test_no_healthy_report_after_startup_counts_as_down():
    alerts, clock, played = make()
    clock.t += ALERT_DELAY_SECONDS
    assert alerts.check_once() == NETWORK


def test_login_problem_has_its_own_message_and_is_not_overwritten_by_network():
    alerts, clock, played = make()
    alerts.report(True)
    alerts.report(False, LOGIN)
    alerts.report(False, NETWORK)
    clock.t += ALERT_DELAY_SECONDS
    assert alerts.check_once() == LOGIN


def test_disabled_outside_production_never_speaks():
    alerts, clock, played = make(enabled=False)
    clock.t += 10_000
    assert alerts.check_once() is None
    alerts.report(True)
    assert played == []


def test_alert_wording_and_offline_recordings_exist():
    assert ALERT_TEXTS[NETWORK] == "សូមជូនដំណឹង ប្រព័ន្ធទទួលប្រាក់ត្រូវបានផ្តាច់ សូមពិនិត្យអ៊ីនធឺណិត"
    assert ALERT_TEXTS[LOGIN] == "សូមចូល Telegram ឡើងវិញ"
    assert ALERT_TEXTS[RECOVERED] == "ប្រព័ន្ធទទួលប្រាក់បានភ្ជាប់ឡើងវិញ"
    for kind in (NETWORK, LOGIN, RECOVERED):
        path = alert_audio_path(kind)
        assert path is not None and path.stat().st_size > 1000


def _listener(reports):
    settings = Settings(1, "a" * 32, "+85510000000", None, (), None, "PayWayByABA_bot", True, None, "v", "+0%")
    return telegram_listener.TelegramListener(
        settings, None, lambda *a: None, lambda *a: None,
        health_callback=lambda healthy, reason: reports.append((healthy, reason)),
    )


@pytest.mark.parametrize("outcome, expected", [
    ("ok", (True, "ok")),
    (SessionRevokedError(request=None), (False, "login")),
    (OSError("offline"), (False, "network")),
    (asyncio.TimeoutError(), (False, "network")),
])
def test_health_loop_reports_ping_results(outcome, expected, monkeypatch):
    reports = []
    listener = _listener(reports)

    async def ping(request):
        if outcome != "ok":
            raise outcome
        return SimpleNamespace(ping_id=1)

    listener._client = ping

    async def stop_after_first(_seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr(telegram_listener.asyncio, "sleep", stop_after_first)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(listener._health_loop())
    assert reports == [expected]
