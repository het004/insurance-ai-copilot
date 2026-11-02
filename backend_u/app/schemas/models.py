"""Pydantic request/response contracts."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

__all__ = ["ChatRequest", "ChatResponse", "ToolUse", "Card", "Citation", "QuoteRequest", "ClaimCreate",
           "RenewRequest", "KnowledgeAsk", "PurchaseRequest", "LineQuoteRequest"]


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000, examples=["I need insurance for my new vehicle"])
    session_id: Optional[str] = None
    lang: Optional[str] = Field(None, examples=["en", "ar"], description="Reply language (auto-detected if omitted)")
    # NOTE: no customer_id — who is chatting is decided server-side (identify / KYC onboarding).


class ToolUse(BaseModel):
    name: str
    args: dict[str, Any] = {}
    ok: bool = True


class Card(BaseModel):
    type: Literal["quote", "profile", "policies", "claim", "renewal", "identity", "kyc", "registered", "purchase", "vehicle"]
    data: Any


class Citation(BaseModel):
    ref: int
    source: str
    title: str
    section: str
    content: str
    score: float
    cited: Optional[bool] = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    tools_used: list[ToolUse] = []
    cards: list[Card] = []
    citations: list[Citation] = []
    mode: Literal["gemini", "offline"]
    notice: Optional[str] = None
    identity: Optional[dict[str, Any]] = None


class QuoteRequest(BaseModel):
    customer_id: Optional[str] = None
    vehicle_type: str = Field(..., examples=["car"])
    vehicle_age: float = Field(..., ge=0, le=30, examples=[0])
    coverage: str = Field("comprehensive", examples=["comprehensive_plus"])
    location: str = Field(..., examples=["Riyadh"])
    ncb_percent: int = Field(0, ge=0, le=50)


class ClaimCreate(BaseModel):
    customer_id: Optional[str] = None
    policy_id: Optional[str] = None
    incident_date: Optional[str] = Field(None, examples=["2026-10-27"])
    incident_type: Optional[str] = None
    description: str = Field(..., min_length=5)
    location: Optional[str] = None
    estimated_amount: Optional[float] = Field(None, ge=0)


class RenewRequest(BaseModel):
    confirm: bool = False
    customer_id: Optional[str] = None


class KnowledgeAsk(BaseModel):
    question: str = Field(..., min_length=2, max_length=1000)
    k: int = Field(4, ge=1, le=8)


class PurchaseRequest(BaseModel):
    customer_id: Optional[str] = None
    quote_id: Optional[str] = None
    coverage: Optional[str] = None
    confirm: bool = False
    payment_method: Optional[str] = Field(None, examples=["mada"])
    registration_number: Optional[str] = None


class LineQuoteRequest(BaseModel):
    customer_id: Optional[str] = None
    plan: Optional[str] = None
    params: dict[str, Any] = Field(..., examples=[{"age": 38, "city": "Riyadh", "pre_existing": False}])
