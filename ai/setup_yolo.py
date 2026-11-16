"""Cross-platform installer, conflict checker, and runtime verifier for optional YOLO Pose."""
from __future__ import annotations

import argparse
import importlib.metadata as importlib_meta
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_MODEL_FILENAME = "yolo11n-pose.pt"
DEFAULT_WEIGHTS_URL = "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n-pose.pt"
PYTORCH_CPU_INDEX_URL = "https://download.pytorch.org/whl/cpu"
MIN_WEIGHTS_BYTES = 1_000_000

_TRUTHY = {"1", "true", "yes", "on", "si", "sí"}
_FALSY = {"0", "false", "no", "off"}
_LIGHT_MODES = {"light", "ligero", "lightweight"}
_FULL_MODES = {"full", "completo"}

_INFERENCE_CACHE: dict[str, dict[str, Any]] = {}


def get_mode_config_path() -> Path:
    override = (os.getenv("LATIRA_POSE_MODE_FILE") or "").strip()
    if override:
        return Path(override)
    return get_project_root() / "data" / "pose_mode.json"


def read_persisted_pose_mode() -> str | None:
    path = get_mode_config_path()
    try:
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        mode = str(payload.get("mode", "")).strip().lower()
        if mode in _LIGHT_MODES:
            return "light"
        if mode in _FULL_MODES:
            return "full"
    except (OSError, ValueError, TypeError, AttributeError):
        return None
    return None


def set_persisted_pose_mode(mode: str) -> Path:
    norm = mode.strip().lower()
    if norm in _LIGHT_MODES:
        canonical = "light"
    elif norm in _FULL_MODES:
        canonical = "full"
    else:
        raise ValueError(f"Unsupported pose mode: {mode}")
    path = get_mode_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".json.tmp")
    payload = {
        "mode": canonical,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)
    clear_runtime_cache()
    return path


def get_effective_yolo_config() -> dict[str, Any]:
    skip_val = (os.getenv("LATIRA_SKIP_YOLO_SETUP") or "").strip().lower()
    if skip_val in _TRUTHY:
        return {"enabled": False, "mode": "light", "source": "LATIRA_SKIP_YOLO_SETUP"}

    enabled_env = (os.getenv("LATIRA_YOLO_ENABLED") or "").strip().lower()
    if enabled_env in _FALSY:
        return {"enabled": False, "mode": "light", "source": "LATIRA_YOLO_ENABLED"}

    mode_env = (os.getenv("LATIRA_MODE") or "").strip().lower()
    if mode_env in _LIGHT_MODES:
        return {"enabled": False, "mode": "light", "source": "LATIRA_MODE"}
    if mode_env in _FULL_MODES:
        return {"enabled": True, "mode": "full", "source": "LATIRA_MODE"}

    persisted = read_persisted_pose_mode()
    if persisted == "light":
        return {"enabled": False, "mode": "light", "source": "persisted_config"}
    if persisted == "full":
        return {"enabled": True, "mode": "full", "source": "persisted_config"}

    return {"enabled": True, "mode": "full", "source": "default"}


def is_yolo_enabled() -> bool:
    return bool(get_effective_yolo_config()["enabled"])


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def get_models_dir() -> Path:
    return get_project_root() / "models"


def resolve_weights_candidates(model_cfg: str | None = None) -> tuple[str, list[Path]]:
    cfg = (model_cfg or os.getenv("YOLO_POSE_MODEL") or DEFAULT_MODEL_FILENAME).strip() or DEFAULT_MODEL_FILENAME
    root = get_project_root()
    p = Path(cfg)
    candidates: list[Path] = []
    if p.is_absolute():
        candidates.append(p)
    else:
        candidates.extend(
            [
                root / "models" / cfg,
                root / cfg,
                root / "ai" / cfg,
                root / "backend" / cfg,
            ]
        )
    return cfg, candidates


def find_weights_file(model_cfg: str | None = None) -> tuple[str, Path | None]:
    cfg, candidates = resolve_weights_candidates(model_cfg)
    for cand in candidates:
        if cand.is_file():
            return cfg, cand
    return cfg, None


def is_valid_weights_file(path: Path) -> bool:
    try:
        if not path.is_file() or path.stat().st_size < MIN_WEIGHTS_BYTES:
            return False
        # Ultralytics .pt checkpoints are PyTorch zip archives.
        return zipfile.is_zipfile(path)
    except OSError:
        return False


