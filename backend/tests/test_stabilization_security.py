"""Stabilization, production auth, RBAC, YOLO readiness, and LÁTI error-state tests."""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))
from _db_isolation import configure_isolated_test_db

configure_isolated_test_db()

from fastapi.testclient import TestClient
from app.main import app, conn, ensure_demo_accounts, hash_password
from app.services import lati_ai


class StabilizationSecurityTests(unittest.TestCase):
    def setUp(self):
        lati_ai.reset_runtime_state()
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

    def test_production_env_blocks_demo_login_and_never_autoseeds_demo_users(self):
        with patch.dict(os.environ, {"LATIRA_ENV": "production", "LATIRA_DEMO_LOGIN": "false", "LATIRA_DEMO_PASSWORD": ""}):
            profiles = self.client.get("/api/auth/demo-profiles")
            self.assertEqual(profiles.status_code, 200)
            self.assertFalse(profiles.json()["enabled"])
            self.assertEqual(profiles.json()["profiles"], [])

            attempt = self.client.post("/api/auth/demo-login", json={"profile": "astronaut"})
            self.assertEqual(attempt.status_code, 403)

            with tempfile.TemporaryDirectory() as tmp:
                fresh_db = Path(tmp) / "fresh.sqlite3"
                c = sqlite3.connect(fresh_db)
                try:
                    c.row_factory = sqlite3.Row
                    c.execute("CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT UNIQUE, password_hash TEXT NOT NULL, role TEXT NOT NULL, astronaut_id TEXT, active INTEGER DEFAULT 1)")
                    c.execute("CREATE TABLE assignments(medic_username TEXT NOT NULL, astronaut_id TEXT NOT NULL, PRIMARY KEY(medic_username, astronaut_id))")
                    ensure_demo_accounts(c)
                    count = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
                    self.assertEqual(count, 0)
                finally:
                    c.close()

    def test_pose_status_and_integrations_expose_full_flags_without_private_paths(self):
        st = self.client.get("/api/pose/status", headers=self.h("astro1"))
        self.assertEqual(st.status_code, 200)
        body = st.json()
        for key in (
            "status",
            "mode",
            "torch_installed",
            "ultralytics_installed",
            "opencv_installed",
            "weights_present",
            "model_loadable",
            "inference_ready",
        ):
            self.assertIn(key, body)
        self.assertNotIn("/app/", str(body))
        self.assertNotIn("/home/", str(body))
        self.assertNotIn("C:\\", str(body))

        integ = self.client.get("/api/integrations", headers=self.h("admin1"))
        self.assertEqual(integ.status_code, 200)
        self.assertIn("mode", integ.json()["pose"])
        self.assertIn("inference_ready", integ.json()["pose"])

    def test_lati_status_reports_connection_error_honestly_after_timeout(self):
        env_patch = {"GEMINI_API_KEY": "secret-test-key-000", "LATIRA_LLM_API_KEY": ""}
        with (
            patch.dict(os.environ, env_patch),
            patch("app.services.lati_ai._default_http_post", side_effect=httpx.TimeoutException("timeout")),
        ):
            chat = self.client.post(
                "/api/lati/chat",
                headers=self.h("astro1"),
                json={"message": "Hola LÁTI", "language": "es", "input_mode": "text"},
            )
            self.assertEqual(chat.status_code, 200)
            self.assertTrue(chat.json()["fallback_used"])
            st = self.client.get("/api/lati/status", headers=self.h("astro1")).json()
            self.assertFalse(st["connected"])
            self.assertEqual(st["status"], "connection_error")
            self.assertEqual(st["last_error_code"], "timeout")
            self.assertNotIn("secret-test-key-000", str(st))

    def test_strict_rbac_isolation_across_all_three_roles(self):
        # Seed metric for astro2 (unassigned to medic1)
        self.client.post(
            "/api/metrics",
            headers=self.h("astro2"),
            json={"sleep": 6.5, "heart_rate": 72, "source": "manual", "unit": "mixed", "recorded_at": "2026-06-01T08:00:00Z"},
        )
        # Astro1 cannot see astro2 metrics
        m1 = self.client.get("/api/metrics", headers=self.h("astro1")).json()
        self.assertEqual(m1, [])
        # Medic1 cannot fetch unassigned astro2 detail or CSV
        self.assertEqual(self.client.get("/api/admin/astronauts/AST-002", headers=self.h("medic1")).status_code, 404)
        self.assertEqual(self.client.get("/api/admin/reports/astronauts.csv?astronaut_id=AST-002", headers=self.h("medic1")).status_code, 404)
        # Admin cannot access clinical endpoints
        for clinical_path in ("/api/metrics", "/api/alerts", "/api/baseline", "/api/checkins", "/api/conversation", "/api/thermography/history"):
            self.assertEqual(self.client.get(clinical_path, headers=self.h("admin1")).status_code, 403)


if __name__ == "__main__":
    unittest.main()
