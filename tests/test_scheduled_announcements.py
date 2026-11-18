from datetime import datetime

from app.scheduled_announcements import (
    CAMBODIA_TIMEZONE,
    ScheduledTimeAnnouncementService,
    scheduled_slot,
    time_announcement_text,
)


def at(year, month, day, hour, minute, second=0):
    return datetime(year, month, day, hour, minute, second, tzinfo=CAMBODIA_TIMEZONE)


def test_regular_days_use_1610_and_1810_slots():
    assert scheduled_slot(at(2026, 11, 4, 16, 10)) == "16:10"
    assert scheduled_slot(at(2026, 11, 4, 18, 10)) == "18:10"
    assert scheduled_slot(at(2026, 11, 4, 16, 5)) is None
    assert scheduled_slot(at(2026, 11, 4, 16, 11)) is None
    assert scheduled_slot(at(2026, 11, 4, 16, 10, 1)) is None


def test_thursday_uses_1605_and_1805_slots():
    assert scheduled_slot(at(2026, 11, 5, 16, 5)) == "16:05"
    assert scheduled_slot(at(2026, 11, 5, 18, 5)) == "18:05"
    assert scheduled_slot(at(2026, 11, 5, 16, 10)) is None


def test_thursday_announcement_includes_day_then_time():
    assert time_announcement_text(at(2026, 11, 5, 16, 5)) == (
        "ថ្ងៃនេះជាថ្ងៃព្រហស្បតិ៍។ ឥឡូវ ម៉ោង ៤ និង ៥ នាទី រសៀល។"
    )
    assert time_announcement_text(at(2026, 11, 5, 18, 5)).endswith("ម៉ោង ៦ និង ៥ នាទី ល្ងាច។")


def test_regular_time_announcement_is_khmer_without_thursday_prefix():
    assert time_announcement_text(at(2026, 11, 4, 16, 10)) == "ម៉ោង ៤ និង ១០ នាទី រសៀល។"


def test_slot_is_claimed_and_queued_at_most_once():
    claimed = set()
    queued = []

    def claim(day, slot):
        key = (day, slot)
        if key in claimed:
            return False
        claimed.add(key)
        return True

    service = ScheduledTimeAnnouncementService(claim, queued.append)
    current = at(2026, 11, 4, 16, 10)

    assert service.check_once(current)
    assert not service.check_once(current)
    assert len(queued) == 1
    assert queued[0] == "ម៉ោង ៤ និង ១០ នាទី រសៀល។"


def test_missed_slot_is_skipped_instead_of_announced_late():
    claimed = []
    queued = []
    service = ScheduledTimeAnnouncementService(
        lambda day, slot: claimed.append((day, slot)) or True,
        queued.append,
    )

    assert not service.check_once(at(2026, 11, 4, 16, 11))
    assert not claimed
    assert not queued


# --- 2026-11-18: extra daily times, Tuesday/Thursday day prefix ----------------------------------

from datetime import datetime as _dt  # noqa: E402

from app.scheduled_announcements import (  # noqa: E402
    CAMBODIA_TIMEZONE as _ICT,
    DAILY_ANNOUNCEMENT_TIMES,
    scheduled_slot as _slot,
    time_announcement_text as _text,
)


def _on(day: int, hour: int, minute: int) -> _dt:
    # 2026-11-16 is a Monday; day 0..6 = Monday..Sunday.
    return _dt(2026, 11, 16 + day, hour, minute, tzinfo=_ICT)


def test_extra_daily_times_every_day_of_the_week():
    assert DAILY_ANNOUNCEMENT_TIMES == (
        (15, 50), (15, 55), (16, 15), (16, 20), (16, 25), (16, 27), (16, 28), (16, 29),
        (17, 50), (17, 55), (18, 15), (18, 20), (18, 25), (18, 27), (18, 28), (18, 29),
    )
    for day in range(7):
        for hour, minute in DAILY_ANNOUNCEMENT_TIMES:
            assert _slot(_on(day, hour, minute)) == f"{hour:02d}:{minute:02d}"
    assert _slot(_on(0, 16, 30)) is None and _slot(_on(0, 18, 30)) is None


def test_existing_times_are_kept_alongside():
    assert _slot(_on(0, 16, 10)) == "16:10" and _slot(_on(0, 18, 10)) == "18:10"
    assert _slot(_on(3, 16, 5)) == "16:05" and _slot(_on(3, 16, 10)) is None


def test_day_is_said_first_only_at_the_agreed_times():
    assert _text(_on(1, 15, 55)) == "ថ្ងៃនេះជាថ្ងៃអង្គារ។ ឥឡូវ ម៉ោង ៣ និង ៥៥ នាទី រសៀល។"
    assert _text(_on(3, 17, 55)) == "ថ្ងៃនេះជាថ្ងៃព្រហស្បតិ៍។ ឥឡូវ ម៉ោង ៥ និង ៥៥ នាទី រសៀល។"
    assert _text(_on(3, 16, 5)).startswith("ថ្ងៃនេះជាថ្ងៃព្រហស្បតិ៍។")
    assert _text(_on(3, 16, 27)) == "ម៉ោង ៤ និង ២៧ នាទី រសៀល។"  # other Thursday times: time only
    assert _text(_on(1, 18, 29)) == "ម៉ោង ៦ និង ២៩ នាទី ល្ងាច។"
    assert _text(_on(0, 15, 55)) == "ម៉ោង ៣ និង ៥៥ នាទី រសៀល។"  # Monday: no day
