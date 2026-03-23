import time
from threading import Lock

VALID_TRANSITIONS = {
    "requested": ["dialing", "failed"],
    "dialing": ["ringing", "failed"],
    "ringing": ["answered", "completed", "failed"],
    "answered": ["voicemail", "ivr_nav", "human", "completed", "failed"],
    "voicemail": ["leaving_msg", "failed"],
    "leaving_msg": ["completed", "failed"],
    "ivr_nav": ["navigating", "voicemail", "human", "completed", "failed"],
    "navigating": ["ivr_nav", "voicemail", "human", "completed", "failed"],
    "human": ["transferring", "completed", "failed"],
    "transferring": ["completed", "failed"],
    "completed": [],
    "failed": [],
    "canceled": [],
}

class InvalidTransition(Exception):
    pass

class CallEvent:
    def __init__(self, event_id: int, event: str, data: dict):
        self.event_id = event_id
        self.event = event
        self.data = data
        self.ts = time.time()

    def to_dict(self) -> dict:
        return {"id": self.event_id, "event": self.event, "ts": self.ts, **self.data}

class CallState:
    def __init__(self):
        self.state = "requested"
        self.reason = None
        self.duration = None
        self.history = ["requested"]
        self._events: list[CallEvent] = []
        self._event_counter = 0
        self._lock = Lock()

    def transition(self, new_state: str, reason: str = None, duration: float = None):
        if new_state not in VALID_TRANSITIONS.get(self.state, []):
            raise InvalidTransition(f"Cannot go from '{self.state}' to '{new_state}'")
        self.state = new_state
        self.history.append(new_state)
        if reason:
            self.reason = reason
        if duration is not None:
            self.duration = duration
        self.add_event("state_change", {"state": new_state, "reason": reason})

    def is_terminal(self) -> bool:
        return self.state in ("completed", "failed", "canceled")

    def add_event(self, event: str, data: dict = None):
        with self._lock:
            self._event_counter += 1
            self._events.append(CallEvent(self._event_counter, event, data or {}))

    def get_events(self, after: int = 0) -> list[dict]:
        with self._lock:
            return [e.to_dict() for e in self._events if e.event_id > after]

    def state_history_str(self) -> str:
        return " → ".join(self.history)
