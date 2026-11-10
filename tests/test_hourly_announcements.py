from datetime import datetime

from app.scheduled_announcements import (
    CAMBODIA_TIMEZONE,
    HOURLY_ANNOUNCEMENT_HOURS,
    ScheduledTimeAnnouncementService,
    hourly_announcement_text,
    hourly_slot,
    scheduled_slot,
)


def at(hour, minute=0, second=0, day=4):
    return datetime(2026, 11, day, hour, minute, second, tzinfo=CAMBODIA_TIMEZONE)


def test_hourly_slots_run_every_hour_from_8_to_22_only_at_the_exact_hour():
    assert HOURLY_ANNOUNCEMENT_HOURS == tuple(range(8, 23))
    assert [hourly_slot(at(hour)) for hour in (8, 12, 18, 22)] == ["08:00", "12:00", "18:00", "22:00"]
    assert hourly_slot(at(7)) is None
    assert hourly_slot(at(23)) is None
    assert hourly_slot(at(8, 0, 1)) is None
    assert hourly_slot(at(8, 1)) is None


def test_owner_approved_hourly_wording_without_final_full_stop():
    expected = {
        8: "នៅពេលនេះម៉ោង ៨ ព្រឹក",
        11: "នៅពេលនេះម៉ោង ១១ ព្រឹក",
        12: "នៅពេលនេះម៉ោង ១២ ថ្ងៃត្រង់",
        13: "នៅពេលនេះម៉ោង ១ រសៀល",
        14: "នៅពេលនេះម៉ោង ២ រសៀល",
        17: "នៅពេលនេះម៉ោង ៥ រសៀល",
        18: "នៅពេលនេះម៉ោង ៦ ល្ងាច",
        19: "នៅពេលនេះម៉ោង ៧ យប់",
        22: "នៅពេលនេះម៉ោង ១០ យប់",
    }
    for hour, text in expected.items():
        assert hourly_announcement_text(hour) == text
        assert not text.endswith("។")


def test_hourly_and_existing_announcements_use_their_own_paths_once_per_slot():
    claimed = set()
    regular, hourly = [], []

    def claim(day, slot):
        if (day, slot) in claimed:
            return False
        claimed.add((day, slot))
        return True

    service = ScheduledTimeAnnouncementService(claim, regular.append, enqueue_hourly=hourly.append)
    assert service.check_once(at(16))
    assert not service.check_once(at(16))
    assert service.check_once(at(16, 10))
    assert hourly == ["នៅពេលនេះម៉ោង ៤ រសៀល"]
    assert regular == ["ម៉ោង ៤ និង ១០ នាទី រសៀល។"]
    assert scheduled_slot(at(16)) is None


def test_missed_hour_is_not_announced_later():
    hourly = []
    service = ScheduledTimeAnnouncementService(lambda day, slot: True, hourly.append, enqueue_hourly=hourly.append)
    assert not service.check_once(at(9, 0, 5))
    assert not service.check_once(at(9, 3))
    assert hourly == []
