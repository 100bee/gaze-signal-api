from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, update

from gaze_signal_api.errors import NotFoundError
from gaze_signal_api.schemas.analysis import AnalysisEvent, StateTransition
from gaze_signal_api.schemas.calibration import (
    CalibrationCreate,
    CalibrationParameters,
    CalibrationRead,
)
from gaze_signal_api.schemas.common import SessionStatus, utc_now
from gaze_signal_api.schemas.session import SessionCreate, SessionRead
from gaze_signal_api.storage.database import Database
from gaze_signal_api.storage.models import (
    AnalysisEventRow,
    CalibrationRow,
    SessionRow,
    StateTransitionRow,
)


class Repository:
    """Small synchronous persistence boundary for the local SQLite database."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def create_session(self, payload: SessionCreate) -> SessionRead:
        row = SessionRow(
            id=str(uuid4()),
            status=SessionStatus.CREATED.value,
            **payload.model_dump(mode="json"),
        )
        with self.database.session_factory.begin() as db:
            db.add(row)
        return self._session_read(row)

    def get_session(self, session_id: UUID | str) -> SessionRead:
        with self.database.session_factory() as db:
            row = db.get(SessionRow, str(session_id))
            if row is None:
                raise NotFoundError("session not found")
            return self._session_read(row)

    def list_sessions(self, limit: int, offset: int) -> tuple[list[SessionRead], int]:
        with self.database.session_factory() as db:
            total = db.scalar(select(func.count()).select_from(SessionRow)) or 0
            rows = db.scalars(
                select(SessionRow)
                .order_by(SessionRow.created_at.desc())
                .limit(limit)
                .offset(offset)
            ).all()
            return [self._session_read(row) for row in rows], total

    def set_session_status(
        self,
        session_id: UUID | str,
        status: SessionStatus,
        *,
        failure_code: str | None = None,
        at: datetime | None = None,
    ) -> SessionRead:
        changed_at = at or utc_now()
        with self.database.session_factory.begin() as db:
            row = db.get(SessionRow, str(session_id))
            if row is None:
                raise NotFoundError("session not found")
            row.status = status.value
            row.failure_code = failure_code
            if status == SessionStatus.RUNNING:
                row.started_at = changed_at
                row.stopped_at = None
            elif status in {SessionStatus.STOPPED, SessionStatus.FAILED}:
                row.stopped_at = changed_at
            db.flush()
            result = self._session_read(row)
        return result

    def delete_session(self, session_id: UUID | str) -> None:
        with self.database.session_factory.begin() as db:
            result = db.execute(delete(SessionRow).where(SessionRow.id == str(session_id)))
            if result.rowcount == 0:
                raise NotFoundError("session not found")

    def fail_stale_running_sessions(self) -> int:
        """Recover database state after an unclean process exit."""

        # End at the last stored event, not at restart time, or the summary counts the downtime.
        last_event_at = (
            select(func.max(AnalysisEventRow.timestamp))
            .where(AnalysisEventRow.session_id == SessionRow.id)
            .scalar_subquery()
        )
        with self.database.session_factory.begin() as db:
            result = db.execute(
                update(SessionRow)
                .where(SessionRow.status == SessionStatus.RUNNING.value)
                .values(
                    status=SessionStatus.FAILED.value,
                    stopped_at=func.coalesce(last_event_at, SessionRow.started_at),
                    failure_code="server_restarted",
                )
            )
            return int(result.rowcount or 0)

    def add_events(self, events: Sequence[AnalysisEvent]) -> None:
        if not events:
            return
        rows = []
        for item in events:
            values = item.model_dump(mode="python")
            values["session_id"] = str(item.session_id)
            values["gaze_zone"] = item.gaze_zone.value
            values["state"] = item.state.value
            rows.append(AnalysisEventRow(**values))
        with self.database.session_factory.begin() as db:
            db.add_all(rows)

    def add_transition(self, transition: StateTransition) -> None:
        values = transition.model_dump(mode="python")
        values["session_id"] = str(transition.session_id)
        values["from_state"] = transition.from_state.value
        values["to_state"] = transition.to_state.value
        row = StateTransitionRow(**values)
        with self.database.session_factory.begin() as db:
            db.add(row)

    def list_events(
        self, session_id: UUID | str, limit: int, offset: int
    ) -> tuple[list[AnalysisEvent], int]:
        self.get_session(session_id)
        with self.database.session_factory() as db:
            condition = AnalysisEventRow.session_id == str(session_id)
            total = (
                db.scalar(select(func.count()).select_from(AnalysisEventRow).where(condition)) or 0
            )
            rows = db.scalars(
                select(AnalysisEventRow)
                .where(condition)
                .order_by(AnalysisEventRow.timestamp.asc())
                .limit(limit)
                .offset(offset)
            ).all()
            return [self._event_read(row) for row in rows], total

    def all_events(self, session_id: UUID | str) -> list[AnalysisEvent]:
        with self.database.session_factory() as db:
            rows = db.scalars(
                select(AnalysisEventRow)
                .where(AnalysisEventRow.session_id == str(session_id))
                .order_by(AnalysisEventRow.timestamp.asc())
            ).all()
            return [self._event_read(row) for row in rows]

    def create_calibration(
        self, payload: CalibrationCreate, parameters: CalibrationParameters
    ) -> CalibrationRead:
        row = CalibrationRow(
            id=str(uuid4()),
            label=payload.label,
            pattern_points=payload.pattern_points,
            camera_index=payload.camera_index,
            camera_width=payload.camera_width,
            camera_height=payload.camera_height,
            screen_width=payload.screen_width,
            screen_height=payload.screen_height,
            parameters_json=json.dumps(parameters.model_dump(mode="json"), separators=(",", ":")),
            sample_count=len(payload.samples),
        )
        with self.database.session_factory.begin() as db:
            db.add(row)
        return self._calibration_read(row)

    def get_calibration(self, calibration_id: UUID | str) -> CalibrationRead:
        with self.database.session_factory() as db:
            row = db.get(CalibrationRow, str(calibration_id))
            if row is None:
                raise NotFoundError("calibration not found")
            return self._calibration_read(row)

    def list_calibrations(self, limit: int, offset: int) -> tuple[list[CalibrationRead], int]:
        with self.database.session_factory() as db:
            total = db.scalar(select(func.count()).select_from(CalibrationRow)) or 0
            rows = db.scalars(
                select(CalibrationRow)
                .order_by(CalibrationRow.created_at.desc())
                .limit(limit)
                .offset(offset)
            ).all()
            return [self._calibration_read(row) for row in rows], total

    def delete_calibration(self, calibration_id: UUID | str) -> None:
        with self.database.session_factory.begin() as db:
            result = db.execute(
                delete(CalibrationRow).where(CalibrationRow.id == str(calibration_id))
            )
            if result.rowcount == 0:
                raise NotFoundError("calibration not found")

    @staticmethod
    def _as_utc(value: datetime | None) -> datetime | None:
        if value is None or value.tzinfo is not None:
            return value
        return value.replace(tzinfo=UTC)

    @classmethod
    def _session_read(cls, row: SessionRow) -> SessionRead:
        result = SessionRead.model_validate(row)
        return result.model_copy(
            update={
                "created_at": cls._as_utc(result.created_at),
                "started_at": cls._as_utc(result.started_at),
                "stopped_at": cls._as_utc(result.stopped_at),
            }
        )

    @classmethod
    def _event_read(cls, row: AnalysisEventRow) -> AnalysisEvent:
        result = AnalysisEvent.model_validate(row, from_attributes=True)
        return result.model_copy(update={"timestamp": cls._as_utc(result.timestamp)})

    @classmethod
    def _calibration_read(cls, row: CalibrationRow) -> CalibrationRead:
        result = CalibrationRead.model_validate(row)
        return result.model_copy(update={"created_at": cls._as_utc(result.created_at)})
