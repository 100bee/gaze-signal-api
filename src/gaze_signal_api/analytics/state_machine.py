from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from gaze_signal_api.schemas.analysis import FrameSignals, StateTransition
from gaze_signal_api.schemas.common import GazeZone, SignalState


@dataclass(slots=True)
class TemporalStateMachine:
    """Debounces observable signal states without inferring cognitive attention."""

    session_id: UUID
    confidence_threshold: float = 0.45
    debounce_ms: int = 350
    away_min_duration_ms: int = 1000
    state: SignalState = SignalState.UNKNOWN
    _pending_state: SignalState | None = None
    _pending_since: datetime | None = None

    def update(self, signal: FrameSignals) -> tuple[SignalState, StateTransition | None]:
        candidate = self._candidate(signal)
        if candidate == self.state:
            self._clear_pending()
            return self.state, None

        if candidate != self._pending_state:
            self._pending_state = candidate
            self._pending_since = signal.timestamp

        assert self._pending_since is not None
        required_ms = self.debounce_ms
        if candidate == SignalState.LOOKING_AWAY:
            required_ms = max(required_ms, self.away_min_duration_ms)
        if signal.timestamp - self._pending_since < timedelta(milliseconds=required_ms):
            return self.state, None

        previous = self.state
        self.state = candidate
        self._clear_pending()
        transition = StateTransition(
            session_id=self.session_id,
            timestamp=signal.timestamp,
            from_state=previous,
            to_state=self.state,
        )
        return self.state, transition

    def _candidate(self, signal: FrameSignals) -> SignalState:
        if not signal.face_analysis_available:
            return SignalState.UNKNOWN
        if not signal.face_present:
            return SignalState.FACE_MISSING
        if signal.confidence < self.confidence_threshold or signal.gaze_zone == GazeZone.UNKNOWN:
            return SignalState.UNKNOWN
        if signal.gaze_zone == GazeZone.AWAY:
            return SignalState.LOOKING_AWAY
        return SignalState.SCREEN_FACING

    def _clear_pending(self) -> None:
        self._pending_state = None
        self._pending_since = None
