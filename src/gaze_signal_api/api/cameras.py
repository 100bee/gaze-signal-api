from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel

from gaze_signal_api.capture.camera import list_cameras
from gaze_signal_api.errors import ConsentRequiredError

router = APIRouter(prefix="/cameras", tags=["cameras"])


class CameraRead(BaseModel):
    index: int
    available: bool
    width: int | None
    height: int | None


@router.get("", response_model=list[CameraRead], summary="Probe locally available cameras")
def cameras(
    consent: Annotated[
        bool,
        Query(description="Explicit acknowledgement that probing may activate camera hardware"),
    ] = False,
    max_index: Annotated[int, Query(ge=1, le=16)] = 5,
) -> list[CameraRead]:
    if not consent:
        raise ConsentRequiredError("explicit camera consent is required before probing devices")
    return [
        CameraRead.model_validate(item, from_attributes=True) for item in list_cameras(max_index)
    ]
