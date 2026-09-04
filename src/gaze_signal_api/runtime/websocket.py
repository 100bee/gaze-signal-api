from __future__ import annotations

import asyncio
import threading
from collections import defaultdict
from contextlib import suppress
from dataclasses import dataclass
from uuid import UUID

from gaze_signal_api.schemas.analysis import AnalysisEvent


@dataclass(frozen=True)
class _Subscriber:
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[dict[str, object]]


class EventHub:
    """Thread-safe latest-event fan-out for WebSocket subscribers."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[_Subscriber]] = defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, session_id: UUID | str) -> asyncio.Queue[dict[str, object]]:
        queue: asyncio.Queue[dict[str, object]] = asyncio.Queue(maxsize=1)
        subscriber = _Subscriber(asyncio.get_running_loop(), queue)
        with self._lock:
            self._subscribers[str(session_id)].append(subscriber)
        return queue

    def unsubscribe(self, session_id: UUID | str, queue: asyncio.Queue[dict[str, object]]) -> None:
        key = str(session_id)
        with self._lock:
            self._subscribers[key] = [
                subscriber
                for subscriber in self._subscribers.get(key, [])
                if subscriber.queue is not queue
            ]
            if not self._subscribers[key]:
                self._subscribers.pop(key, None)

    def publish(self, event: AnalysisEvent) -> None:
        payload = event.model_dump(mode="json")
        dead: list[_Subscriber] = []
        with self._lock:
            subscribers = tuple(self._subscribers.get(str(event.session_id), ()))
        for subscriber in subscribers:
            try:
                subscriber.loop.call_soon_threadsafe(self._put_latest, subscriber.queue, payload)
            except RuntimeError:
                # The client event loop may close between snapshotting subscribers
                # and scheduling delivery. A stale WebSocket must not fail analysis.
                dead.append(subscriber)
        if dead:
            with self._lock:
                key = str(event.session_id)
                current = self._subscribers.get(key, [])
                self._subscribers[key] = [item for item in current if item not in dead]
                if not self._subscribers[key]:
                    self._subscribers.pop(key, None)

    @staticmethod
    def _put_latest(queue: asyncio.Queue[dict[str, object]], payload: dict[str, object]) -> None:
        if queue.full():
            with suppress(asyncio.QueueEmpty):
                queue.get_nowait()
        queue.put_nowait(payload)
