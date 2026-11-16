"""Verified scientific source registry and controlled reference query helpers for NASA/CSA."""
from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Callable

from .nasa_catalog import get_domain_catalog, get_static_sources
from .nasa_client import (
    DEFAULT_TIMEOUT_SECONDS,
    clear_cache,
    fetch_osdr_human_studies,
    verify_reference_reachability,
)
from .nasa_models import VerificationStatus


def source_registry(include_additional_public: bool = True) -> list[dict[str, Any]]:
    """Return the verified structured catalog of official NASA/CSA sources."""
    return get_static_sources(include_additional_public=include_additional_public)


def get_source(source_id: str) -> dict[str, Any] | None:
    for entry in source_registry(include_additional_public=True):
        if entry["id"] == source_id:
            return entry
    return None


def get_domain_context() -> dict[str, Any]:
    return get_domain_catalog()


def refresh_sources(
    source_id: str | None = None,
    *,
    force_refresh: bool = True,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    http_get: Callable[[str, float], tuple[int, str, str]] | None = None,
) -> dict[str, Any]:
    """Refresh runtime verification status for whitelisted catalog sources only."""
    sources = source_registry(include_additional_public=True)
    if source_id is not None:
        sources = [s for s in sources if s["id"] == source_id]
        if not sources:
            raise KeyError(f"Unknown NASA/CSA source_id: {source_id}")

    updated_sources: list[dict[str, Any]] = []
    fetched_records: list[dict[str, Any]] = []
    errors: dict[str, str] = {}

    for src in sources:
        item = deepcopy(src)
        if item.get("endpoint"):
            res = fetch_osdr_human_studies(
                item,
                force_refresh=force_refresh,
                timeout=timeout,
                http_get=http_get,
            )
            item["verification_status"] = res["status"]
            item["last_checked"] = res["queried_at"]
            item["http_verified"] = bool(res.get("http_verified"))
            item["http_status"] = res.get("http_status")
            if res["status"] == VerificationStatus.CONNECTED.value:
                item["last_successful_at"] = res["queried_at"]
            if res["error"]:
                errors[item["id"]] = res["error"]
                item["last_error"] = res["error"]
            else:
                item["last_error"] = None
            fetched_records.extend(res["records"])
        else:
            res = verify_reference_reachability(item, timeout=timeout, http_get=http_get)
            item["verification_status"] = res["status"]
            item["last_checked"] = res["queried_at"]
            item["http_verified"] = bool(res.get("http_verified"))
            item["http_status"] = res.get("http_status")
            if res.get("http_verified"):
                item["last_successful_at"] = res["queried_at"]
            if res["error"]:
                errors[item["id"]] = res["error"]
                item["last_error"] = res["error"]
            else:
                item["last_error"] = None
        updated_sources.append(item)

    return {
        "sources": updated_sources,
        "records": fetched_records,
        "errors": errors,
    }


