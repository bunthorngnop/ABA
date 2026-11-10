import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Callable

from .khmer_numbers import khmer_digits

CAMBODIA_TIMEZONE = timezone(timedelta(hours=7), "ICT")
REGULAR_ANNOUNCEMENT_TIMES = ((16, 10), (18, 10))
THURSDAY_ANNOUNCEMENT_TIMES = ((16, 5), (18, 5))
# Hourly "នៅពេលនេះម៉ោង …" announcements, every day on the hour from 08:00 to 22:00.
HOURLY_ANNOUNCEMENT_HOURS = tuple(range(8, 23))
HOURLY_LATE_LIMIT_SECONDS = 60
logger = logging.getLogger(__name__)


def hourly_slot(now: datetime) -> str | None:
    local_now = _as_cambodia_datetime(now)
    if local_now.second != 0 or local_now.minute != 0 or local_now.hour not in HOURLY_ANNOUNCEMENT_HOURS:
        return None
    return f"{local_now.hour:02d}:00"


def hourly_period(hour: int) -> str:
    if hour < 12:
        return "ព្រឹក"
    if hour == 12:
        return "ថ្ងៃត្រង់"
    if hour <= 17:
        return "រសៀល"
    if hour == 18:
        return "ល្ងាច"
    return "យប់"


def hourly_announcement_text(hour: int) -> str:
    """Owner-approved wording, without a final ។, e.g. "នៅពេលនេះម៉ោង ៨ ព្រឹក"."""
    spoken_hour = hour if hour <= 12 else hour - 12
    return f"នៅពេលនេះម៉ោង {khmer_digits(spoken_hour)} {hourly_period(hour)}"


def scheduled_slot(now: datetime) -> str | None:
    local_now = _as_cambodia_datetime(now)
    if local_now.second != 0:
        return None
    times = THURSDAY_ANNOUNCEMENT_TIMES if local_now.weekday() == 3 else REGULAR_ANNOUNCEMENT_TIMES
    if (local_now.hour, local_now.minute) not in times:
        return None
    return f"{local_now.hour:02d}:{local_now.minute:02d}"


def time_announcement_text(now: datetime) -> str:
    local_now = _as_cambodia_datetime(now)
    hour = local_now.hour % 12 or 12
    period = "ព្រឹក" if local_now.hour < 12 else "រសៀល" if local_now.hour < 18 else "ល្ងាច"
    spoken_time = f"ម៉ោង {khmer_digits(hour)} និង {khmer_digits(local_now.minute)} នាទី {period}។"
    if local_now.weekday() == 3:
        return f"ថ្ងៃនេះជាថ្ងៃព្រហស្បតិ៍។ ឥឡូវ {spoken_time}"
    return spoken_time


def _as_cambodia_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=CAMBODIA_TIMEZONE)
    return value.astimezone(CAMBODIA_TIMEZONE)


class ScheduledTimeAnnouncementService:
    def __init__(
        self,
        claim_slot: Callable[[str, str], bool],
        enqueue: Callable[[str], None],
        clock: Callable[[], datetime] = lambda: datetime.now(CAMBODIA_TIMEZONE),
        interval: float = 0.25,
        enqueue_hourly: Callable[[str], None] | None = None,
    ):
        self.claim_slot = claim_slot
        self.enqueue = enqueue
        self.enqueue_hourly = enqueue_hourly or enqueue
        self.clock = clock
        self.interval = interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="scheduled-announcements", daemon=True)
        self._last_attempted_slot: str | None = None

    def check_once(self, now: datetime | None = None) -> bool:
        current = _as_cambodia_datetime(now or self.clock())
        hourly = hourly_slot(current)
        slot = scheduled_slot(current) or hourly
        if slot is None:
            return False
        key = f"{current.date().isoformat()}:{slot}"
        if key == self._last_attempted_slot:
            return False
        if not self.claim_slot(current.date().isoformat(), slot):
            self._last_attempted_slot = key
            return False
        self._last_attempted_slot = key
        if hourly is not None and slot == hourly:
            self.enqueue_hourly(hourly_announcement_text(current.hour))
        else:
            self.enqueue(time_announcement_text(current))
        logger.info("Scheduled time announcement queued for %s %s", current.date(), slot)
        return True

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.check_once()
            except Exception:
                logger.exception("Could not queue scheduled time announcement")
            if self._stop.wait(self.interval):
                break

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2)
