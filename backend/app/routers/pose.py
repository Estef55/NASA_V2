"""Authenticated optional YOLO Pose video and live-frame API."""
from __future__ import annotations

import inspect
import json
import os
import sqlite3
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from ai.pose_interpreter import interpret_pose_sequence
from ai.yolo_video import (
    VIDEO_SUFFIXES,
    finalize_live_session,
    process_frame_bytes,
    process_video,
)

router = APIRouter(prefix="/api/pose", tags=["pose"])

MAX_FRAME_BYTES = 5 * 1024 * 1024
IMAGE_SIGNATURES = (
    b"\xff\xd8\xff",       # JPEG
    b"\x89PNG\r\n\x1a\n",  # PNG
    b"RIFF",               # WebP (checked with WEBP at offset 8)
)


def _auth(authorization: str | None):
    # Lazy import avoids coupling the router import to main.py initialization.
    from app.main import auth
    return auth(authorization)


def _settings():
    root = Path(os.getenv("POSE_STORAGE_DIR", Path(__file__).resolve().parents[3] / "data" / "pose"))
    history = Path(os.getenv("POSE_HISTORY_DB", root / "history.sqlite3"))
    max_bytes = int(os.getenv("POSE_MAX_UPLOAD_BYTES", str(100 * 1024 * 1024)))
    return root, history, max_bytes


