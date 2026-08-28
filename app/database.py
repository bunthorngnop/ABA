import hashlib
import sqlite3
import threading
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional

from .models import PaymentResult


class PaymentStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                event_key TEXT PRIMARY KEY,
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                update_id INTEGER,
                received_at TEXT NOT NULL,
                amount TEXT,
                currency TEXT,
                sender_name TEXT,
                bank TEXT,
                payment_channel TEXT,
                parser_status TEXT NOT NULL,
                announcement_status TEXT NOT NULL,
                review_reason TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_events_received ON events(received_at);
        """)
        self._connection.commit()

    @staticmethod
    def event_key(chat_id: int, message_id: int) -> str:
        return hashlib.sha256(f"telegram:{chat_id}:{message_id}".encode()).hexdigest()

    def reserve(self, chat_id: int, message_id: int, update_id: Optional[int], result: PaymentResult) -> Optional[str]:
        key = self.event_key(chat_id, message_id)
        with self._lock:
            cursor = self._connection.execute(
                """INSERT OR IGNORE INTO events
                (event_key, chat_id, message_id, update_id, received_at, amount, currency,
                 sender_name, bank, payment_channel, parser_status, announcement_status, review_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (key, chat_id, message_id, update_id, datetime.now(timezone.utc).isoformat(),
                 str(result.amount) if isinstance(result.amount, Decimal) else None, result.currency,
                 result.sender_name, result.bank, result.payment_channel, result.status.value,
                 "QUEUED" if result.valid_incoming_payment else "SILENT", result.reason_if_rejected),
            )
            self._connection.commit()
            return key if cursor.rowcount == 1 else None

    def set_announcement_status(self, key: str, status: str) -> None:
        with self._lock:
            self._connection.execute("UPDATE events SET announcement_status=? WHERE event_key=?", (status, key))
            self._connection.commit()

    def announced_today(self) -> int:
        row = self._connection.execute(
            """SELECT COUNT(*) AS n FROM events
               WHERE date(received_at, 'localtime') = date('now', 'localtime')
                 AND announcement_status='SPOKEN'"""
        ).fetchone()
        return int(row["n"])

    def close(self) -> None:
        with self._lock:
            self._connection.close()
