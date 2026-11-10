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