@contextmanager
def _connect(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(db_path)
    try:
        db.execute(
            "CREATE TABLE IF NOT EXISTS pose_analysis_history ("
            "id TEXT PRIMARY KEY, owner TEXT NOT NULL, created_at TEXT NOT NULL, "
            "input_name TEXT NOT NULL, output_path TEXT NOT NULL, measurements_json TEXT NOT NULL, "
            "astronaut_id TEXT)"
        )
        cols = {row[1] for row in db.execute("PRAGMA table_info(pose_analysis_history)").fetchall()}
        if "astronaut_id" not in cols:
            db.execute("ALTER TABLE pose_analysis_history ADD COLUMN astronaut_id TEXT")
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def _save_upload(file: UploadFile, destination: Path, limit: int):
    if Path(file.filename or "").suffix.lower() not in VIDEO_SUFFIXES:
        raise HTTPException(400, "Unsupported video file type")
    total = 0
    try:
        with destination.open("xb") as out:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > limit:
                    raise HTTPException(413, "Video exceeds upload size limit")
                out.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    if total == 0:
        destination.unlink(missing_ok=True)
        raise HTTPException(400, "Video file is missing or empty")
    with destination.open("rb") as stream:
        header = stream.read(16)
    suffix = destination.suffix.lower()
    valid = (
        (suffix in {".mp4", ".mov"} and len(header) >= 8 and header[4:8] == b"ftyp")
        or (suffix == ".avi" and len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"AVI ")
        or (suffix in {".mkv", ".webm"} and header[:4] == bytes.fromhex("1a45dfa3"))
    )
    if not valid:
        destination.unlink(missing_ok=True)
        raise HTTPException(415, "Video content does not match the file extension")


def _validate_image_frame(payload: bytes) -> None:
    if not payload:
        raise HTTPException(400, "Camera frame is empty")
    if len(payload) > MAX_FRAME_BYTES:
        raise HTTPException(413, "Camera frame exceeds 5 MiB limit")
    is_jpeg = payload.startswith(IMAGE_SIGNATURES[0])
    is_png = payload.startswith(IMAGE_SIGNATURES[1])
    is_webp = len(payload) >= 12 and payload[:4] == b"RIFF" and payload[8:12] == b"WEBP"
    if not (is_jpeg or is_png or is_webp):
        raise HTTPException(415, "Unsupported camera frame image format")


def _assigned_astronauts_for_medic(username: str) -> set[str]:
    try:
        from app.database import conn

        with conn() as db:
            rows = db.execute(
                "SELECT astronaut_id FROM assignments WHERE medic_username=?",
                (username,),
            ).fetchall()
            return {row[0] for row in rows if row and row[0]}
    except Exception:
        return set()


class LiveFrameRecord(BaseModel):
    frame: int = Field(ge=1)
    timestamp_s: float | None = Field(default=None, ge=0.0)
    visible_keypoints: int = Field(default=0, ge=0)
    mean_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    trunk_inclination_deg: float | None = Field(default=None, ge=0.0, le=90.0)
    shoulder_tilt_deg: float | None = Field(default=None, ge=0.0, le=90.0)
    hip_tilt_deg: float | None = Field(default=None, ge=0.0, le=90.0)
    person_count: int = Field(default=0, ge=0)
    regions: dict[str, bool] | None = None


class LiveSnapshot(BaseModel):
    frame: int = Field(ge=1)
    timestamp_s: float | None = Field(default=None, ge=0.0)
    trunk_inclination_deg: float | None = None
    confidence_percent: int = Field(default=0, ge=0, le=100)
    image_data_url: str = Field(max_length=250_000)


class LiveSessionComplete(BaseModel):
    model: str | None = Field(default=None, max_length=120)
    duration_seconds: float | None = Field(default=None, ge=0.0, le=3600.0)
    input_name: str = Field(default="Cámara en vivo", min_length=1, max_length=120)
    frames: list[LiveFrameRecord] = Field(min_length=1, max_length=1800)
    representative_frames: list[LiveSnapshot] = Field(default_factory=list, max_length=3)


@router.get("/status")
def pose_status(authorization: str | None = Header(default=None)):
    user = _auth(authorization)
    from app.main import _pose_integration_status, need

    need(user, "astronaut", "medic", "admin")
    info = _pose_integration_status()
    return {
        **info,
        "model": os.getenv("YOLO_POSE_MODEL", "yolo11n-pose.pt"),
        "live_endpoint": "/api/pose/frame",
        "upload_endpoint": "/api/pose/process",
    }


@router.post("/frame")
async def analyze_live_frame(
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
):
    user = _auth(authorization)
    from app.main import need

    need(user, "astronaut", "medic", "admin")
    payload = await file.read(MAX_FRAME_BYTES + 1)
    _validate_image_frame(payload)
    try:
        return process_frame_bytes(payload)
    except RuntimeError as exc:
        msg = str(exc).lower()
        if "optional dependencies" in msg or "ultralytics" in msg or "model unavailable" in msg:
            raise HTTPException(503, "Optional YOLO Pose dependencies/model unavailable") from exc
        raise HTTPException(422, "Frame processing failed") from exc
    except ValueError as exc:
        raise HTTPException(415, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(422, "Frame processing failed") from exc


@router.post("/live/complete")
def complete_live_session(
    data: LiveSessionComplete,
    authorization: str | None = Header(default=None),
):
    user = _auth(authorization)
    from app.main import need

    need(user, "astronaut", "medic", "admin")
    _, history, _ = _settings()

    frames = [f.model_dump() for f in data.frames]
    snaps = [
        s.model_dump()
        for s in data.representative_frames
        if s.image_data_url.startswith("data:image/jpeg;base64,")
    ]
    record = finalize_live_session(
        frames,
        model=data.model,
        duration_seconds=data.duration_seconds,
        input_name=data.input_name,
        representative_frames=snaps,
    )
    result_id = record["id"]
    payload = {
        **record,
        "owner": user["username"],
        "astronaut_id": user.get("astronaut_id"),
        "video_url": None,
    }
    with _connect(history) as db:
        db.execute(
            "INSERT INTO pose_analysis_history (id, owner, created_at, input_name, output_path, measurements_json, astronaut_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                result_id,
                user["username"],
                record["created_at"],
                record["input_name"],
                "",
                json.dumps(payload),
                user.get("astronaut_id"),
            ),
        )
    return payload


@router.post("/process")
async def upload_video(
    file: UploadFile = File(...),
    source_mode: str = Form(default="upload"),
    authorization: str | None = Header(default=None),
):
    user = _auth(authorization)
    from app.main import need

    need(user, "astronaut", "medic", "admin")
    normalized_mode = source_mode if source_mode in {"upload", "recording"} else "upload"
    root, history, limit = _settings()
    uploads = root / "uploads"
    outputs = root / "annotated"
    uploads.mkdir(parents=True, exist_ok=True)
    uploads_path = uploads / f"{uuid.uuid4().hex}{Path(file.filename or '').suffix.lower()}"
    await _save_upload(file, uploads_path, limit)
    original_name = Path(file.filename or "video").name
    try:
        try:
            sig = inspect.signature(process_video)
            if "source_mode" in sig.parameters:
                record = process_video(
                    uploads_path,
                    outputs,
                    source_mode=normalized_mode,
                    display_name=original_name,
                )
            else:
                record = process_video(uploads_path, outputs)
        except RuntimeError as exc:
            msg = str(exc).lower()
            if "optional dependencies" in msg or "ultralytics" in msg or "model unavailable" in msg:
                raise HTTPException(503, "Optional YOLO Pose dependencies/model unavailable") from exc
            raise HTTPException(422, "Video processing failed") from exc
        except Exception as exc:
            raise HTTPException(422, "Video processing failed") from exc
        result_id = uuid.uuid4().hex
        output_path = Path(record["output_video"]).resolve()
        if not output_path.is_file():
            raise HTTPException(422, "Annotated video was not produced")
        payload = {k: v for k, v in record.items() if k != "output_video"}
        if "interpretation" not in payload:
            payload["interpretation"] = interpret_pose_sequence(
                payload.get("measurements") or [],
                source_mode=normalized_mode,
                input_name=original_name,
                model_name=str(payload.get("model") or "yolo11n-pose.pt"),
            )
        payload.update(
            id=result_id,
            owner=user["username"],
            astronaut_id=user.get("astronaut_id"),
            source_mode=payload.get("source_mode", normalized_mode),
            input_name=original_name,
            video_url=f"/api/pose/history/{result_id}/video",
        )
        try:
            with _connect(history) as db:
                db.execute(
                    "INSERT INTO pose_analysis_history (id, owner, created_at, input_name, output_path, measurements_json, astronaut_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        result_id,
                        user["username"],
                        datetime.now(timezone.utc).isoformat(),
                        payload["input_name"],
                        str(output_path),
                        json.dumps(payload),
                        user.get("astronaut_id"),
                    ),
                )
        except Exception:
            output_path.unlink(missing_ok=True)
            raise
        return payload
    finally:
        uploads_path.unlink(missing_ok=True)