def get_integration_summary(runtime_sources: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Summarize real integration state without conflating URL references with API connections."""
    sources = runtime_sources if runtime_sources is not None else source_registry(include_additional_public=True)
    official_challenge_count = sum(1 for s in sources if s.get("challenge_official_source"))
    public_data_sources = [s for s in sources if s.get("endpoint")]
    connected_sources = [s for s in sources if s.get("verification_status") == VerificationStatus.CONNECTED.value]
    unavailable_sources = [s for s in sources if s.get("verification_status") == VerificationStatus.UNAVAILABLE.value]
    http_verified_sources = [s for s in sources if s.get("http_verified")]
    restricted_sources = [
        s for s in sources
        if s.get("access_type") == "restricted_data_request"
        or s.get("verification_status") == VerificationStatus.RESTRICTED.value
    ]
    reference_sources = [
        s for s in sources
        if s.get("verification_status") in (
            VerificationStatus.REFERENCE_ONLY.value,
            VerificationStatus.CATALOGUED.value,
            VerificationStatus.RESTRICTED.value,
        )
    ]
    checked_timestamps = [s["last_checked"] for s in sources if s.get("last_checked")]
    last_checked = max(checked_timestamps) if checked_timestamps else None

    osdr_source = next((s for s in sources if s.get("id") == "nasa-osdr-studies"), None)
    osdr_status = osdr_source.get("verification_status") if osdr_source else VerificationStatus.AVAILABLE.value
    osdr_error = osdr_source.get("last_error") if osdr_source else None
    last_successful_at = osdr_source.get("last_successful_at") if osdr_source else None

    if connected_sources:
        overall_status = "partial_api_connected"
        reason = (
            f"{official_challenge_count} official NASA/CSA scientific references catalogued; "
            f"{len(connected_sources)} public NASA Open Data API connected (OSDR study metadata). "
            "No personal astronaut telemetry or CANS radiation feed connected."
        )
    elif osdr_status == VerificationStatus.UNAVAILABLE.value:
        overall_status = "api_unavailable"
        reason = (
            f"{official_challenge_count} official NASA/CSA sources catalogued as scientific references; "
            "NASA OSDR public API is temporarily unavailable (cached records preserved if present). "
            "No personal astronaut telemetry or CANS radiation feed connected."
        )
    else:
        overall_status = "catalogued_reference_only"
        reason = (
            f"{official_challenge_count} official NASA/CSA sources catalogued as scientific references; "
            f"{len(public_data_sources)} public NASA Open Data API available (OSDR, pending live verification). "
            "No personal astronaut telemetry or CANS radiation feed connected."
        )

    return {
        "status": overall_status,
        "reason": reason,
        "registered_sources_total": len(sources),
        "official_challenge_sources_count": official_challenge_count,
        "reference_only_or_catalogued_count": len(reference_sources),
        "http_verified_count": len(http_verified_sources),
        "restricted_count": len(restricted_sources),
        "unavailable_count": len(unavailable_sources),
        "public_verifiable_data_sources_count": len(public_data_sources),
        "api_connected_count": len(connected_sources),
        "osdr_status": osdr_status,
        "osdr_error": osdr_error,
        "last_checked": last_checked,
        "last_successful_at": last_successful_at,
        "access_limitations": (
            "NASA HRP clinical/study datasets (ARCHeR, Immune Biomarkers, Standard Measures, CIPHER, Spinal Health, Tempus Pro) "
            "and CSA CANS data are not exposed via open telemetry APIs. OSDR provides public study metadata only."
        ),
    }


def answer_scientific_query(question: str, language: str = "es") -> dict[str, Any] | None:
    """Deterministic local lookup over verified NASA/CSA scientific references for LÁTI.

    Returns None if the question is not about NASA/CSA scientific references so existing
    personal health/alert rules handle personal queries first.
    Never invents numbers, units, or private astronaut study values, and never calls external APIs.
    """
    q = (question or "").strip().casefold()
    if not q:
        return None
    is_en = language.lower().startswith("en")
    catalog = get_domain_catalog()

    # Honest boundary if user asks for personal radiation dose or live CANS/NASA telemetry
    if re.search(r"\b(mi radiación|my radiation|cans|dosis|dose|radiation|radiación)\b", q):
        cans = catalog["csa_cans"]
        if is_en:
            reply = (
                "Scientific reference (CSA CANS & NASA HRP): Space radiation is one of NASA's five human spaceflight hazards, "
                "and CSA's Canadian Active Neutron Spectrometer (CANS, 2026-02-26) is designed to monitor neutron radiation "
                "(~30% of the ISS radiation environment). Limitation: LÁTIRA is NOT connected to CANS, does not receive personal "
                "radiation measurements, and the 2026-02-26 CSA article does not publish quantitative dose units or a public dataset. "
                f"Official source: {cans['official_url']}"
            )
        else:
            reply = (
                "Referencia científica (CSA CANS y NASA HRP): La radiación espacial es uno de los cinco peligros de NASA, "
                "y el espectrómetro canadiense CANS (CSA, 2026-02-26) está diseñado para monitorear radiación neutrónica "
                "(~30% de la radiación total en la EEI). Limitación: LÁTIRA NO está conectado a CANS, no recibe mediciones "
                "personales de radiación y la fuente oficial no publica unidades cuantitativas ni un conjunto de datos público. "
                f"Fuente oficial: {cans['official_url']}"
            )
        return {
            "reply": reply,
            "context_source": "verified_nasa_csa_references",
            "citations": [cans["official_url"], "https://www.nasa.gov/hrp/hazards/"],
        }

    # Five Hazards
    if re.search(r"\b(hazards?|peligros?|five hazards|cinco peligros)\b", q):
        names = [h["name_en"] if is_en else h["name_es"] for h in catalog["five_hazards"]]
        if is_en:
            reply = (
                "Scientific reference (NASA HRP Five Hazards): " + "; ".join(names) + ". "
                "These are mission-level scientific context domains, not personal measurements collected by LÁTIRA. "
                "Official source: https://www.nasa.gov/hrp/hazards/"
            )
        else:
            reply = (
                "Referencia científica (Cinco peligros de NASA HRP): " + "; ".join(names) + ". "
                "Son dominios de contexto científico de misión, no mediciones individuales recolectadas automáticamente por LÁTIRA. "
                "Fuente oficial: https://www.nasa.gov/hrp/hazards/"
            )
        return {
            "reply": reply,
            "context_source": "verified_nasa_csa_references",
            "citations": ["https://www.nasa.gov/hrp/hazards/"],
        }

    # Ongoing HRP Programs
    for prog in catalog["ongoing_programs"]:
        tokens = {prog["id"].replace("_", " "), prog["name"].split("(")[0].strip().casefold()}
        if any(re.search(rf"\b{re.escape(tok)}\b", q) for tok in tokens if tok):
            desc = prog["description_en"] if is_en else prog["description_es"]
            lim = prog["access_limitations_en"] if is_en else prog["access_limitations_es"]
            if is_en:
                reply = (
                    f"Scientific reference ({prog['name']} — {prog['responsible_institution']}): {desc} "
                    f"Limitation: {lim} Official URL: {prog['official_url']}"
                )
            else:
                reply = (
                    f"Referencia científica ({prog['name']} — {prog['responsible_institution']}): {desc} "
                    f"Limitación: {lim} URL oficial: {prog['official_url']}"
                )
            return {
                "reply": reply,
                "context_source": "verified_nasa_csa_references",
                "citations": [prog["official_url"], "https://www.nasa.gov/hrp/ongoing-hrp-research/"],
            }

    # General NASA / CSA / Risks / Microgravity / OSDR / Research queries
    if re.search(r"\b(nasa|csa|asc|hrp|risks?|riesgos?|microgravity|microgravedad|iss|osdr|experiments?|experimentos?|eei)\b", q):
        if re.search(r"\b(microgravity|microgravedad|experiments?|experimentos?|csa|asc|iss|eei)\b", q):
            csa_sci = catalog["csa_iss_science"]
            if is_en:
                reply = (
                    "Scientific reference (CSA ISS Science): On average ~200 international experiments run on the ISS to prepare for "
                    "deep-space missions (weightlessness, radiation, isolation, delays) and improve life on Earth (studying accelerated "
                    "aging-like bone, muscle, cardiovascular, and balance changes). Note: this is conceptual scientific context, not a clinical dataset. "
                    f"Official source: {csa_sci['official_url']}"
                )
            else:
                reply = (
                    "Referencia científica (CSA Ciencia en la EEI): En promedio se realizan ~200 experimentos internacionales en la EEI "
                    "para preparar misiones al espacio profundo (ingravidez, radiación, aislamiento, retrasos) y mejorar la salud en la Tierra "
                    "(cambios acelerados en hueso, músculo, corazón y equilibrio). Nota: es contexto científico, no un conjunto de datos clínicos. "
                    f"Fuente oficial: {csa_sci['official_url']}"
                )
            return {
                "reply": reply,
                "context_source": "verified_nasa_csa_references",
                "citations": [csa_sci["official_url"]],
            }

        domains = [d["domain_en"] if is_en else d["domain_es"] for d in catalog["risk_domains"]]
        if is_en:
            reply = (
                "Scientific reference (NASA HRP & OSDR): LÁTIRA catalogs NASA's 5 Hazards, 9 Risk Domains (" + ", ".join(domains[:6]) + ", etc.), "
                "and 6 ongoing HRP studies (ARCHeR, Immune Biomarkers, Standard Measures, CIPHER, Spinal Health, Tempus Pro). "
                "These references contextualize wellbeing signals and do not diagnose or alter your personal baseline. "
                "For details beyond this verified catalog, LÁTIRA does not invent unverified NASA claims. "
                "Official source: https://www.nasa.gov/hrp/risks/"
            )
        else:
            reply = (
                "Referencia científica (NASA HRP y OSDR): LÁTIRA cataloga los 5 Peligros de NASA, 9 Dominios de Riesgo (" + ", ".join(domains[:6]) + ", etc.) "
                "y 6 programas HRP (ARCHeR, Immune Biomarkers, Standard Measures, CIPHER, Spinal Health, Tempus Pro). "
                "Estas referencias contextualizan señales de bienestar y no diagnostican ni modifican tu línea base personal. "
                "Si tu consulta excede este catálogo verificado, LÁTIRA no inventa datos ni afirmaciones no documentadas. "
                "Fuente oficial: https://www.nasa.gov/hrp/risks/"
            )
        return {
            "reply": reply,
            "context_source": "verified_nasa_csa_references",
            "citations": ["https://www.nasa.gov/hrp/risks/", "https://www.nasa.gov/hrp/ongoing-hrp-research/"],
        }

    return None


__all__ = [
    "answer_scientific_query",
    "clear_cache",
    "get_domain_context",
    "get_integration_summary",
    "get_source",
    "refresh_sources",
    "source_registry",
]
