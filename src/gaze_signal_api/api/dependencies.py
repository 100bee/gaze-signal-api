from __future__ import annotations

from fastapi import Request

from gaze_signal_api.config.settings import Settings
from gaze_signal_api.runtime.manager import SessionRuntimeManager
from gaze_signal_api.runtime.websocket import EventHub
from gaze_signal_api.storage.repository import Repository


def get_repository(request: Request) -> Repository:
    return request.app.state.repository


def get_runtime(request: Request) -> SessionRuntimeManager:
    return request.app.state.runtime


def get_event_hub(request: Request) -> EventHub:
    return request.app.state.event_hub


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings
