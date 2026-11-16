"""Authenticated, RBAC-protected NASA and CSA scientific integration routes."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from ..database import conn
from ..security import auth, need

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai.nasa_models import DataClassification, VerificationStatus, utc_now_iso, validate_external_record
from ai.nasa_sources import (
    get_domain_context,
    get_integration_summary,
    get_source,
    refresh_sources,
    source_registry,
)

router = APIRouter(prefix="/api/integrations/nasa", tags=["nasa"])

_SOURCE_ID_RE = re.compile(r"^[a-z0-9-]+$")


def _ensure_column(db, table: str, column: str, definition: str) -> None:
    cols = {r["name"] for r in db.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def ensure_nasa_tables() -> None:
    with conn() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS nasa_source_cache (
                source_id TEXT PRIMARY KEY,
                verification_status TEXT NOT NULL,
                last_checked TEXT,
                last_successful_at TEXT,
                http_verified INTEGER NOT NULL DEFAULT 0,
                http_status INTEGER,
                error TEXT,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS nasa_external_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                origin_url TEXT NOT NULL,
                queried_at TEXT NOT NULL,
                observation_date TEXT NOT NULL,
                variable TEXT NOT NULL,
                value TEXT NOT NULL,
                unit TEXT NOT NULL,
                population TEXT NOT NULL,
                retrieval_method TEXT NOT NULL,
                quality_indicator TEXT NOT NULL,
                classification TEXT NOT NULL,
                license_or_terms TEXT NOT NULL,
                accession TEXT,
                study_url TEXT,
                organism TEXT,
                release_date TEXT,
                mission_name TEXT,
                flight_program TEXT,
                assay_technology TEXT,
                material_type TEXT,
                sync_state TEXT NOT NULL DEFAULT 'previously_stored',
                UNIQUE(source_id, accession, variable)
            );
            """
        )
        _ensure_column(db, "nasa_source_cache", "last_successful_at", "TEXT")
        _ensure_column(db, "nasa_source_cache", "http_verified", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(db, "nasa_source_cache", "http_status", "INTEGER")
        _ensure_column(db, "nasa_external_records", "organism", "TEXT")
        _ensure_column(db, "nasa_external_records", "release_date", "TEXT")
        _ensure_column(db, "nasa_external_records", "sync_state", "TEXT NOT NULL DEFAULT 'previously_stored'")


ensure_nasa_tables()


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str | None = Field(default=None, min_length=2, max_length=80, pattern=r"^[a-z0-9-]+$")


def _merged_sources() -> list[dict[str, Any]]:
    ensure_nasa_tables()
    base = source_registry(include_additional_public=True)
    with conn() as db:
        rows = {
            row["source_id"]: dict(row)
            for row in db.execute(
                "SELECT source_id, verification_status, last_checked, last_successful_at, http_verified, http_status, error FROM nasa_source_cache"
            ).fetchall()
        }
    merged: list[dict[str, Any]] = []
    for src in base:
        item = dict(src)
        cached = rows.get(item["id"])
        if cached:
            item["verification_status"] = cached["verification_status"]
            item["last_checked"] = cached["last_checked"]
            item["last_successful_at"] = cached["last_successful_at"]
            item["http_verified"] = bool(cached["http_verified"])
            item["http_status"] = cached["http_status"]
            item["last_error"] = cached["error"]
        else:
            item["last_successful_at"] = None
            item["http_verified"] = False
            item["http_status"] = None
            item["last_error"] = None
        merged.append(item)
    return merged


def get_nasa_runtime_overview() -> dict[str, Any]:
    sources = _merged_sources()
    summary = get_integration_summary(sources)
    with conn() as db:
        record_count = db.execute("SELECT COUNT(*) FROM nasa_external_records").fetchone()[0]
    summary["external_records_count"] = int(record_count)
    return summary


def persist_refresh_results(result: dict[str, Any]) -> dict[str, Any]:
    ensure_nasa_tables()
    now_iso = utc_now_iso()
    records_fetched = len(result.get("records", []))
    records_inserted = 0
    records_updated = 0

    with conn() as db:
        previously_stored_count = int(
            db.execute("SELECT COUNT(*) FROM nasa_external_records").fetchone()[0]
        )

        for src in result.get("sources", []):
            err = result.get("errors", {}).get(src["id"])
            http_verified = 1 if src.get("http_verified") else 0
            http_status = src.get("http_status")
            last_successful = src.get("last_successful_at")
            if not last_successful and (
                src.get("verification_status") == VerificationStatus.CONNECTED.value or http_verified
            ):
                last_successful = src.get("last_checked")
            db.execute(
                """
                INSERT INTO nasa_source_cache(
                    source_id, verification_status, last_checked, last_successful_at,
                    http_verified, http_status, error, updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    verification_status=excluded.verification_status,
                    last_checked=excluded.last_checked,
                    last_successful_at=COALESCE(excluded.last_successful_at, nasa_source_cache.last_successful_at),
                    http_verified=excluded.http_verified,
                    http_status=excluded.http_status,
                    error=excluded.error,
                    updated_at=excluded.updated_at
                """,
                (
                    src["id"],
                    src["verification_status"],
                    src.get("last_checked"),
                    last_successful,
                    http_verified,
                    http_status,
                    err,
                    now_iso,
                ),
            )

        # Preserve previously stored records and explicitly tag prior vs newly fetched records.
        db.execute("UPDATE nasa_external_records SET sync_state='previously_stored'")

        for rec in result.get("records", []):
            validated = validate_external_record(rec)
            existing = db.execute(
                "SELECT id FROM nasa_external_records WHERE source_id=? AND accession IS ? AND variable=?",
                (validated["source_id"], validated.get("accession"), validated["variable"]),
            ).fetchone()
            sync_state = "updated" if existing else "new"
            if existing:
                records_updated += 1
            else:
                records_inserted += 1
            db.execute(
                """
                INSERT INTO nasa_external_records(
                    source_id, origin_url, queried_at, observation_date, variable, value,
                    unit, population, retrieval_method, quality_indicator, classification,
                    license_or_terms, accession, study_url, organism, release_date,
                    mission_name, flight_program, assay_technology, material_type, sync_state
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, accession, variable) DO UPDATE SET
                    origin_url=excluded.origin_url,
                    queried_at=excluded.queried_at,
                    observation_date=excluded.observation_date,
                    value=excluded.value,
                    unit=excluded.unit,
                    population=excluded.population,
                    retrieval_method=excluded.retrieval_method,
                    quality_indicator=excluded.quality_indicator,
                    classification=excluded.classification,
                    license_or_terms=excluded.license_or_terms,
                    study_url=excluded.study_url,
                    organism=excluded.organism,
                    release_date=excluded.release_date,
                    mission_name=excluded.mission_name,
                    flight_program=excluded.flight_program,
                    assay_technology=excluded.assay_technology,
                    material_type=excluded.material_type,
                    sync_state=excluded.sync_state
                """,
                (
                    validated["source_id"],
                    validated["origin_url"],
                    validated["queried_at"],
                    validated["observation_date"],
                    validated["variable"],
                    str(validated["value"]),
                    validated["unit"],
                    validated["population"],
                    validated["retrieval_method"],
                    validated["quality_indicator"],
                    validated["classification"],
                    validated["license_or_terms"],
                    validated.get("accession"),
                    validated.get("study_url"),
                    validated.get("organism"),
                    validated.get("release_date"),
                    validated.get("mission_name"),
                    validated.get("flight_program"),
                    validated.get("assay_technology"),
                    validated.get("material_type"),
                    sync_state,
                ),
            )

        total_stored_records = int(
            db.execute("SELECT COUNT(*) FROM nasa_external_records").fetchone()[0]
        )
        previously_stored_retained = int(
            db.execute("SELECT COUNT(*) FROM nasa_external_records WHERE sync_state='previously_stored'").fetchone()[0]
        )

    return {
        "previously_stored_count": previously_stored_count,
        "previously_stored_retained": previously_stored_retained,
        "records_fetched": records_fetched,
        "records_inserted": records_inserted,
        "records_updated": records_updated,
        "total_stored_records": total_stored_records,
    }


@router.get("")
def nasa_overview(authorization: str | None = Header(default=None)):
    user = auth(authorization)
    need(user, "medic", "admin")
    sources = _merged_sources()
    summary = get_integration_summary(sources)
    with conn() as db:
        record_count = db.execute("SELECT COUNT(*) FROM nasa_external_records").fetchone()[0]
    summary["external_records_count"] = int(record_count)
    return {
        "summary": summary,
        "sources": sources,
        "domains": get_domain_context(),
        "separation_notice": (
            "External NASA/CSA scientific references and public OSDR study metadata are strictly separated from "
            "personal astronaut telemetry, personal baselines, alerts, and synthetic demo data."
        ),
    }


@router.get("/sources")
def list_nasa_sources(
    authorization: str | None = Header(default=None),
    organization: str | None = Query(default=None, max_length=40),
    verification_status: VerificationStatus | None = Query(default=None),
    challenge_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    user = auth(authorization)
    need(user, "medic", "admin")
    items = _merged_sources()
    if challenge_only:
        items = [s for s in items if s.get("challenge_official_source")]
    if organization:
        org_q = organization.strip().lower()
        items = [s for s in items if org_q in s["organization"].lower()]
    if verification_status is not None:
        items = [s for s in items if s["verification_status"] == verification_status.value]
    total = len(items)
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items[offset : offset + limit],
    }


@router.get("/sources/{source_id}")
def get_nasa_source_detail(source_id: str, authorization: str | None = Header(default=None)):
    user = auth(authorization)
    need(user, "medic", "admin")
    if not _SOURCE_ID_RE.match(source_id):
        raise HTTPException(422, "Invalid source_id format")
    merged = {s["id"]: s for s in _merged_sources()}
    source = merged.get(source_id)
    if not source:
        raise HTTPException(404, "NASA/CSA source not found")

    domains = get_domain_context()
    detail_section: dict[str, Any] = {}
    if source_id == "nasa-hrp-hazards":
        detail_section["five_hazards"] = domains["five_hazards"]
    elif source_id == "nasa-hrp-risks":
        detail_section["risk_domains"] = domains["risk_domains"]
    elif source_id == "nasa-hrp-ongoing-research":
        detail_section["ongoing_programs"] = domains["ongoing_programs"]
    elif source_id == "csa-cans-radiation":
        detail_section["csa_cans"] = domains["csa_cans"]
    elif source_id == "csa-iss-science":
        detail_section["csa_iss_science"] = domains["csa_iss_science"]
    elif source_id == "nasa-osdr-studies":
        with conn() as db:
            rows = db.execute(
                "SELECT * FROM nasa_external_records WHERE source_id=? ORDER BY id DESC LIMIT 20",
                (source_id,),
            ).fetchall()
        detail_section["records"] = [dict(r) for r in rows]

    return {"source": source, "context": detail_section}


@router.get("/data")
def list_nasa_external_data(
    authorization: str | None = Header(default=None),
    source_id: str | None = Query(default=None, max_length=80, pattern=r"^[a-z0-9-]+$"),
    classification: DataClassification | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
):
    user = auth(authorization)
    need(user, "medic", "admin")
    if classification == DataClassification.SYNTHETIC_DEMO:
        raise HTTPException(422, "External scientific dataset endpoint never stores synthetic demo data")

    ensure_nasa_tables()
    clauses = ["1=1"]
    params: list[Any] = []
    if source_id:
        if not get_source(source_id):
            raise HTTPException(404, "Unknown NASA/CSA source_id")
        clauses.append("source_id=?")
        params.append(source_id)
    if classification is not None:
        clauses.append("classification=?")
        params.append(classification.value)

    where_sql = " AND ".join(clauses)
    with conn() as db:
        total = db.execute(f"SELECT COUNT(*) FROM nasa_external_records WHERE {where_sql}", params).fetchone()[0]
        rows = db.execute(
            f"SELECT * FROM nasa_external_records WHERE {where_sql} ORDER BY id DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()

    return {
        "total": int(total),
        "limit": limit,
        "offset": offset,
        "items": [dict(r) for r in rows],
        "separation_notice": (
            "Public NASA OSDR study-level metadata records only. Never merged with astronaut personal metrics, "
            "baselines, alerts, or synthetic demo scenarios."
        ),
    }


@router.post("/refresh")
def refresh_nasa_sources(
    payload: RefreshRequest | None = None,
    authorization: str | None = Header(default=None),
):
    user = auth(authorization)
    need(user, "admin")
    target_id = payload.source_id if payload else None
    if target_id and not get_source(target_id):
        raise HTTPException(404, "Unknown NASA/CSA source_id")

    result = refresh_sources(source_id=target_id, force_refresh=True)
    sync_counts = persist_refresh_results(result)

    from app.main import audit

    audit(user["username"], f"nasa_sources_refresh:{target_id or 'all'}")
    overview = get_nasa_runtime_overview()
    errors = result.get("errors", {})
    return {
        "ok": True,
        "partial_errors": bool(errors),
        "summary": overview,
        "sources": _merged_sources(),
        "records_ingested": sync_counts["records_fetched"],
        "refresh_report": {
            **sync_counts,
            "osdr_status": overview.get("osdr_status"),
            "osdr_error": overview.get("osdr_error"),
            "last_checked": overview.get("last_checked"),
            "last_successful_at": overview.get("last_successful_at"),
        },
        "errors": errors,
    }
