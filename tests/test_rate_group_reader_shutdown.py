"""Shutdown safety for the private-group reader.

The Telethon client and its SQLite session must only ever be used by the reader's own thread.
These tests call stop() from another thread while the reader is connecting, connected, and
disconnecting, and check that every client call happened on the reader thread and that the
session is disconnected exactly once.
"""

import asyncio
import logging
import threading
import time
from types import SimpleNamespace

import pytest

import main
from app.config import Settings
from app.rate_group_reader import TARGET_RATE_GROUP_ID, RateGroupReader

WAIT = 5


def make_settings(tmp_path):
    return Settings(
        12345,
        "a" * 32,
        "+85510000000",
        tmp_path / "payment_user.session",
        (),
        None,
        "PayWayByABA_bot",
        True,
        tmp_path / "state.sqlite3",
        "voice",
        "+0%",
        rate_group_session_path=tmp_path / "rate_group_user.session",
    )


class RecordingClient:
    """Fake Telethon client that records which thread made each call."""

    instance = None
    block_in = "run"  # "connect" or "run": where the reader waits until stopped
    fail_run = False  # end run_until_disconnected with an error instead of waiting
    disconnect_seconds = 0.0

    def __init__(self, *_args, **_kwargs):
        self.session = SimpleNamespace(save_entities=True)
        self.calls = []
        self.connected = False
        self.disconnects_started = 0
        self.disconnects_finished = 0
        self.reached = threading.Event()
        self.disconnecting = threading.Event()
        type(self).instance = self

    def _record(self, name):
        self.calls.append((name, threading.current_thread().name))

    async def connect(self):
        self._record("connect")
        self.connected = True
        if self.block_in == "connect":
            self.reached.set()
            await asyncio.Event().wait()

    async def is_user_authorized(self):
        self._record("is_user_authorized")
        return True

    async def iter_dialogs(self):
        self._record("iter_dialogs")
        yield SimpleNamespace(id=TARGET_RATE_GROUP_ID, entity="group")

    def add_event_handler(self, *_args):
        self._record("add_event_handler")

    async def get_messages(self, *_args, **_kwargs):
        self._record("get_messages")
        return []

    async def run_until_disconnected(self):
        self._record("run_until_disconnected")
        self._disconnected = asyncio.Event()
        self.reached.set()
        if self.fail_run:
            raise ConnectionError("simulated network drop")
        await self._disconnected.wait()

    def is_connected(self):
        self._record("is_connected")
        return self.connected

    def disconnect(self):
        # Like Telethon, the calling thread does work as soon as disconnect() is called, before
        # any coroutine is awaited, so a call from another thread is recorded as such.
        self._record("disconnect")
        return self._disconnect()

    async def _disconnect(self):
        self.disconnects_started += 1
        self.disconnecting.set()
        await asyncio.sleep(self.disconnect_seconds)
        self.connected = False
        self.disconnects_finished += 1
        disconnected = getattr(self, "_disconnected", None)
        if disconnected is not None:
            disconnected.set()


@pytest.fixture
def client_class(monkeypatch):
    class Client(RecordingClient):
        instance = None

    monkeypatch.setattr("app.rate_group_reader.TelegramClient", Client)
    return Client


def start_reader(tmp_path):
    statuses = []
    reader = RateGroupReader(
        make_settings(tmp_path),
        lambda name, value: statuses.append(value) if name == "rate_group_status" else None,
    )
    reader.start()
    return reader, statuses


def assert_only_reader_thread_used_client(client):
    assert client.calls
    assert {thread for _name, thread in client.calls} == {"telegram-rate-group-reader"}


def test_stop_while_connecting_ends_reader_on_its_own_thread(tmp_path, client_class):
    client_class.block_in = "connect"
    reader, statuses = start_reader(tmp_path)
    assert wait_for_client(client_class).reached.wait(WAIT)

    reader.stop()

    client = client_class.instance
    assert not reader._thread.is_alive()
    assert client.disconnects_finished == 1
    assert_only_reader_thread_used_client(client)
    assert statuses[-1].startswith("DISCONNECTED")


def test_stop_while_connected_disconnects_once_on_reader_thread(tmp_path, client_class):
    reader, statuses = start_reader(tmp_path)
    assert wait_for_client(client_class).reached.wait(WAIT)

    reader.stop()

    client = client_class.instance
    assert not reader._thread.is_alive()
    assert client.disconnects_started == client.disconnects_finished == 1
    assert_only_reader_thread_used_client(client)
    assert statuses[-1].startswith("DISCONNECTED")


def test_stop_during_disconnect_lets_the_disconnect_finish(tmp_path, client_class):
    client_class.fail_run = True
    client_class.disconnect_seconds = 0.3
    reader, statuses = start_reader(tmp_path)
    client = wait_for_client(client_class)
    assert client.disconnecting.wait(WAIT)

    reader.stop(wait=False)
    reader.stop()

    assert not reader._thread.is_alive()
    assert client.disconnects_started == client.disconnects_finished == 1
    assert_only_reader_thread_used_client(client)
    assert statuses[-1].startswith("ERROR · ConnectionError")


def test_dashboard_disconnect_does_not_block_and_reader_finishes(tmp_path, client_class):
    reader, _statuses = start_reader(tmp_path)
    assert wait_for_client(client_class).reached.wait(WAIT)

    started = time.monotonic()
    reader.stop(wait=False)  # the Dashboard DISCONNECT button path, on the Tk thread
    assert time.monotonic() - started < 1

    reader._thread.join(WAIT)
    client = client_class.instance
    assert not reader._thread.is_alive()
    assert client.disconnects_finished == 1
    assert_only_reader_thread_used_client(client)


def test_reader_can_reconnect_after_stop(tmp_path, client_class):
    reader, _statuses = start_reader(tmp_path)
    first = wait_for_client(client_class)
    assert first.reached.wait(WAIT)
    reader.stop()

    client_class.instance = None
    reader.start()
    second = wait_for_client(client_class)
    assert second is not first
    assert second.reached.wait(WAIT)
    reader.stop()
    assert not reader._thread.is_alive()


def test_stop_without_start_or_after_finish_is_harmless(tmp_path, client_class):
    reader = RateGroupReader(make_settings(tmp_path), lambda *_args: None)
    reader.stop()
    reader.stop(wait=False)


def wait_for_client(client_class):
    deadline = time.monotonic() + WAIT
    while client_class.instance is None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert client_class.instance is not None
    return client_class.instance


def test_cleanup_steps_all_run_when_one_fails(caplog):
    ran = []

    def failing():
        ran.append("failing")
        raise RuntimeError("cleanup failure")

    with caplog.at_level(logging.ERROR):
        main.run_cleanup_steps([
            ("first", lambda: ran.append("first")),
            ("failing", failing),
            ("skipped", None),
            ("last", lambda: ran.append("last")),
        ])

    assert ran == ["first", "failing", "last"]
    assert "Shutdown step failed: failing" in caplog.text
