"""Unit tests for NASA/CSA scientific catalog, client error handling, provenance, and LÁTI lookup."""
from __future__ import annotations

import json
import unittest
import urllib.error

from ai.nasa_client import (
    clear_cache,
    fetch_osdr_human_studies,
    parse_osdr_search_payload,
    verify_reference_reachability,
)
from ai.nasa_models import (
    REQUIRED_PROVENANCE_FIELDS,
    REQUIRED_SOURCE_FIELDS,
    VerificationStatus,
    is_official_whitelisted_url,
    validate_external_record,
    validate_source_entry,
)
from ai.nasa_sources import (
    answer_scientific_query,
    get_domain_context,
    get_integration_summary,
    get_source,
    refresh_sources,
    source_registry,
)


MOCK_OSDR_RESPONSE = json.dumps({
    "hits": {
        "total": 2,
        "hits": [
            {
                "_id": "mock-1",
                "_source": {
                    "Accession": "OSD-943",
                    "Study Title": "Longitudinal immune transcriptomic analysis in astronauts",
                    "organism": "Homo sapiens",
                    "Material Type": "Whole Blood",
                    "Study Assay Technology Type": "DNA microarray",
                    "Flight Program": "International Space Station (ISS)",
                    "Mission": {"Name": "AX-1", "Start Date": "4/8/22", "End Date": "4/25/22"},
                },
            },
            {
                "_id": "mock-2",
                "_source": {
                    "Accession": "OSD-BED-1",
                    "Study Title": "Bed rest analog study for sleep and circadian adaptation",
                    "organism": ["Homo sapiens"],
                    "Material Type": "Saliva",
                    "Study Assay Technology Type": "Metabolomics",
                    "Flight Program": "",
                    "Mission": {"Name": "Bed Rest Analog", "Start Date": "2024-01-01", "End Date": "2024-02-01"},
                },
            },
        ],
    }
})


