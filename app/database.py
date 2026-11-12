import hashlib
import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from .models import PaymentResult
from .integration_contract import payment_event

if TYPE_CHECKING:
    from .exchange_rates import ExchangeRate

_CAMBODIA = timezone(timedelta(hours=7), "ICT")


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
            CREATE TABLE IF NOT EXISTS exchange_rate_cache (
                source TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                official_rate TEXT,
                buy_rate TEXT,
                sell_rate TEXT,
                effective_at TEXT NOT NULL,
                fetched_at TEXT,
                last_error TEXT
            );
            CREATE TABLE IF NOT EXISTS nbc_rate_history (
                rate_date TEXT PRIMARY KEY,
                official_rate TEXT NOT NULL,
                recorded_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS fuel_price_cache (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                payload TEXT NOT NULL,
                saved_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS scheduled_announcements (
                schedule_date TEXT NOT NULL,
                slot TEXT NOT NULL,
                claimed_at TEXT NOT NULL,
                PRIMARY KEY(schedule_date, slot)
            );
        """)
        columns = {row[1] for row in self._connection.execute("PRAGMA table_info(events)")}
        if "bank_mapping_status" not in columns:
            self._connection.execute("ALTER TABLE events ADD COLUMN bank_mapping_status TEXT NOT NULL DEFAULT 'UNMAPPED'")
        if "announced_at" not in columns:
            self._connection.execute("ALTER TABLE events ADD COLUMN announced_at TEXT")
        rate_columns = {row[1] for row in self._connection.execute("PRAGMA table_info(exchange_rate_cache)")}
        for column in ("previous_official_rate", "previous_buy_rate", "previous_sell_rate"):
            if column not in rate_columns:
                self._connection.execute(f"ALTER TABLE exchange_rate_cache ADD COLUMN {column} TEXT")
        self._connection.commit()

    def save_exchange_rate(self, rate: "ExchangeRate") -> None:
        with self._lock:
            self._connection.execute(
                """INSERT INTO exchange_rate_cache
                   (source, category, official_rate, buy_rate, sell_rate, effective_at, fetched_at, last_error)
                   VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                   ON CONFLICT(source) DO UPDATE SET
                       category=excluded.category,
                       previous_official_rate=CASE
                           WHEN exchange_rate_cache.official_rate IS NOT NULL
                                AND excluded.official_rate IS NOT NULL
                                AND CAST(exchange_rate_cache.official_rate AS REAL) != CAST(excluded.official_rate AS REAL)
                           THEN exchange_rate_cache.official_rate
                           ELSE exchange_rate_cache.previous_official_rate END,
                       previous_buy_rate=CASE
                           WHEN exchange_rate_cache.buy_rate IS NOT NULL
                                AND excluded.buy_rate IS NOT NULL
                                AND CAST(exchange_rate_cache.buy_rate AS REAL) != CAST(excluded.buy_rate AS REAL)
                           THEN exchange_rate_cache.buy_rate
                           ELSE exchange_rate_cache.previous_buy_rate END,
                       previous_sell_rate=CASE
                           WHEN exchange_rate_cache.sell_rate IS NOT NULL
                                AND excluded.sell_rate IS NOT NULL
                                AND CAST(exchange_rate_cache.sell_rate AS REAL) != CAST(excluded.sell_rate AS REAL)
                           THEN exchange_rate_cache.sell_rate
                           ELSE exchange_rate_cache.previous_sell_rate END,
                       official_rate=excluded.official_rate,
                       buy_rate=excluded.buy_rate,
                       sell_rate=excluded.sell_rate,
                       effective_at=excluded.effective_at,
                       fetched_at=excluded.fetched_at,
                       last_error=NULL""",
                (
                    rate.source,
                    rate.category,
                    str(rate.official_rate) if rate.official_rate is not None else None,
                    str(rate.buy_rate) if rate.buy_rate is not None else None,
                    str(rate.sell_rate) if rate.sell_rate is not None else None,
                    rate.effective_at,
                    rate.fetched_at.isoformat() if rate.fetched_at is not None else None,
                ),
            )
            if rate.source == "NBC" and rate.official_rate is not None and rate.fetched_at is not None:
                local_date = rate.fetched_at.astimezone(_CAMBODIA).date().isoformat() if rate.fetched_at.tzinfo else rate.fetched_at.date().isoformat()
                self._connection.execute(
                    """INSERT INTO nbc_rate_history(rate_date, official_rate, recorded_at) VALUES (?, ?, ?)
                       ON CONFLICT(rate_date) DO UPDATE SET
                           official_rate=excluded.official_rate, recorded_at=excluded.recorded_at""",
                    (local_date, str(rate.official_rate), datetime.now(timezone.utc).isoformat()),
                )
            self._connection.commit()

    def load_nbc_history(self, days: int = 7) -> list[Decimal]:
        """Return up to the last `days` daily NBC official rates, oldest first (public data only)."""
        with self._lock:
            rows = self._connection.execute(
                "SELECT official_rate FROM nbc_rate_history ORDER BY rate_date DESC LIMIT ?",
                (max(1, int(days)),),
            ).fetchall()
        return [Decimal(str(row["official_rate"])) for row in reversed(rows)]

    def clear_exchange_rate_error(self, source: str) -> None:
        with self._lock:
            self._connection.execute(
                "UPDATE exchange_rate_cache SET last_error=NULL WHERE source=?",
                (source,),
            )
            self._connection.commit()

    def mark_exchange_rate_error(self, source: str, category: str, error: str) -> None:
        with self._lock:
            self._connection.execute(
                """INSERT INTO exchange_rate_cache
                   (source, category, effective_at, last_error)
                   VALUES (?, ?, '', ?)
                   ON CONFLICT(source) DO UPDATE SET
                       category=excluded.category,
                       last_error=excluded.last_error""",
                (source, category, error),
            )
            self._connection.commit()

    def load_exchange_rates(self) -> list[dict[str, object]]:
        with self._lock:
            rows = self._connection.execute(
                """SELECT source, category, official_rate, buy_rate, sell_rate,
                          effective_at, fetched_at, last_error,
                          previous_official_rate, previous_buy_rate, previous_sell_rate
                   FROM exchange_rate_cache ORDER BY source"""
            ).fetchall()
        return [dict(row) for row in rows]

    def save_fuel_prices(self, prices: dict[str, object]) -> None:
        """Keep the latest Ministry fuel-price post (display only)."""
        payload = json.dumps(prices, ensure_ascii=False, sort_keys=True)
        with self._lock:
            self._connection.execute(
                """INSERT INTO fuel_price_cache(id, payload, saved_at) VALUES (1, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET payload=excluded.payload, saved_at=excluded.saved_at""",
                (payload, datetime.now(_CAMBODIA).isoformat()),
            )
            self._connection.commit()

    def load_fuel_prices(self) -> Optional[dict[str, object]]:
        with self._lock:
            row = self._connection.execute("SELECT payload FROM fuel_price_cache WHERE id = 1").fetchone()
        if row is None:
            return None
        try:
            value = json.loads(row["payload"])
        except (TypeError, ValueError):
            return None
        return value if isinstance(value, dict) else None

    def claim_scheduled_announcement(self, schedule_date: str, slot: str) -> bool:
        with self._lock:
            cursor = self._connection.execute(
                """INSERT OR IGNORE INTO scheduled_announcements(schedule_date, slot, claimed_at)
                   VALUES (?, ?, ?)""",
                (schedule_date, slot, datetime.now(timezone.utc).isoformat()),
            )
            self._connection.commit()
            return cursor.rowcount == 1

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
