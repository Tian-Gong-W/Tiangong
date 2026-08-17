from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Condition
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class RuntimeEvent:
    cursor: int
    type: str
    timestamp: datetime
    data: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "cursor": self.cursor,
            "type": self.type,
            "timestamp": self.timestamp.isoformat(),
            "data": dict(self.data),
        }


class EventBus:
    """Thread-safe cursor event stream for local TONMEN runtime consumers."""

    def __init__(self, capacity: int = 2048) -> None:
        if capacity < 32 or capacity > 100_000:
            raise ValueError("event bus capacity must be between 32 and 100000")
        self.capacity = capacity
        self._events: deque[RuntimeEvent] = deque(maxlen=capacity)
        self._cursor = 0
        self._condition = Condition()

    @property
    def cursor(self) -> int:
        with self._condition:
            return self._cursor

    def publish(self, event_type: str, **data: Any) -> RuntimeEvent:
        event_type = str(event_type).strip()
        if not event_type:
            raise ValueError("event type cannot be empty")
        with self._condition:
            self._cursor += 1
            event = RuntimeEvent(
                cursor=self._cursor,
                type=event_type,
                timestamp=datetime.now(timezone.utc),
                data=dict(data),
            )
            self._events.append(event)
            self._condition.notify_all()
            return event

    def read_after(self, cursor: int = 0, *, limit: int = 200) -> list[RuntimeEvent]:
        cursor = max(0, int(cursor))
        limit = max(1, min(int(limit), 1000))
        with self._condition:
            return [event for event in self._events if event.cursor > cursor][:limit]

    def wait_after(
        self,
        cursor: int = 0,
        *,
        timeout: float = 20.0,
        limit: int = 200,
    ) -> list[RuntimeEvent]:
        cursor = max(0, int(cursor))
        timeout = max(0.0, min(float(timeout), 30.0))
        limit = max(1, min(int(limit), 1000))
        with self._condition:
            ready = [event for event in self._events if event.cursor > cursor][:limit]
            if ready or timeout == 0:
                return ready
            self._condition.wait_for(lambda: self._cursor > cursor, timeout=timeout)
            return [event for event in self._events if event.cursor > cursor][:limit]
