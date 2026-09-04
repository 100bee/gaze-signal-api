# Third-party notices

GazeSignal source code in this repository was independently written; no code was copied from the candidate gaze-tracking repositories reviewed during project setup.

Runtime libraries are installed from their own distributions and are not vendored here:

- FastAPI, Pydantic, Uvicorn and SQLAlchemy: permissive open-source licenses; see each installed distribution.
- NumPy: BSD-3-Clause.
- OpenCV: Apache-2.0 for current distributions. MediaPipe requires `opencv-contrib-python`; the optional Ultralytics extra separately requires `opencv-python`. The tested environment pins both distributions to 5.0.0.93, but they share the `cv2` namespace and must be regression-tested together.
- Google MediaPipe: Apache-2.0. Its separately downloaded model asset is subject to the terms published with that asset.
- Ultralytics: AGPL-3.0 or a commercial enterprise license. It is an optional extra and is disabled by default.

Dependency names are informational, not an endorsement. Review the exact license files of locked versions before redistribution. The project MIT license covers only original GazeSignal code and documentation; it does not relicense dependencies or model weights.
