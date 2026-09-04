from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from gaze_signal_api.api.dependencies import get_repository
from gaze_signal_api.calibration.service import CalibrationService
from gaze_signal_api.schemas.calibration import CalibrationCreate, CalibrationPage, CalibrationRead
from gaze_signal_api.storage.repository import Repository

router = APIRouter(prefix="/calibrations", tags=["calibrations"])


@router.post(
    "",
    response_model=CalibrationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Fit and store a 5- or 9-point calibration",
)
def create_calibration(
    payload: CalibrationCreate,
    repository: Annotated[Repository, Depends(get_repository)],
) -> CalibrationRead:
    parameters = CalibrationService().fit(payload)
    return repository.create_calibration(payload, parameters)


@router.get("", response_model=CalibrationPage, summary="List saved calibrations")
def list_calibrations(
    repository: Annotated[Repository, Depends(get_repository)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CalibrationPage:
    items, total = repository.list_calibrations(limit, offset)
    return CalibrationPage(items=items, total=total, limit=limit, offset=offset)


@router.delete(
    "/{calibration_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete calibration data",
)
def delete_calibration(
    calibration_id: UUID,
    repository: Annotated[Repository, Depends(get_repository)],
) -> Response:
    repository.delete_calibration(calibration_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
