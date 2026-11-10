import asyncio
import logging
import queue
import re
import threading
from collections import deque
from datetime import timezone
from typing import Callable, Optional

from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError

from .config import Settings
from .exchange_rates import CAMBODIA_TIMEZONE
from .rate_post_format import NON_TEXT_PLACEHOLDER, PHOTO_PLACEHOLDER

logger = logging.getLogger(__name__)

TARGET_RATE_GROUP_ID = -1001563868468
MAX_HISTORY_MESSAGES = 50
MAX_DEDUPLICATED_MESSAGE_IDS = 200
_PHONE_NUMBER = re.compile(r"^\+[1-9][0-9]{6,14}$")
_API_HASH = re.compile(r"^[0-9a-fA-F]{32}$")


def normalize_phone_number(value: str) -> Optional[str]:
    phone = re.sub(r"[\s()-]", "", value)
    return phone if _PHONE_NUMBER.fullmatch(phone) else None


def format_group_post(sender: str, posted_at: str, text: str) -> str:
    return f"[{posted_at}] {sender}: {text}"


class LoginCancelledError(RuntimeError):
    pass


class TargetGroupUnavailableError(RuntimeError):
    pass


class RateGroupReader:
    """Read and display only the configured private group's posts."""

    def __init__(self, settings: Settings, state_callback: Callable[[str, object], None]):
        self.settings = settings
        self.state_callback = state_callback
        self._client: Optional[TelegramClient] = None
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop_requested = threading.Event()
        self._shown_ids: set[int] = set()
        self._shown_id_order: deque[int] = deque()

    def _request_login_value(self, kind: str, prompt: str) -> str:
        responses: "queue.Queue[Optional[str]]" = queue.Queue(maxsize=1)
        self.state_callback(
            "rate_group_auth_request",
            {"kind": kind, "prompt": prompt, "responses": responses},
        )
        value = responses.get()
        if value is None or not value.strip():
            raise LoginCancelledError(f"Telegram {kind} entry was cancelled")
        return value if kind == "password" else value.strip()

    async def _authenticate(self) -> bool:
        if (
            self.settings.telegram_api_id is None
            or self.settings.telegram_api_id <= 0
            or not _API_HASH.fullmatch(self.settings.telegram_api_hash)
        ):
            self.state_callback("rate_group_status", "ERROR · TELEGRAM API CREDENTIALS REQUIRED")
            return False

        session_path = self.settings.rate_group_session_path
        if session_path is None:
            session_path = self.settings.telegram_session_path.with_name("rate_group_user.session")
        session_path.parent.mkdir(parents=True, exist_ok=True)
        self._client = TelegramClient(
            str(session_path),
            self.settings.telegram_api_id,
            self.settings.telegram_api_hash,
            auto_reconnect=True,
            connection_retries=None,
            retry_delay=3,
        )
        self._client.session.save_entities = False
        await self._client.connect()
        if await self._client.is_user_authorized():
            return True

        phone_value = await asyncio.to_thread(
            self._request_login_value,
            "phone",
            "Enter the group member's Telegram phone number, including country code:",
        )
        phone = normalize_phone_number(phone_value)
        if phone is None:
            self.state_callback("rate_group_status", "ERROR · INVALID PHONE NUMBER")
            return False

        sent_code = await self._client.send_code_request(phone)
        code = await asyncio.to_thread(
            self._request_login_value,
            "code",
            "Enter the Telegram login code sent to the group member's account:",
        )
        try:
            await self._client.sign_in(
                phone=phone,
                code=code,
                phone_code_hash=sent_code.phone_code_hash,
            )
        except SessionPasswordNeededError:
            password = await asyncio.to_thread(
                self._request_login_value,
                "password",
                "Enter the Telegram two-step verification password:",
            )
            await self._client.sign_in(password=password)
        return True

    async def _find_target_group(self):
        client = self._client
        if client is None:
            raise RuntimeError("Telegram client is not initialized")
        async for dialog in client.iter_dialogs():
            if dialog.id == TARGET_RATE_GROUP_ID:
                return dialog.entity
        raise TargetGroupUnavailableError("The configured private group is not available to this account")

    async def _publish_message(self, message, edited: bool = False) -> None:
        message_id = int(message.id)
        if not edited:
            if message_id in self._shown_ids:
                return
            if len(self._shown_id_order) >= MAX_DEDUPLICATED_MESSAGE_IDS:
                self._shown_ids.discard(self._shown_id_order.popleft())
            self._shown_ids.add(message_id)
            self._shown_id_order.append(message_id)

        sender = await message.get_sender()
        sender_name = "Unknown sender"
        if sender is not None:
            sender_name = " ".join(
                part for part in (
                    getattr(sender, "first_name", None),
                    getattr(sender, "last_name", None),
                )
                if part
            ) or getattr(sender, "title", None) or sender_name
        posted_utc = message.date
        if posted_utc.tzinfo is None:
            posted_utc = posted_utc.replace(tzinfo=timezone.utc)
        posted_utc = posted_utc.astimezone(timezone.utc)
        posted_at = posted_utc.astimezone(CAMBODIA_TIMEZONE).strftime("%H:%M")
        text = message.message or (
            PHOTO_PLACEHOLDER if getattr(message, "photo", None) else NON_TEXT_PLACEHOLDER
        )
        self.state_callback(
            "rate_group_message",
            {
                "id": message_id,
                "sender": sender_name,
                "posted_at": posted_at,
                "timestamp": posted_utc.isoformat(),
                "text": text,
                "edited": bool(edited or getattr(message, "edit_date", None)),
            },
        )

    async def _handle_message(self, event) -> None:
        if event.chat_id != TARGET_RATE_GROUP_ID:
            return
        await self._publish_message(event.message)

    async def _handle_edit(self, event) -> None:
        if event.chat_id != TARGET_RATE_GROUP_ID:
            return
        await self._publish_message(event.message, edited=True)

    async def _handle_delete(self, event) -> None:
        if getattr(event, "chat_id", None) != TARGET_RATE_GROUP_ID:
            return
        deleted_ids = [int(message_id) for message_id in (event.deleted_ids or [])]
        if deleted_ids:
            self.state_callback("rate_group_message_deleted", {"ids": deleted_ids})

    async def _run_async(self) -> None:
        failed = False
        try:
            if not await self._authenticate():
                failed = True
                return
            if self._stop_requested.is_set():
                return

            client = self._client
            if client is None:
                raise RuntimeError("Telegram client is not initialized")
            group = await self._find_target_group()
            client.add_event_handler(
                self._handle_message,
                events.NewMessage(chats=group, incoming=True),
            )
            client.add_event_handler(self._handle_edit, events.MessageEdited(chats=group))
            client.add_event_handler(self._handle_delete, events.MessageDeleted(chats=group))
            history = await client.get_messages(group, limit=MAX_HISTORY_MESSAGES)
            for message in reversed(list(history)):
                await self._publish_message(message)
            self.state_callback("rate_group_status", "CONNECTED · PRIVATE GROUP")
            await client.run_until_disconnected()
        except TargetGroupUnavailableError:
            failed = True
            logger.warning("Rate-group reader could not find the configured group in this account")
            self.state_callback(
                "rate_group_status",
                "ERROR · GROUP NOT AVAILABLE TO THIS ACCOUNT · POSTS MAY BE OLD",
            )
        except LoginCancelledError:
            failed = True
            self.state_callback("rate_group_status", "LOGIN CANCELLED")
        except Exception as exc:
            failed = True
            logger.error("Rate-group reader stopped (%s)", type(exc).__name__)
            self.state_callback(
                "rate_group_status",
                f"ERROR · {type(exc).__name__} · POSTS MAY BE OLD",
            )
        finally:
            client = self._client
            if client and client.is_connected():
                await client.disconnect()
            if not failed:
                self.state_callback(
                    "rate_group_status",
                    "DISCONNECTED · POSTS MAY BE OLD · SESSION SAVED LOCALLY",
                )

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._run_async())
        finally:
            self._loop.close()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_requested.clear()
        self._shown_ids.clear()
        self._shown_id_order.clear()
        self.state_callback("rate_group_status", "CONNECTING")
        self._thread = threading.Thread(target=self._run, name="telegram-rate-group-reader", daemon=True)
        self._thread.start()

    def stop(self, wait: bool = True) -> None:
        self._stop_requested.set()
        if self._client and self._loop and self._loop.is_running() and self._client.is_connected():
            asyncio.run_coroutine_threadsafe(self._client.disconnect(), self._loop)
        if wait and self._thread:
            self._thread.join(timeout=15)
