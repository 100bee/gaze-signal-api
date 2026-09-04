from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from gaze_signal_api.schemas.analysis import AnalysisEvent
from gaze_signal_api.schemas.common import GazeZone, SignalState, utc_now
from gaze_signal_api.schemas.session import SessionRead, SessionSummary


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _safe_ratio(value: float, total: float) -> float:
    if total <= 0.0:
        return 0.0
    return min(1.0, max(0.0, value / total))


def calculate_summary(
    session: SessionRead,
    events: list[AnalysisEvent],
    *,
    now: datetime | None = None,
) -> SessionSummary:
    if session.started_at is None:
        start = _aware(session.created_at)
        end = start
    else:
        start = _aware(session.started_at)
        end = _aware(session.stopped_at or now or utc_now())
    if end < start:
        end = start
    duration = max(0.0, (end - start).total_seconds())

    state_seconds = dict.fromkeys(SignalState, 0.0)
    zone_seconds = dict.fromkeys(GazeZone, 0.0)
    phone_seconds = 0.0
    away_spans: list[float] = []
    current_away = 0.0

    ordered = sorted(events, key=lambda item: _aware(item.timestamp))
    cursor = start
    if ordered:
        first_time = min(end, max(start, _aware(ordered[0].timestamp)))
        leading = max(0.0, (first_time - cursor).total_seconds())
        state_seconds[SignalState.UNKNOWN] += leading
        zone_seconds[GazeZone.UNKNOWN] += leading
        cursor = first_time
    else:
        state_seconds[SignalState.UNKNOWN] = duration
        zone_seconds[GazeZone.UNKNOWN] = duration

    for index, event in enumerate(ordered):
        event_time = min(end, max(start, _aware(event.timestamp)))
        if event_time >= end:
            break
        next_time = end
        if index + 1 < len(ordered):
            next_time = min(end, max(event_time, _aware(ordered[index + 1].timestamp)))
        seconds = max(0.0, (next_time - event_time).total_seconds())
        state_seconds[event.state] += seconds
        zone_seconds[event.gaze_zone] += seconds
        if event.phone_visible:
            phone_seconds += seconds
        if event.state == SignalState.LOOKING_AWAY:
            current_away += seconds
        elif current_away > 0.0:
            away_spans.append(current_away)
            current_away = 0.0
        cursor = next_time
    if current_away > 0.0:
        away_spans.append(current_away)
    if cursor < end:
        trailing = (end - cursor).total_seconds()
        state_seconds[SignalState.UNKNOWN] += trailing
        zone_seconds[GazeZone.UNKNOWN] += trailing

    detected = state_seconds[SignalState.SCREEN_FACING] + state_seconds[SignalState.LOOKING_AWAY]
    total_away = sum(away_spans)
    latency = (
        sum(event.processing_latency_ms for event in ordered) / len(ordered) if ordered else 0.0
    )

    return SessionSummary(
        session_id=UUID(str(session.id)),
        session_duration_seconds=duration,
        detected_duration_seconds=detected,
        screen_facing_ratio=_safe_ratio(state_seconds[SignalState.SCREEN_FACING], duration),
        looking_away_ratio=_safe_ratio(state_seconds[SignalState.LOOKING_AWAY], duration),
        face_missing_ratio=_safe_ratio(state_seconds[SignalState.FACE_MISSING], duration),
        unknown_ratio=_safe_ratio(state_seconds[SignalState.UNKNOWN], duration),
        gaze_zone_distribution={
            zone: _safe_ratio(seconds, duration) for zone, seconds in zone_seconds.items()
        },
        away_event_count=len(away_spans),
        total_away_duration_seconds=total_away,
        longest_away_duration_seconds=max(away_spans, default=0.0),
        average_away_duration_seconds=total_away / len(away_spans) if away_spans else 0.0,
        phone_visible_duration_seconds=phone_seconds,
        blink_count=sum(1 for event in ordered if event.blink_detected),
        average_processing_latency_ms=latency,
        effective_fps=len(ordered) / duration if duration > 0.0 else 0.0,
    )
