# Optional AI adapters

All adapters are isolated in `ai/`; importing the package does not require Ultralytics.

## YOLO Pose video

Install optional dependencies with `python -m pip install -r ai/requirements.txt`. Configure `YOLO_POSE_MODEL` to a locally available Ultralytics pose model path or model name (default `yolo11n-pose.pt`; Ultralytics may download it on first use). The first run needs network access unless the model is already cached. Use `ai.yolo_video.process_video(video_path, output_dir, model=None, history_db=None, confidence=0.25)` after saving an uploaded video to a controlled temporary location. It validates supported video extensions, writes an annotated video, returns per-frame keypoint/confidence detections, and optionally persists history to SQLite. Apply upload size limits, authentication, per-user storage isolation, cleanup/retention, and async job handling in the web layer. Detections are not medical measurements.

Suggested endpoint wiring (not applied to `backend/app/main.py`): add an authenticated `POST /ai/pose` multipart route with a `video` field and optional model/confidence parameters; stream the upload to a randomized temporary file with a configured size limit; call `process_video` in a background worker; return a job id/status and provide a separately authorized result-download route. Store history with an owner identifier and enforce ownership on reads. Do not expose arbitrary filesystem paths or accept arbitrary model URLs from clients.

## Thermography

`ai.thermography.analyze_thermal_image(bytes, filename)` accepts user-provided raster thermal imagery and returns intake metadata only. It deliberately does not decode colors into temperatures or infer core temperature. Calibration/device metadata and domain validation are not implemented.

## NASA & CSA sources

`ai/nasa_models.py`, `ai/nasa_catalog.py`, `ai/nasa_client.py`, and `ai/nasa_sources.py` implement the verified scientific integration catalog covering the five official NASA HRP / CSA sources plus the public NASA Open Science Data Repository (OSDR) REST JSON metadata endpoint (`osdr.nasa.gov`). Reference webpages remain `reference_only`/`catalogued` and never claim live telemetry connections; only verified public JSON API queries transition `nasa-osdr-studies` to `connected`, preserving provenance, classification, and unit limitations.
