"""Reusable Gemini service: chat model (with tool calling) + embeddings.

Wraps the Google Gen AI SDK through `langchain-google-genai` so the same client plugs into LangGraph (tool
binding, message history) and Chroma (embeddings). Two providers:
  • vertex      — Gemini on Vertex AI in your Google Cloud project, authenticated with your gcloud login,
                  optionally on Flex PayGo (header X-Vertex-AI-LLM-Shared-Request-Type: flex)
  • gemini_api  — Google AI Studio API key
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any

from app.config import settings

log = logging.getLogger(__name__)


class GeminiUnavailable(RuntimeError):
    pass


# ---------------------------------------------------------------- Vertex AI credentials
def _gcloud_token() -> str:
    """Same as the sample script: `gcloud auth print-access-token` (works on Windows, macOS, Linux)."""
    exe = shutil.which("gcloud") or shutil.which("gcloud.cmd") or "gcloud"
    try:
        out = subprocess.run([exe, "auth", "print-access-token"], capture_output=True, text=True, check=True,
                             timeout=30, shell=os.name == "nt" and exe.endswith(".cmd"))
    except FileNotFoundError as e:
        raise GeminiUnavailable("gcloud CLI not found — install Google Cloud CLI and run `gcloud auth login`") from e
    except subprocess.CalledProcessError as e:
        raise GeminiUnavailable(f"gcloud could not provide a token: {e.stderr.strip()[:200]}") from e
    token = out.stdout.strip().splitlines()[-1] if out.stdout.strip() else ""
    if not token:
        raise GeminiUnavailable("gcloud returned an empty access token — run `gcloud auth login`")
    return token


def _vertex_credentials():
    """google-auth credentials for Vertex AI.

    VERTEX_AUTH=gcloud (default): the user's gcloud login, refreshed by re-running `gcloud auth print-access-token`
    every ~50 minutes — exactly what the sample script does. VERTEX_AUTH=adc: Application Default Credentials
    (`gcloud auth application-default login`, or a service account on Cloud Run / GCE).
    """
    if settings.VERTEX_AUTH == "adc":
        import google.auth  # noqa: PLC0415

        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        return creds
    from google.oauth2.credentials import Credentials  # noqa: PLC0415

    class GcloudCredentials(Credentials):
        def refresh(self, request: Any) -> None:  # noqa: ARG002 — called by google-auth when expired
            self.token = _gcloud_token()
            self.expiry = datetime.utcnow() + timedelta(minutes=50)

    creds = GcloudCredentials(token=None)
    creds.refresh(None)
    return creds


_shared_creds: Any = None


def vertex_token() -> str:
    """A valid OAuth token for Google Cloud REST calls (TTS / STT), refreshed only when it expires."""
    global _shared_creds
    if _shared_creds is None:
        _shared_creds = _vertex_credentials()
    if not _shared_creds.valid:
        from google.auth.transport.requests import Request  # noqa: PLC0415

        _shared_creds.refresh(Request())
    return _shared_creds.token


def _vertex_headers() -> dict[str, str]:
    h = {"X-Server-Timeout": str(max(settings.VERTEX_TIMEOUT, 60))}
    if settings.VERTEX_FLEX:
        h["X-Vertex-AI-LLM-Shared-Request-Type"] = "flex"  # Flex PayGo — same header as the sample script
    return h


@lru_cache(maxsize=4)
def get_chat_model(temperature: float | None = None):
    if not settings.llm_enabled:
        raise GeminiUnavailable("No LLM configured (set VERTEX_PROJECT or GEMINI_API_KEY)")
    from langchain_google_genai import ChatGoogleGenerativeAI

    temp = settings.GEMINI_TEMPERATURE if temperature is None else temperature
    if settings.LLM_PROVIDER == "vertex":
        log.info("LLM: Vertex AI · project %s · %s · %s%s", settings.VERTEX_PROJECT, settings.VERTEX_LOCATION,
                 settings.VERTEX_MODEL, " · Flex PayGo" if settings.VERTEX_FLEX else "")
        return ChatGoogleGenerativeAI(
            model=settings.VERTEX_MODEL, vertexai=True, project=settings.VERTEX_PROJECT,
            location=settings.VERTEX_LOCATION, credentials=_vertex_credentials(),
            additional_headers=_vertex_headers(),
            **({"temperature": temp} if settings.VERTEX_MODEL.startswith(("gemini-2", "gemini-1")) else {}),
            max_retries=1, timeout=settings.VERTEX_TIMEOUT,
            **({"base_url": os.getenv("VERTEX_BASE_URL")} if os.getenv("VERTEX_BASE_URL") else {}),
        )
    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=temp,
        max_retries=2,
        timeout=60,
    )


@lru_cache(maxsize=1)
def get_embeddings():
    if not settings.llm_enabled:
        raise GeminiUnavailable("No LLM configured")
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    if settings.LLM_PROVIDER == "vertex":
        return GoogleGenerativeAIEmbeddings(model=settings.VERTEX_EMBEDDING_MODEL, vertexai=True,
                                            project=settings.VERTEX_PROJECT, location=settings.VERTEX_LOCATION,
                                            credentials=_vertex_credentials())
    return GoogleGenerativeAIEmbeddings(model=settings.EMBEDDING_MODEL, google_api_key=settings.GEMINI_API_KEY)


def text_of(content: Any) -> str:
    """Gemini may return str or a list of content parts — normalise to text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, str):
                parts.append(p)
            elif isinstance(p, dict) and p.get("type") == "text":
                parts.append(p.get("text", ""))
        return "".join(parts)
    return str(content or "")


def generate(prompt: str, system: str | None = None, temperature: float = 0.2) -> str:
    """One-shot generation (used by the Knowledge page answerer)."""
    from langchain_core.messages import HumanMessage, SystemMessage

    msgs = ([SystemMessage(system)] if system else []) + [HumanMessage(prompt)]
    return text_of(get_chat_model(temperature).invoke(msgs).content)


def embed_documents(texts: list[str]) -> list[list[float]]:
    return get_embeddings().embed_documents(texts)


def embed_query(text: str) -> list[float]:
    return get_embeddings().embed_query(text)
