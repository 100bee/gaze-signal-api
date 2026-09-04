from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from starlette.concurrency import run_in_threadpool

from gaze_signal_api.analytics.summary import calculate_summary
from gaze_signal_api.api.dependencies import get_repository, get_runtime
from gaze_signal_api.errors import ConflictError
from gaze_signal_api.runtime.manager import SessionRuntimeManager
from gaze_signal_api.schemas.analysis import EventPage
from gaze_signal_api.schemas.session import SessionCreate, SessionPage, SessionRead, SessionSummary
from gaze_signal_api.storage.repository import Repository

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post(
    "",
    response_model=SessionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an analysis session after recording the consent choice",
)
def create_session(
    payload: SessionCreate,
    repository: Annotated[Repository, Depends(get_repository)],
) -> SessionRead:
    if payload.calibration_id is not None:
        calibration = repository.get_calibration(payload.calibration_id)
        if (
            calibration.camera_index != payload.camera_index
            or calibration.camera_width != payload.frame_width
            or calibration.camera_height != payload.frame_height
            or calibration.screen_width != payload.screen_width
            or calibration.screen_height != payload.screen_height
        ):
            raise ConflictError("calibration geometry does not match the requested session")
    return repository.create_session(payload)


@router.get("", response_model=SessionPage, summary="List past sessions")
def list_sessions(
    repository: Annotated[Repository, Depends(get_repository)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SessionPage:
    items, total = repository.list_sessions(limit, offset)
    return SessionPage(items=items, total=total, limit=limit, offset=offset)


@router.get("/{session_id}", response_model=SessionRead, summary="Get session state")
def get_session(
    session_id: UUID,
    repository: Annotated[Repository, Depends(get_repository)],
) -> SessionRead:
    return repository.get_session(session_id)


@router.post("/{session_id}/start", response_model=SessionRead, summary="Start camera analysis")
async def start_session(
    session_id: UUID,
    runtime: Annotated[SessionRuntimeManager, Depends(get_runtime)],
) -> SessionRead:
    return await run_in_threadpool(runtime.start, session_id)


@router.post("/{session_id}/stop", response_model=SessionRead, summary="Stop and release camera")
async def stop_session(
    session_id: UUID,
    runtime: Annotated[SessionRuntimeManager, Depends(get_runtime)],
) -> SessionRead:
    return await run_in_threadpool(runtime.stop, session_id)


@router.get(
    "/{session_id}/events",
    response_model=EventPage,
    summary="Page through derived frame events",
)
def list_events(
    session_id: UUID,
    repository: Annotated[Repository, Depends(get_repository)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EventPage:
    items, total = repository.list_events(session_id, limit, offset)
    return EventPage(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/{session_id}/summary",
    response_model=SessionSummary,
    summary="Calculate a session-level signal summary",
)
def get_summary(
    session_id: UUID,
    repository: Annotated[Repository, Depends(get_repository)],
) -> SessionSummary:
    session = repository.get_session(session_id)
    return calculate_summary(session, repository.all_events(session_id))


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a session and all derived events",
)
async def delete_session(
    session_id: UUID,
    runtime: Annotated[SessionRuntimeManager, Depends(get_runtime)],
) -> Response:
    await run_in_threadpool(runtime.delete, session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
