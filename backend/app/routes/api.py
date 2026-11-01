"""REST API. Every route delegates to services/ — the same functions the agent tools call."""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from pydantic import BaseModel

from app.config import settings
from app.rag import kb
from app.schemas import ChatRequest, ChatResponse, ClaimCreate, KnowledgeAsk, LineQuoteRequest, PurchaseRequest, QuoteRequest, RenewRequest
from app.services import insurance_service as svc
from app.services import knowledge_service, purchase_service, reprice_service, stt_service, tts_service
from app.services.agent_service import agent_service
from app.services.excel_store import excel_store
from app.services.session_store import session_store

router = APIRouter(prefix="/api")


def _cid(customer_id: Optional[str]) -> str:
    return customer_id or settings.DEFAULT_CUSTOMER_ID


def _guard(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except svc.NotFound as e:
        raise HTTPException(404, str(e)) from e
    except (svc.InvalidRequest, ValueError) as e:
        raise HTTPException(400, str(e)) from e


# ---------------------------------------------------------------- health
@router.get("/health", tags=["system"])
def health():
    return {"status": "ok", "insurer": settings.INSURER_NAME, "insurer_short": settings.INSURER_SHORT,
            "agent_mode": agent_service.mode, "retrieval_mode": kb.mode,
            "model": settings.model_label if settings.llm_enabled else None, "llm_provider": settings.LLM_PROVIDER, "model_id": settings.model_name if settings.llm_enabled else None,
            "knowledge_chunks": len(kb.chunks), "default_customer_id": settings.DEFAULT_CUSTOMER_ID,
            "stt_server": stt_service.enabled(), "tts_providers": tts_service.status()["providers"]}


# ---------------------------------------------------------------- chat (agent)
class TTSRequest(BaseModel):
    text: str
    lang: Optional[str] = None


@router.post("/tts", tags=["voice"], summary="Neural text-to-speech (MP3). 503 → the browser uses its own voice")
async def tts(body: TTSRequest):
    try:
        audio, voice = await tts_service.synthesize(body.text, body.lang)
    except tts_service.TTSUnavailable as e:
        raise HTTPException(503, f"Neural voice unavailable: {e}") from e
    return Response(audio, media_type="audio/mpeg", headers={"X-TTS-Voice": voice, "Cache-Control": "no-store"})


@router.post("/stt", tags=["voice"], summary="Speech-to-text (Google Cloud Chirp). 503 → the browser recognises speech itself")
async def stt(audio: UploadFile = File(...), lang: Optional[str] = None):
    data = await audio.read()
    try:
        import asyncio  # noqa: PLC0415

        return await asyncio.to_thread(stt_service.transcribe, data, lang)
    except stt_service.STTUnavailable as e:
        raise HTTPException(503, f"Server speech recognition unavailable: {e}") from e


@router.get("/voice", tags=["voice"], summary="Which voice engines are active")
def voice_status():
    return {"tts": tts_service.status(), "stt": {"server": stt_service.enabled(), "models": stt_service.ATTEMPTS}}


@router.post("/chat", response_model=ChatResponse, tags=["chat"])
def chat(req: ChatRequest):
    return _guard(agent_service.chat, req.message, req.session_id, req.lang)


@router.post("/chat/stream", tags=["chat"], summary="Server-Sent Events: live agent progress + final reply")
def chat_stream(req: ChatRequest):
    """Streams `data: {json}\\n\\n` events: run_started, step, tool_call, tool_result, notice, final, error."""
    def events():
        try:
            for ev in agent_service.chat_stream(req.message, req.session_id, req.lang):
                yield f"data: {json.dumps(ev, default=str)}\n\n"
        except Exception as e:  # noqa: BLE001
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})


@router.get("/chat/{session_id}/identity", tags=["chat"])
def chat_identity(session_id: str):
    return session_store.get(session_id).public()


@router.delete("/chat/{session_id}", tags=["chat"])
def reset_chat(session_id: str):
    agent_service.reset(session_id)
    return {"ok": True}


@router.get("/interactions/recent", tags=["chat"])
def recent(customer_id: Optional[str] = None, limit: int = 6):
    return svc.recent_interactions(_cid(customer_id), min(limit, 20))


# ---------------------------------------------------------------- customers
@router.get("/customers", tags=["customers"])
def customers():
    return svc.list_customers()


@router.get("/customers/{customer_id}/360", tags=["customers"])
def customer_360(customer_id: str):
    return _guard(svc.get_customer_360, customer_id)


# ---------------------------------------------------------------- policies
@router.get("/policies", tags=["policies"])
def policies(customer_id: Optional[str] = None):
    return svc.list_policies(_cid(customer_id))


@router.get("/policies/{policy_id}", tags=["policies"])
def policy(policy_id: str):
    return _guard(svc.get_policy, policy_id)


@router.get("/policies/{policy_id}/document", tags=["policies"], response_class=HTMLResponse,
            summary="Policy schedule (demo document)")
def policy_document(policy_id: str):
    return HTMLResponse(_guard(purchase_service.policy_document, policy_id))


@router.post("/purchase", tags=["policies"], summary="Checkout: review (confirm=false) or pay + issue (confirm=true)")
def purchase(req: PurchaseRequest):
    return _guard(purchase_service.purchase, _cid(req.customer_id), quote_id=req.quote_id, coverage=req.coverage,
                  confirm=req.confirm, payment_method=req.payment_method, registration_number=req.registration_number)


@router.get("/payments", tags=["policies"])
def payments(customer_id: Optional[str] = None):
    return purchase_service.list_payments(_cid(customer_id))


@router.get("/policies/{policy_id}/renewal-quote", tags=["policies"])
def renewal_quote(policy_id: str):
    return _guard(svc.renewal_quote, policy_id)


@router.post("/policies/{policy_id}/renew", tags=["policies"])
def renew(policy_id: str, req: RenewRequest):
    return _guard(svc.renew_policy, policy_id, req.confirm, req.customer_id)


# ---------------------------------------------------------------- quotes
@router.post("/quotes", tags=["quotes"])
def create_quote(req: QuoteRequest):
    return _guard(svc.create_quote, _cid(req.customer_id), req.vehicle_type, req.vehicle_age,
                  req.coverage, req.location, req.ncb_percent)


@router.get("/products", tags=["quotes"], summary="Our online product catalogue (motor, health, home)")
def product_catalogue():
    from app.services import products

    return {"insurer": settings.INSURER_NAME, "lines": products.CATALOGUE}


@router.post("/quotes/{line}", tags=["quotes"], summary="Quote any portfolio: motor | health | life | savings | general")
def create_line_quote(line: str, req: LineQuoteRequest):
    return _guard(svc.create_product_quote, _cid(req.customer_id), line.lower(), req.params, req.plan)


class RepriceRequest(BaseModel):
    changes: dict
    session_id: Optional[str] = None


@router.post("/quotes/{quote_id}/reprice/stream", tags=["quotes"],
             summary="Re-price a quote after a slider / toggle change (SSE with live engine steps)")
def reprice_quote(quote_id: str, req: RepriceRequest):
    def events():
        try:
            for ev in reprice_service.reprice_stream(quote_id, req.changes, req.session_id):
                yield f"data: {json.dumps(ev, default=str)}\n\n"
        except Exception as e:  # noqa: BLE001
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})


@router.get("/quotes", tags=["quotes"])
def list_quotes(customer_id: Optional[str] = None):
    return svc.list_quotes(_cid(customer_id))


# ---------------------------------------------------------------- claims
@router.post("/claims", tags=["claims"])
def create_claim(req: ClaimCreate):
    return _guard(svc.create_claim, _cid(req.customer_id), req.description, req.incident_date, req.location,
                  req.policy_id, req.incident_type, req.estimated_amount)


@router.get("/claims", tags=["claims"])
def list_claims(customer_id: Optional[str] = None):
    return svc.list_claims(_cid(customer_id))


@router.get("/claims/{claim_id}", tags=["claims"])
def get_claim(claim_id: str):
    return _guard(svc.get_claim, claim_id)


@router.post("/claims/{claim_id}/advance", tags=["claims"], summary="Demo: move claim to next stage")
def advance_claim(claim_id: str):
    return _guard(svc.advance_claim, claim_id)


# ---------------------------------------------------------------- knowledge (RAG)
@router.post("/knowledge/ask", tags=["knowledge"])
def ask(req: KnowledgeAsk):
    return knowledge_service.answer(req.question, req.k)


@router.get("/knowledge/sources", tags=["knowledge"])
def sources():
    return {"retrieval_mode": kb.mode, "sources": kb.sources()}


@router.post("/knowledge/upload", tags=["knowledge"])
async def upload(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 10 MB)")
    return _guard(kb.add_document, file.filename or "upload.txt", data)


@router.post("/knowledge/reindex", tags=["knowledge"])
def reindex():
    kb.reset_vectors()
    return {"ok": True, "chunks": len(kb.chunks), "retrieval_mode": kb.mode}


# ---------------------------------------------------------------- staff console
@router.get("/console/overview", tags=["console"])
def console_overview():
    customers = svc.list_customers()
    return {"customers": customers, "active_sessions": session_store.active(), "excel": excel_store.status()}


@router.get("/console/customer-360.xlsx", tags=["console"], summary="Download the Customer 360 workbook")
def download_workbook():
    from fastapi.responses import FileResponse

    excel_store.sync()
    return FileResponse(excel_store.path, filename="art_customer_360.xlsx",
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@router.post("/console/excel/sync", tags=["console"])
def sync_workbook():
    return excel_store.sync()
