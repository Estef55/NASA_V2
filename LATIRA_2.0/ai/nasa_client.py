"""Safe HTTP client and TTL cache for verified public NASA/CSA scientific resources."""
from __future__ import annotations

from datetime import datetime, timezone
import http.client
import json
import ssl
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Callable

from .nasa_models import (
    DataClassification,
    VerificationStatus,
    is_official_whitelisted_url,
    utc_now_iso,
    validate_external_record,
)

DEFAULT_TIMEOUT_SECONDS = 8.0
DEFAULT_CACHE_TTL_SECONDS = 900

_CACHE_LOCK = threading.Lock()
_OSDR_CACHE: dict[str, Any] = {
    "fetched_at_mono": 0.0,
    "queried_at": None,
    "status": VerificationStatus.AVAILABLE.value,
    "http_verified": False,
    "http_status": None,
    "error": None,
    "records": [],
}


def clear_cache() -> None:
    with _CACHE_LOCK:
        _OSDR_CACHE.update(
            {
                "fetched_at_mono": 0.0,
                "queried_at": None,
                "status": VerificationStatus.AVAILABLE.value,
                "http_verified": False,
                "http_status": None,
                "error": None,
                "records": [],
            }
        )


def _default_http_get(url: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> tuple[int, str, str]:
    if not is_official_whitelisted_url(url):
        raise ValueError(f"Blocked non-whitelisted URL: {url}")
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; LATIRA-2.0/2.0; +https://www.nasa.gov/hrp/)",
            "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "close",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        status_code = getattr(resp, "status", 200)
        content_type = resp.headers.get("Content-Type", "")
        body = resp.read(2 * 1024 * 1024).decode("utf-8", errors="replace")
        return int(status_code), str(content_type), body


_CONFIRMED_FLIGHT_TOKENS = (
    "iss",
    "international space station",
    "space shuttle",
    "sts-",
    "artemis",
    "commercial crew",
    "axiom",
    "ax-",
    "inspiration4",
    "spacex",
    "crew dragon",
    "soyuz",
    "bion",
    "foton",
    "skylab",
    "mir",
    "orion",
    "expedition",
)


def _classify_osdr_study(src: dict[str, Any]) -> tuple[str, str]:
    """Classify an OSDR study prudently using structured mission/program metadata.

    Never promotes a study to `mission_observation` solely because its title mentions
    keywords like 'ISS', 'astronaut', or 'spaceflight'.
    """
    mission = src.get("Mission") if isinstance(src.get("Mission"), dict) else {}
    mission_name = str(mission.get("Name") or "").strip()
    flight_program = str(src.get("Flight Program") or "").strip()
    study_factor = str(src.get("Study Factor Name") or src.get("Study Factor Type") or "").strip()
    project_type = str(src.get("Project Type") or "").strip()
    title = str(src.get("Study Title") or "").strip()

    structured_flight = f"{mission_name} {flight_program}".lower()
    all_descriptive = f"{mission_name} {flight_program} {study_factor} {project_type} {title}".lower()

    if any(k in all_descriptive for k in ("bed rest", "bed-rest", "analog", "isolation", "mardi", "mars500", "chapea")):
        return DataClassification.ANALOG_STUDY.value, "verified_osdr_study_metadata"
    if any(k in all_descriptive for k in ("simulation", "simulated", "clinostat", "hindlimb", "parabolic")):
        return DataClassification.SIMULATION.value, "verified_osdr_study_metadata"
    if any(k in all_descriptive for k in ("ground control", "ground study", "ground-based", "terrestrial cohort")):
        return DataClassification.GROUND_HUMAN_RESEARCH.value, "verified_osdr_study_metadata"

    has_confirmed_flight = any(tok in structured_flight for tok in _CONFIRMED_FLIGHT_TOKENS)
    if has_confirmed_flight:
        return DataClassification.MISSION_OBSERVATION.value, "verified_osdr_study_metadata"

    if project_type.lower() in {"ground", "ground study"}:
        return DataClassification.GROUND_HUMAN_RESEARCH.value, "verified_osdr_study_metadata"

    return (
        DataClassification.UNCONFIRMED_STUDY_CONTEXT.value,
        "verified_osdr_study_metadata; orbital_provenance_unconfirmed",
    )


def _clean_date_token(raw: Any) -> str:
    val = str(raw or "").strip()
    if val in {"", "0000000000", "0000-00-00", "null", "None"}:
        return ""
    return val


def _format_release_date(raw: Any) -> str | None:
    if raw is None or raw == "":
        return None
    try:
        ts = float(raw)
        if ts <= 0:
            return None
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def parse_osdr_search_payload(
    raw_text: str,
    origin_url: str,
    queried_at: str,
    license_or_terms: str,
) -> list[dict[str, Any]]:
    """Parse and strictly validate NASA OSDR search JSON hits into provenance-preserving records."""
    payload = json.loads(raw_text)
    if not isinstance(payload, dict) or "hits" not in payload or not isinstance(payload["hits"], dict):
        raise ValueError("Invalid OSDR JSON payload: missing 'hits' object")
    hits = payload["hits"].get("hits")
    if not isinstance(hits, list):
        raise ValueError("Invalid OSDR JSON payload: 'hits.hits' must be a list")

    records: list[dict[str, Any]] = []
    for item in hits:
        if not isinstance(item, dict):
            continue
        src = item.get("_source")
        if not isinstance(src, dict):
            continue
        accession = str(src.get("Accession") or src.get("Study Identifier") or item.get("_id") or "").strip()
        title = str(src.get("Study Title") or "").strip()
        if not accession or not title:
            continue

        mission = src.get("Mission") if isinstance(src.get("Mission"), dict) else {}
        mission_name = str(mission.get("Name") or "").strip() or None
        start_date = _clean_date_token(mission.get("Start Date"))
        end_date = _clean_date_token(mission.get("End Date"))
        release_date = _format_release_date(src.get("Study Public Release Date"))

        if start_date and end_date and start_date != end_date:
            observation_date = f"{start_date} – {end_date}"
        elif end_date or start_date:
            observation_date = end_date or start_date
        elif release_date:
            observation_date = release_date
        else:
            observation_date = "unspecified"

        raw_organism = src.get("organism") if src.get("organism") is not None else src.get("Organism")
        if isinstance(raw_organism, list):
            organism_label = ", ".join(str(x).strip() for x in raw_organism if str(x).strip()) or None
        elif raw_organism is not None:
            organism_label = str(raw_organism).strip() or None
        else:
            organism_label = None

        assay = str(src.get("Study Assay Technology Type") or "").strip() or None
        material = str(src.get("Material Type") or "").strip() or None
        flight_program = str(src.get("Flight Program") or src.get("Space Program") or "").strip() or None

        raw_unit = src.get("Study Unit") or src.get("unit")
        if raw_unit is None:
            # Study catalog records describe study metadata rather than scalar vital measurements.
            unit_field = "study_metadata_record" if assay else ""
        else:
            unit_field = str(raw_unit).strip()

        classification, quality_indicator = _classify_osdr_study(src)
        if organism_label is None:
            quality_indicator = f"{quality_indicator}; organism_missing_in_source"

        pop_parts = [p for p in (organism_label, material, mission_name, flight_program) if p]
        population_label = " · ".join(pop_parts) if pop_parts else "unspecified"
        variable_label = f"{accession} ({assay})" if assay else accession

        record = validate_external_record(
            {
                "source_id": "nasa-osdr-studies",
                "origin_url": origin_url,
                "queried_at": queried_at,
                "observation_date": observation_date,
                "variable": variable_label,
                "value": title,
                "unit": unit_field,
                "population": population_label,
                "retrieval_method": "https_json_rest_api",
                "quality_indicator": quality_indicator,
                "classification": classification,
                "license_or_terms": license_or_terms,
                "accession": accession,
                "study_url": f"https://osdr.nasa.gov/bio/repo/data/studies/{accession}" if accession.startswith("OSD-") else origin_url,
                "organism": organism_label,
                "release_date": release_date,
                "mission_name": mission_name,
                "flight_program": flight_program,
                "assay_technology": assay,
                "material_type": material,
                "record_nature": "study_metadata_record",
                "is_personal_astronaut_measurement": False,
            }
        )
        records.append(record)
    return records


def fetch_osdr_human_studies(
    source: dict[str, Any],
    *,
    force_refresh: bool = False,
    ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    http_get: Callable[[str, float], tuple[int, str, str]] | None = None,
) -> dict[str, Any]:
    """Query NASA OSDR public search endpoint safely with caching, timeouts, and error isolation."""
    endpoint = source.get("endpoint")
    if not endpoint or not is_official_whitelisted_url(endpoint):
        return {
            "source_id": source.get("id"),
            "status": VerificationStatus.REFERENCE_ONLY.value,
            "http_verified": False,
            "http_status": None,
            "queried_at": utc_now_iso(),
            "records": [],
            "error": "Source has no verified public API endpoint.",
            "from_cache": False,
        }

    now_mono = time.monotonic()
    with _CACHE_LOCK:
        if (
            not force_refresh
            and http_get is None
            and _OSDR_CACHE["queried_at"] is not None
            and (now_mono - float(_OSDR_CACHE["fetched_at_mono"])) < ttl_seconds
        ):
            return {
                "source_id": source["id"],
                "status": _OSDR_CACHE["status"],
                "http_verified": bool(_OSDR_CACHE.get("http_verified")),
                "http_status": _OSDR_CACHE.get("http_status"),
                "queried_at": _OSDR_CACHE["queried_at"],
                "records": list(_OSDR_CACHE["records"]),
                "error": _OSDR_CACHE["error"],
                "from_cache": True,
            }

    queried_at = utc_now_iso()
    fetcher = http_get or _default_http_get
    try:
        status_code, content_type, body = fetcher(endpoint, timeout)
        if status_code >= 400:
            raise RuntimeError(f"HTTP {status_code} returned by official endpoint")
        if "json" not in content_type.lower() and not body.lstrip().startswith("{"):
            raise ValueError(f"Unexpected non-JSON response content-type: {content_type or 'unknown'}")
        records = parse_osdr_search_payload(
            body,
            origin_url=endpoint,
            queried_at=queried_at,
            license_or_terms=source["license_or_terms"],
        )
        result = {
            "source_id": source["id"],
            "status": VerificationStatus.CONNECTED.value,
            "http_verified": True,
            "http_status": int(status_code),
            "queried_at": queried_at,
            "records": records,
            "error": None,
            "from_cache": False,
        }
    except (
        TimeoutError,
        ssl.SSLError,
        urllib.error.URLError,
        urllib.error.HTTPError,
        http.client.HTTPException,
        OSError,
        ValueError,
        json.JSONDecodeError,
        RuntimeError,
    ) as exc:
        result = {
            "source_id": source["id"],
            "status": VerificationStatus.UNAVAILABLE.value,
            "http_verified": False,
            "http_status": None,
            "queried_at": queried_at,
            "records": [],
            "error": f"{type(exc).__name__}: {exc}",
            "from_cache": False,
        }

    if http_get is None:
        with _CACHE_LOCK:
            _OSDR_CACHE.update(
                {
                    "fetched_at_mono": time.monotonic(),
                    "queried_at": result["queried_at"],
                    "status": result["status"],
                    "http_verified": result["http_verified"],
                    "http_status": result["http_status"],
                    "error": result["error"],
                    "records": list(result["records"]),
                }
            )
    return result


def verify_reference_reachability(
    source: dict[str, Any],
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    http_get: Callable[[str, float], tuple[int, str, str]] | None = None,
) -> dict[str, Any]:
    """Check HTTP reachability of a reference-only webpage without scraping or pretending it is a data API."""
    url = source.get("official_url")
    queried_at = utc_now_iso()
    if not url or not is_official_whitelisted_url(url):
        return {
            "source_id": source.get("id"),
            "status": VerificationStatus.UNAVAILABLE.value,
            "http_verified": False,
            "http_status": None,
            "queried_at": queried_at,
            "error": "Invalid or non-whitelisted URL.",
        }
    fetcher = http_get or _default_http_get
    try:
        status_code, _, _ = fetcher(url, timeout)
        if status_code >= 400:
            return {
                "source_id": source["id"],
                "status": VerificationStatus.UNAVAILABLE.value,
                "http_verified": False,
                "http_status": int(status_code),
                "queried_at": queried_at,
                "error": f"HTTP {status_code}",
            }
        # Never promote a webpage without an API endpoint to 'connected'.
        return {
            "source_id": source["id"],
            "status": source["verification_status"],
            "http_verified": True,
            "http_status": int(status_code),
            "queried_at": queried_at,
            "error": None,
        }
    except Exception as exc:
        return {
            "source_id": source["id"],
            "status": VerificationStatus.UNAVAILABLE.value,
            "http_verified": False,
            "http_status": None,
            "queried_at": queried_at,
            "error": f"{type(exc).__name__}: {exc}",
        }

