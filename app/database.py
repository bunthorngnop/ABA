import hashlib
import sqlite3
import threading
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional

from .models import PaymentResult
from .integration_contract import payment_event


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
            CREATE TABLE IF NOT EXISTS integration_updates (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_key TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(event_key) REFERENCES events(event_key)
            );
        """)
        columns = {row[1] for row in self._connection.execute("PRAGMA table_info(events)")}
        if "bank_mapping_status" not in columns:
            self._connection.execute("ALTER TABLE events ADD COLUMN bank_mapping_status TEXT NOT NULL DEFAULT 'UNMAPPED'")
        if "announced_at" not in columns:
            self._connection.execute("ALTER TABLE events ADD COLUMN announced_at TEXT")
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
                 sender_name, bank, payment_channel, parser_status, announcement_status, review_reason,
                 bank_mapping_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (key, chat_id, message_id, update_id, datetime.now(timezone.utc).isoformat(),
                 str(result.amount) if isinstance(result.amount, Decimal) else None, result.currency,
                 result.sender_name, result.bank, result.payment_channel, result.status.value,
                 "QUEUED" if result.valid_incoming_payment else "SILENT", result.reason_if_rejected,
                 result.institution_status),
            )
            if cursor.rowcount == 1 and result.valid_incoming_payment:
                self._connection.execute(
                    "INSERT INTO integration_updates(event_key, updated_at) VALUES(?, ?)",
                    (key, datetime.now(timezone.utc).isoformat()),
                )
            self._connection.commit()
            return key if cursor.rowcount == 1 else None

    def set_announcement_status(self, key: str, status: str) -> None:
        with self._lock:
            announced_at = datetime.now(timezone.utc).isoformat() if status == "SPOKEN" else None
            cursor = self._connection.execute(
                "UPDATE events SET announcement_status=?, announced_at=COALESCE(?, announced_at) WHERE event_key=?",
                (status, announced_at, key),
            )
            if cursor.rowcount:
                row = self._connection.execute(
                    "SELECT parser_status FROM events WHERE event_key=?", (key,)
                ).fetchone()
                if row and row["parser_status"] == "VALID" and status in {"QUEUED", "SPOKEN", "FAILED"}:
                    self._connection.execute(
                        "INSERT INTO integration_updates(event_key, updated_at) VALUES(?, ?)",
                        (key, datetime.now(timezone.utc).isoformat()),
                    )
            self._connection.commit()

    def get_integration_events(self, after_cursor: str = "", limit: int = 50) -> tuple[list[dict], str]:
        if after_cursor:
            if not after_cursor.startswith("v1-") or not after_cursor[3:].isdigit():
                raise ValueError("Invalid cursor")
            after_sequence = int(after_cursor[3:])
        else:
            after_sequence = 0
        safe_limit = max(1, min(int(limit), 100))
        with self._lock:
            rows = self._connection.execute(
                """SELECT u.sequence, e.event_key, e.received_at, e.amount, e.currency,
                          e.sender_name, e.bank, e.bank_mapping_status,
                          e.announcement_status, e.announced_at
                   FROM integration_updates u
                   JOIN events e ON e.event_key=u.event_key
                   WHERE u.sequence > ? AND e.parser_status='VALID'
                   ORDER BY u.sequence ASC LIMIT ?""",
                (after_sequence, safe_limit),
            ).fetchall()
        events = [payment_event(dict(row)) for row in rows]
        last_sequence = int(rows[-1]["sequence"]) if rows else after_sequence
        return events, f"v1-{last_sequence}"

    def announced_today(self) -> int:
        row = self._connection.execute(
            """SELECT COUNT(*) AS n FROM events
               WHERE date(received_at, 'localtime') = date('now', 'localtime')
                 AND announcement_status='SPOKEN'"""
        ).fetchone()
        return int(row["n"])

    def today_summary(self) -> dict[str, object]:
        """Return local-day spoken-payment totals without combining currencies."""
        with self._lock:
            rows = self._connection.execute(
                """SELECT currency, COUNT(*) AS payment_count,
                          COALESCE(SUM(CAST(amount AS NUMERIC)), 0) AS total
                   FROM events
                   WHERE date(received_at, 'localtime') = date('now', 'localtime')
                     AND parser_status='VALID' AND announcement_status='SPOKEN'
                   GROUP BY currency"""
            ).fetchall()
        totals = {"count": 0, "KHR": "0", "USD": "0.00"}
        for row in rows:
            currency = row["currency"]
            if currency not in {"KHR", "USD"}:
                continue
            totals["count"] += int(row["payment_count"])
            totals[currency] = str(row["total"])
        return totals

    def recent_announced(self, limit: int = 5) -> list[dict[str, object]]:
        """Return privacy-safe fields for the latest successfully spoken payments."""
        safe_limit = max(1, min(int(limit), 20))
        with self._lock:
            rows = self._connection.execute(
                """SELECT event_key, amount, currency, sender_name, bank, received_at
                   FROM events
                   WHERE parser_status='VALID' AND announcement_status='SPOKEN'
                   ORDER BY received_at DESC LIMIT ?""",
                (safe_limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def announced_today_rows(self, limit: int = 1000) -> list[dict[str, object]]:
        """Return privacy-safe successfully spoken payments from the current local day."""
        safe_limit = max(1, min(int(limit), 1000))
        with self._lock:
            rows = self._connection.execute(
                """SELECT event_key, amount, currency, sender_name, bank, received_at
                   FROM events
                   WHERE date(received_at, 'localtime') = date('now', 'localtime')
                     AND parser_status='VALID' AND announcement_status='SPOKEN'
                   ORDER BY received_at DESC LIMIT ?""",
                (safe_limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def close(self) -> None:
        with self._lock:
            self._connection.close()