def _dist_installed(dist_name: str) -> bool:
    try:
        importlib_meta.version(dist_name)
        return True
    except importlib_meta.PackageNotFoundError:
        return False


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _run_pip(args: list[str]) -> tuple[bool, str]:
    cmd = [sys.executable, "-m", "pip", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    return proc.returncode == 0, output.strip()


def resolve_opencv_conflicts(*, auto_fix: bool = False) -> dict[str, Any]:
    gui_installed = _dist_installed("opencv-python")
    headless_installed = _dist_installed("opencv-python-headless")
    contrib_installed = _dist_installed("opencv-contrib-python")
    conflict = (gui_installed and headless_installed) or contrib_installed

    actions: list[str] = []
    if auto_fix and (gui_installed or contrib_installed or not headless_installed):
        if gui_installed:
            ok, out = _run_pip(["uninstall", "-y", "opencv-python"])
            actions.append(f"uninstall opencv-python: {'ok' if ok else out}")
        if contrib_installed:
            ok, out = _run_pip(["uninstall", "-y", "opencv-contrib-python"])
            actions.append(f"uninstall opencv-contrib-python: {'ok' if ok else out}")
        ok, out = _run_pip(["install", "--force-reinstall", "--no-deps", "opencv-python-headless>=4.10,<5"])
        actions.append(f"install opencv-python-headless: {'ok' if ok else out}")
        gui_installed = _dist_installed("opencv-python")
        headless_installed = _dist_installed("opencv-python-headless")
        contrib_installed = _dist_installed("opencv-contrib-python")
        conflict = (gui_installed and headless_installed) or contrib_installed

    return {
        "opencv_importable": _module_available("cv2"),
        "opencv_headless_installed": headless_installed,
        "opencv_gui_installed": gui_installed,
        "opencv_conflict": conflict,
        "actions": actions,
    }


def download_weights(target_path: Path, url: str | None = None, timeout: int = 120) -> tuple[bool, str]:
    download_url = (url or os.getenv("LATIRA_YOLO_DOWNLOAD_URL") or DEFAULT_WEIGHTS_URL).strip()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    part_path = target_path.with_suffix(target_path.suffix + ".part")
    part_path.unlink(missing_ok=True)
    try:
        req = urllib.request.Request(download_url, headers={"User-Agent": "LATIRA-2.0-Setup"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if getattr(resp, "status", 200) >= 400:
                return False, f"HTTP {resp.status} downloading weights"
            with part_path.open("wb") as out:
                while True:
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    out.write(chunk)
        if not is_valid_weights_file(part_path):
            part_path.unlink(missing_ok=True)
            return False, "Downloaded weights file failed integrity/size verification"
        part_path.replace(target_path)
        return True, f"Downloaded and verified {target_path.name} ({target_path.stat().st_size} bytes)"
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        part_path.unlink(missing_ok=True)
        return False, f"Download failed: {exc}"


def verify_model_load_and_inference(weights_path: Path) -> dict[str, Any]:
    if not is_valid_weights_file(weights_path):
        return {
            "model_loadable": False,
            "inference_ready": False,
            "error": "Weights file is missing or invalid",
        }
    try:
        import cv2  # noqa: F401
        import numpy as np
        from ultralytics import YOLO
    except Exception as exc:
        return {
            "model_loadable": False,
            "inference_ready": False,
            "error": f"Required runtime imports failed: {type(exc).__name__}",
        }

    try:
        detector = YOLO(str(weights_path))
    except Exception as exc:
        return {
            "model_loadable": False,
            "inference_ready": False,
            "error": f"Model load failed: {type(exc).__name__}",
        }

    try:
        # Synthetic 320x320 RGB frame for real forward-pass verification without user media.
        frame = np.zeros((320, 320, 3), dtype=np.uint8)
        cv2.circle(frame, (160, 90), 22, (220, 220, 220), -1)
        cv2.line(frame, (160, 112), (160, 220), (200, 200, 200), 10)
        results = detector.predict(source=frame, conf=0.25, verbose=False)
        if results is None:
            raise RuntimeError("Empty predict result")
        return {
            "model_loadable": True,
            "inference_ready": True,
            "error": None,
        }
    except Exception as exc:
        return {
            "model_loadable": True,
            "inference_ready": False,
            "error": f"Inference verification failed: {type(exc).__name__}",
        }


def clear_runtime_cache() -> None:
    _INFERENCE_CACHE.clear()


def get_yolo_runtime_status(*, verify_inference: bool = False) -> dict[str, Any]:
    eff = get_effective_yolo_config()
    yolo_enabled = bool(eff["enabled"])

    torch_ok = _module_available("torch")
    torchvision_ok = _module_available("torchvision")
    ultralytics_ok = _module_available("ultralytics")
    cv_info = resolve_opencv_conflicts(auto_fix=False)
    cv_ok = cv_info["opencv_importable"]

    model_cfg, found_path = find_weights_file()
    model_label = Path(model_cfg).name or DEFAULT_MODEL_FILENAME
    weights_present = found_path is not None
    weights_valid = is_valid_weights_file(found_path) if found_path is not None else False

    deps_ok = torch_ok and ultralytics_ok and cv_ok
    model_loadable = False
    inference_ready = False
    verify_error: str | None = None

    if not yolo_enabled:
        status = "not_configured"
        mode = "lightweight"
        reason = (
            "Lightweight core mode active: YOLO Pose is disabled "
            f"({eff['source']}). Any installed packages or local weights are preserved and not loaded."
        )
    else:
        if deps_ok and weights_valid and found_path is not None:
            cache_key = f"{found_path.name}:{found_path.stat().st_size}:{int(found_path.stat().st_mtime)}"
            if verify_inference or cache_key not in _INFERENCE_CACHE:
                _INFERENCE_CACHE[cache_key] = verify_model_load_and_inference(found_path)
            cached = _INFERENCE_CACHE[cache_key]
            model_loadable = bool(cached["model_loadable"])
            inference_ready = bool(cached["inference_ready"])
            verify_error = cached.get("error")

        if deps_ok and weights_valid and model_loadable and inference_ready:
            status = "available"
            mode = "full"
            reason = (
                f"YOLO Pose ready ({model_label}): PyTorch, Ultralytics, OpenCV, weights load, "
                "and real inference verified. Geometric keypoints only; not medical diagnosis."
            )
        elif not deps_ok and not weights_present:
            status = "not_configured"
            mode = "lightweight"
            reason = (
                "Lightweight core mode active: optional YOLO Pose dependencies (PyTorch, Ultralytics, "
                "OpenCV Headless) and model weights are not installed."
            )
        elif not deps_ok:
            status = "unavailable"
            mode = "lightweight"
            missing = [
                name
                for name, ok in (
                    ("PyTorch", torch_ok),
                    ("Ultralytics", ultralytics_ok),
                    ("OpenCV", cv_ok),
                )
                if not ok
            ]
            reason = f"YOLO Pose unavailable: missing {', '.join(missing)}."
        elif not weights_present:
            status = "not_configured"
            mode = "lightweight"
            reason = (
                f"YOLO dependencies installed, but weights '{model_label}' are not present yet. "
                "Run install_yolo.sh / install_yolo.bat to download and verify them."
            )
        elif not weights_valid:
            status = "error"
            mode = "lightweight"
            reason = f"YOLO weights '{model_label}' appear incomplete or corrupted; re-run YOLO setup."
        else:
            status = "error"
            mode = "lightweight"
            reason = verify_error or f"YOLO model '{model_label}' failed load or inference verification."

    return {
        "status": status,
        "mode": mode,
        "yolo_enabled": yolo_enabled,
        "mode_source": eff["source"],
        "model": model_label,
        "torch_installed": torch_ok,
        "torchvision_installed": torchvision_ok,
        "ultralytics_installed": ultralytics_ok,
        "opencv_installed": cv_ok,
        "opencv_headless_installed": cv_info["opencv_headless_installed"],
        "opencv_gui_installed": cv_info["opencv_gui_installed"],
        "opencv_conflict": cv_info["opencv_conflict"],
        "weights_present": weights_present,
        "weights_valid": weights_valid,
        "model_loadable": model_loadable,
        "inference_ready": inference_ready,
        "reason": reason,
    }


def install_yolo_stack(*, skip_deps: bool = False) -> dict[str, Any]:
    root = get_project_root()
    steps: list[dict[str, Any]] = []

    skip_env = (os.getenv("LATIRA_SKIP_YOLO_SETUP") or "").strip().lower()
    if skip_env in _TRUTHY:
        set_persisted_pose_mode("light")
        return {
            "ok": False,
            "skipped": True,
            "error": "YOLO Pose preparation disabled by LATIRA_SKIP_YOLO_SETUP=1",
            "steps": steps,
            "status": get_yolo_runtime_status(verify_inference=False),
        }

    if sys.version_info < (3, 10):
        return {
            "ok": False,
            "error": f"Python 3.10+ required; detected {sys.version.split()[0]}",
            "steps": steps,
            "status": get_yolo_runtime_status(verify_inference=False),
        }

    if not skip_deps:
        ok, out = _run_pip(["install", "--upgrade", "pip"])
        steps.append({"step": "pip_upgrade", "ok": ok})

        # Install CPU PyTorch + torchvision first to avoid incompatible/GPU mismatch wheels.
        ok, out = _run_pip(
            [
                "install",
                "--index-url",
                PYTORCH_CPU_INDEX_URL,
                "torch>=2.2,<3",
                "torchvision>=0.17,<1",
            ]
        )
        steps.append({"step": "pytorch_cpu", "ok": ok, "detail": "" if ok else out[-400:]})
        if not ok:
            return {
                "ok": False,
                "error": "Failed installing CPU PyTorch/torchvision",
                "steps": steps,
                "status": get_yolo_runtime_status(verify_inference=False),
            }

        ai_req = root / "ai" / "requirements.txt"
        ok, out = _run_pip(["install", "-r", str(ai_req)])
        steps.append({"step": "ai_requirements", "ok": ok, "detail": "" if ok else out[-400:]})
        if not ok:
            return {
                "ok": False,
                "error": "Failed installing ai/requirements.txt",
                "steps": steps,
                "status": get_yolo_runtime_status(verify_inference=False),
            }

        cv_res = resolve_opencv_conflicts(auto_fix=True)
        steps.append({"step": "opencv_headless_check", "ok": not cv_res["opencv_conflict"] and cv_res["opencv_importable"], "detail": cv_res["actions"]})

    cfg, found = find_weights_file()
    if found is None or not is_valid_weights_file(found):
        target = found if found is not None else (get_models_dir() / Path(cfg).name)
        dl_ok, dl_msg = download_weights(target)
        steps.append({"step": "weights_download", "ok": dl_ok, "detail": dl_msg})
        if not dl_ok:
            return {
                "ok": False,
                "error": dl_msg,
                "steps": steps,
                "status": get_yolo_runtime_status(verify_inference=False),
            }
    else:
        steps.append({"step": "weights_check", "ok": True, "detail": f"Valid local weights: {found.name}"})

    set_persisted_pose_mode("full")
    clear_runtime_cache()
    status = get_yolo_runtime_status(verify_inference=True)
    ok = status["status"] == "available" and status["model_loadable"] and status["inference_ready"]
    return {
        "ok": ok,
        "error": None if ok else status["reason"],
        "steps": steps,
        "status": status,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LÁTIRA 2.0 YOLO Pose setup & verification")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--install", action="store_true", help="Install CPU PyTorch, Ultralytics, OpenCV Headless, download weights, and verify inference")
    group.add_argument("--verify", action="store_true", help="Verify installed libraries, weights, model load, and real inference")
    group.add_argument("--check", action="store_true", help="Report current availability without modifying packages or downloading")
    group.add_argument("--disable", "--light", dest="disable", action="store_true", help="Persist lightweight mode (disable YOLO without uninstalling packages)")
    group.add_argument("--enable", action="store_true", help="Persist full mode configuration without modifying installed packages")
    parser.add_argument("--skip-deps", action="store_true", help="With --install, skip pip installs and only download/verify weights")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    args = parser.parse_args(argv)

    if args.disable:
        set_persisted_pose_mode("light")
        status = get_yolo_runtime_status(verify_inference=False)
        print(json.dumps(status, indent=2, ensure_ascii=args.json))
        return 0

    if args.enable:
        set_persisted_pose_mode("full")
        status = get_yolo_runtime_status(verify_inference=False)
        print(json.dumps(status, indent=2, ensure_ascii=args.json))
        return 0

    if args.install:
        result = install_yolo_stack(skip_deps=args.skip_deps)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["ok"] else 1

    verify_inf = bool(args.verify)
    status = get_yolo_runtime_status(verify_inference=verify_inf)
    if args.json:
        print(json.dumps(status, indent=2))
    else:
        print(json.dumps(status, indent=2, ensure_ascii=False))

    if args.verify:
        return 0 if status["status"] == "available" else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
