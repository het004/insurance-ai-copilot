"""Quick check that the backend can reach Gemini on Vertex AI with your gcloud login (and Flex, if enabled).

Run from the backend folder:   python scripts/check_vertex.py
Uses the same settings as the app (backend/.env): VERTEX_PROJECT, VERTEX_LOCATION, VERTEX_MODEL, VERTEX_FLEX, VERTEX_AUTH.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings  # noqa: E402
from app.services import gemini_service  # noqa: E402

if settings.LLM_PROVIDER != "vertex":
    sys.exit("LLM_PROVIDER is not 'vertex' — set VERTEX_PROJECT (and LLM_PROVIDER=vertex) in backend/.env")

print(f"Project : {settings.VERTEX_PROJECT}\nLocation: {settings.VERTEX_LOCATION}\nModel   : {settings.VERTEX_MODEL}"
      f"\nFlex    : {settings.VERTEX_FLEX}\nAuth    : {settings.VERTEX_AUTH}\n" + "-" * 60)
t0 = time.time()
try:
    reply = gemini_service.generate("Hello Gemini. Give me a one sentence response.")
except Exception as e:  # noqa: BLE001
    sys.exit(f"FAILED after {time.time() - t0:.1f}s: {e}")
print(f"OK in {time.time() - t0:.1f}s\n{reply}")
