from enum import Enum


class LocalAnnouncementState(str, Enum):
    QUEUED = "QUEUED"
    CLAIMED = "CLAIMED"
    SPOKEN = "SPOKEN"
    MUTED = "MUTED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


_ALLOWED_TRANSITIONS = {
    LocalAnnouncementState.QUEUED: frozenset({
        LocalAnnouncementState.CLAIMED,
        LocalAnnouncementState.MUTED,
        LocalAnnouncementState.EXPIRED,
    }),
    LocalAnnouncementState.CLAIMED: frozenset({
        LocalAnnouncementState.SPOKEN,
        LocalAnnouncementState.FAILED,
        LocalAnnouncementState.EXPIRED,
    }),
}


def transition_state(current: LocalAnnouncementState, target: LocalAnnouncementState) -> LocalAnnouncementState:
    if not isinstance(current, LocalAnnouncementState) or not isinstance(target, LocalAnnouncementState):
        raise TypeError("announcement states must use LocalAnnouncementState")
    if current == target:
        return current
    if target not in _ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise ValueError(f"invalid announcement state transition: {current.value} -> {target.value}")
    return target