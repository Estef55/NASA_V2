"""Backend API, RBAC, safety, baseline-isolation, and LÁTI integration tests for NASA/CSA phase."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))
from _db_isolation import configure_isolated_test_db

configure_isolated_test_db()

from fastapi.testclient import TestClient
from app.main import app, conn, hash_password
from app.routers.nasa import ensure_nasa_tables


MOCK_OSDR_API_JSON = json.dumps({
    "hits": {
        "total": 1,
        "hits": [
            {
                "_id": "osdr-test-1",
                "_source": {
                    "Accession": "OSD-943",
                    "Study Title": "Longitudinal transcriptomic analysis in astronauts",
                    "organism": "Homo sapiens",
                    "Material Type": "Whole Blood",
                    "Study Assay Technology Type": "DNA microarray",
                    "Flight Program": "International Space Station (ISS)",
                    "Mission": {"Name": "AX-1", "Start Date": "4/8/22", "End Date": "4/25/22"},
                },
            }
        ],
    }
})


class NasaApiTests(unittest.TestCase):
    def setUp(self):
        ensure_nasa_tables()
        self.client = TestClient(app)
        with conn() as db:
            db.execute("DELETE FROM nasa_external_records")
            db.execute("DELETE FROM nasa_source_cache")
            db.execute("DELETE FROM audit")
            db.execute("DELETE FROM sessions")
            db.execute("DELETE FROM followups")
            db.execute("DELETE FROM alerts")
            db.execute("DELETE FROM metrics")
            db.execute("DELETE FROM conversations")
            db.execute("DELETE FROM assignments")
            db.execute("DELETE FROM users")
            for name, role, aid in [
                ("astro_n", "astronaut", "AST-N1"),
                ("medic_n", "medic", None),
                ("admin_n", "admin", None),
            ]:
                db.execute(
                    "INSERT INTO users(username,password_hash,role,astronaut_id) VALUES(?,?,?,?)",
                    (name, hash_password("[REDACTED]"), role, aid),
                )
            db.execute("INSERT INTO assignments(medic_username,astronaut_id) VALUES('medic_n','AST-N1')")
        self.tokens = {
            name: self.client.post("/api/auth/login", json={"username": name, "password": "[REDACTED]"}).json()["token"]
            for name in ("astro_n", "medic_n", "admin_n")
        }

    def headers(self, user: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens[user]}"}

    def test_nasa_endpoints_require_auth_and_enforce_rbac(self):
        for path in (
            "/api/integrations/nasa",
            "/api/integrations/nasa/sources",
            "/api/integrations/nasa/sources/nasa-hrp-hazards",
            "/api/integrations/nasa/data",
        ):
            self.assertEqual(self.client.get(path).status_code, 401)
            self.assertEqual(self.client.get(path, headers=self.headers("astro_n")).status_code, 403)
            self.assertEqual(self.client.get(path, headers=self.headers("medic_n")).status_code, 200)
            self.assertEqual(self.client.get(path, headers=self.headers("admin_n")).status_code, 200)

        # Only admin can trigger refresh
        self.assertEqual(self.client.post("/api/integrations/nasa/refresh").status_code, 401)
        self.assertEqual(self.client.post("/api/integrations/nasa/refresh", headers=self.headers("astro_n")).status_code, 403)
        self.assertEqual(self.client.post("/api/integrations/nasa/refresh", headers=self.headers("medic_n")).status_code, 403)

        # Admin still has zero clinical access
        self.assertEqual(self.client.get("/api/metrics", headers=self.headers("admin_n")).status_code, 403)
        self.assertEqual(self.client.get("/api/alerts", headers=self.headers("admin_n")).status_code, 403)

    def test_refresh_rejects_arbitrary_urls_and_persists_mocked_osdr_records_with_audit(self):
        # Arbitrary URL field is rejected by Pydantic extra="forbid"
        bad = self.client.post(
            "/api/integrations/nasa/refresh",
            headers=self.headers("admin_n"),
            json={"url": "https://evil.example.com/steal"},
        )
        self.assertEqual(bad.status_code, 422)

        # Unknown source_id returns 404
        unknown = self.client.post(
            "/api/integrations/nasa/refresh",
            headers=self.headers("admin_n"),
            json={"source_id": "nonexistent-source"},
        )
        self.assertEqual(unknown.status_code, 404)

        def mock_http(url, timeout):
            if "osdr.nasa.gov" in url:
                return (200, "application/json", MOCK_OSDR_API_JSON)
            return (200, "text/html", "<html>ok</html>")

        with patch("ai.nasa_sources.fetch_osdr_human_studies") as mock_fetch, patch(
            "ai.nasa_sources.verify_reference_reachability"
        ) as mock_reach:
            from ai.nasa_client import fetch_osdr_human_studies as real_fetch, verify_reference_reachability as real_reach

            mock_fetch.side_effect = lambda src, **kw: real_fetch(src, force_refresh=True, http_get=mock_http)
            mock_reach.side_effect = lambda src, **kw: real_reach(src, http_get=mock_http)
            res = self.client.post("/api/integrations/nasa/refresh", headers=self.headers("admin_n"), json={})

        self.assertEqual(res.status_code, 200, res.text)
        body = res.json()
        self.assertEqual(body["records_ingested"], 1)
        self.assertEqual(body["summary"]["api_connected_count"], 1)
        self.assertEqual(body["summary"]["official_challenge_sources_count"], 5)

        data_resp = self.client.get("/api/integrations/nasa/data", headers=self.headers("medic_n"))
        self.assertEqual(data_resp.status_code, 200)
        items = data_resp.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["accession"], "OSD-943")
        self.assertEqual(items[0]["classification"], "mission_observation")

        # Synthetic demo filter must be rejected on external data endpoint
        syn = self.client.get("/api/integrations/nasa/data?classification=synthetic_demo", headers=self.headers("medic_n"))
        self.assertEqual(syn.status_code, 422)

        # Audit log recorded the refresh
        audits = self.client.get("/api/admin/audit", headers=self.headers("admin_n")).json()
        self.assertTrue(any(a["action"] == "nasa_sources_refresh:all" for a in audits))

    def test_external_nasa_data_does_not_alter_personal_baseline_or_alerts(self):
        # Populate external NASA table via mocked refresh
        with conn() as db:
            db.execute(
                """
                INSERT INTO nasa_external_records(
                    source_id, origin_url, queried_at, observation_date, variable, value,
                    unit, population, retrieval_method, quality_indicator, classification,
                    license_or_terms, accession
                ) VALUES(
                    'nasa-osdr-studies', 'https://osdr.nasa.gov/osdr/data/search', '2026-11-13T21:00:00Z',
                    '2022-04-25', 'OSD-943', 'Study', 'study_metadata_record', 'Homo sapiens',
                    'https_json_rest_api', 'verified_osdr_study_metadata', 'mission_observation', 'CC0', 'OSD-943'
                )
                """
            )
        # Personal baseline for AST-N1 remains empty/insufficient with 0 samples
        baseline = self.client.get("/api/baseline", headers=self.headers("astro_n")).json()
        self.assertFalse(baseline["sufficient"])
        self.assertEqual(baseline["sample_count"], 0)
        self.assertEqual(self.client.get("/api/alerts", headers=self.headers("astro_n")).json(), [])

    def test_lati_chat_separates_personal_records_from_scientific_references_en_and_es(self):
        # Personal sleep query still uses authenticated_astronaut_records
        personal = self.client.post(
            "/api/lati/chat",
            headers=self.headers("astro_n"),
            json={"message": "How is my sleep?", "language": "en"},
        )
        self.assertEqual(personal.status_code, 200)
        self.assertEqual(personal.json()["context_source"], "authenticated_astronaut_records")

        # Scientific CANS radiation query uses verified_nasa_csa_references and denies connection honestly
        cans_es = self.client.post(
            "/api/lati/chat",
            headers=self.headers("astro_n"),
            json={"message": "¿Cuál es mi dosis de radiación CANS?", "language": "es"},
        )
        self.assertEqual(cans_es.status_code, 200)
        self.assertEqual(cans_es.json()["context_source"], "verified_nasa_csa_references")
        self.assertEqual(cans_es.json()["origin"], "rules_local")
        self.assertIn("NO está conectado a CANS", cans_es.json()["reply"])

        cipher_en = self.client.post(
            "/api/lati/chat",
            headers=self.headers("astro_n"),
            json={"message": "Tell me about NASA CIPHER", "language": "en"},
        )
        self.assertEqual(cipher_en.status_code, 200)
        self.assertEqual(cipher_en.json()["context_source"], "verified_nasa_csa_references")
        self.assertIn("CIPHER", cipher_en.json()["reply"])

    def test_refresh_report_counts_and_preserves_previous_records_when_osdr_fails(self):
        from ai.nasa_client import fetch_osdr_human_studies as real_fetch, verify_reference_reachability as real_reach

        def mock_ok(url, timeout):
            if "osdr.nasa.gov" in url:
                return (200, "application/json", MOCK_OSDR_API_JSON)
            return (200, "text/html", "<html>ok</html>")

        with patch("ai.nasa_sources.fetch_osdr_human_studies") as mf, patch(
            "ai.nasa_sources.verify_reference_reachability"
        ) as mr:
            mf.side_effect = lambda src, **kw: real_fetch(src, force_refresh=True, http_get=mock_ok)
            mr.side_effect = lambda src, **kw: real_reach(src, http_get=mock_ok)
            first = self.client.post("/api/integrations/nasa/refresh", headers=self.headers("admin_n"), json={})

        self.assertEqual(first.status_code, 200)
        first_body = first.json()
        self.assertFalse(first_body["partial_errors"])
        self.assertEqual(first_body["refresh_report"]["records_fetched"], 1)
        self.assertEqual(first_body["refresh_report"]["records_inserted"], 1)
        self.assertEqual(first_body["refresh_report"]["records_updated"], 0)
        self.assertIsNotNone(first_body["refresh_report"]["last_successful_at"])

        # Second refresh with same record marks it as updated
        with patch("ai.nasa_sources.fetch_osdr_human_studies") as mf, patch(
            "ai.nasa_sources.verify_reference_reachability"
        ) as mr:
            mf.side_effect = lambda src, **kw: real_fetch(src, force_refresh=True, http_get=mock_ok)
            mr.side_effect = lambda src, **kw: real_reach(src, http_get=mock_ok)
            second = self.client.post("/api/integrations/nasa/refresh", headers=self.headers("admin_n"), json={})

        self.assertEqual(second.status_code, 200)
        second_report = second.json()["refresh_report"]
        self.assertEqual(second_report["records_fetched"], 1)
        self.assertEqual(second_report["records_inserted"], 0)
        self.assertEqual(second_report["records_updated"], 1)

        # Third refresh fails on OSDR -> error reported honestly and prior record preserved
        def mock_osdr_down(url, timeout):
            if "osdr.nasa.gov" in url:
                raise TimeoutError("OSDR unreachable")
            return (200, "text/html", "<html>ok</html>")

        with patch("ai.nasa_sources.fetch_osdr_human_studies") as mf, patch(
            "ai.nasa_sources.verify_reference_reachability"
        ) as mr:
            mf.side_effect = lambda src, **kw: real_fetch(src, force_refresh=True, http_get=mock_osdr_down)
            mr.side_effect = lambda src, **kw: real_reach(src, http_get=mock_osdr_down)
            failed = self.client.post("/api/integrations/nasa/refresh", headers=self.headers("admin_n"), json={})

        self.assertEqual(failed.status_code, 200)
        failed_body = failed.json()
        self.assertTrue(failed_body["partial_errors"])
        self.assertIn("nasa-osdr-studies", failed_body["errors"])
        self.assertEqual(failed_body["summary"]["status"], "api_unavailable")
        self.assertEqual(failed_body["summary"]["osdr_status"], "unavailable")
        self.assertEqual(failed_body["refresh_report"]["records_fetched"], 0)
        self.assertEqual(failed_body["refresh_report"]["previously_stored_retained"], 1)
        self.assertIsNotNone(failed_body["refresh_report"]["last_successful_at"])

        stored = self.client.get("/api/integrations/nasa/data", headers=self.headers("medic_n")).json()
        self.assertEqual(stored["total"], 1)
        self.assertEqual(stored["items"][0]["sync_state"], "previously_stored")

    def test_clinical_baseline_thresholds_remain_unchanged(self):
        from app.services.health_baseline import BASELINE_MIN_SAMPLES, DEVIATION_THRESHOLD

        self.assertEqual(BASELINE_MIN_SAMPLES, 3)
        self.assertAlmostEqual(DEVIATION_THRESHOLD, 0.20, places=4)


if __name__ == "__main__":
    unittest.main()

