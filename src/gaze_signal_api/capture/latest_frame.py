from __future__ import annotations

from queue import Empty, Full, Queue
from typing import Generic, TypeVar

T = TypeVar("T")


class LatestFrameBuffer(Generic[T]):
    """A one-item buffer that drops stale work instead of growing a queue."""

    def __init__(self) -> None:
        self._queue: Queue[T] = Queue(maxsize=1)
        self.dropped = 0

    def put(self, item: T) -> None:
        try:
            self._queue.put_nowait(item)
            return
        except Full:
            pass
        try:
            self._queue.get_nowait()
            self.dropped += 1
        except Empty:
            pass
        self._queue.put_nowait(item)

    def get(self, timeout: float | None = None) -> T:
        return self._queue.get(timeout=timeout)

    def empty(self) -> bool:
        return self._queue.empty()
