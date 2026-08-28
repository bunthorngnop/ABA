import asyncio
from pathlib import Path
from types import SimpleNamespace

from telethon.errors import SessionPasswordNeededError

from app.config import Settings
from app.telegram_listener import TelegramListener


def settings(tmp_path):
    return Settings(12345, "a" * 32, "+85510000000", tmp_path / "telegram_user.session",
                    (), None, "PayWayByABA_bot", True, tmp_path / "state.sqlite3", "voice", "+0%")


class FakeClient:
    authorized = False
    require_password = False
    instance = None

    def __init__(self, *args, **kwargs):
        self.session = SimpleNamespace(save_entities=True)
        self.sign_ins = []
        FakeClient.instance = self

    async def connect(self): pass
    async def is_user_authorized(self): return self.authorized
    async def send_code_request(self, phone): return SimpleNamespace(phone_code_hash="code-hash")
    async def sign_in(self, **values):
        self.sign_ins.append(values)
        if self.require_password and "code" in values:
            raise SessionPasswordNeededError(request=None)
    async def get_me(self): return SimpleNamespace(id=166792174, first_name="Operator")


def test_first_login_requests_code_and_disables_entity_caching(tmp_path, monkeypatch):
    events = []
    monkeypatch.setattr("app.telegram_listener.TelegramClient", FakeClient)
    listener = TelegramListener(settings(tmp_path), object(), lambda text, key: None,
                                lambda event, value: events.append((event, value)))
    monkeypatch.setattr(listener, "_request_login_value", lambda kind, prompt: "12345")
    assert asyncio.run(listener._authenticate())
    client = FakeClient.instance
    assert client.session.save_entities is False
    assert client.sign_ins == [{"phone": "+85510000000", "code": "12345", "phone_code_hash": "code-hash"}]
    assert ("setup", "Verification code required") in events
    assert ("setup", "Session authenticated") in events


def test_existing_session_reuses_authorization_without_requesting_code(tmp_path, monkeypatch):
    events = []
    FakeClient.authorized = True
    monkeypatch.setattr("app.telegram_listener.TelegramClient", FakeClient)
    listener = TelegramListener(settings(tmp_path), object(), lambda text, key: None,
                                lambda event, value: events.append((event, value)))
    monkeypatch.setattr(listener, "_request_login_value", lambda kind, prompt: (_ for _ in ()).throw(AssertionError()))
    try:
        assert asyncio.run(listener._authenticate())
        assert FakeClient.instance.sign_ins == []
        assert ("setup", "Session authenticated") in events
    finally:
        FakeClient.authorized = False


def test_two_step_password_is_requested_only_after_telegram_requires_it(tmp_path, monkeypatch):
    events = []
    FakeClient.require_password = True
    monkeypatch.setattr("app.telegram_listener.TelegramClient", FakeClient)
    listener = TelegramListener(settings(tmp_path), object(), lambda text, key: None,
                                lambda event, value: events.append((event, value)))
    values = iter(("12345", "private-password"))
    monkeypatch.setattr(listener, "_request_login_value", lambda kind, prompt: next(values))
    try:
        assert asyncio.run(listener._authenticate())
        assert FakeClient.instance.sign_ins[-1] == {"password": "private-password"}
        assert ("setup", "Two-step verification password required") in events
    finally:
        FakeClient.require_password = False
