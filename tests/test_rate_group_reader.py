import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from telethon.errors import SessionPasswordNeededError

from app.config import Settings
from app.rate_group_reader import (
    MAX_HISTORY_MESSAGES,
    TARGET_RATE_GROUP_ID,
    RateGroupReader,
    format_group_post,
    normalize_phone_number,
)


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


def test_phone_input_is_normalized_and_validated():
    assert normalize_phone_number(" +855 (12) 345-678 ") == "+85512345678"
    assert normalize_phone_number("012345678") is None


def test_login_uses_entered_phone_and_dedicated_session(tmp_path, monkeypatch):
    class LoginClient:
        instance = None

        def __init__(self, session, api_id, api_hash, **kwargs):
            self.session_path = session
            self.session = SimpleNamespace(save_entities=True)
            self.sent_phone = None
            self.sign_in_values = None
            LoginClient.instance = self

        async def connect(self):
            pass

        async def is_user_authorized(self):
            return False

        async def send_code_request(self, phone):
            self.sent_phone = phone
            return SimpleNamespace(phone_code_hash="one-time-hash")

        async def sign_in(self, **values):
            self.sign_in_values = values

    monkeypatch.setattr("app.rate_group_reader.TelegramClient", LoginClient)
    events = []
    responses = {"phone": "+855 (12) 345-678", "code": "12345"}

    def publish(name, value):
        events.append(name)
        if name == "rate_group_auth_request":
            value["responses"].put(responses[value["kind"]])

    reader = RateGroupReader(make_settings(tmp_path), publish)

    assert asyncio.run(reader._authenticate())
    assert LoginClient.instance.session_path == str(tmp_path / "rate_group_user.session")
    assert LoginClient.instance.session.save_entities is False
    assert LoginClient.instance.sent_phone == "+85512345678"
    assert LoginClient.instance.sign_in_values == {
        "phone": "+85512345678",
        "code": "12345",
        "phone_code_hash": "one-time-hash",
    }
    assert events == ["rate_group_auth_request", "rate_group_auth_request"]


def test_login_requests_two_step_password_only_when_telegram_requires_it(tmp_path, monkeypatch):
    class TwoStepClient:
        instance = None

        def __init__(self, *args, **kwargs):
            self.session = SimpleNamespace(save_entities=True)
            self.sign_ins = []
            TwoStepClient.instance = self

        async def connect(self):
            pass

        async def is_user_authorized(self):
            return False

        async def send_code_request(self, phone):
            return SimpleNamespace(phone_code_hash="one-time-hash")

        async def sign_in(self, **values):
            self.sign_ins.append(values)
            if "code" in values:
                raise SessionPasswordNeededError(request=None)

    monkeypatch.setattr("app.rate_group_reader.TelegramClient", TwoStepClient)
    responses = {"phone": "+85512345678", "code": "12345", "password": "private-password"}
    requested = []

    def publish(name, value):
        if name == "rate_group_auth_request":
            requested.append(value["kind"])
            value["responses"].put(responses[value["kind"]])

    reader = RateGroupReader(make_settings(tmp_path), publish)

    assert asyncio.run(reader._authenticate())
    assert requested == ["phone", "code", "password"]
    assert TwoStepClient.instance.sign_ins[-1] == {"password": "private-password"}


def test_group_post_format_preserves_message_text_verbatim():
    raw_text = "USD buy 4,100\nKHR sell 4,090"
    assert format_group_post("Dara", "16:10", raw_text) == f"[16:10] Dara: {raw_text}"


class FakeMessage:
    def __init__(self, message_id, text, photo=None, edit_date=None):
        self.id = message_id
        self.message = text
        self.photo = photo
        self.edit_date = edit_date
        self.date = datetime(2026, 11, 5, 9, 10, tzinfo=timezone.utc)

    async def get_sender(self):
        return SimpleNamespace(first_name="Dara", last_name="Sok")


class FakeReaderClient:
    def __init__(self, dialogs, messages):
        self.dialogs = dialogs
        self.messages = messages
        self.requested_entity = None
        self.requested_limit = None
        self.handlers = []
        self.connected = False

    async def iter_dialogs(self):
        for dialog in self.dialogs:
            yield dialog

    async def get_messages(self, entity, limit):
        self.requested_entity = entity
        self.requested_limit = limit
        return self.messages

    def add_event_handler(self, handler, event):
        self.handlers.append((handler, event))

    async def run_until_disconnected(self):
        pass

    def is_connected(self):
        return self.connected


