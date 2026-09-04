from __future__ import annotations


class GazeSignalError(Exception):
    """Base class for expected, safe-to-return domain errors."""

    status_code = 400
    code = "gaze_signal_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(GazeSignalError):
    status_code = 404
    code = "not_found"


class ConflictError(GazeSignalError):
    status_code = 409
    code = "invalid_state_transition"


class ConsentRequiredError(GazeSignalError):
    status_code = 403
    code = "camera_consent_required"


class ResourceUnavailableError(GazeSignalError):
    status_code = 503
    code = "resource_unavailable"
