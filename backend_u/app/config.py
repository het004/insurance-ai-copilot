"""Central configuration, loaded from environment / .env."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-001")
    GEMINI_TEMPERATURE: float = float(os.getenv("GEMINI_TEMPERATURE", "0.3"))

    # ---- LLM provider: "vertex" (Google Cloud project, e.g. Flex PayGo) or "gemini_api" (AI Studio key)
    VERTEX_PROJECT: str = os.getenv("VERTEX_PROJECT", "")
    VERTEX_LOCATION: str = os.getenv("VERTEX_LOCATION", "global")
    VERTEX_MODEL: str = os.getenv("VERTEX_MODEL", "gemini-3.5-flash-lite")
    VERTEX_EMBEDDING_MODEL: str = os.getenv("VERTEX_EMBEDDING_MODEL", "gemini-embedding-001")
    VERTEX_FLEX: bool = os.getenv("VERTEX_FLEX", "true").lower() in ("1", "true", "yes")
    VERTEX_AUTH: str = os.getenv("VERTEX_AUTH", "gcloud").lower()   # gcloud = `gcloud auth print-access-token`; adc
    VERTEX_TIMEOUT: int = int(os.getenv("VERTEX_TIMEOUT", "120"))    # seconds before the chat falls back to offline
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "vertex" if os.getenv("VERTEX_PROJECT") else "gemini_api").lower()

    DATA_DIR: Path = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data"))).resolve()
    DOCS_DIR: Path = BASE_DIR / "app" / "rag" / "documents"

    # Brand — the app is the insurer's own assistant (Al Rajhi Takaful for this POC).
    INSURER_NAME: str = os.getenv("INSURER_NAME", "Al Rajhi Takaful")
    INSURER_SHORT: str = os.getenv("INSURER_SHORT", "Al Rajhi Takaful")
    ASSISTANT_NAME: str = os.getenv("ASSISTANT_NAME", "Amaan")
    ASSISTANT_NAME_AR: str = os.getenv("ASSISTANT_NAME_AR", "أمان")
    COUNTRY: str = "Saudi Arabia"
    CURRENCY: str = "SAR"
    VAT_RATE: float = 0.15  # ZATCA: health, motor, general standard-rated; life insurance exempt

    DEFAULT_CUSTOMER_ID: str = os.getenv("DEFAULT_CUSTOMER_ID", "CUST-1001")
    CORS_ORIGINS: list[str] = [
        o.strip()
        for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
        if o.strip()
    ]
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def SQLITE_PATH(self) -> Path:
        return self.DATA_DIR / "art_ksa.db"  # KSA edition (Saudi customers, SAR)

    @property
    def EXCEL_PATH(self) -> Path:
        return Path(os.getenv("CUSTOMER_360_XLSX", str(self.DATA_DIR / "art_customer_360.xlsx"))).resolve()

    @property
    def CHROMA_DIR(self) -> Path:
        return self.DATA_DIR / "chroma"

    @property
    def UPLOAD_DIR(self) -> Path:
        return self.DATA_DIR / "uploads"

    @property
    def llm_enabled(self) -> bool:
        if self.LLM_PROVIDER == "vertex":
            return bool(self.VERTEX_PROJECT)
        return bool(self.GEMINI_API_KEY)

    @property
    def model_name(self) -> str:
        return self.VERTEX_MODEL if self.LLM_PROVIDER == "vertex" else self.GEMINI_MODEL

    @property
    def model_label(self) -> str:
        if self.LLM_PROVIDER == "vertex":
            return f"Amaan AI · Vertex AI{' Flex' if self.VERTEX_FLEX else ''}"
        return "Amaan AI"


settings = Settings()
for _d in (settings.DATA_DIR, settings.CHROMA_DIR, settings.UPLOAD_DIR):
    _d.mkdir(parents=True, exist_ok=True)
