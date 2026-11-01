"""Insurance AI Voice Copilot — FastAPI entrypoint.

Run:  uvicorn app.main:app --reload --port 8000
Docs: http://localhost:8000/docs
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.rag import kb
from app.services.excel_store import excel_store
from app.routes.api import router
from app.services.agent_service import agent_service
from app.services.state_sync import state_sync

logging.basicConfig(level=settings.LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    state_sync.restore()  # Cloud Run: pull the last snapshot from Cloud Storage (no-op locally)
    init_db()          # SQLite schema + seed (policies, claims, quotes)
    excel_store.init() # Customer 360 workbook (customer master)
    excel_store.sync() # mirror policies/claims/quotes sheets
    kb.load()          # RAG ingestion → ChromaDB
    agent_service.init()  # LangGraph + Gemini (or offline agent)
    state_sync.start()    # Cloud Run: push changes to Cloud Storage every few seconds
    yield
    state_sync.stop()     # final snapshot on shutdown / scale-down


app = FastAPI(title="Insurance AI Voice Copilot API", version="1.0.0", lifespan=lifespan)


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):  # surface the real error in the chat UI (POC)
    logging.getLogger("app").exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": f"Backend error: {type(exc).__name__}: {str(exc)[:300]}"})
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=True,
                   # the UI may call FastAPI directly (proxy fallback) from localhost or a LAN address
                   allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|\[::1\]|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)(:\d+)?",
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(router)


@app.get("/")
def root():
    return {"name": "Insurance AI Voice Copilot API", "docs": "/docs", "health": "/api/health"}
