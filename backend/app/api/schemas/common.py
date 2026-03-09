"""Common Pydantic schemas for API request/response."""

from datetime import datetime
from pydantic import BaseModel, Field


# --- Sessions ---

class SessionCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str = ""


class SessionUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None


class SessionResponse(BaseModel):
    id: int
    title: str
    description: str
    status: str
    created_at: datetime
    updated_at: datetime
    paper_count: int = 0

    model_config = {"from_attributes": True}


# --- Chat ---

class ChatMessageRequest(BaseModel):
    content: str = Field(..., min_length=1)
    session_id: int


class ChatMessageResponse(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Search Plans ---

class SearchPlanResponse(BaseModel):
    id: int
    session_id: int
    plan_data: dict
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SearchPlanAction(BaseModel):
    action: str  # approve, reject, modify


# --- Papers ---

class PaperResponse(BaseModel):
    id: int
    session_id: int
    doi: str | None
    arxiv_id: str | None
    openalex_id: str | None
    title: str
    abstract: str
    authors: list
    journal: str
    year: int | None
    citation_count: int
    keywords: list
    fields: list
    source: str | None
    discovery_method: str | None
    relevance_score: float | None
    is_included: bool
    notes: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PaperUpdate(BaseModel):
    is_included: bool | None = None
    notes: str | None = None


# --- Analysis ---

class AnalysisRequest(BaseModel):
    session_id: int
    analysis_type: str  # bibliometrics, topic_modeling, trend, network
    params: dict = {}


class AnalysisResponse(BaseModel):
    id: int
    session_id: int
    analysis_type: str
    results: dict
    chart_configs: list
    ai_interpretation: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Reports ---

class ReportResponse(BaseModel):
    id: int
    session_id: int
    parent_report_id: int | None
    title: str
    content_markdown: str
    chart_configs: list
    version: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportGenerateRequest(BaseModel):
    session_id: int
    parent_report_id: int | None = None  # for incremental updates


# --- Settings ---

class SettingUpdate(BaseModel):
    key: str
    value: str
    is_sensitive: bool = False


class SettingResponse(BaseModel):
    key: str
    value: str  # masked if encrypted
    is_encrypted: bool

    model_config = {"from_attributes": True}


# --- Health ---

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    sources: dict = {}
