"""Verification tests for the five final stabilization fixes in LÁTIRA 2.0."""
from __future__ import annotations

import csv
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))
from _db_isolation import configure_isolated_test_db

configure_isolated_test_db()

from fastapi.testclient import TestClient
import app.database as database
import app.main as main
from app import demo_tools
from app.main import app, conn, hash_password


class FinalStabilizationFixesTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        with conn() as db:
            db.execute("DELETE FROM audit")
            db.execute("DELETE FROM sessions")
            db.execute("DELETE FROM followups")
            db.execute("DELETE FROM alerts")
            db.execute("DELETE FROM checkins")
            db.execute("DELETE FROM conversations")
            db.execute("DELETE FROM metrics")
            db.execute("DELETE FROM assignments")
            db.execute("DELETE FROM demo_owner_state")
            db.execute("UPDATE demo_state SET day=0, active=0 WHERE id=1")
            db.execute("DELETE FROM users")
            for uname, role, aid in [
                ("astro1", "astronaut", "AST-001"),
                ("astro2", "astronaut", "AST-002"),
                ("medic1", "medic", None),
                ("admin1", "admin", None),
            ]:
                db.execute(
                    "INSERT INTO users(username,password_hash,role,astronaut_id) VALUES(?,?,?,?)",
                    (uname, hash_password("[REDACTED]"), role, aid),
                )
            db.execute("INSERT INTO assignments(medic_username,astronaut_id) VALUES('medic1','AST-001')")
        self.tokens = {
            name: self.client.post("/api/auth/login", json={"username": name, "password": "[REDACTED]"}).json()["token"]
            for name in ("astro1", "astro2", "medic1", "admin1")
        }

    def h(self, user: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens[user]}"}

    def test_demo_reset_and_restart_delete_demo_followups_without_orphans_or_real_loss(self):
        # Seed a real metric & real alert + followup for AST-001, plus demo alert + followup for AST-002
        with conn() as db:
            cur_real = db.execute(
                "INSERT INTO alerts(astronaut_id,created_at,priority,reason,demo) VALUES('AST-001','2026-06-01T00:00:00Z','review','Real clinical alert',0)"
            )
            real_alert_id = cur_real.lastrowid
            cur_other = db.execute(
                "INSERT INTO alerts(astronaut_id,created_at,priority,reason,demo) VALUES('AST-002','2026-06-01T00:00:00Z','review','Other astro demo alert',1)"
            )
            other_alert_id = cur_other.lastrowid
            db.execute(
                "INSERT INTO followups(alert_id,author,note,created_at) VALUES(?,'medic_other','Other astro demo note','2026-06-01T01:00:00Z')",
                (other_alert_id,),
            )

        self.assertEqual(
            self.client.post(f"/api/alerts/{real_alert_id}/followups", headers=self.h("medic1"), json={"note": "Real followup note"}).status_code,
            200,
        )

        # Run full demo scenario for AST-001 (5 days -> generates demo=1 alerts) and attach followups to demo alerts
        self.assertEqual(self.client.post("/api/demo/start", headers=self.h("astro1")).status_code, 200)
        for _ in range(4):
            self.assertEqual(self.client.post("/api/demo/next", headers=self.h("astro1")).status_code, 200)

        demo_alerts = [a for a in self.client.get("/api/alerts", headers=self.h("astro1")).json() if a["demo"] == 1]
        self.assertTrue(demo_alerts)
        for da in demo_alerts:
            self.assertEqual(
                self.client.post(
                    f"/api/alerts/{da['id']}/followups",
                    headers=self.h("medic1"),
                    json={"note": f"Demo followup for alert {da['id']}"},
                ).status_code,
                200,
            )

        # 1) demo_reset must remove demo followups first, leaving 0 orphans and preserving real/other data
        self.assertEqual(self.client.post("/api/demo/reset", headers=self.h("astro1")).status_code, 200)
        with conn() as db:
            orphans = db.execute(
                "SELECT COUNT(*) FROM followups WHERE alert_id NOT IN (SELECT id FROM alerts)"
            ).fetchone()[0]
            self.assertEqual(orphans, 0)
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM alerts WHERE demo=1 AND astronaut_id='AST-001'").fetchone()[0],
                0,
            )
            real_fups = db.execute("SELECT note FROM followups WHERE alert_id=?", (real_alert_id,)).fetchall()
            self.assertEqual([r["note"] for r in real_fups], ["Real followup note"])
            self.assertEqual(db.execute("SELECT COUNT(*) FROM alerts WHERE id=?", (other_alert_id,)).fetchone()[0], 1)
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])

        # 2) Repeat scenario and invoke demo_start directly while active -> must also leave 0 orphans
        self.assertEqual(self.client.post("/api/demo/start", headers=self.h("astro1")).status_code, 200)
        for _ in range(4):
            self.assertEqual(self.client.post("/api/demo/next", headers=self.h("astro1")).status_code, 200)
        demo_alerts_2 = [a for a in self.client.get("/api/alerts", headers=self.h("astro1")).json() if a["demo"] == 1]
        self.assertTrue(demo_alerts_2)
        self.assertEqual(
            self.client.post(
                f"/api/alerts/{demo_alerts_2[0]['id']}/followups",
                headers=self.h("medic1"),
                json={"note": "Second demo cycle followup"},
            ).status_code,
            200,
        )

        restarted = self.client.post("/api/demo/start", headers=self.h("astro1"))
        self.assertEqual(restarted.status_code, 200)
        self.assertEqual(restarted.json()["state"]["day"], 1)
        with conn() as db:
            orphans = db.execute(
                "SELECT COUNT(*) FROM followups WHERE alert_id NOT IN (SELECT id FROM alerts)"
            ).fetchone()[0]
            self.assertEqual(orphans, 0)
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_pose_routes_return_503_not_configured_in_lightweight_mode_across_restart(self):
        from ai import setup_yolo

        jpeg_header = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        mp4_header = bytes.fromhex("000000186674797069736f6d00000000")

        with tempfile.TemporaryDirectory() as tmp:
            mode_file = Path(tmp) / "pose_mode.json"
            setup_env = {
                "LATIRA_POSE_MODE_FILE": str(mode_file),
                "LATIRA_MODE": "",
                "LATIRA_SKIP_YOLO_SETUP": "",
                "LATIRA_YOLO_ENABLED": "",
            }
            with patch.dict(os.environ, setup_env):
                # Switch to lightweight mode via persisted config (simulating run.sh --light after --full)
                setup_yolo.set_persisted_pose_mode("light")
                # Simulate application restart with a fresh TestClient and cleared cache
                setup_yolo.clear_runtime_cache()
                restarted_client = TestClient(app)

                with (
                    patch("app.routers.pose.process_frame_bytes") as mock_frame,
                    patch("app.routers.pose.process_video") as mock_video,
                ):
                    st = restarted_client.get("/api/pose/status", headers=self.h("astro1"))
                    self.assertEqual(st.status_code, 200)
                    self.assertEqual(st.json()["status"], "not_configured")
                    self.assertEqual(st.json()["mode"], "lightweight")
                    self.assertFalse(st.json()["yolo_enabled"])

                    r_frame = restarted_client.post(
                        "/api/pose/frame",
                        headers=self.h("astro1"),
                        files={"file": ("frame.jpg", jpeg_header, "image/jpeg")},
                    )
                    self.assertEqual(r_frame.status_code, 503)
                    self.assertIn("not_configured", r_frame.json()["detail"])

                    r_proc = restarted_client.post(
                        "/api/pose/process",
                        headers=self.h("astro1"),
                        files={"file": ("clip.mp4", mp4_header, "video/mp4")},
                    )
                    self.assertEqual(r_proc.status_code, 503)
                    self.assertIn("not_configured", r_proc.json()["detail"])

                    r_live = restarted_client.post(
                        "/api/pose/live/complete",
                        headers=self.h("astro1"),
                        json={"frames": [{"frame": 1, "visible_keypoints": 5}]},
                    )
                    self.assertEqual(r_live.status_code, 503)
                    self.assertIn("not_configured", r_live.json()["detail"])

                    mock_frame.assert_not_called()
                    mock_video.assert_not_called()

    def test_demo_tools_secure_prepare_show_reset_and_production_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            cred_file = Path(tmp) / ".demo_credentials.json"
            with patch.dict(
                os.environ,
                {"LATIRA_ENV": "production", "LATIRA_DEMO_CREDENTIALS_FILE": str(cred_file)},
            ):
                with self.assertRaises(demo_tools.DemoToolError):
                    demo_tools.prepare_demo_environment()
                with self.assertRaises(demo_tools.DemoToolError):
                    demo_tools.get_demo_credentials()

            # Pre-seed an existing user and real metric to ensure prepare/reset never overwrite them
            with conn() as db:
                db.execute(
                    "INSERT INTO users(username,password_hash,role,astronaut_id) VALUES('real_crew', ?, 'astronaut', 'AST-REAL')",
                    (hash_password("RealCrewStrongPass99!"),),
                )
                db.execute(
                    "INSERT INTO metrics(astronaut_id,recorded_at,sleep,source,demo) VALUES('AST-001','2026-06-01T08:00:00Z',7.9,'manual',0)"
                )

            with patch.dict(
                os.environ,
                {"LATIRA_ENV": "demo", "LATIRA_DEMO_LOGIN": "", "LATIRA_DEMO_CREDENTIALS_FILE": str(cred_file)},
            ):
                prep = demo_tools.prepare_demo_environment(scenario_days=5)
                self.assertTrue(prep["ok"])
                self.assertEqual(set(prep["created_accounts"]), {"astro_demo", "medic_demo", "admin_demo"})
                self.assertEqual(prep["scenario_days"], 5)

                shown = demo_tools.get_demo_credentials()
                pwds = {a["username"]: a["password"] for a in shown["accounts"]}
                self.assertEqual(len(set(pwds.values())), 3)
                for uname, pwd in pwds.items():
                    self.assertGreaterEqual(len(pwd), 20)
                    login_res = self.client.post("/api/auth/login", json={"username": uname, "password": pwd})
                    self.assertEqual(login_res.status_code, 200)

                # Running prepare a second time must NOT overwrite existing demo accounts or real users
                prep2 = demo_tools.prepare_demo_environment(scenario_days=2)
                self.assertEqual(prep2["created_accounts"], [])
                self.assertEqual(set(prep2["preserved_existing_accounts"]), {"astro_demo", "medic_demo", "admin_demo"})
                shown2 = demo_tools.get_demo_credentials()
                pwds2 = {a["username"]: a["password"] for a in shown2["accounts"]}
                self.assertEqual(pwds, pwds2)

                # Reset demo scenario without touching real_crew or demo=0 metrics
                rst = demo_tools.reset_demo_environment()
                self.assertTrue(rst["ok"])
                with conn() as db:
                    self.assertEqual(db.execute("SELECT COUNT(*) FROM metrics WHERE demo=1").fetchone()[0], 0)
                    self.assertEqual(db.execute("SELECT COUNT(*) FROM metrics WHERE demo=0 AND astronaut_id='AST-001'").fetchone()[0], 1)
                    self.assertIsNotNone(db.execute("SELECT 1 FROM users WHERE username='real_crew'").fetchone())

    def test_demo_tools_cli_subprocess_fresh_db_and_sqlite_integrity(self):
        import json
        import sqlite3
        import subprocess

        backend_dir = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "cli_demo.sqlite3"
            cred_path = Path(tmp) / ".demo_credentials.json"
            env = {
                **os.environ,
                "LATIRA_ENV": "demo",
                "LATIRA_DEMO_LOGIN": "",
                "LATIRA_DEMO_PASSWORD": "",
                "LATIRA_DB_PATH": str(db_path),
                "LATIRA_DEMO_CREDENTIALS_FILE": str(cred_path),
                "PYTHONPATH": str(backend_dir),
            }
            prep = subprocess.run(
                [sys.executable, "-m", "app.demo_tools", "prepare", "--days", "3", "--json"],
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            prep_data = json.loads(prep.stdout)
            self.assertTrue(prep_data["ok"])
            self.assertEqual(set(prep_data["created_accounts"]), {"astro_demo", "medic_demo", "admin_demo"})

            shown = subprocess.run(
                [sys.executable, "-m", "app.demo_tools", "show", "--json"],
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            shown_data = json.loads(shown.stdout)
            for acc in shown_data["accounts"]:
                self.assertEqual(acc["password_status"], "available_locally")
                self.assertGreaterEqual(len(acc["password"]), 24)

            rst = subprocess.run(
                [sys.executable, "-m", "app.demo_tools", "reset", "--json"],
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertTrue(json.loads(rst.stdout)["ok"])
            with sqlite3.connect(db_path) as db:
                db.execute("PRAGMA foreign_keys=ON")
                self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_csv_report_always_emits_all_11_columns_matching_sqlite_and_rbac(self):
        expected_cols = [
            "id",
            "astronaut_id",
            "day",
            "recorded_at",
            "sleep",
            "heart_rate",
            "fatigue",
            "mood",
            "source",
            "demo",
            "unit",
        ]
        # Empty CSV must still contain all 11 columns
        empty_res = self.client.get("/api/admin/reports/astronauts.csv?astronaut_id=AST-001&demo=false", headers=self.h("medic1"))
        self.assertEqual(empty_res.status_code, 200)
        empty_rows = list(csv.reader(io.StringIO(empty_res.text)))
        self.assertEqual(empty_rows, [expected_cols])

        # Seed real metric and verify exact match with SQLite
        self.client.post(
            "/api/metrics",
            headers=self.h("astro1"),
            json={"sleep": 7.5, "heart_rate": 64, "fatigue": 2, "mood": 4, "source": "manual", "unit": "mixed", "recorded_at": "2026-06-01T08:00:00Z"},
        )
        full_res = self.client.get("/api/admin/reports/astronauts.csv?astronaut_id=AST-001&demo=false", headers=self.h("medic1"))
        self.assertEqual(full_res.status_code, 200)
        parsed = list(csv.reader(io.StringIO(full_res.text)))
        self.assertEqual(parsed[0], expected_cols)
        self.assertEqual(len(parsed), 2)
        with conn() as db:
            db_row = db.execute("SELECT id,astronaut_id,day,recorded_at,sleep,heart_rate,fatigue,mood,source,demo,unit FROM metrics WHERE astronaut_id='AST-001' AND demo=0").fetchone()
        self.assertEqual(parsed[1], ["" if db_row[c] is None else str(db_row[c]) for c in expected_cols])

        # RBAC: astro and admin rejected (403); unassigned AST-002 rejected (404)
        self.assertEqual(self.client.get("/api/admin/reports/astronauts.csv", headers=self.h("astro1")).status_code, 403)
        self.assertEqual(self.client.get("/api/admin/reports/astronauts.csv", headers=self.h("admin1")).status_code, 403)
        self.assertEqual(self.client.get("/api/admin/reports/astronauts.csv?astronaut_id=AST-002", headers=self.h("medic1")).status_code, 404)


if __name__ == "__main__":
    unittest.main()
