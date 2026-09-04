from __future__ import annotations

import uvicorn

from gaze_signal_api.api.app import create_app
from gaze_signal_api.config.settings import get_settings

app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "gaze_signal_api.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        reload=False,
    )


if __name__ == "__main__":
    run()