class NasaIntegrationTests(unittest.TestCase):
    def setUp(self):
        clear_cache()

    def test_five_official_sources_registered_with_required_metadata(self):
        challenge_sources = source_registry(include_additional_public=False)
        self.assertEqual(len(challenge_sources), 5)
        expected_ids = {
            "nasa-hrp-hazards",
            "nasa-hrp-risks",
            "nasa-hrp-ongoing-research",
            "csa-cans-radiation",
            "csa-iss-science",
        }
        self.assertEqual({s["id"] for s in challenge_sources}, expected_ids)
        for src in source_registry(include_additional_public=True):
            for field in REQUIRED_SOURCE_FIELDS:
                self.assertIn(field, src)
            validate_source_entry(src)

    def test_metadata_validation_blocks_arbitrary_urls_and_false_connected_state(self):
        self.assertFalse(is_official_whitelisted_url("https://evil.example.com/api"))
        self.assertFalse(is_official_whitelisted_url("http://www.nasa.gov/hrp/hazards/"))
        self.assertTrue(is_official_whitelisted_url("https://www.nasa.gov/hrp/hazards/"))
        self.assertTrue(is_official_whitelisted_url("https://osdr.nasa.gov/osdr/data/search"))

        bad_source = dict(get_source("nasa-hrp-hazards"))
        bad_source["verification_status"] = VerificationStatus.CONNECTED.value
        with self.assertRaises(ValueError):
            validate_source_entry(bad_source)

    def test_classification_of_references_and_public_datasets(self):
        hazards = get_source("nasa-hrp-hazards")
        risks = get_source("nasa-hrp-risks")
        ongoing = get_source("nasa-hrp-ongoing-research")
        cans = get_source("csa-cans-radiation")
        why = get_source("csa-iss-science")
        osdr = get_source("nasa-osdr-studies")

        self.assertEqual(hazards["verification_status"], "reference_only")
        self.assertEqual(risks["verification_status"], "catalogued")
        self.assertEqual(ongoing["verification_status"], "catalogued")
        self.assertEqual(cans["verification_status"], "reference_only")
        self.assertEqual(why["verification_status"], "reference_only")
        self.assertEqual(osdr["verification_status"], "available")
        self.assertIsNone(cans["endpoint"])
        self.assertIsNotNone(osdr["endpoint"])

        # Webpage HTTP 200 reachability never turns reference_only into connected
        reach = verify_reference_reachability(cans, http_get=lambda url, timeout: (200, "text/html", "<html></html>"))
        self.assertEqual(reach["status"], "reference_only")

    def test_mocked_osdr_query_transitions_to_connected_and_preserves_provenance(self):
        osdr = get_source("nasa-osdr-studies")
        res = fetch_osdr_human_studies(
            osdr,
            force_refresh=True,
            http_get=lambda url, timeout: (200, "application/json", MOCK_OSDR_RESPONSE),
        )
        self.assertEqual(res["status"], "connected")
        self.assertEqual(len(res["records"]), 2)
        first, second = res["records"]
        for field in REQUIRED_PROVENANCE_FIELDS:
            self.assertIn(field, first)
        self.assertEqual(first["classification"], "mission_observation")
        self.assertEqual(second["classification"], "analog_study")
        self.assertNotEqual(first["classification"], "synthetic_demo")

        summary = get_integration_summary(
            refresh_sources(http_get=lambda url, timeout: (200, "application/json", MOCK_OSDR_RESPONSE))["sources"]
        )
        self.assertEqual(summary["api_connected_count"], 1)
        self.assertEqual(summary["status"], "partial_api_connected")

    def test_invalid_external_response_returns_unavailable_without_fabricating_data(self):
        osdr = get_source("nasa-osdr-studies")
        bad_json = fetch_osdr_human_studies(
            osdr,
            force_refresh=True,
            http_get=lambda url, timeout: (200, "text/html", "<html>not json</html>"),
        )
        self.assertEqual(bad_json["status"], "unavailable")
        self.assertEqual(bad_json["records"], [])

        bad_schema = fetch_osdr_human_studies(
            osdr,
            force_refresh=True,
            http_get=lambda url, timeout: (200, "application/json", '{"unexpected": 1}'),
        )
        self.assertEqual(bad_schema["status"], "unavailable")
        self.assertEqual(bad_schema["records"], [])

    def test_timeout_and_connection_failure_handled_gracefully(self):
        osdr = get_source("nasa-osdr-studies")

        def raise_timeout(url, timeout):
            raise TimeoutError("Read timed out")

        res_timeout = fetch_osdr_human_studies(osdr, force_refresh=True, http_get=raise_timeout)
        self.assertEqual(res_timeout["status"], "unavailable")
        self.assertIn("TimeoutError", res_timeout["error"])
        self.assertEqual(res_timeout["records"], [])

        def raise_net(url, timeout):
            raise urllib.error.URLError("Name resolution failure")

        res_net = fetch_osdr_human_studies(osdr, force_refresh=True, http_get=raise_net)
        self.assertEqual(res_net["status"], "unavailable")
        self.assertEqual(res_net["records"], [])

    def test_missing_units_are_flagged_honestly_not_invented(self):
        rec = validate_external_record({
            "source_id": "nasa-osdr-studies",
            "origin_url": "https://osdr.nasa.gov/osdr/data/search",
            "queried_at": "2026-11-13T21:00:00+00:00",
            "observation_date": "2026-01-01",
            "variable": "neutron_flux_example",
            "value": "12.4",
            "unit": "",
            "population": "ISS cohort",
            "retrieval_method": "https_json_rest_api",
            "quality_indicator": "raw_source",
            "classification": "mission_observation",
            "license_or_terms": "CC0",
        })
        self.assertEqual(rec["unit"], "unspecified")
        self.assertIn("unit_missing_in_source", rec["quality_indicator"])

        with self.assertRaises(ValueError):
            validate_external_record({**rec, "classification": "synthetic_demo"})

    def test_domain_context_covers_hazards_programs_and_cans_limitations(self):
        ctx = get_domain_context()
        self.assertEqual(len(ctx["five_hazards"]), 5)
        self.assertTrue(all(h["measured_by_latira"] is False for h in ctx["five_hazards"]))
        prog_ids = {p["id"] for p in ctx["ongoing_programs"]}
        self.assertEqual(prog_ids, {"archer", "immune_biomarkers", "standard_measures", "cipher", "spinal_health", "tempus_pro"})
        self.assertFalse(ctx["csa_cans"]["connected"])
        self.assertFalse(ctx["csa_cans"]["units_specified_in_source"])

    def test_lati_local_scientific_lookup_works_offline_in_en_and_es(self):
        ans_es = answer_scientific_query("¿LÁTIRA recibe mi radiación de CANS?", "es")
        self.assertIsNotNone(ans_es)
        self.assertEqual(ans_es["context_source"], "verified_nasa_csa_references")
        self.assertIn("NO está conectado a CANS", ans_es["reply"])

        ans_en = answer_scientific_query("What are NASA five hazards?", "en")
        self.assertIsNotNone(ans_en)
        self.assertIn("Space Radiation", ans_en["reply"])

        # Personal query without NASA/CSA keywords returns None so clinical/personal handler runs
        self.assertIsNone(answer_scientific_query("How is my sleep?", "en"))

    def test_osdr_title_keywords_without_structured_mission_do_not_claim_mission_observation(self):
        payload = json.dumps({
            "hits": {
                "total": 1,
                "hits": [
                    {
                        "_id": "mock-unconfirmed",
                        "_source": {
                            "Accession": "OSD-999",
                            "Study Title": "Spaceflight and ISS astronauts immune markers review",
                            "organism": "Homo sapiens",
                            "Material Type": "PBMC",
                            "Study Assay Technology Type": "RNA-seq",
                            "Flight Program": "",
                            "Mission": {"Name": "", "Start Date": "", "End Date": ""},
                        },
                    }
                ],
            }
        })
        records = parse_osdr_search_payload(
            payload,
            origin_url="https://osdr.nasa.gov/osdr/data/search",
            queried_at="2026-11-13T21:00:00+00:00",
            license_or_terms="CC0",
        )
        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertEqual(rec["classification"], "unconfirmed_study_context")
        self.assertIn("orbital_provenance_unconfirmed", rec["quality_indicator"])
        self.assertEqual(rec["record_nature"], "study_metadata_record")
        self.assertFalse(rec["is_personal_astronaut_measurement"])

    def test_hrp_hazards_risk_domains_and_programs_completeness_and_accuracy(self):
        ctx = get_domain_context()
        self.assertEqual(len(ctx["five_hazards"]), 5)
        for hazard in ctx["five_hazards"]:
            self.assertEqual(hazard["official_url"], "https://www.nasa.gov/hrp/hazards/")
            self.assertIn("related_latira_indicators", hazard)
            self.assertFalse(hazard["measured_by_latira"])

        self.assertEqual(len(ctx["risk_domains"]), 9)
        by_id = {d["id"]: d for d in ctx["risk_domains"]}
        self.assertEqual(by_id["cardiovascular"]["related_latira_indicators"], ["heart_rate"])
        self.assertEqual(by_id["sleep_circadian"]["related_latira_indicators"], ["sleep", "fatigue"])
        self.assertEqual(by_id["behavioral_health"]["related_latira_indicators"], ["mood", "fatigue"])
        self.assertEqual(by_id["musculoskeletal"]["related_latira_indicators"], ["pose_geometric_keypoints"])
        self.assertEqual(by_id["immune"]["related_latira_indicators"], [])
        for dom in ctx["risk_domains"]:
            self.assertEqual(dom["official_url"], "https://www.nasa.gov/hrp/risks/")
            self.assertTrue(dom.get("relevance_explanation_es"))
            self.assertTrue(dom.get("relevance_explanation_en"))

        self.assertEqual(len(ctx["ongoing_programs"]), 6)
        for prog in ctx["ongoing_programs"]:
            self.assertTrue(is_official_whitelisted_url(prog["official_url"]))
            self.assertTrue(prog.get("research_objective_es"))

    def test_osdr_missing_metadata_fields_are_preserved_as_none_without_fabrication(self):
        payload = json.dumps({
            "hits": {
                "total": 1,
                "hits": [
                    {
                        "_id": "GSE47126",
                        "_source": {
                            "Accession": "GSE47126",
                            "Study Title": "Transcriptional profiling in spaceflight analog cohort",
                            "Material Type": "",
                            "Study Assay Technology Type": "",
                            "Flight Program": "",
                            "Study Public Release Date": 1381834800,
                            "Mission": {"Name": "", "Start Date": "0000000000", "End Date": "0000000000"},
                        },
                    }
                ],
            }
        })
        records = parse_osdr_search_payload(
            payload,
            origin_url="https://osdr.nasa.gov/osdr/data/search",
            queried_at="2026-11-13T21:00:00+00:00",
            license_or_terms="CC0",
        )
        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertIsNone(rec["organism"])
        self.assertIsNone(rec["material_type"])
        self.assertIsNone(rec["assay_technology"])
        self.assertIsNone(rec["mission_name"])
        self.assertIsNone(rec["flight_program"])
        self.assertEqual(rec["release_date"], "2013-10-15")
        self.assertEqual(rec["observation_date"], "2013-10-15")
        self.assertIn("organism_missing_in_source", rec["quality_indicator"])
        self.assertEqual(rec["unit"], "unspecified")
        self.assertIn("unit_missing_in_source", rec["quality_indicator"])

    def test_ssl_and_http_error_handling_plus_api_unavailable_summary(self):
        import ssl

        osdr = get_source("nasa-osdr-studies")

        def raise_ssl(url, timeout):
            raise ssl.SSLError("CERTIFICATE_VERIFY_FAILED")

        res_ssl = fetch_osdr_human_studies(osdr, force_refresh=True, http_get=raise_ssl)
        self.assertEqual(res_ssl["status"], "unavailable")
        self.assertFalse(res_ssl["http_verified"])
        self.assertIn("SSLError", res_ssl["error"])
        self.assertEqual(res_ssl["records"], [])

        res_503 = fetch_osdr_human_studies(
            osdr,
            force_refresh=True,
            http_get=lambda url, timeout: (503, "application/json", "{}"),
        )
        self.assertEqual(res_503["status"], "unavailable")
        self.assertEqual(res_503["records"], [])

        refreshed = refresh_sources(http_get=raise_ssl)
        summary = get_integration_summary(refreshed["sources"])
        self.assertEqual(summary["status"], "api_unavailable")
        self.assertEqual(summary["osdr_status"], "unavailable")
        self.assertGreaterEqual(summary["unavailable_count"], 1)
        self.assertGreaterEqual(summary["restricted_count"], 1)


if __name__ == "__main__":
    unittest.main()

