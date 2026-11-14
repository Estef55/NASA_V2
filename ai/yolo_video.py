"""Optional Ultralytics YOLO Pose video and live-frame processing service.

Requires the optional `ai` requirements and a user-configured/downloadable model.
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import sqlite3
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .pose_interpreter import (
    COCO_SKELETON,
    compute_person_geometry,
    interpret_pose_sequence,
)

VIDEO_SUFFIXES = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
_MODEL_LOCK = threading.Lock()
_MODEL_CACHE: dict[str, Any] = {}


def validate_video_upload(path: str | Path) -> Path:
    p = Path(path)
    if p.suffix.lower() not in VIDEO_SUFFIXES:
        raise ValueError("Unsupported video file type")
    if not p.is_file() or p.stat().st_size == 0:
        raise ValueError("Video file is missing or empty")
    return p


def summarize_keypoints(points, confidence_threshold: float = 0.0) -> dict:
    """Summarize detected point coordinates/confidence without clinical inference."""
    visible = []
    for point in points or []:
        if len(point) < 2:
            continue
        x, y = float(point[0]), float(point[1])
        conf = float(point[2]) if len(point) > 2 else 1.0
        if conf >= confidence_threshold:
            visible.append((x, y, conf))
    return {
        "visible_keypoints": len(visible),
        "mean_confidence": sum(p[2] for p in visible) / len(visible) if visible else None,
        "keypoints": [{"x": x, "y": y, "confidence": c} for x, y, c in visible],
    }


def _resolve_model_target(model_name: str) -> str:
    p = Path(model_name)
    if p.is_file():
        return str(p)
    repo_root = Path(__file__).resolve().parents[1]
    for cand in (repo_root / model_name, repo_root / "ai" / model_name, repo_root / "backend" / model_name):
        if cand.is_file():
            return str(cand)
    return model_name


def _get_yolo_model(model_name: str):
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError(
            "YOLO processing requires optional dependencies: pip install -r ai/requirements.txt"
        ) from exc
    resolved = _resolve_model_target(model_name)
    with _MODEL_LOCK:
        cached = _MODEL_CACHE.get(resolved)
        if cached is not None:
            return cached
        try:
            detector = YOLO(resolved)
        except Exception as exc:
            raise RuntimeError(f"YOLO model unavailable ({model_name}): {exc}") from exc
        _MODEL_CACHE[resolved] = detector
        return detector


def _persist(history_db: str | Path, record: dict) -> None:
    """Legacy standalone history helper; authenticated API owns user-scoped history."""
    with sqlite3.connect(history_db) as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS pose_analysis_history (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, input_name TEXT NOT NULL, output_path TEXT NOT NULL, measurements_json TEXT NOT NULL)"
        )
        db.execute(
            "INSERT INTO pose_analysis_history VALUES (?, ?, ?, ?, ?)",
            (
                record["id"],
                record["created_at"],
                record["input_name"],
                record["output_video"],
                json.dumps(record["measurements"]),
            ),
        )


def _find_saved_video(run_dir: Path, source_name: str) -> Path | None:
    direct = run_dir / source_name
    if direct.is_file():
        return direct
    if not run_dir.is_dir():
        return None
    for suffix in (".mp4", ".avi", ".mov", ".mkv", ".webm"):
        matches = sorted(run_dir.glob(f"*{suffix}"))
        if matches:
            return matches[0]
    return None


def _finalize_video(saved: Path, target_mp4: Path) -> Path:
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        proc = subprocess.run(
            [
                ffmpeg_bin,
                "-y",
                "-i",
                str(saved),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                "-an",
                str(target_mp4),
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0 and target_mp4.is_file() and target_mp4.stat().st_size > 0:
            saved.unlink(missing_ok=True)
            return target_mp4
    final_path = target_mp4.with_suffix(saved.suffix)
    saved.replace(final_path)
    return final_path


def _encode_annotated_thumbnail(result, max_width: int = 400) -> str | None:
    """Encode an Ultralytics plotted BGR frame as a compact JPEG data URL."""
    try:
        import cv2

        plotted = result.plot()
        if plotted is None:
            return None
        h, w = plotted.shape[:2]
        if w > max_width and w > 0:
            scale = max_width / float(w)
            plotted = cv2.resize(plotted, (max_width, max(1, int(h * scale))))
        ok, buf = cv2.imencode(".jpg", plotted, [int(cv2.IMWRITE_JPEG_QUALITY), 72])
        if not ok:
            return None
        b64 = base64.b64encode(buf.tobytes()).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"
    except Exception:
        return None


def _extract_video_fps(source: Path) -> float | None:
    try:
        import cv2

        cap = cv2.VideoCapture(str(source))
        try:
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
            if 1.0 <= fps <= 120.0:
                return fps
        finally:
            cap.release()
    except Exception:
        pass
    return None


def _pick_representative_thumbnails(candidates: list[dict[str, Any]], max_items: int = 3) -> list[dict[str, Any]]:
    if not candidates:
        return []
    if len(candidates) <= max_items:
        return candidates
    indices = [0, len(candidates) // 2, len(candidates) - 1]
    seen = set()
    picked = []
    for idx in indices:
        if idx not in seen:
            seen.add(idx)
            picked.append(candidates[idx])
    return picked


def process_video(
    video_path: str | Path,
    output_dir: str | Path,
    model: str | None = None,
    history_db: str | Path | None = None,
    confidence: float = 0.25,
    source_mode: str = "upload",
    display_name: str | None = None,
) -> dict:
    source = validate_video_upload(video_path)
    model_name = model or os.getenv("YOLO_POSE_MODEL", "yolo11n-pose.pt")
    detector = _get_yolo_model(model_name)

    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    run_name = f"{source.stem}-pose-{uuid.uuid4().hex[:10]}"
    output = outdir / f"{run_name}.mp4"
    run_dir = outdir / run_name

    fps = _extract_video_fps(source)
    frame_count = 0
    measurements: list[dict[str, Any]] = []
    interpreted_frames: list[dict[str, Any]] = []
    thumb_candidates: list[dict[str, Any]] = []

    try:
        results = detector.predict(
            source=str(source),
            conf=confidence,
            stream=True,
            save=True,
            project=str(outdir),
            name=run_name,
            exist_ok=False,
        )
        for result in results:
            frame_count += 1
            all_points: list[list[float]] = []
            persons: list[dict[str, Any]] = []
            if result.keypoints is not None and result.keypoints.data is not None:
                raw_people = result.keypoints.data.cpu().tolist()
                for person_pts in raw_people:
                    all_points.extend(person_pts)
                    persons.append(compute_person_geometry(person_pts, min_conf=confidence))

            primary = max(persons, key=lambda p: p["visible_keypoints"]) if persons else None
            ts = round((frame_count - 1) / fps, 2) if fps else None
            base_summary = summarize_keypoints(all_points, confidence_threshold=0.0)
            frame_entry = {
                "frame": frame_count,
                "timestamp_s": ts,
                **base_summary,
                "person_count": len(persons),
                "trunk_inclination_deg": primary["trunk_inclination_deg"] if primary else None,
                "shoulder_tilt_deg": primary["shoulder_tilt_deg"] if primary else None,
                "hip_tilt_deg": primary["hip_tilt_deg"] if primary else None,
                "regions": primary["regions"] if primary else None,
            }
            measurements.append(
                {
                    "frame": frame_count,
                    "timestamp_s": ts,
                    "person_count": len(persons),
                    "trunk_inclination_deg": frame_entry["trunk_inclination_deg"],
                    "shoulder_tilt_deg": frame_entry["shoulder_tilt_deg"],
                    **base_summary,
                }
            )
            interpreted_frames.append(frame_entry)

            if primary and primary["visible_keypoints"] >= 4 and (frame_count == 1 or frame_count % 10 == 0):
                thumb = _encode_annotated_thumbnail(result)
                if thumb:
                    thumb_candidates.append(
                        {
                            "frame": frame_count,
                            "timestamp_s": ts,
                            "trunk_inclination_deg": primary["trunk_inclination_deg"],
                            "confidence_percent": round((primary["mean_confidence"] or 0.0) * 100),
                            "image_data_url": thumb,
                        }
                    )

        saved = _find_saved_video(run_dir, source.name)
        if not saved:
            raise RuntimeError("Ultralytics did not produce an annotated video")
        final_output = _finalize_video(saved, output)
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)

    duration_s = round(frame_count / fps, 2) if fps and frame_count > 0 else None
    interpretation = interpret_pose_sequence(
        interpreted_frames,
        source_mode=source_mode,
        input_name=display_name or source.name,
        model_name=model_name,
        duration_seconds=duration_s,
    )

    record = {
        "id": uuid.uuid4().hex,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_name": display_name or source.name,
        "source_mode": source_mode,
        "output_video": str(final_output),
        "model": model_name,
        "frames_processed": frame_count,
        "measurements": measurements,
        "representative_frames": _pick_representative_thumbnails(thumb_candidates, max_items=3),
        "interpretation": interpretation,
        "notice": "Pose keypoints are geometric detections, not medical or physiological measurements.",
    }
    if history_db:
        _persist(history_db, record)
    return record


def process_frame_bytes(
    frame_bytes: bytes,
    *,
    model: str | None = None,
    confidence: float = 0.25,
) -> dict[str, Any]:
    """Run real YOLO Pose inference on a single JPEG/PNG image frame for live camera tracking."""
    if not frame_bytes:
        raise ValueError("Empty frame payload")
    model_name = model or os.getenv("YOLO_POSE_MODEL", "yolo11n-pose.pt")
    detector = _get_yolo_model(model_name)

    try:
        import cv2
        import numpy as np

        arr = np.frombuffer(frame_bytes, dtype=np.uint8)
        image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Could not decode camera frame image")
        height, width = image.shape[:2]
    except ImportError as exc:
        raise RuntimeError(
            "YOLO processing requires optional dependencies: pip install -r ai/requirements.txt"
        ) from exc

    results = detector.predict(source=image, conf=confidence, verbose=False)
    persons_out: list[dict[str, Any]] = []

    if results:
        res0 = results[0]
        if res0.keypoints is not None and res0.keypoints.data is not None:
            raw_people = res0.keypoints.data.cpu().tolist()
            for idx, person_pts in enumerate(raw_people):
                geom = compute_person_geometry(person_pts, min_conf=confidence)
                norm_kps = []
                for kp in geom["keypoints"]:
                    norm_kps.append(
                        {
                            **kp,
                            "nx": round(kp["x"] / width, 4) if width else 0.0,
                            "ny": round(kp["y"] / height, 4) if height else 0.0,
                        }
                    )
                persons_out.append(
                    {
                        "person_index": idx,
                        "visible_keypoints": geom["visible_keypoints"],
                        "mean_confidence": geom["mean_confidence"],
                        "trunk_inclination_deg": geom["trunk_inclination_deg"],
                        "shoulder_tilt_deg": geom["shoulder_tilt_deg"],
                        "hip_tilt_deg": geom["hip_tilt_deg"],
                        "regions": geom["regions"],
                        "keypoints": norm_kps,
                    }
                )

    primary = max(persons_out, key=lambda p: p["visible_keypoints"]) if persons_out else None
    return {
        "model": model_name,
        "width": int(width),
        "height": int(height),
        "person_count": len(persons_out),
        "visible_keypoints": primary["visible_keypoints"] if primary else 0,
        "mean_confidence": primary["mean_confidence"] if primary else None,
        "trunk_inclination_deg": primary["trunk_inclination_deg"] if primary else None,
        "shoulder_tilt_deg": primary["shoulder_tilt_deg"] if primary else None,
        "hip_tilt_deg": primary["hip_tilt_deg"] if primary else None,
        "regions": primary["regions"] if primary else None,
        "persons": persons_out,
        "skeleton": [list(edge) for edge in COCO_SKELETON],
        "notice": "Pose keypoints are geometric detections, not medical or physiological measurements.",
    }


def finalize_live_session(
    frames: list[dict[str, Any]],
    *,
    model: str | None = None,
    duration_seconds: float | None = None,
    input_name: str = "Cámara en vivo",
    representative_frames: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Summarize and interpret a completed live-camera YOLO Pose session without storing raw video."""
    model_name = model or os.getenv("YOLO_POSE_MODEL", "yolo11n-pose.pt")
    interpretation = interpret_pose_sequence(
        frames,
        source_mode="live",
        input_name=input_name,
        model_name=model_name,
        duration_seconds=duration_seconds,
    )
    return {
        "id": uuid.uuid4().hex,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_name": input_name,
        "source_mode": "live",
        "model": model_name,
        "frames_processed": len(frames),
        "measurements": frames,
        "representative_frames": (representative_frames or [])[:3],
        "interpretation": interpretation,
        "notice": "Pose keypoints are geometric detections, not medical or physiological measurements.",
    }
