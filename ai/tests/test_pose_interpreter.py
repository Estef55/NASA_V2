"""Unit tests for plain-language YOLO Pose geometric interpreter."""
from __future__ import annotations

import unittest

from ai.pose_interpreter import compute_person_geometry, interpret_pose_sequence


def _make_keypoints(*, trunk_dx: float = 0.0, shoulder_dy: float = 0.0, conf: float = 0.9, include_legs: bool = True):
    # 17 COCO keypoints: [x, y, conf]
    pts = [[0.0, 0.0, 0.0] for _ in range(17)]
    pts[0] = [320 + trunk_dx, 80, conf]           # nose
    pts[5] = [280 + trunk_dx, 140, conf]          # left_shoulder
    pts[6] = [360 + trunk_dx, 140 + shoulder_dy, conf]  # right_shoulder
    pts[7] = [260 + trunk_dx, 200, conf]          # left_elbow
    pts[8] = [380 + trunk_dx, 200, conf]          # right_elbow
    pts[9] = [255 + trunk_dx, 250, conf]          # left_wrist
    pts[10] = [385 + trunk_dx, 250, conf]         # right_wrist
    pts[11] = [290, 280, conf]                    # left_hip
    pts[12] = [350, 280, conf]                    # right_hip
    if include_legs:
        pts[13] = [290, 360, conf]                # left_knee
        pts[14] = [350, 360, conf]                # right_knee
        pts[15] = [290, 440, conf]                # left_ankle
        pts[16] = [350, 440, conf]                # right_ankle
    return pts


class PoseInterpreterTests(unittest.TestCase):
    def test_geometry_upright_vs_inclined_and_shoulder_tilt(self):
        upright = compute_person_geometry(_make_keypoints(trunk_dx=0.0, shoulder_dy=0.0))
        self.assertLess(upright["trunk_inclination_deg"], 5.0)
        self.assertLess(upright["shoulder_tilt_deg"], 2.0)
        self.assertTrue(upright["regions"]["upper_body_visible"])
        self.assertTrue(upright["regions"]["lower_body_visible"])

        inclined = compute_person_geometry(_make_keypoints(trunk_dx=75.0, shoulder_dy=20.0))
        self.assertGreater(inclined["trunk_inclination_deg"], 20.0)
        self.assertGreater(inclined["shoulder_tilt_deg"], 10.0)

    def test_insufficient_data_does_not_invent_findings(self):
        res = interpret_pose_sequence(
            [{"frame": 1, "visible_keypoints": 0, "mean_confidence": None}],
            source_mode="live",
            input_name="Cámara en vivo",
        )
        self.assertEqual(res["status"], "insufficient_data")
        self.assertEqual(res["confidence_band"], "insufficient")
        self.assertIn("No se obtuvo información suficiente", res["observations"]["es"][0])
        self.assertIn("No constituye un diagnóstico médico", res["non_diagnostic_notice"]["es"])
        self.assertTrue(res["limitations"]["es"])

    def test_inclined_sequence_generates_plain_spanish_summary_and_human_review_flag(self):
        frames = []
        for idx in range(6):
            geom = compute_person_geometry(
                _make_keypoints(trunk_dx=10.0 + idx * 18.0, shoulder_dy=15.0 if idx >= 3 else 0.0, include_legs=False)
            )
            frames.append({
                "frame": idx + 1,
                "timestamp_s": round(idx * 0.5, 2),
                "visible_keypoints": geom["visible_keypoints"],
                "mean_confidence": geom["mean_confidence"],
                "trunk_inclination_deg": geom["trunk_inclination_deg"],
                "shoulder_tilt_deg": geom["shoulder_tilt_deg"],
                "hip_tilt_deg": geom["hip_tilt_deg"],
                "regions": geom["regions"],
            })

        res = interpret_pose_sequence(
            frames,
            source_mode="recording",
            input_name="grabacion-test.webm",
            duration_seconds=3.0,
        )
        self.assertTrue(res["requires_human_review"])
        self.assertIn("grabación desde cámara", res["summary"]["es"])
        self.assertTrue(any("inclinada" in obs.lower() for obs in res["observations"]["es"]))
        self.assertTrue(any("piernas" in obs.lower() or "extremidades inferiores" in lim.lower()
                            for obs, lim in zip(res["observations"]["es"] + [""], res["limitations"]["es"] + [""])
                            if True))
        self.assertEqual(len(res["timeline"]), 6)
        self.assertIn("trunk_inclination_stats_deg", res["technical_details"])


if __name__ == "__main__":
    unittest.main()
