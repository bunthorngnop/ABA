"""Daily automatic close at 07:30 so ABA starts fresh every morning (owner-approved 2026-11-24).

ABA closes itself the normal way and the Windows watchdog task ("ABA Payment Speaker", every
minute) starts it again. It waits for the announcement being spoken (and any queued ones) to
finish, never closes in the first hour after a start (so a fresh start is not restarted again),
and gives up for the day if it has not been idle by 08:00.
"""

import logging
from datetime import datetime, time, timedelta
from typing import Callable, Optional

logger = logging.getLogger(__name__)

RESTART_AT = time(7, 30)  # Cambodia time, every day
RESTART_LATEST = time(8, 0)  # if announcements keep it busy until then, skip today
MIN_UPTIME = timedelta(hours=1)


class DailyRestart:
    def __init__(
        self,
        clock: Callable[[], datetime],
        is_idle: Callable[[], bool],
        started_at: Optional[datetime] = None,
    ):
        self.clock = clock
        self.is_idle = is_idle
        self.started_at = started_at or clock()
        self._requested = False

    def due(self) -> bool:
        """True once, at 07:30 or soon after, when nothing is being announced."""
        if self._requested:
            return False
        now = self.clock()
        if not (RESTART_AT <= now.time() < RESTART_LATEST):
            return False
        if now - self.started_at < MIN_UPTIME:
            return False
        if not self.is_idle():
            return False
        self._requested = True
        logger.info("Daily 07:30 restart: closing ABA; the watchdog task starts it again")
        return True
