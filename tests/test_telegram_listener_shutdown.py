"""Shutdown safety for the payment listener (same rule as the rate-group reader).

The payment Telethon client and its SQLite session must only be used by the listener's own
thread. stop() is called from the main thread at shutdown; these tests check that every client
call still happened on the listener thread and that the session is disconnected exactly once.
Only shutdown is exercised: no payment messages are created or parsed.
"""

import asyncio
import threading
import time

from app.config import Settings
from app.telegram_listener import TelegramListener

WAIT = 5


def settings(tmp_path):
    return Settings(12345, "a" * 32, "+85510000000", tmp_path / "telegram_user.session",
                    (), None, "PayWayByABA_bot", True, tmp_path / "state.sqlite3", "voice", "+0%")


class RecordingClient:
    def __init__(self, disconnect_seconds=0.0):
        self.calls = []
        self.connected = True
        self.reached = threading.Event()
        self.disconnects_started = 0
        self.disconnects_finished = 0
        self.disconnect_seconds = disconnect_seconds

    def _record(self, name):
        self.calls.append((name, threading.current_thread().name))

    def add_event_handler(self, *_args):
        self._record("add_event_handler")

    async def __call__(self, _request):  # health ping
        self._record("ping")
        return True

    async def run_until_disconnected(self):
        self._record("run_until_disconnected")
        self._disconnected = asyncio.Event()
        self.reached.set()
        await self._disconnected.wait()

    def is_connected(self):
        self._record("is_connected")
        return self.connected

    def disconnect(self):
        # Like Telethon, work starts on the calling thread as soon as disconnect() is called.
        self._record("disconnect")
        return self._disconnect()

    async def _disconnect(self):
        self.disconnects_started += 1
        await asyncio.sleep(self.disconnect_seconds)
        self.connected = False
        self.disconnects_finished += 1
        if getattr(self, "_disconnected", None) is not None:
            self._disconnected.set()


def start_listener(tmp_path, monkeypatch, client):
    health = []
    states = []
    listener = TelegramListener(
        settings(tmp_path), store=None, announce=lambda *_args: None,
        state_callback=lambda name, value: states.append((name, value)),
        health_callback=lambda healthy, reason: health.append((healthy, reason)),
    )

    async def authenticate():
        listener._client = client
        return True

    monkeypatch.setattr(listener, "_authenticate", authenticate)
    listener.start()
    assert client.reached.wait(WAIT)
    return listener, states, health


def assert_listener_thread_only(client):
    assert {thread for _name, thread in client.calls} == {"telegram-user-listener"}


def test_stop_disconnects_once_on_the_listener_thread(tmp_path, monkeypatch):
    client = RecordingClient()
    listener, states, health = start_listener(tmp_path, monkeypatch, client)

    listener.stop()

    assert not listener._thread.is_alive()
    assert client.disconnects_started == client.disconnects_finished == 1
    assert_listener_thread_only(client)
    assert states[-1] == ("telegram", "Disconnected")
    assert (False, "network") not in health  # a deliberate stop is not reported as an outage


def test_second_stop_during_disconnect_lets_it_finish(tmp_path, monkeypatch):
    client = RecordingClient(disconnect_seconds=0.3)
    listener, _states, _health = start_listener(tmp_path, monkeypatch, client)

    stopper = threading.Thread(target=listener.stop)
    stopper.start()
    deadline = time.monotonic() + WAIT
    while client.disconnects_started == 0 and time.monotonic() < deadline:
        time.sleep(0.01)
    listener.stop()
    stopper.join(WAIT)

    assert not listener._thread.is_alive()
    assert client.disconnects_started == client.disconnects_finished == 1
    assert_listener_thread_only(client)


def test_stop_before_start_is_harmless(tmp_path):
    listener = TelegramListener(settings(tmp_path), None, lambda *_args: None, lambda *_args: None)
    listener.stop()
