"""Plain-language geometric pose interpreter for YOLO Pose detections.

Translates raw COCO 17-keypoint coordinates and confidences into cautious,
non-diagnostic Spanish and English descriptions suitable for medical review,
while keeping full technical traceability as secondary metadata.
"""
from __future__ import annotations

import math
import statistics
from typing import Any

COCO_KEYPOINT_NAMES: tuple[str, ...] = (
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
)

COCO_SKELETON: tuple[tuple[int, int], ...] = (
    (0, 1), (0, 2), (1, 3), (2, 4),
    (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
    (5, 11), (6, 12), (11, 12),
    (11, 13), (13, 15), (12, 14), (14, 16),
)

_KEYPOINT_CONF_THRESHOLD = 0.35


def _valid_pt(kps: list[dict[str, Any]], idx: int, min_conf: float = _KEYPOINT_CONF_THRESHOLD) -> tuple[float, float, float] | None:
    if idx < 0 or idx >= len(kps):
        return None
    kp = kps[idx]
    x = float(kp.get("x", 0.0))
    y = float(kp.get("y", 0.0))
    conf = float(kp.get("confidence", 0.0))
    if conf < min_conf or (x == 0.0 and y == 0.0):
        return None
    return (x, y, conf)


def _midpoint(a: tuple[float, float, float] | None, b: tuple[float, float, float] | None) -> tuple[float, float] | None:
    if a and b:
        return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
    if a:
        return (a[0], a[1])
    if b:
        return (b[0], b[1])
    return None


def compute_person_geometry(raw_points: list[list[float]] | list[dict[str, Any]], *, min_conf: float = _KEYPOINT_CONF_THRESHOLD) -> dict[str, Any]:
    """Compute geometric posture indicators from a single person's 17 COCO keypoints."""
    named: list[dict[str, Any]] = []
    for idx, pt in enumerate(raw_points or []):
        if isinstance(pt, dict):
            x = float(pt.get("x", 0.0))
            y = float(pt.get("y", 0.0))
            conf = float(pt.get("confidence", 0.0))
            name = str(pt.get("name") or (COCO_KEYPOINT_NAMES[idx] if idx < len(COCO_KEYPOINT_NAMES) else f"kp_{idx}"))
        else:
            x = float(pt[0]) if len(pt) > 0 else 0.0
            y = float(pt[1]) if len(pt) > 1 else 0.0
            conf = float(pt[2]) if len(pt) > 2 else 1.0
            name = COCO_KEYPOINT_NAMES[idx] if idx < len(COCO_KEYPOINT_NAMES) else f"kp_{idx}"
        named.append({"name": name, "x": round(x, 2), "y": round(y, 2), "confidence": round(conf, 4)})

    ls = _valid_pt(named, 5, min_conf)
    rs = _valid_pt(named, 6, min_conf)
    lh = _valid_pt(named, 11, min_conf)
    rh = _valid_pt(named, 12, min_conf)

    shoulder_mid = _midpoint(ls, rs)
    hip_mid = _midpoint(lh, rh)

    trunk_inclination_deg: float | None = None
    if shoulder_mid and hip_mid:
        dx = shoulder_mid[0] - hip_mid[0]
        dy = hip_mid[1] - shoulder_mid[1]  # positive upward in image coordinates
        if abs(dx) > 1e-3 or abs(dy) > 1e-3:
            angle = math.degrees(math.atan2(abs(dx), max(abs(dy), 1e-3)))
            trunk_inclination_deg = round(min(max(angle, 0.0), 90.0), 1)

    shoulder_tilt_deg: float | None = None
    if ls and rs and abs(rs[0] - ls[0]) > 1e-3:
        raw_tilt = abs(math.degrees(math.atan2(rs[1] - ls[1], rs[0] - ls[0])))
        shoulder_tilt_deg = round(min(raw_tilt, 180.0 - raw_tilt, 90.0), 1)

    hip_tilt_deg: float | None = None
    if lh and rh and abs(rh[0] - lh[0]) > 1e-3:
        raw_hip = abs(math.degrees(math.atan2(rh[1] - lh[1], rh[0] - lh[0])))
        hip_tilt_deg = round(min(raw_hip, 180.0 - raw_hip, 90.0), 1)

    head_vis = sum(1 for i in range(0, 5) if _valid_pt(named, i, min_conf) is not None)
    upper_vis = sum(1 for i in range(5, 11) if _valid_pt(named, i, min_conf) is not None)
    torso_vis = sum(1 for i in (5, 6, 11, 12) if _valid_pt(named, i, min_conf) is not None)
    lower_vis = sum(1 for i in range(11, 17) if _valid_pt(named, i, min_conf) is not None)

    visible_points = [kp for kp in named if kp["confidence"] >= min_conf and (kp["x"] != 0.0 or kp["y"] != 0.0)]
    mean_conf = round(sum(kp["confidence"] for kp in visible_points) / len(visible_points), 4) if visible_points else None

    return {
        "keypoints": named,
        "visible_keypoints": len(visible_points),
        "mean_confidence": mean_conf,
        "trunk_inclination_deg": trunk_inclination_deg,
        "shoulder_tilt_deg": shoulder_tilt_deg,
        "hip_tilt_deg": hip_tilt_deg,
        "regions": {
            "head_visible": head_vis > 0,
            "upper_body_visible": upper_vis >= 2,
            "torso_visible": torso_vis >= 3,
            "lower_body_visible": lower_vis >= 3,
        },
    }


def _confidence_band(mean_conf: float | None, detected_frames: int, avg_visible_kps: float) -> str:
    if detected_frames == 0 or mean_conf is None or mean_conf < 0.30 or avg_visible_kps < 4.0:
        return "insufficient"
    if mean_conf >= 0.70 and avg_visible_kps >= 10.0:
        return "high"
    if mean_conf >= 0.45 and avg_visible_kps >= 6.0:
        return "moderate"
    return "low"


def interpret_pose_sequence(
    frames: list[dict[str, Any]],
    *,
    source_mode: str = "upload",
    input_name: str = "video",
    model_name: str = "yolo11n-pose.pt",
    duration_seconds: float | None = None,
) -> dict[str, Any]:
    """Build bilingual plain-language posture interpretation from real frame measurements."""
    total_frames = len(frames)
    detected_frames = [f for f in frames if (f.get("visible_keypoints") or 0) > 0]
    detected_count = len(detected_frames)
    detection_ratio = (detected_count / total_frames) if total_frames else 0.0

    confs = [float(f["mean_confidence"]) for f in detected_frames if f.get("mean_confidence") is not None]
    mean_conf = round(sum(confs) / len(confs), 4) if confs else None
    avg_kps = (sum(int(f.get("visible_keypoints") or 0) for f in detected_frames) / detected_count) if detected_count else 0.0

    trunk_angles = [float(f["trunk_inclination_deg"]) for f in detected_frames if f.get("trunk_inclination_deg") is not None]
    shoulder_tilts = [float(f["shoulder_tilt_deg"]) for f in detected_frames if f.get("shoulder_tilt_deg") is not None]

    upper_vis_count = sum(1 for f in detected_frames if (f.get("regions") or {}).get("upper_body_visible"))
    lower_vis_count = sum(1 for f in detected_frames if (f.get("regions") or {}).get("lower_body_visible"))
    upper_cov = (upper_vis_count / detected_count) if detected_count else 0.0
    lower_cov = (lower_vis_count / detected_count) if detected_count else 0.0

    band = _confidence_band(mean_conf, detected_count, avg_kps)

    mode_labels_es = {
        "live": "sesión de cámara en vivo",
        "recording": "grabación desde cámara",
        "upload": "video cargado desde dispositivo",
    }
    mode_labels_en = {
        "live": "live camera session",
        "recording": "camera recording",
        "upload": "uploaded video file",
    }
    mode_es = mode_labels_es.get(source_mode, "registro de video")
    mode_en = mode_labels_en.get(source_mode, "video record")

    conf_labels_es = {
        "high": "Alta — los puntos corporales principales se detectaron con claridad",
        "moderate": "Moderada — la postura general fue visible, con algunas variaciones de nitidez",
        "low": "Baja — detección irregular; interpretar con cautela",
        "insufficient": "Insuficiente — no se detectaron puntos corporales suficientes para evaluar la postura",
    }
    conf_labels_en = {
        "high": "High — primary body keypoints were detected clearly",
        "moderate": "Moderate — overall posture was visible with minor clarity variations",
        "low": "Low — irregular keypoint detection; interpret with caution",
        "insufficient": "Insufficient — not enough body keypoints were detected to evaluate posture",
    }

    obs_es: list[str] = []
    obs_en: list[str] = []
    lim_es: list[str] = []
    lim_en: list[str] = []
    requires_review = False

    if band == "insufficient":
        obs_es.append("No se obtuvo información suficiente para realizar una interpretación confiable de la postura o del movimiento.")
        obs_en.append("Insufficient reliable detection data was obtained to interpret posture or movement.")
        if detected_count == 0:
            lim_es.append("No se identificó ninguna silueta o conjunto de puntos corporales en los fotogramas procesados.")
            lim_en.append("No person or body keypoints were detected in the processed frames.")
        else:
            lim_es.append("La visibilidad o confianza de los puntos clave fue demasiado baja para extraer patrones estables.")
            lim_en.append("Keypoint visibility or confidence was too low to extract stable movement patterns.")
    else:
        if detection_ratio >= 0.85:
            obs_es.append(f"Se mantuvo una detección continua de la persona durante casi toda la secuencia ({detected_count} de {total_frames} fotogramas).")
            obs_en.append(f"Continuous body detection was maintained across almost the entire sequence ({detected_count} of {total_frames} frames).")
        elif detection_ratio >= 0.40:
            obs_es.append(f"La detección corporal fue parcial ({detected_count} de {total_frames} fotogramas); hubo tramos sin visibilidad completa.")
            obs_en.append(f"Body detection was intermittent ({detected_count} of {total_frames} frames); visibility dropped in part of the sequence.")
        else:
            obs_es.append(f"Solo se detectó postura en una fracción limitada del video ({detected_count} de {total_frames} fotogramas).")
            obs_en.append(f"Posture was detected in only a limited portion of the video ({detected_count} of {total_frames} frames).")
            lim_es.append("Menos del 40 % de los fotogramas contaron con detección corporal válida.")
            lim_en.append("Fewer than 40% of frames contained valid body detections.")

        if len(trunk_angles) >= 2:
            mean_trunk = sum(trunk_angles) / len(trunk_angles)
            max_trunk = max(trunk_angles)
            inclined_frames = sum(1 for a in trunk_angles if a >= 18.0)
            inclined_ratio = inclined_frames / len(trunk_angles)
            if inclined_ratio >= 0.25 or mean_trunk >= 16.0:
                requires_review = True
                obs_es.append(
                    f"Se identificó una postura inclinada del tronco durante parte del registro "
                    f"(inclinación media de {mean_trunk:.0f}° y máxima observada de {max_trunk:.0f}°)."
                )
                obs_en.append(
                    f"An inclined trunk posture was observed during part of the recording "
                    f"(mean inclination {mean_trunk:.0f}°, peak {max_trunk:.0f}°)."
                )
            else:
                obs_es.append(
                    f"El tronco se mantuvo mayormente erguido en los fotogramas evaluados (inclinación media aproximada de {mean_trunk:.0f}°)."
                )
                obs_en.append(
                    f"The trunk remained mostly upright across evaluated frames (mean inclination ~{mean_trunk:.0f}°)."
                )

            if len(trunk_angles) >= 4:
                trunk_std = statistics.pstdev(trunk_angles)
                trunk_span = max_trunk - min(trunk_angles)
                if trunk_std >= 5.5 or trunk_span >= 16.0:
                    requires_review = True
                    obs_es.append(
                        f"Se observó variación en la posición del tronco durante el movimiento (cambio acumulado de {trunk_span:.0f}°)."
                    )
                    obs_en.append(
                        f"Variation in trunk position was observed during movement (observed range {trunk_span:.0f}°)."
                    )
                else:
                    obs_es.append("La posición del tronco se mantuvo estable durante el movimiento analizado.")
                    obs_en.append("Trunk position remained relatively steady during the analyzed movement.")
        else:
            lim_es.append("No hubo suficientes fotogramas con hombros y caderas visibles simultáneamente para medir la inclinación del tronco.")
            lim_en.append("Not enough frames showed shoulders and hips simultaneously to measure trunk inclination.")

        if len(shoulder_tilts) >= 2:
            mean_sh = sum(shoulder_tilts) / len(shoulder_tilts)
            tilted_ratio = sum(1 for a in shoulder_tilts if a >= 8.0) / len(shoulder_tilts)
            if tilted_ratio >= 0.30 or mean_sh >= 7.5:
                requires_review = True
                obs_es.append(
                    f"Se detectó desnivel o inclinación lateral entre ambos hombros durante parte de la secuencia (promedio {mean_sh:.0f}°)."
                )
                obs_en.append(
                    f"Lateral shoulder tilt or asymmetry was detected during part of the sequence (average {mean_sh:.0f}°)."
                )
            else:
                obs_es.append("La línea de los hombros se observó equilibrada en los fotogramas con buena visibilidad.")
                obs_en.append("Shoulder alignment appeared balanced across clearly visible frames.")

        if upper_cov >= 0.60 and lower_cov < 0.35:
            obs_es.append("Se captó bien la parte superior del cuerpo, pero la detección de piernas y tobillos fue irregular debido a la visibilidad o encuadre.")
            obs_en.append("Upper-body keypoints were captured well, while leg and ankle detection was irregular due to framing or visibility.")
            lim_es.append("Las extremidades inferiores permanecieron parcialmente fuera de cuadro o con baja visibilidad.")
            lim_en.append("Lower extremities were partially out of frame or had limited visibility.")

    if total_frames < 5:
        lim_es.append(f"Secuencia muy breve ({total_frames} fotogramas); una captura más larga ofrece mayor contexto.")
        lim_en.append(f"Very short sequence ({total_frames} frames); a longer capture provides better movement context.")

    if band == "low":
        requires_review = True
        lim_es.append("La confianza media de detección fue baja (posible iluminación insuficiente, desenfoque por movimiento u oclusión parcial).")
        lim_en.append("Average detection confidence was low (possible low lighting, motion blur, or partial occlusion).")

    if mean_conf is not None and band != "insufficient":
        conf_pct = round(mean_conf * 100)
        summary_es = (
            f"Se completó el análisis de {mode_es} ({input_name}, {total_frames} fotogramas). "
            f"Confianza general de detección: {conf_labels_es[band].split(' — ')[0]} ({conf_pct}%)."
        )
        summary_en = (
            f"Completed analysis of {mode_en} ({input_name}, {total_frames} frames). "
            f"Overall detection confidence: {conf_labels_en[band].split(' — ')[0]} ({conf_pct}%)."
        )
    else:
        summary_es = (
            f"Se procesó {mode_es} ({input_name}, {total_frames} fotogramas), "
            "pero no se obtuvieron detecciones corporales suficientes para interpretar la postura."
        )
        summary_en = (
            f"Processed {mode_en} ({input_name}, {total_frames} frames), "
            "but insufficient body detections were found to interpret posture."
        )

    timeline = []
    for idx, f in enumerate(frames):
        frame_no = int(f.get("frame") or (idx + 1))
        ts = f.get("timestamp_s")
        if ts is None:
            if duration_seconds and total_frames > 1:
                ts = round((idx / max(total_frames - 1, 1)) * duration_seconds, 2)
            else:
                ts = round(idx * 0.25, 2)
        timeline.append({
            "frame": frame_no,
            "timestamp_s": ts,
            "detected": (f.get("visible_keypoints") or 0) > 0,
            "visible_keypoints": int(f.get("visible_keypoints") or 0),
            "mean_confidence": f.get("mean_confidence"),
            "trunk_inclination_deg": f.get("trunk_inclination_deg"),
            "shoulder_tilt_deg": f.get("shoulder_tilt_deg"),
        })

    return {
        "status": "insufficient_data" if band == "insufficient" else ("completed_limited_visibility" if lim_es else "completed_with_findings"),
        "confidence_band": band,
        "confidence_percent": round(mean_conf * 100) if mean_conf is not None else 0,
        "confidence_label": {"es": conf_labels_es[band], "en": conf_labels_en[band]},
        "requires_human_review": requires_review,
        "what_was_analyzed": {
            "source_mode": source_mode,
            "input_name": input_name,
            "frames_processed": total_frames,
            "frames_with_detection": detected_count,
            "duration_seconds": round(duration_seconds, 2) if duration_seconds is not None else None,
        },
        "summary": {"es": summary_es, "en": summary_en},
        "observations": {"es": obs_es, "en": obs_en},
        "limitations": {"es": lim_es, "en": lim_en},
        "non_diagnostic_notice": {
            "es": "Este resultado describe únicamente puntos clave geométricos y patrones visuales de postura/movimiento. No constituye un diagnóstico médico, detección de lesiones ni evaluación clínica definitiva.",
            "en": "This result describes geometric keypoints and visual posture/movement patterns only. It is not a medical diagnosis, injury assessment, or definitive clinical evaluation.",
        },
        "timeline": timeline,
        "technical_details": {
            "model": model_name,
            "frames_processed": total_frames,
            "frames_with_detection": detected_count,
            "detection_rate_percent": round(detection_ratio * 100, 1),
            "mean_confidence": mean_conf,
            "average_visible_keypoints_per_detected_frame": round(avg_kps, 1),
            "trunk_inclination_stats_deg": {
                "samples": len(trunk_angles),
                "mean": round(sum(trunk_angles) / len(trunk_angles), 1) if trunk_angles else None,
                "min": round(min(trunk_angles), 1) if trunk_angles else None,
                "max": round(max(trunk_angles), 1) if trunk_angles else None,
            },
            "shoulder_tilt_stats_deg": {
                "samples": len(shoulder_tilts),
                "mean": round(sum(shoulder_tilts) / len(shoulder_tilts), 1) if shoulder_tilts else None,
                "max": round(max(shoulder_tilts), 1) if shoulder_tilts else None,
            },
        },
    }