def test_reader_fetches_history_only_for_fixed_group_and_emits_no_payment_events(tmp_path):
    target_entity = object()
    events = []
    reader = RateGroupReader(make_settings(tmp_path), lambda name, value: events.append((name, value)))
    client = FakeReaderClient(
        [
            SimpleNamespace(id=-100123, entity=object()),
            SimpleNamespace(id=TARGET_RATE_GROUP_ID, entity=target_entity),
            SimpleNamespace(id=-100456, entity=object()),
        ],
        [FakeMessage(8, "KHR sell 4,090"), FakeMessage(7, "USD buy 4,100")],
    )
    reader._client = client

    async def authenticated():
        return True

    reader._authenticate = authenticated
    asyncio.run(reader._run_async())

    assert client.requested_entity is target_entity
    assert client.requested_limit == MAX_HISTORY_MESSAGES == 50
    assert [type(event).__name__ for _, event in client.handlers] == [
        "NewMessage",
        "MessageEdited",
        "MessageDeleted",
    ]
    assert [name for name, _ in events] == [
        "rate_group_message",
        "rate_group_message",
        "rate_group_status",
        "rate_group_status",
    ]
    assert [value["text"] for name, value in events if name == "rate_group_message"] == [
        "USD buy 4,100",
        "KHR sell 4,090",
    ]
    assert all(name not in {"payment", "announcement_status"} for name, _ in events)
    assert events[2] == ("rate_group_status", "CONNECTED · PRIVATE GROUP")


def test_unavailable_group_is_reported_without_requesting_any_history(tmp_path):
    events = []
    reader = RateGroupReader(make_settings(tmp_path), lambda name, value: events.append((name, value)))
    client = FakeReaderClient([], [])
    reader._client = client

    async def authenticated():
        return True

    reader._authenticate = authenticated
    asyncio.run(reader._run_async())

    assert client.requested_entity is None
    assert events == [
        (
            "rate_group_status",
            "ERROR · GROUP NOT AVAILABLE TO THIS ACCOUNT · POSTS MAY BE OLD",
        )
    ]


def test_incoming_handler_rejects_messages_from_other_chats(tmp_path, monkeypatch):
    events = []
    reader = RateGroupReader(make_settings(tmp_path), lambda name, value: events.append((name, value)))
    handled = []

    async def publish_message(message):
        handled.append(message)

    monkeypatch.setattr(reader, "_publish_message", publish_message)

    async def run():
        await reader._handle_message(SimpleNamespace(chat_id=-100123, message="ignored"))
        await reader._handle_message(
            SimpleNamespace(chat_id=TARGET_RATE_GROUP_ID, message="target")
        )

    asyncio.run(run())
    assert handled == ["target"]
    assert events == []


def test_message_display_keeps_raw_text_and_uses_local_group_timestamp(tmp_path):
    events = []
    reader = RateGroupReader(make_settings(tmp_path), lambda name, value: events.append((name, value)))
    message = FakeMessage(9, "Posted exactly as typed\nsecond line")

    asyncio.run(reader._publish_message(message))

    assert events == [
        (
            "rate_group_message",
            {
                "id": 9,
                "sender": "Dara Sok",
                "posted_at": "16:10",
                "timestamp": "2026-11-05T09:10:00+00:00",
                "text": "Posted exactly as typed\nsecond line",
                "edited": False,
            },
        )
    ]


def test_photo_without_caption_uses_placeholder_and_captions_are_kept(tmp_path):
    events = []
    reader = RateGroupReader(make_settings(tmp_path), lambda name, value: events.append((name, value)))

    async def run():
        await reader._publish_message(FakeMessage(10, "", photo=object()))
        await reader._publish_message(FakeMessage(11, "ខ្មែរ AC ដូរ $ 4089", photo=object()))
        await reader._publish_message(FakeMessage(12, ""))

    asyncio.run(run())
    assert [value["text"] for _, value in events] == [
        "[photo — see Telegram]",
        "ខ្មែរ AC ដូរ $ 4089",
        "[non-text message]",
    ]


def test_edits_republish_target_group_posts_in_memory_only(tmp_path):
    events = []
    reader = RateGroupReader(make_settings(tmp_path), lambda name, value: events.append((name, value)))

    async def run():
        await reader._publish_message(FakeMessage(20, "ខ្មែរ AC ដូរ $ 4089"))
        await reader._publish_message(FakeMessage(20, "duplicate ignored"))
        await reader._handle_edit(SimpleNamespace(chat_id=-100123, message=FakeMessage(20, "other chat")))
        await reader._handle_edit(
            SimpleNamespace(chat_id=TARGET_RATE_GROUP_ID, message=FakeMessage(20, "ខ្មែរ AC ដូរ $ 4088"))
        )

    asyncio.run(run())
    assert [(value["text"], value["edited"]) for _, value in events] == [
        ("ខ្មែរ AC ដូរ $ 4089", False),
        ("ខ្មែរ AC ដូរ $ 4088", True),
    ]


def test_deletions_are_forwarded_only_for_the_target_group(tmp_path):
    events = []
    reader = RateGroupReader(make_settings(tmp_path), lambda name, value: events.append((name, value)))

    async def run():
        await reader._handle_delete(SimpleNamespace(chat_id=None, deleted_ids=[5]))
        await reader._handle_delete(SimpleNamespace(chat_id=-100123, deleted_ids=[6]))
        await reader._handle_delete(SimpleNamespace(chat_id=TARGET_RATE_GROUP_ID, deleted_ids=[7, 8]))

    asyncio.run(run())
    assert events == [("rate_group_message_deleted", {"ids": [7, 8]})]
