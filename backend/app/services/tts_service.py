"""Natural-sounding speech for Amaan's replies — English and Arabic.

Providers are tried in order (TTS_PROVIDER, comma-separated):
  • google — Google Cloud Text-to-Speech, Chirp 3 HD voices (the most natural; en-US and ar-XA), using the same
             Google Cloud project and gcloud login as Vertex AI. Needs the Text-to-Speech API enabled.
  • edge   — Microsoft neural voices via the free `edge-tts` client (needs speech.platform.bing.com reachable).
If every provider fails, /api/tts returns 503 and the browser speaks with its own voice.
Audio is cached in memory, so replaying a message is instant.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
from collections import OrderedDict

from app.config import settings

log = logging.getLogger(__name__)

_default = "google,edge" if settings.LLM_PROVIDER == "vertex" and settings.VERTEX_PROJECT else "edge"
PROVIDERS = [p.strip() for p in os.getenv("TTS_PROVIDER", _default).lower().split(",") if p.strip() not in ("", "off")]

# Google Chirp 3 HD — persona names work across languages (Aoede, Kore, Leda, Zephyr… / Charon, Puck, Orus…)
GOOGLE_VOICE_EN = os.getenv("TTS_GOOGLE_VOICE_EN", "en-US-Chirp3-HD-Aoede")
GOOGLE_VOICE_AR = os.getenv("TTS_GOOGLE_VOICE_AR", "ar-XA-Chirp3-HD-Aoede")
GOOGLE_RATE = float(os.getenv("TTS_GOOGLE_RATE", "1.05"))
# Microsoft (edge-tts)
VOICE_EN = os.getenv("TTS_VOICE_EN", "en-US-AvaMultilingualNeural")
VOICE_AR = os.getenv("TTS_VOICE_AR", "ar-SA-ZariyahNeural")
RATE = os.getenv("TTS_RATE", "+4%")

ARABIC = re.compile(r"[؀-ۿ]")
_cache: OrderedDict[str, bytes] = OrderedDict()
_MAX_CACHE = 200
_disabled: set[str] = set()  # providers that failed with a permanent error (e.g. API not enabled)


class TTSUnavailable(Exception):
    pass


def is_arabic(text: str, lang: str | None) -> bool:
    if (lang or "").lower().startswith("ar"):
        return True
    return len(ARABIC.findall(text)) > len(text) * 0.4


# ---------------------------------------------------------------- Google Cloud TTS (Chirp 3 HD)
def _google_sync(text: str, arabic: bool) -> tuple[bytes, str]:
    import base64  # noqa: PLC0415

    import httpx  # noqa: PLC0415

    from app.services.gemini_service import vertex_token  # noqa: PLC0415

    voice = GOOGLE_VOICE_AR if arabic else GOOGLE_VOICE_EN
    body = {"input": {"text": text},
            "voice": {"languageCode": "ar-XA" if arabic else voice[:5], "name": voice},
            "audioConfig": {"audioEncoding": "MP3", "speakingRate": GOOGLE_RATE}}
    headers = {"Authorization": f"Bearer {vertex_token()}", "x-goog-user-project": settings.VERTEX_PROJECT,
               "Content-Type": "application/json; charset=utf-8"}
    r = httpx.post("https://texttospeech.googleapis.com/v1/text:synthesize", json=body, headers=headers, timeout=20)
    if r.status_code in (401, 403, 404):
        _disabled.add("google")  # API not enabled / no permission — don't retry every message
        raise TTSUnavailable(f"Google TTS {r.status_code}: {r.text[:200]}")
    r.raise_for_status()
    return base64.b64decode(r.json()["audioContent"]), voice


# ---------------------------------------------------------------- Microsoft neural voices (edge-tts)
async def _edge(text: str, arabic: bool) -> tuple[bytes, str]:
    import edge_tts  # noqa: PLC0415

    voice = VOICE_AR if arabic else VOICE_EN
    proxy = os.getenv("TTS_PROXY") or os.getenv("HTTPS_PROXY") or os.getenv("https_proxy") or None
    comm = edge_tts.Communicate(text, voice, rate=RATE, proxy=proxy, connect_timeout=6, receive_timeout=20)
    audio = bytearray()
    async with asyncio.timeout(25):
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                audio.extend(chunk["data"])
    if not audio:
        raise TTSUnavailable("No audio returned")
    return bytes(audio), voice


async def synthesize(text: str, lang: str | None = None) -> tuple[bytes, str]:
    text = text.strip()[:1500]
    if not text:
        raise TTSUnavailable("Nothing to say")
    arabic = is_arabic(text, lang)
    errors = []
    for provider in PROVIDERS:
        if provider in _disabled:
            continue
        key = hashlib.sha1(f"{provider}|{arabic}|{text}".encode()).hexdigest()
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key], provider
        try:
            if provider == "google":
                audio, voice = await asyncio.to_thread(_google_sync, text, arabic)
            elif provider == "edge":
                audio, voice = await _edge(text, arabic)
            else:
                continue
        except Exception as e:  # noqa: BLE001 — try the next provider
            log.warning("TTS provider %s failed: %s", provider, str(e)[:200])
            errors.append(f"{provider}: {str(e)[:120]}")
            continue
        _cache[key] = audio
        if len(_cache) > _MAX_CACHE:
            _cache.popitem(last=False)
        return audio, voice
    raise TTSUnavailable("; ".join(errors) or "Neural TTS is disabled (TTS_PROVIDER)")


def status() -> dict:
    return {"providers": [p for p in PROVIDERS if p not in _disabled], "google_voices": [GOOGLE_VOICE_EN, GOOGLE_VOICE_AR],
            "edge_voices": [VOICE_EN, VOICE_AR]}
