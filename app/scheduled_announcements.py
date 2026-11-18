import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Callable

from .khmer_numbers import khmer_digits

CAMBODIA_TIMEZONE = timezone(timedelta(hours=7), "ICT")
REGULAR_ANNOUNCEMENT_TIMES = ((16, 10), (18, 10))
THURSDAY_ANNOUNCEMENT_TIMES = ((16, 5), (18, 5))
# Added 2026-11-18, every day (kept alongside the times above).
DAILY_ANNOUNCEMENT_TIMES = (
    (15, 50), (15, 55), (16, 15), (16, 20), (16, 25), (16, 27), (16, 28), (16, 29),
    (17, 50), (17, 55), (18, 15), (18, 20), (18, 25), (18, 27), (18, 28), (18, 29),
)
# Times that start with "ថ្ងៃនេះជាថ្ងៃ…។": Thursday 16:05/18:05, and 15:55/17:55 on Tuesday and Thursday.
TUESDAY, THURSDAY = 1, 3
DAY_NAMES = {TUESDAY: "អង្គារ", THURSDAY: "ព្រហស្បតិ៍"}
DAY_PREFIX_TIMES = {
    TUESDAY: ((15, 55), (17, 55)),
    THURSDAY: ((16, 5), (18, 5), (15, 55), (17, 55)),
}
# Hourly "នៅពេលនេះម៉ោង …" announcements, every day on the hour from 08:00 until 00:00 (midnight).
HOURLY_ANNOUNCEMENT_HOURS = (*range(8, 24), 0)
HOURLY_LATE_LIMIT_SECONDS = 60
logger = logging.getLogger(__name__)


def hourly_slot(now: datetime) -> str | None:
    local_now = _as_cambodia_datetime(now)
    if local_now.second != 0 or local_now.minute != 0 or local_now.hour not in HOURLY_ANNOUNCEMENT_HOURS:
        return None
    return f"{local_now.hour:02d}:00"


def hourly_period(hour: int) -> str:
    if hour == 0:
        return "អធ្រាត្រ"
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
    spoken_hour = 12 if hour == 0 else hour if hour <= 12 else hour - 12
    return f"នៅពេលនេះម៉ោង {khmer_digits(spoken_hour)} {hourly_period(hour)}"


def scheduled_slot(now: datetime) -> str | None:
    local_now = _as_cambodia_datetime(now)
    if local_now.second != 0:
        return None
    times = THURSDAY_ANNOUNCEMENT_TIMES if local_now.weekday() == THURSDAY else REGULAR_ANNOUNCEMENT_TIMES
    if (local_now.hour, local_now.minute) not in (*times, *DAILY_ANNOUNCEMENT_TIMES):
        return None
    return f"{local_now.hour:02d}:{local_now.minute:02d}"


def time_announcement_text(now: datetime) -> str:
    local_now = _as_cambodia_datetime(now)
    hour = local_now.hour % 12 or 12
    period = "ព្រឹក" if local_now.hour < 12 else "រសៀល" if local_now.hour < 18 else "ល្ងាច"
    spoken_time = f"ម៉ោង {khmer_digits(hour)} និង {khmer_digits(local_now.minute)} នាទី {period}។"
    weekday = local_now.weekday()
    if (local_now.hour, local_now.minute) in DAY_PREFIX_TIMES.get(weekday, ()):
        return f"ថ្ងៃនេះជាថ្ងៃ{DAY_NAMES[weekday]}។ ឥឡូវ {spoken_time}"
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


def all_fixed_time_texts() -> list[str]:
    """Every time sentence the schedule can speak (for recording them once, in advance)."""
    texts: list[str] = [hourly_announcement_text(hour) for hour in HOURLY_ANNOUNCEMENT_HOURS]
    monday = datetime(2026, 11, 16, tzinfo=CAMBODIA_TIMEZONE)  # any Monday; weekday offsets below
    for day in range(7):
        times = THURSDAY_ANNOUNCEMENT_TIMES if day == THURSDAY else REGULAR_ANNOUNCEMENT_TIMES
        for hour, minute in (*times, *DAILY_ANNOUNCEMENT_TIMES):
            text = time_announcement_text((monday + timedelta(days=day)).replace(hour=hour, minute=minute))
            if text not in texts:
                texts.append(text)
    return texts
