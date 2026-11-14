import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ai.thermography import analyze_thermal_image
from ai.nasa_sources import source_registry
from ai.yolo_video import validate_video_upload, summarize_keypoints


class AdapterTests(unittest.TestCase):
    def test_thermal_image_reports_image_only_without_core_temperature(self):
        result = analyze_thermal_image(b"thermal bytes", filename="heat.png")
        self.assertEqual(result["status"], "user_image_received")
        self.assertNotIn("core_temperature", result)
        self.assertFalse(result["core_temperature_inferred"])

    def test_nasa_registry_contains_verified_official_sources_without_false_connections(self):
        sources = source_registry()
        ids = {s["id"] for s in sources}
        self.assertTrue({
            "nasa-hrp-hazards",
            "nasa-hrp-risks",
            "nasa-hrp-ongoing-research",
            "csa-cans-radiation",
            "csa-iss-science",
        }.issubset(ids))
        self.assertTrue(all(s["verification_status"] != "connected" for s in sources))

    def test_video_upload_validation_and_keypoint_summary(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "clip.mp4"
            p.write_bytes(b"x")
            self.assertEqual(validate_video_upload(str(p)), p)
        summary = summarize_keypoints([[10, 20, .9], [30, 40, .8]])
        self.assertEqual(summary["visible_keypoints"], 2)
        self.assertAlmostEqual(summary["mean_confidence"], .85)

    def test_find_saved_video_detects_avi_output(self):
        from ai.yolo_video import _find_saved_video
        with TemporaryDirectory() as d:
            run_dir = Path(d) / "run"
            run_dir.mkdir()
            avi = run_dir / "clip.avi"
            avi.write_bytes(b"RIFF")
            self.assertEqual(_find_saved_video(run_dir, "clip.mp4"), avi)


if __name__ == "__main__":
    unittest.main()
