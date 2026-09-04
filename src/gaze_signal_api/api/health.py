from __future__ import annotations

import importlib.util
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text

from gaze_signal_api.api.dependencies import get_app_settings, get_repository
from gaze_signal_api.config.settings import Settings
from gaze_signal_api.storage.repository import Repository

router = APIRouter(tags=["system"])


class ComponentHealth(BaseModel):
    database: str
    opencv_installed: bool
    mediapipe_installed: bool
    face_model_installed: bool
    ultralytics_installed: bool


class HealthResponse(BaseModel):
    status: str
    components: ComponentHealth


@router.get("/health", response_model=HealthResponse, summary="Check local service health")
def health(
    repository: Annotated[Repository, Depends(get_repository)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> HealthResponse:
    database_status = "ok"
    try:
        with repository.database.session_factory() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        database_status = "unavailable"
    return HealthResponse(
        status="ok" if database_status == "ok" else "degraded",
        components=ComponentHealth(
            database=database_status,
            opencv_installed=importlib.util.find_spec("cv2") is not None,
            mediapipe_installed=importlib.util.find_spec("mediapipe") is not None,
            face_model_installed=settings.face_model_path.is_file(),
            ultralytics_installed=importlib.util.find_spec("ultralytics") is not None,
        ),
    )
