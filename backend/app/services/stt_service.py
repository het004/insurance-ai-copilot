"""Server-side speech recognition (English + Saudi Arabic) with Google Cloud Speech-to-Text V2.

The browser records a short clip (WebM/Opus) and posts it to /api/stt. We try Chirp 3 first (most accurate,
ar-SA + en-US) and fall back to the "short" model in the global location. Same Google Cloud project and gcloud
login as Vertex AI; the Speech-to-Text API must be enabled. If it isn't available the browser's own
SpeechRecognition is used instead (Chrome / Edge also support ar-SA).
"""
from __future__ import annotations

import base64
import logging
import os

from app.config import settings

log = logging.getLogger(__name__)

_default = "google" if settings.LLM_PROVIDER == "vertex" and settings.VERTEX_PROJECT else "browser"
PROVIDER = os.getenv("STT_PROVIDER", _default).lower()
# "model@location" attempts in order
ATTEMPTS = [tuple(x.split("@")) for x in os.getenv("STT_MODELS", "chirp_3@eu,short@global").split(",") if "@" in x]
LANGS = {"ar": os.getenv("STT_LANG_AR", "ar-SA"), "en": os.getenv("STT_LANG_EN", "en-US")}
_dead: set[tuple[str, str]] = set()


class STTUnavailable(Exception):
    pass


def enabled() -> bool:
    return PROVIDER == "google" and bool(settings.VERTEX_PROJECT)


def _host(location: str) -> str:
    return "https://speech.googleapis.com" if location == "global" else f"https://{location}-speech.googleapis.com"


def transcribe(audio: bytes, lang: str | None = None) -> dict:
    if not enabled():
        raise STTUnavailable("Server speech recognition is off (STT_PROVIDER)")
    if len(audio) < 1200:
        return {"text": "", "engine": None}
    import httpx  # noqa: PLC0415

    from app.services.gemini_service import vertex_token  # noqa: PLC0415

    code = LANGS["ar" if (lang or "").lower().startswith("ar") else "en"]
    errors = []
    for model, location in ATTEMPTS:
        if (location, model) in _dead:
            continue
        url = f"{_host(location)}/v2/projects/{settings.VERTEX_PROJECT}/locations/{location}/recognizers/_:recognize"
        body = {"config": {"autoDecodingConfig": {}, "languageCodes": [code], "model": model,
                           "features": {"enableAutomaticPunctuation": True}},
                "content": base64.b64encode(audio).decode()}
        try:
            r = httpx.post(url, json=body, timeout=30, headers={
                "Authorization": f"Bearer {vertex_token()}", "x-goog-user-project": settings.VERTEX_PROJECT})
            if r.status_code >= 400:
                if r.status_code in (403, 404) or (r.status_code == 400 and any(
                        w in r.text.lower() for w in ("model", "language", "location", "not supported"))):
                    _dead.add((location, model))  # model/region/API not available for this project
                raise STTUnavailable(f"{r.status_code}: {r.text[:200]}")
            results = r.json().get("results", [])
            text = " ".join(a["alternatives"][0]["transcript"].strip() for a in results if a.get("alternatives"))
            return {"text": text.strip(), "engine": f"{model}@{location}", "language": code}
        except Exception as e:  # noqa: BLE001
            log.warning("STT %s@%s failed: %s", model, location, str(e)[:200])
            errors.append(f"{model}@{location}: {str(e)[:120]}")
    raise STTUnavailable("; ".join(errors) or "No speech model available")
