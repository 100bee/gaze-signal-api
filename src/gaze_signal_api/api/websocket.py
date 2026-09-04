from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from gaze_signal_api.errors import NotFoundError

router = APIRouter(tags=["realtime"])


@router.websocket("/ws/sessions/{session_id}")
async def session_events(websocket: WebSocket, session_id: UUID) -> None:
    repository = websocket.app.state.repository
    hub = websocket.app.state.event_hub
    origin = websocket.headers.get("origin")
    if origin is not None and origin not in websocket.app.state.settings.allowed_origins:
        await websocket.close(code=4403, reason="origin not allowed")
        return
    try:
        repository.get_session(session_id)
    except NotFoundError:
        await websocket.close(code=4404, reason="session not found")
        return

    await websocket.accept()
    queue = hub.subscribe(session_id)
    try:
        while True:
            payload = await queue.get()
            await websocket.send_json(payload)
    except WebSocketDisconnect:
        pass
    finally:
        hub.unsubscribe(session_id, queue)