@router.get("/history")
def history_list(authorization: str | None = Header(default=None)):
    user = _auth(authorization)
    _, db_path, _ = _settings()
    if not db_path.exists():
        return []
    with _connect(db_path) as db:
        if user["role"] == "medic":
            assigned = _assigned_astronauts_for_medic(user["username"])
            if assigned:
                placeholders = ",".join("?" for _ in assigned)
                rows = db.execute(
                    f"SELECT measurements_json FROM pose_analysis_history "
                    f"WHERE owner=? OR astronaut_id IN ({placeholders}) ORDER BY created_at DESC",
                    (user["username"], *sorted(assigned)),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT measurements_json FROM pose_analysis_history WHERE owner=? ORDER BY created_at DESC",
                    (user["username"],),
                ).fetchall()
        else:
            rows = db.execute(
                "SELECT measurements_json FROM pose_analysis_history WHERE owner=? ORDER BY created_at DESC",
                (user["username"],),
            ).fetchall()
    items = []
    for row in rows:
        item = json.loads(row[0])
        if "interpretation" not in item:
            item["interpretation"] = interpret_pose_sequence(
                item.get("measurements") or [],
                source_mode=item.get("source_mode", "upload"),
                input_name=item.get("input_name", "video"),
                model_name=str(item.get("model") or "yolo11n-pose.pt"),
            )
        items.append(item)
    return items


@router.get("/history/{analysis_id}/video")
def download_video(analysis_id: str, authorization: str | None = Header(default=None)):
    user = _auth(authorization)
    _, db_path, _ = _settings()
    if not db_path.exists():
        raise HTTPException(404, "Analysis not found")
    with _connect(db_path) as db:
        if user["role"] == "medic":
            assigned = _assigned_astronauts_for_medic(user["username"])
            if assigned:
                placeholders = ",".join("?" for _ in assigned)
                row = db.execute(
                    f"SELECT output_path FROM pose_analysis_history WHERE id=? AND (owner=? OR astronaut_id IN ({placeholders}))",
                    (analysis_id, user["username"], *sorted(assigned)),
                ).fetchone()
            else:
                row = db.execute(
                    "SELECT output_path FROM pose_analysis_history WHERE id=? AND owner=?",
                    (analysis_id, user["username"]),
                ).fetchone()
        else:
            row = db.execute(
                "SELECT output_path FROM pose_analysis_history WHERE id=? AND owner=?",
                (analysis_id, user["username"]),
            ).fetchone()
    if not row or not row[0]:
        raise HTTPException(404, "Analysis not found")
    path = Path(row[0]).resolve()
    if not path.is_file():
        raise HTTPException(404, "Annotated video not found")
    media_types = {
        ".mp4": "video/mp4",
        ".avi": "video/x-msvideo",
        ".mov": "video/quicktime",
        ".mkv": "video/x-matroska",
        ".webm": "video/webm",
    }
    return FileResponse(path, media_type=media_types.get(path.suffix.lower(), "application/octet-stream"), filename=path.name)


@router.delete("/history/{analysis_id}")
def delete_analysis(analysis_id: str, authorization: str | None = Header(default=None)):
    user = _auth(authorization)
    _, db_path, _ = _settings()
    if not db_path.exists():
        raise HTTPException(404, "Analysis not found")
    with _connect(db_path) as db:
        row = db.execute(
            "SELECT output_path FROM pose_analysis_history WHERE id=? AND owner=?",
            (analysis_id, user["username"]),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Analysis not found")
        db.execute(
            "DELETE FROM pose_analysis_history WHERE id=? AND owner=?",
            (analysis_id, user["username"]),
        )
    if row[0]:
        Path(row[0]).unlink(missing_ok=True)
    return {"ok": True}
