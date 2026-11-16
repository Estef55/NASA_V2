"""Server-side external generative AI adapter for LÁTI (Google AI Studio Gemini & OpenAI-compatible).

Strictly keeps API keys on the server, never fabricates external connections,
categorizes auth/quota/model/network errors explicitly, and enforces privacy boundaries.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
import time
from typing import Any, Callable
from urllib.parse import urlparse

import httpx

DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_GEMINI_MODEL = "gemini-4-hydrogen"
DEFAULT_TIMEOUT_SECONDS = 15.0
USER_AGENT = "aistudio-build"

_RUNTIME_STATE: dict[str, Any] = {
    "verification_status": "not_checked",
    "last_checked": None,
    "last_successful_at": None,
    "last_error": None,
    "last_error_code": None,
    "last_latency_ms": None,
}


@dataclass(frozen=True)
class LatiAiConfig:
    configured: bool
    provider: str  # 'gemini' | 'openai_compatible' | 'rules_local'
    base_url: str
    endpoint_host: str | None
    model: str | None
    api_key: str
    timeout_seconds: float


class LatiExternalAiError(RuntimeError):
    def __init__(self, code: str, message: str, http_status: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


def _redact_secret(text: str, api_key: str) -> str:
    clean = str(text or "").strip()
    if api_key and api_key in clean:
        clean = clean.replace(api_key, "[REDACTED]")
    return clean[:320]


def get_lati_ai_config() -> LatiAiConfig:
    api_key = (
        os.getenv("LATIRA_LLM_API_KEY", "").strip()
        or os.getenv("GEMINI_API_KEY", "").strip()
        or os.getenv("GOOGLE_API_KEY", "").strip()
    )
    raw_base_url = os.getenv("LATIRA_LLM_BASE_URL", "").strip()
    raw_model = (
        os.getenv("LATIRA_LLM_MODEL", "").strip()
        or os.getenv("GEMINI_MODEL", "").strip()
    )
    provider_override = os.getenv("LATIRA_LLM_PROVIDER", "").strip().lower()
    try:
        timeout = max(2.0, min(60.0, float(os.getenv("LATIRA_LLM_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))))
    except ValueError:
        timeout = DEFAULT_TIMEOUT_SECONDS

    if not api_key:
        return LatiAiConfig(
            configured=False,
            provider="rules_local",
            base_url="",
            endpoint_host=None,
            model=None,
            api_key="",
            timeout_seconds=timeout,
        )

    is_gemini = (
        provider_override in ("gemini", "google", "google_ai_studio")
        or (not raw_base_url and not provider_override)
        or ("generativelanguage.googleapis.com" in raw_base_url.lower())
    )

    if is_gemini:
        base_url = (raw_base_url or DEFAULT_GEMINI_BASE_URL).rstrip("/")
        model = raw_model or DEFAULT_GEMINI_MODEL
        host = urlparse(base_url).netloc or "generativelanguage.googleapis.com"
        return LatiAiConfig(
            configured=True,
            provider="gemini",
            base_url=base_url,
            endpoint_host=host,
            model=model,
            api_key=api_key,
            timeout_seconds=timeout,
        )

    base_url = raw_base_url.rstrip("/")
    model = raw_model or "gpt-4o-mini"
    host = urlparse(base_url).netloc or base_url
    return LatiAiConfig(
        configured=True,
        provider="openai_compatible",
        base_url=base_url,
        endpoint_host=host,
        model=model,
        api_key=api_key,
        timeout_seconds=timeout,
    )


def reset_runtime_state() -> None:
    _RUNTIME_STATE.update({
        "verification_status": "not_checked",
        "last_checked": None,
        "last_successful_at": None,
        "last_error": None,
        "last_error_code": None,
        "last_latency_ms": None,
    })


def _record_success(latency_ms: int) -> None:
    now = datetime.now(timezone.utc).isoformat()
    _RUNTIME_STATE.update({
        "verification_status": "connected",
        "last_checked": now,
        "last_successful_at": now,
        "last_error": None,
        "last_error_code": None,
        "last_latency_ms": latency_ms,
    })


def _record_failure(code: str, message: str, latency_ms: int | None = None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    _RUNTIME_STATE.update({
        "verification_status": code,
        "last_checked": now,
        "last_error": message,
        "last_error_code": code,
        "last_latency_ms": latency_ms,
    })


def get_lati_llm_status() -> dict[str, Any]:
    cfg = get_lati_ai_config()
    if not cfg.configured:
        return {
            "status": "not_configured",
            "mode": "rules_local",
            "configured": False,
            "connected": False,
            "provider": "rules_local",
            "model": None,
            "endpoint_host": None,
            "verification_status": "not_configured",
            "last_checked": _RUNTIME_STATE["last_checked"],
            "last_successful_at": _RUNTIME_STATE["last_successful_at"],
            "last_error": None,
            "last_error_code": None,
            "reason": (
                "No external generative model API key is configured. "
                "LÁTI operates with deterministic local rules and verified NASA/CSA catalog references."
            ),
        }

    v_status = _RUNTIME_STATE["verification_status"]
    connected = v_status == "connected"
    if v_status == "connected":
        status_value = "connected"
        reason = (
            f"External generative model verified ({cfg.provider} · {cfg.model}). "
            "Personal metrics, alerts, and check-ins stay local and are never sent externally."
        )
    elif _RUNTIME_STATE["last_error"]:
        status_value = "connection_error"
        reason = (
            f"External model configured ({cfg.provider} · {cfg.model}), but last check reported "
            f"{_RUNTIME_STATE['last_error_code'] or 'error'}: {_RUNTIME_STATE['last_error']}. "
            "Controlled local fallback remains available."
        )
    else:
        status_value = "configured"
        reason = (
            f"External generative model credentials configured ({cfg.provider} · {cfg.model}); "
            "live verification pending first chat request or explicit verification check. "
            "Personal metrics and clinical alerts remain isolated locally."
        )

    return {
        "status": status_value,
        "mode": "external_generative_hybrid",
        "configured": True,
        "connected": connected,
        "provider": cfg.provider,
        "model": cfg.model,
        "endpoint_host": cfg.endpoint_host,
        "verification_status": v_status,
        "last_checked": _RUNTIME_STATE["last_checked"],
        "last_successful_at": _RUNTIME_STATE["last_successful_at"],
        "last_error": _RUNTIME_STATE["last_error"],
        "last_error_code": _RUNTIME_STATE["last_error_code"],
        "last_latency_ms": _RUNTIME_STATE["last_latency_ms"],
        "reason": reason,
    }


def _build_system_prompt(language: str) -> str:
    if language == "en":
        return (
            "You are LÁTI, the crew wellbeing companion in LÁTIRA 2.0 for astronauts in training or orbit. "
            "Rules you MUST follow:\n"
            "1. Respond naturally and warmly in English using plain, clear sentences suitable for both reading and voice playback.\n"
            "2. Avoid markdown code blocks, tables, raw URLs, or repetitive technical disclaimers in every sentence.\n"
            "3. You are NOT a medical device and NOT a physician: never diagnose conditions, never prescribe medications, and never invent biometric measurements or alerts.\n"
            "4. If the crew member asks about their personal sleep/heart-rate numbers, alerts, or check-ins, remind them kindly to ask specifically for their saved indicators or check-ins.\n"
            "5. If the crew member reports persistent physical symptoms, distress, or feels unsafe, clearly encourage contacting the mission medical team."
        )
    return (
        "Eres LÁTI, el acompañante de bienestar de la tripulación en LÁTIRA 2.0 para astronautas en entrenamiento o en órbita. "
        "Reglas obligatorias:\n"
        "1. Responde de forma natural, empática y clara en español, con frases sencillas aptas tanto para lectura como para reproducción por voz.\n"
        "2. Evita bloques de código markdown, tablas o texto técnico innecesario que suene mal al leerse en voz alta.\n"
        "3. NO eres un dispositivo médico ni personal clínico: nunca diagnostiques enfermedades, nunca prescribas fármacos ni inventes mediciones biométricas o alertas.\n"
        "4. Si te preguntan por sus mediciones personales guardadas, línea base, chequeos o alertas, indícales que pueden consultarlos directamente en el chat usando sus registros locales.\n"
        "5. Si reportan malestar persistente o riesgo, recomienda contactar al equipo médico de la misión."
    )


def _default_http_post(url: str, headers: dict[str, str], json_body: dict[str, Any], timeout: float) -> tuple[int, dict[str, Any]]:
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, headers=headers, json=json_body)
        try:
            payload = resp.json()
        except Exception:
            payload = {"raw": resp.text[:400]}
        return resp.status_code, payload


def _extract_error_message(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("error"), dict):
        return str(payload["error"].get("message") or payload["error"].get("status") or "Provider error")
    if isinstance(payload.get("error"), str):
        return payload["error"]
    if payload.get("detail"):
        return str(payload["detail"])
    if payload.get("raw"):
        return str(payload["raw"])
    return "External AI request failed"


def _classify_http_error(status_code: int, payload: dict[str, Any], api_key: str) -> LatiExternalAiError:
    raw_msg = _extract_error_message(payload)
    msg = _redact_secret(raw_msg, api_key)
    lower = msg.lower()
    if status_code in (401, 403) or (status_code == 400 and ("api key" in lower or "api_key_invalid" in lower)):
        return LatiExternalAiError("auth_error", f"Authentication failed ({status_code}): {msg}", status_code)
    if status_code == 404:
        return LatiExternalAiError("model_not_found", f"Model or endpoint not found (404): {msg}", status_code)
    if status_code == 429 or "quota" in lower or "rate limit" in lower or "resource_exhausted" in lower:
        return LatiExternalAiError("quota_exceeded", f"Quota or rate limit reached ({status_code}): {msg}", status_code)
    if status_code >= 500:
        return LatiExternalAiError("provider_unavailable", f"External provider error ({status_code}): {msg}", status_code)
    return LatiExternalAiError("bad_request", f"External request rejected ({status_code}): {msg}", status_code)


def _call_gemini(
    cfg: LatiAiConfig,
    prompt_text: str,
    history: list[dict[str, str]],
    language: str,
    http_post: Callable[[str, dict[str, str], dict[str, Any], float], tuple[int, dict[str, Any]]],
    *,
    max_output_tokens: int = 400,
) -> tuple[str, int]:
    model_path = cfg.model if str(cfg.model).startswith("models/") else f"models/{cfg.model}"
    url = f"{cfg.base_url}/{model_path}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": cfg.api_key,
        "User-Agent": USER_AGENT,
    }
    contents: list[dict[str, Any]] = []
    for turn in history[-10:]:
        role = "model" if turn.get("role") == "assistant" else "user"
        text = str(turn.get("content") or "").strip()
        if text:
            contents.append({"role": role, "parts": [{"text": text}]})
    contents.append({"role": "user", "parts": [{"text": prompt_text}]})

    body: dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": _build_system_prompt(language)}]},
        "contents": contents,
        "generationConfig": {
            "temperature": 0.55,
            "maxOutputTokens": max_output_tokens,
        },
    }

    t0 = time.monotonic()
    try:
        status_code, payload = http_post(url, headers, body, cfg.timeout_seconds)
    except httpx.TimeoutException as exc:
        raise LatiExternalAiError("timeout", f"External model request timed out after {cfg.timeout_seconds}s") from exc
    except httpx.RequestError as exc:
        raise LatiExternalAiError("network_error", _redact_secret(f"Network error contacting external AI: {exc}", cfg.api_key)) from exc
    except Exception as exc:
        raise LatiExternalAiError("network_error", _redact_secret(f"Error contacting external AI: {exc}", cfg.api_key)) from exc

    latency_ms = int((time.monotonic() - t0) * 1000)
    if status_code >= 400:
        raise _classify_http_error(status_code, payload, cfg.api_key)

    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise LatiExternalAiError("invalid_response", "External model returned no candidates.")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(str(p.get("text") or "") for p in parts if isinstance(p, dict)).strip()
    if not text:
        raise LatiExternalAiError("invalid_response", "External model returned empty text.")
    return text, latency_ms


def _call_openai_compatible(
    cfg: LatiAiConfig,
    prompt_text: str,
    history: list[dict[str, str]],
    language: str,
    http_post: Callable[[str, dict[str, str], dict[str, Any], float], tuple[int, dict[str, Any]]],
    *,
    max_output_tokens: int = 400,
) -> tuple[str, int]:
    url = cfg.base_url if cfg.base_url.endswith("/chat/completions") else f"{cfg.base_url}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cfg.api_key}",
        "User-Agent": USER_AGENT,
    }
    messages: list[dict[str, str]] = [{"role": "system", "content": _build_system_prompt(language)}]
    for turn in history[-10:]:
        role = "assistant" if turn.get("role") == "assistant" else "user"
        text = str(turn.get("content") or "").strip()
        if text:
            messages.append({"role": role, "content": text})
    messages.append({"role": "user", "content": prompt_text})

    body: dict[str, Any] = {
        "model": cfg.model,
        "messages": messages,
        "temperature": 0.55,
        "max_tokens": max_output_tokens,
    }

    t0 = time.monotonic()
    try:
        status_code, payload = http_post(url, headers, body, cfg.timeout_seconds)
    except httpx.TimeoutException as exc:
        raise LatiExternalAiError("timeout", f"External model request timed out after {cfg.timeout_seconds}s") from exc
    except httpx.RequestError as exc:
        raise LatiExternalAiError("network_error", _redact_secret(f"Network error contacting external AI: {exc}", cfg.api_key)) from exc
    except Exception as exc:
        raise LatiExternalAiError("network_error", _redact_secret(f"Error contacting external AI: {exc}", cfg.api_key)) from exc

    latency_ms = int((time.monotonic() - t0) * 1000)
    if status_code >= 400:
        raise _classify_http_error(status_code, payload, cfg.api_key)

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LatiExternalAiError("invalid_response", "External model returned no choices.")
    msg_obj = choices[0].get("message") or {}
    text = str(msg_obj.get("content") or "").strip()
    if not text:
        raise LatiExternalAiError("invalid_response", "External model returned empty content.")
    return text, latency_ms


def generate_lati_reply(
    prompt_text: str,
    *,
    language: str = "es",
    history: list[dict[str, str]] | None = None,
    http_post: Callable[[str, dict[str, str], dict[str, Any], float], tuple[int, dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Generate a reply from the configured external model. Raises LatiExternalAiError on failure."""
    cfg = get_lati_ai_config()
    if not cfg.configured:
        raise LatiExternalAiError("not_configured", "External generative model is not configured.")

    sender = http_post or _default_http_post
    safe_history = history or []
    try:
        if cfg.provider == "gemini":
            text, latency_ms = _call_gemini(cfg, prompt_text, safe_history, language, sender)
            origin = "external_gemini"
        else:
            text, latency_ms = _call_openai_compatible(cfg, prompt_text, safe_history, language, sender)
            origin = "external_llm"
        _record_success(latency_ms)
        return {
            "reply": text,
            "origin": origin,
            "provider": cfg.provider,
            "model": cfg.model,
            "latency_ms": latency_ms,
        }
    except LatiExternalAiError as exc:
        _record_failure(exc.code, exc.message)
        raise


def verify_lati_llm_connection(
    *,
    http_post: Callable[[str, dict[str, str], dict[str, Any], float], tuple[int, dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Run a lightweight real probe against the configured external model endpoint."""
    cfg = get_lati_ai_config()
    if not cfg.configured:
        return get_lati_llm_status()

    sender = http_post or _default_http_post
    try:
        if cfg.provider == "gemini":
            _, latency_ms = _call_gemini(
                cfg,
                "Reply with OK.",
                [],
                "en",
                sender,
                max_output_tokens=16,
            )
        else:
            _, latency_ms = _call_openai_compatible(
                cfg,
                "Reply with OK.",
                [],
                "en",
                sender,
                max_output_tokens=16,
            )
        _record_success(latency_ms)
    except LatiExternalAiError as exc:
        _record_failure(exc.code, exc.message)

    return get_lati_llm_status()
