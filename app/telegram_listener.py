import asyncio
import logging
import queue
import threading
from pathlib import Path
from typing import Callable, Optional

from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError

from .config import Settings, user_session_configuration_errors
from .database import PaymentStore
from .models import ParserStatus
from .payment_parser import build_announcement, parse_payment

logger = logging.getLogger(__name__)


def authorize_message(settings: Settings, chat_id: int, sender_id: Optional[int], username: Optional[str]) -> tuple[bool, str]:
    if settings.diagnostic_mode:
        return False, "diagnostic_mode_active"
    if chat_id not in settings.allowed_chat_ids:
        return False, "wrong_group"
    if settings.allowed_aba_sender_id is None:
        return False, "sender_id_not_configured"
    if sender_id != settings.allowed_aba_sender_id:
        return False, "unauthorized_sender"
    if not username or username.lstrip("@").lower() != settings.expected_aba_username.lower():
        return False, "sender_username_mismatch"
    return True, "authorized"


def group_is_in_scope(settings: Settings, chat_id: Optional[int], is_group: bool) -> bool:
    if not is_group or chat_id is None:
        return False
    if settings.allowed_chat_ids:
        return chat_id in settings.allowed_chat_ids
    return settings.diagnostic_mode


class TelegramListener:
    """Read-only Telegram user-session monitor using Telethon."""

    def __init__(self, settings: Settings, store: PaymentStore, announce: Callable[[str, str], None],
                 state_callback: Callable[[str, object], None]):
        self.settings = settings
        self.store = store
        self.announce = announce
        self.state_callback = state_callback
        self._client: Optional[TelegramClient] = None
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _request_login_value(self, kind: str, prompt: str) -> str:
        responses: "queue.Queue[Optional[str]]" = queue.Queue(maxsize=1)
        self.state_callback("auth_request", {"kind": kind, "prompt": prompt, "responses": responses})
        value = responses.get()
        if not value:
            raise RuntimeError(f"Telegram {kind} entry was cancelled")
        return value.strip()

    async def _authenticate(self) -> bool:
        if not self.settings.user_session_configured:
            errors = user_session_configuration_errors(self.settings)
            self.state_callback("setup", "API credentials missing or invalid: " + "; ".join(errors))
            self.state_callback("telegram", "Not configured")
            return False
        session_path = Path(self.settings.telegram_session_path)
        session_path.parent.mkdir(parents=True, exist_ok=True)
        self._client = TelegramClient(
            str(session_path), self.settings.telegram_api_id, self.settings.telegram_api_hash,
            auto_reconnect=True, connection_retries=None, retry_delay=3,
        )
        self._client.session.save_entities = False
        await self._client.connect()
        if not await self._client.is_user_authorized():
            self.state_callback("setup", "Login required")
            sent_code = await self._client.send_code_request(self.settings.telegram_phone)
            self.state_callback("setup", "Verification code required")
            code = await asyncio.to_thread(
                self._request_login_value, "code", "Enter the Telegram login code sent to your account:"
            )
            try:
                await self._client.sign_in(
                    phone=self.settings.telegram_phone, code=code,
                    phone_code_hash=sent_code.phone_code_hash,
                )
            except SessionPasswordNeededError:
                self.state_callback("setup", "Two-step verification password required")
                password = await asyncio.to_thread(
                    self._request_login_value, "password", "Enter your Telegram two-step verification password:"
                )
                await self._client.sign_in(password=password)
        me = await self._client.get_me()
        self.state_callback("setup", "Session authenticated")
        self.state_callback("telegram", f"Connected as {getattr(me, 'first_name', 'Telegram user')}")
        logger.info("Telegram user session authenticated user_id=%s", me.id)
        return True

    async def _handle(self, event) -> None:
        chat_id = event.chat_id
        if not group_is_in_scope(self.settings, chat_id, bool(event.is_group)):
            return
        chat = await event.get_chat()
        sender = await event.get_sender()
        sender_id = event.sender_id
        username = getattr(sender, "username", None) if sender else None
        username_matches = bool(username and username.lstrip("@").lower() == self.settings.expected_aba_username.lower())
        if self.settings.diagnostic_mode:
            self.state_callback("diagnostic", {
                "chat_id": chat_id, "chat_title": getattr(chat, "title", None) or "(untitled group)",
                "chat_type": "group", "sender_id": sender_id, "username": username,
                "message_type": "text" if event.raw_text else "non-text",
                "expected_username": self.settings.expected_aba_username,
                "expected_source_detected": username_matches,
            })
            self.state_callback("setup", "PayWay source detected" if username_matches else "Groups detected")
        if username_matches:
            self.state_callback("source", "Detected")
        authorized, reason = authorize_message(self.settings, chat_id, sender_id, username)
        if not authorized:
            logger.info("Message ignored reason=%s chat_id=%s sender_id=%s", reason, chat_id, sender_id)
            return
        text = event.raw_text
        if not text:
            logger.info("Authorized non-text message ignored")
            return
        result = parse_payment(text)
        key = self.store.reserve(chat_id, event.id, None, result)
        if key is None:
            logger.info("Duplicate Telegram message suppressed chat_id=%s message_id=%s", chat_id, event.id)
            return
        if result.status != ParserStatus.VALID or not result.valid_incoming_payment:
            logger.warning("Authorized message remained silent parser_status=%s reason=%s",
                           result.status.value, result.reason_if_rejected)
            self.state_callback("review", result.reason_if_rejected or "unknown")
            return
        announcement = build_announcement(result)
        self.state_callback("payment", {
            "amount": str(result.amount), "currency": result.currency, "payer": result.sender_name,
            "bank": result.bank or "—", "announcement": announcement,
        })
        self.announce(announcement, key)

    async def _run_async(self) -> None:
        try:
            if not await self._authenticate():
                return
            self._client.add_event_handler(self._handle, events.NewMessage(incoming=True))
            if self.settings.production_ready:
                self.state_callback("setup", "Production ready")
            await self._client.run_until_disconnected()
        except Exception as exc:
            logger.exception("Telegram user-session listener stopped: %s", type(exc).__name__)
            self.state_callback("telegram", "Error")
            self.state_callback("setup", f"Setup error: {type(exc).__name__}")
        finally:
            if self._client and self._client.is_connected():
                await self._client.disconnect()
            self.state_callback("telegram", "Disconnected")

    def run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._run_async())
        self._loop.close()

    def start(self) -> None:
        self._thread = threading.Thread(target=self.run, name="telegram-user-listener", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._client and self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._client.disconnect(), self._loop)
        if self._thread:
            self._thread.join(timeout=15)
