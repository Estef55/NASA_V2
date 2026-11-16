"""Data models, controlled enums, and provenance validation for NASA/CSA integration."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from urllib.parse import urlparse


class VerificationStatus(str, Enum):
    REFERENCE_ONLY = "reference_only"
    CATALOGUED = "catalogued"
    AVAILABLE = "available"
    CONNECTED = "connected"
    UNAVAILABLE = "unavailable"
    RESTRICTED = "restricted"


class ResourceType(str, Enum):
    SCIENTIFIC_DOCUMENTATION = "scientific_documentation"
    RESEARCH_CATALOG = "research_catalog"
    PUBLIC_API_DATASET = "public_api_dataset"
    NEWS_ARTICLE = "news_article"
    EDUCATIONAL_CONTEXT = "educational_context"


class AccessType(str, Enum):
    PUBLIC_WEBPAGE = "public_webpage"
    RESTRICTED_DATA_REQUEST = "restricted_data_request"
    PUBLIC_REST_API = "public_rest_api"


class DataClassification(str, Enum):
    MISSION_OBSERVATION = "mission_observation"
    GROUND_HUMAN_RESEARCH = "ground_human_research"
    ANALOG_STUDY = "analog_study"
    SIMULATION = "simulation"
    SCIENTIFIC_REFERENCE = "scientific_reference"
    UNCONFIRMED_STUDY_CONTEXT = "unconfirmed_study_context"
    SYNTHETIC_DEMO = "synthetic_demo"


OFFICIAL_ALLOWED_HOSTS = frozenset({
    "www.nasa.gov",
    "nasa.gov",
    "humanresearchroadmap.nasa.gov",
    "osdr.nasa.gov",
    "www.asc-csa.gc.ca",
    "asc-csa.gc.ca",
})

REQUIRED_SOURCE_FIELDS = (
    "id",
    "name",
    "organization",
    "category",
    "description",
    "official_url",
    "resource_type",
    "access_type",
    "endpoint",
    "data_format",
    "variables",
    "units",
    "population",
    "coverage",
    "license_or_terms",
    "limitations",
    "verification_status",
    "last_checked",
)

REQUIRED_PROVENANCE_FIELDS = (
    "source_id",
    "origin_url",
    "queried_at",
    "observation_date",
    "variable",
    "value",
    "unit",
    "population",
    "retrieval_method",
    "quality_indicator",
    "classification",
    "license_or_terms",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_official_whitelisted_url(url: str | None) -> bool:
    if not url or not isinstance(url, str):
        return False
    parsed = urlparse(url.strip())
    if parsed.scheme != "https":
        return False
    hostname = (parsed.hostname or "").lower()
    return hostname in OFFICIAL_ALLOWED_HOSTS


def validate_source_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Validate that a catalogued source contains all required metadata fields and valid enums."""
    if not isinstance(entry, dict):
        raise ValueError("Source entry must be a dictionary")
    missing = [field for field in REQUIRED_SOURCE_FIELDS if field not in entry]
    if missing:
        raise ValueError(f"Source entry missing required fields: {', '.join(missing)}")
    if not is_official_whitelisted_url(entry["official_url"]):
        raise ValueError(f"Source official_url is not on the official NASA/CSA whitelist: {entry['official_url']}")
    if entry["endpoint"] is not None and not is_official_whitelisted_url(entry["endpoint"]):
        raise ValueError(f"Source endpoint is not on the official NASA/CSA whitelist: {entry['endpoint']}")

    VerificationStatus(entry["verification_status"])
    ResourceType(entry["resource_type"])
    AccessType(entry["access_type"])

    if entry["verification_status"] == VerificationStatus.CONNECTED.value and not entry["endpoint"]:
        raise ValueError("A source without a verified endpoint cannot be marked as connected")

    return dict(entry)


def validate_external_record(record: dict[str, Any]) -> dict[str, Any]:
    """Validate provenance and units of an external scientific/dataset record before persistence."""
    if not isinstance(record, dict):
        raise ValueError("External record must be a dictionary")
    missing = [field for field in REQUIRED_PROVENANCE_FIELDS if field not in record]
    if missing:
        raise ValueError(f"External record missing provenance fields: {', '.join(missing)}")
    if not is_official_whitelisted_url(record["origin_url"]):
        raise ValueError(f"External record origin_url not whitelisted: {record['origin_url']}")

    classification = DataClassification(record["classification"])
    if classification == DataClassification.SYNTHETIC_DEMO:
        raise ValueError("External dataset records must never be classified as synthetic_demo")

    cleaned = dict(record)
    raw_unit = cleaned.get("unit")
    if raw_unit is None or not str(raw_unit).strip():
        cleaned["unit"] = "unspecified"
        existing_quality = str(cleaned.get("quality_indicator") or "").strip()
        note = "unit_missing_in_source"
        cleaned["quality_indicator"] = f"{existing_quality}; {note}".strip("; ") if existing_quality else note

    return cleaned
