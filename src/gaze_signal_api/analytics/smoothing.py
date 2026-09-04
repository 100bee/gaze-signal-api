from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field

from gaze_signal_api.schemas.common import GazeZone


@dataclass(slots=True)
class ExponentialMovingAverage:
    alpha: float
    value: float | None = None

    def __post_init__(self) -> None:
        if not 0.0 < self.alpha <= 1.0:
            raise ValueError("alpha must be in (0, 1]")

    def update(self, sample: float) -> float:
        if self.value is None:
            self.value = sample
        else:
            self.value = self.alpha * sample + (1.0 - self.alpha) * self.value
        return self.value

    def reset(self) -> None:
        self.value = None


@dataclass(slots=True)
class ZoneMajoritySmoother:
    window_size: int = 5
    _values: deque[GazeZone] = field(init=False)

    def __post_init__(self) -> None:
        if self.window_size < 1:
            raise ValueError("window_size must be positive")
        self._values = deque(maxlen=self.window_size)

    def update(self, zone: GazeZone) -> GazeZone:
        self._values.append(zone)
        counts = Counter(self._values)
        max_count = max(counts.values())
        winners = {candidate for candidate, count in counts.items() if count == max_count}
        # A tie resolves to the newest value, making the smoother deterministic.
        return next(value for value in reversed(self._values) if value in winners)

    def reset(self) -> None:
        self._values.clear()
