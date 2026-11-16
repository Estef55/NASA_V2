"""Phase 2 tests for LÁTI voice metadata, external generative AI integration, privacy isolation, error fallback, and history persistence."""
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

import app.database as database
import app.main as main
from app.main import app, conn, hash_password
from app.services import lati_ai


class LatiPhase2Tests(unittest.TestCase):
    def setUp(self):
        lati_ai.reset_runtime_state()
        self.client = __import__("fastapi.testclient", fromlist=["TestClient"]).TestClient(app)
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

    def test_unconfigured_external_model_reports_honest_status_and_local_rules(self):
        clean_env = {
            "GEMINI_API_KEY": "",
            "GOOGLE_API_KEY": "",
            "LATIRA_LLM_API_KEY": "",
            "LATIRA_LLM_BASE_URL": "",
            "LATIRA_LLM_MODEL": "",
        }
        with patch.dict(os.environ, clean_env):
            st = self.client.get("/api/lati/status", headers=self.h("astro1"))
            self.assertEqual(st.status_code, 200)
            self.assertFalse(st.json()["configured"])
            self.assertEqual(st.json()["status"], "not_configured")
            self.assertEqual(st.json()["mode"], "rules_local")

            chat = self.client.post(
                "/api/lati/chat",
                headers=self.h("astro1"),
                json={"message": "Hola LÁTI, ¿qué puedes hacer?", "language": "es", "input_mode": "voice"},
            )
            self.assertEqual(chat.status_code, 200)
            body = chat.json()
            self.assertEqual(body["origin"], "rules_local")
            self.assertEqual(body["input_mode"], "voice")
            self.assertFalse(body["fallback_used"])
            self.assertFalse(body["external_model_configured"])

    def test_gemini_external_chat_multiturn_and_strict_privacy_isolation(self):
        captured_calls: list[dict] = []

        def mock_post(url: str, headers: dict, json_body: dict, timeout: float):
            captured_calls.append({"url": url, "headers": headers, "body": json_body, "timeout": timeout})
            return (
                200,
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "text": f"Respira lento 4 segundos e inhala con calma (turno {len(captured_calls)})."
                                    }
                                ]
                            }
                        }
                    ]
                },
            )

        # Seed sensitive private astronaut telemetry, check-in note, and open alert
        with conn() as db:
            db.execute(
                "INSERT INTO metrics(astronaut_id,recorded_at,sleep,heart_rate,fatigue,mood,source,demo,unit) "
                "VALUES('AST-001','2026-06-01T08:00:00Z',4.2,102,4,2,'wearable',0,'mixed')"
            )
            db.execute(
                "INSERT INTO alerts(astronaut_id,created_at,priority,reason,demo) "
                "VALUES('AST-001','2026-06-01T08:05:00Z','high','Secret alert reason XYZ',0)"
            )
        self.client.post(
            "/api/checkins",
            headers=self.h("astro1"),
            json={"fatigue": 4, "mood": 2, "note": "Private personal check-in note ABC", "language": "es"},
        )

        # Personal query MUST stay local and never contact external model
        env_patch = {
            "GEMINI_API_KEY": "super-secret-gemini-key-123",
            "LATIRA_LLM_API_KEY": "",
            "LATIRA_LLM_BASE_URL": "",
            "LATIRA_LLM_MODEL": "",
        }
        with patch.dict(os.environ, env_patch), patch("app.services.lati_ai._default_http_post", side_effect=mock_post):
            personal = self.client.post(
                "/api/lati/chat",
                headers=self.h("astro1"),
                json={"message": "¿Cómo está mi sueño hoy?", "language": "es", "input_mode": "text"},
            )
            self.assertEqual(personal.status_code, 200)
            self.assertEqual(personal.json()["origin"], "rules_local")
            self.assertEqual(personal.json()["context_source"], "authenticated_astronaut_records")
            self.assertEqual(len(captured_calls), 0)

            # Status must never expose raw API key
            st = self.client.get("/api/lati/status", headers=self.h("astro1")).json()
            self.assertTrue(st["configured"])
            self.assertEqual(st["provider"], "gemini")
            self.assertEqual(st["model"], "gemini-4-hydrogen")
            self.assertNotIn("super-secret-gemini-key-123", str(st))

            # Turn 1 general conversational voice message -> hits Gemini
            turn1 = self.client.post(
                "/api/lati/chat",
                headers=self.h("astro1"),
                json={
                    "message": "Estoy algo tenso antes de dormir, ¿me guías en una pausa breve?",
                    "language": "es",
                    "input_mode": "voice",
                    "client_message_id": "voice-turn-1",
                },
            )
            self.assertEqual(turn1.status_code, 200)
            t1_json = turn1.json()
            self.assertEqual(t1_json["origin"], "external_gemini")
            self.assertEqual(t1_json["model"], "gemini-4-hydrogen")
            self.assertEqual(t1_json["input_mode"], "voice")
            self.assertFalse(t1_json["fallback_used"])
            self.assertEqual(len(captured_calls), 1)
            self.assertIn("models/gemini-4-hydrogen:generateContent", captured_calls[0]["url"])
            self.assertEqual(captured_calls[0]["headers"]["x-goog-api-key"], "super-secret-gemini-key-123")
            self.assertEqual(captured_calls[0]["headers"]["User-Agent"], "aistudio-build")

            # Verify ZERO private clinical records leaked to external payload
            serialized_payload = str(captured_calls[0]["body"])
            for sensitive in ("Secret alert reason XYZ", "Private personal check-in note ABC", "102", "4.2", "AST-001"):
                self.assertNotIn(sensitive, serialized_payload)

            # Turn 2 follow-up -> sends previous non-clinical turn for session continuity
            turn2 = self.client.post(
                "/api/lati/chat",
                headers=self.h("astro1"),
                json={
                    "message": "Gracias, ¿puedes darme otro consejo breve?",
                    "language": "es",
                    "input_mode": "text",
                    "client_message_id": "text-turn-2",
                },
            )
            self.assertEqual(turn2.status_code, 200)
            self.assertEqual(turn2.json()["origin"], "external_gemini")
            self.assertEqual(len(captured_calls), 2)
            turn2_texts = " ".join(
                p.get("text", "")
                for msg in captured_calls[1]["body"]["contents"]
                for p in msg.get("parts", [])
            )
            self.assertIn("pausa breve", turn2_texts)
            self.assertNotIn("Private personal check-in note ABC", turn2_texts)

    def test_openai_compatible_endpoint_and_admin_verify_endpoint(self):
        def mock_openai_post(url: str, headers: dict, json_body: dict, timeout: float):
            self.assertTrue(url.endswith("/v1/chat/completions"))
            self.assertEqual(headers["Authorization"], "Bearer custom-key-xyz")
            return (200, {"choices": [{"message": {"content": "OK from compatible endpoint"}}]})

        env_patch = {
            "GEMINI_API_KEY": "",
            "LATIRA_LLM_BASE_URL": "https://llm.example.internal/v1",
            "LATIRA_LLM_API_KEY": "custom-key-xyz",
            "LATIRA_LLM_MODEL": "custom-wellbeing-v1",
        }
        with patch.dict(os.environ, env_patch), patch("app.services.lati_ai._default_http_post", side_effect=mock_openai_post):
            # Only admin can invoke /api/integrations/lati/verify
            self.assertEqual(self.client.post("/api/integrations/lati/verify", headers=self.h("astro1")).status_code, 403)
            self.assertEqual(self.client.post("/api/integrations/lati/verify", headers=self.h("medic1")).status_code, 403)

            ver = self.client.post("/api/integrations/lati/verify", headers=self.h("admin1"))
            self.assertEqual(ver.status_code, 200)
            vdata = ver.json()
            self.assertTrue(vdata["connected"])
            self.assertEqual(vdata["verification_status"], "connected")
            self.assertEqual(vdata["provider"], "openai_compatible")
            self.assertEqual(vdata["model"], "custom-wellbeing-v1")
            self.assertNotIn("custom-key-xyz", str(vdata))

            chat = self.client.post(
                "/api/lati/chat",
                headers=self.h("astro1"),
                json={"message": "Hello LÁTI", "language": "en", "input_mode": "text"},
            )
            self.assertEqual(chat.status_code, 200)
            self.assertEqual(chat.json()["origin"], "external_llm")
            self.assertEqual(chat.json()["reply"], "OK from compatible endpoint")

    def test_external_errors_trigger_honest_controlled_fallback_without_key_leak(self):
        secret = "leak-check-secret-999"
        env_patch = {
            "GEMINI_API_KEY": secret,
            "LATIRA_LLM_BASE_URL": "",
            "LATIRA_LLM_MODEL": "gemini-4-hydrogen",
        }

        cases = [
            ((401, {"error": {"message": f"Invalid key {secret}"}}), "auth_error"),
            ((404, {"error": {"message": "Model not found"}}), "model_not_found"),
            ((429, {"error": {"message": "Quota exceeded"}}), "quota_exceeded"),
            (httpx.TimeoutException("timed out"), "timeout"),
        ]

        for idx, (outcome, expected_code) in enumerate(cases):
            def mock_fail(*_args, **_kwargs):
                if isinstance(outcome, Exception):
                    raise outcome
                return outcome

            with patch.dict(os.environ, env_patch), patch("app.services.lati_ai._default_http_post", side_effect=mock_fail):
                res = self.client.post(
                    "/api/lati/chat",
                    headers=self.h("astro1"),
                    json={
                        "message": f"Hola LÁTI prueba error {idx}",
                        "language": "es",
                        "input_mode": "voice",
                    },
                )
                self.assertEqual(res.status_code, 200)
                body = res.json()
                self.assertEqual(body["origin"], "rules_local")
                self.assertTrue(body["fallback_used"])
                self.assertEqual(body["fallback_reason"], expected_code)
                self.assertEqual(body["context_source"], "local_fallback")
                self.assertNotIn(secret, body["external_error"])
                self.assertNotIn(secret, body["reply"])

    def test_history_persists_modalities_deduplicates_retries_and_enforces_rbac(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "", "LATIRA_LLM_API_KEY": ""}):
            # Send message with client_message_id twice -> must NOT duplicate
            first = self.client.post(
                "/api/lati/chat",
                headers=self.h("astro1"),
                json={
                    "message": "Hola por voz",
                    "language": "es",
                    "input_mode": "voice",
                    "client_message_id": "dup-check-1",
                },
            )
            self.assertEqual(first.status_code, 200)
            second = self.client.post(
                "/api/lati/chat",
                headers=self.h("astro1"),
                json={
                    "message": "Hola por voz",
                    "language": "es",
                    "input_mode": "voice",
                    "client_message_id": "dup-check-1",
                },
            )
            self.assertEqual(second.status_code, 200)
            self.assertTrue(second.json()["deduplicated"])

            # Send typed message
            third = self.client.post(
                "/api/lati/chat",
                headers=self.h("astro1"),
                json={"message": "Hello typed", "language": "en", "input_mode": "text"},
            )
            self.assertEqual(third.status_code, 200)

            # Invalid empty message or bad mode rejected cleanly without inserting rows
            self.assertEqual(
                self.client.post(
                    "/api/lati/chat",
                    headers=self.h("astro1"),
                    json={"message": "   ", "language": "es", "input_mode": "voice"},
                ).status_code,
                422,
            )
            self.assertEqual(
                self.client.post(
                    "/api/lati/chat",
                    headers=self.h("astro1"),
                    json={"message": "hi", "language": "es", "input_mode": "telepathy"},
                ).status_code,
                422,
            )

        conv = self.client.get("/api/conversation", headers=self.h("astro1"))
        self.assertEqual(conv.status_code, 200)
        rows = conv.json()
        # Exactly 4 rows (2 turns: voice + text)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["input_mode"], "voice")
        self.assertEqual(rows[2]["input_mode"], "text")
        self.assertTrue(all(r["created_at"] for r in rows))

        # Owner isolation & RBAC: medic, admin get 403; astro2 sees empty list
        self.assertEqual(self.client.get("/api/conversation", headers=self.h("medic1")).status_code, 403)
        self.assertEqual(self.client.get("/api/conversation", headers=self.h("admin1")).status_code, 403)
        self.assertEqual(self.client.get("/api/conversation", headers=self.h("astro2")).json(), [])

    def test_legacy_conversations_table_migrates_without_losing_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            legacy_db = Path(tmp) / "legacy.sqlite3"
            with sqlite3.connect(legacy_db) as raw:
                raw.execute(
                    "CREATE TABLE conversations(id INTEGER PRIMARY KEY, astronaut_id TEXT NOT NULL, "
                    "role TEXT NOT NULL, content TEXT NOT NULL, origin TEXT NOT NULL, created_at TEXT NOT NULL)"
                )
                raw.execute(
                    "INSERT INTO conversations(astronaut_id,role,content,origin,created_at) "
                    "VALUES('AST-001','user','Mensaje previo','rules_local','2026-01-01T00:00:00Z')"
                )

            old_db, old_main_db = database.DB, main.DB
            database.DB = main.DB = legacy_db
            try:
                main.init()
                with conn() as db:
                    cols = {r["name"] for r in db.execute("PRAGMA table_info(conversations)")}
                    self.assertTrue({"input_mode", "context_source", "model", "client_message_id"}.issubset(cols))
                    row = db.execute("SELECT content, input_mode FROM conversations WHERE astronaut_id='AST-001'").fetchone()
                    self.assertEqual(row["content"], "Mensaje previo")
                    self.assertEqual(row["input_mode"], "text")
            finally:
                database.DB, main.DB = old_db, old_main_db


if __name__ == "__main__":
    unittest.main()
