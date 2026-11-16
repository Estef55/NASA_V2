"""Tests for ai.setup_yolo cross-platform installer, conflict check, and runtime status."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai import setup_yolo


class SetupYoloTests(unittest.TestCase):
    def setUp(self):
        setup_yolo.clear_runtime_cache()

    def test_lightweight_mode_when_dependencies_and_weights_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing_model = Path(tmp) / "missing.pt"
            with (
                patch.dict(os.environ, {"YOLO_POSE_MODEL": str(missing_model)}),
                patch.object(setup_yolo, "_module_available", return_value=False),
                patch.object(setup_yolo, "_dist_installed", return_value=False),
            ):
                st = setup_yolo.get_yolo_runtime_status(verify_inference=False)
        self.assertEqual(st["status"], "not_configured")
        self.assertEqual(st["mode"], "lightweight")
        self.assertFalse(st["torch_installed"])
        self.assertFalse(st["ultralytics_installed"])
        self.assertFalse(st["opencv_installed"])
        self.assertFalse(st["weights_present"])
        self.assertFalse(st["model_loadable"])
        self.assertFalse(st["inference_ready"])
        self.assertNotIn(tmp, st["reason"])
        self.assertNotIn(tmp, st["model"])

    def test_controlled_download_failure_leaves_no_partial_weights(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "models" / "yolo11n-pose.pt"
            with patch("urllib.request.urlopen", side_effect=OSError("network unreachable")):
                ok, msg = setup_yolo.download_weights(target, url="https://example.invalid/yolo11n-pose.pt")
            self.assertFalse(ok)
            self.assertIn("Download failed", msg)
            self.assertFalse(target.exists())
            self.assertFalse(target.with_suffix(".pt.part").exists())

    def test_corrupt_or_undersized_weights_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "yolo11n-pose.pt"
            bad.write_bytes(b"not a real checkpoint")
            self.assertFalse(setup_yolo.is_valid_weights_file(bad))

            # Valid zip but below MIN_WEIGHTS_BYTES
            small_zip = Path(tmp) / "small.pt"
            with zipfile.ZipFile(small_zip, "w") as zf:
                zf.writestr("data.pkl", b"x")
            self.assertFalse(setup_yolo.is_valid_weights_file(small_zip))

            # Valid zip above MIN_WEIGHTS_BYTES
            good_zip = Path(tmp) / "good.pt"
            with zipfile.ZipFile(good_zip, "w") as zf:
                zf.writestr("data.pkl", b"0" * (setup_yolo.MIN_WEIGHTS_BYTES + 128))
            self.assertTrue(setup_yolo.is_valid_weights_file(good_zip))

    def test_opencv_conflict_detection(self):
        def fake_dist(name: str) -> bool:
            return name in {"opencv-python", "opencv-python-headless"}

        with (
            patch.object(setup_yolo, "_dist_installed", side_effect=fake_dist),
            patch.object(setup_yolo, "_module_available", return_value=True),
        ):
            info = setup_yolo.resolve_opencv_conflicts(auto_fix=False)
        self.assertTrue(info["opencv_gui_installed"])
        self.assertTrue(info["opencv_headless_installed"])
        self.assertTrue(info["opencv_conflict"])

    def test_full_mode_reported_only_when_load_and_inference_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            weights = Path(tmp) / "yolo11n-pose.pt"
            with zipfile.ZipFile(weights, "w") as zf:
                zf.writestr("data.pkl", b"1" * (setup_yolo.MIN_WEIGHTS_BYTES + 128))
            with (
                patch.dict(os.environ, {"YOLO_POSE_MODEL": str(weights)}),
                patch.object(setup_yolo, "_module_available", return_value=True),
                patch.object(setup_yolo, "_dist_installed", side_effect=lambda n: n == "opencv-python-headless"),
                patch.object(
                    setup_yolo,
                    "verify_model_load_and_inference",
                    return_value={"model_loadable": True, "inference_ready": True, "error": None},
                ),
            ):
                st = setup_yolo.get_yolo_runtime_status(verify_inference=True)
        self.assertEqual(st["status"], "available")
        self.assertEqual(st["mode"], "full")
        self.assertTrue(st["weights_present"])
        self.assertTrue(st["weights_valid"])
        self.assertTrue(st["model_loadable"])
        self.assertTrue(st["inference_ready"])
        self.assertFalse(st["opencv_conflict"])

    def test_switch_from_full_to_light_disables_yolo_even_with_installed_deps_and_weights(self):
        from ai import yolo_video

        with tempfile.TemporaryDirectory() as tmp:
            weights = Path(tmp) / "yolo11n-pose.pt"
            mode_file = Path(tmp) / "pose_mode.json"
            with zipfile.ZipFile(weights, "w") as zf:
                zf.writestr("data.pkl", b"1" * (setup_yolo.MIN_WEIGHTS_BYTES + 128))
            base_env = {
                "YOLO_POSE_MODEL": str(weights),
                "LATIRA_POSE_MODE_FILE": str(mode_file),
                "LATIRA_MODE": "",
                "LATIRA_SKIP_YOLO_SETUP": "",
                "LATIRA_YOLO_ENABLED": "",
            }
            with (
                patch.dict(os.environ, base_env),
                patch.object(setup_yolo, "_module_available", return_value=True),
                patch.object(setup_yolo, "_dist_installed", side_effect=lambda n: n == "opencv-python-headless"),
                patch.object(
                    setup_yolo,
                    "verify_model_load_and_inference",
                    return_value={"model_loadable": True, "inference_ready": True, "error": None},
                ) as mock_verify,
            ):
                setup_yolo.set_persisted_pose_mode("full")
                full_st = setup_yolo.get_yolo_runtime_status(verify_inference=True)
                self.assertEqual(full_st["status"], "available")
                self.assertEqual(full_st["mode"], "full")
                self.assertTrue(full_st["yolo_enabled"])
                self.assertEqual(mock_verify.call_count, 1)

                # Switch same directory to lightweight mode via CLI --disable
                rc = setup_yolo.main(["--disable", "--json"])
                self.assertEqual(rc, 0)

                # Simulate process restart by clearing cache and querying status again
                setup_yolo.clear_runtime_cache()
                light_st = setup_yolo.get_yolo_runtime_status(verify_inference=True)
                self.assertEqual(light_st["status"], "not_configured")
                self.assertEqual(light_st["mode"], "lightweight")
                self.assertFalse(light_st["yolo_enabled"])
                self.assertFalse(light_st["model_loadable"])
                self.assertFalse(light_st["inference_ready"])
                # Packages and weights were NOT deleted
                self.assertTrue(weights.is_file())
                self.assertTrue(light_st["torch_installed"])
                self.assertTrue(light_st["weights_present"])
                # Verify inference/model load was NOT called in lightweight mode
                self.assertEqual(mock_verify.call_count, 1)

                # yolo_video must also refuse to load or run models in lightweight mode
                with self.assertRaises(RuntimeError) as ctx:
                    yolo_video.process_frame_bytes(b"\xff\xd8\xff\xe0test")
                self.assertIn("not_configured", str(ctx.exception))

    def test_skip_yolo_setup_env_disables_install_and_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            mode_file = Path(tmp) / "pose_mode.json"
            with (
                patch.dict(
                    os.environ,
                    {
                        "LATIRA_POSE_MODE_FILE": str(mode_file),
                        "LATIRA_SKIP_YOLO_SETUP": "1",
                        "LATIRA_MODE": "full",
                    },
                ),
                patch.object(setup_yolo, "_module_available", return_value=True),
                patch.object(setup_yolo, "verify_model_load_and_inference") as mock_verify,
            ):
                res = setup_yolo.install_yolo_stack()
                self.assertFalse(res["ok"])
                self.assertTrue(res.get("skipped"))
                self.assertEqual(res["status"]["status"], "not_configured")
                self.assertEqual(res["status"]["mode"], "lightweight")
                self.assertFalse(res["status"]["yolo_enabled"])
                mock_verify.assert_not_called()

    def test_yolo_video_rejects_missing_or_corrupt_weights_without_download(self):
        from ai import yolo_video

        with tempfile.TemporaryDirectory() as tmp:
            mode_file = Path(tmp) / "pose_mode.json"
            corrupt = Path(tmp) / "corrupt.pt"
            corrupt.write_bytes(b"corrupt")
            with patch.dict(
                os.environ,
                {
                    "LATIRA_POSE_MODE_FILE": str(mode_file),
                    "LATIRA_MODE": "full",
                    "LATIRA_SKIP_YOLO_SETUP": "",
                    "LATIRA_YOLO_ENABLED": "",
                },
            ):
                setup_yolo.set_persisted_pose_mode("full")
                with patch.dict("sys.modules", {"ultralytics": type("U", (), {"YOLO": lambda *_: None})()}):
                    with self.assertRaises(RuntimeError) as ctx_missing:
                        yolo_video._get_yolo_model(str(Path(tmp) / "missing.pt"))
                    self.assertIn("not_configured", str(ctx_missing.exception))

                    with self.assertRaises(RuntimeError) as ctx_corrupt:
                        yolo_video._get_yolo_model(str(corrupt))
                    self.assertIn("not_configured", str(ctx_corrupt.exception))


if __name__ == "__main__":
    unittest.main()
