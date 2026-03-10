"""SQLAlchemy ORM models for ARTA."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class ResearchSession(Base):
    __tablename__ = "research_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, default="")
    status = Column(String(50), default="active")  # active, archived, completed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")
    search_plans = relationship("SearchPlan", back_populates="session", cascade="all, delete-orphan")
    papers = relationship("Paper", back_populates="session", cascade="all, delete-orphan")
    analysis_runs = relationship("AnalysisRun", back_populates="session", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ResearchSession", back_populates="messages")


class SearchPlan(Base):
    __tablename__ = "search_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False)
    plan_data = Column(JSON, nullable=False)  # structured plan
    status = Column(String(50), default="draft")  # draft, approved, executing, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    session = relationship("ResearchSession", back_populates="search_plans")
    executions = relationship("SearchExecution", back_populates="plan", cascade="all, delete-orphan")


class SearchExecution(Base):
    __tablename__ = "search_executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(Integer, ForeignKey("search_plans.id", ondelete="CASCADE"), nullable=False)
    source_name = Column(String(100), nullable=False)  # openalex, arxiv, scopus
    query = Column(Text, nullable=False)
    params = Column(JSON, default=dict)
    results_count = Column(Integer, default=0)
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    error_message = Column(Text)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    plan = relationship("SearchPlan", back_populates="executions")


class Paper(Base):
    __tablename__ = "papers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False)

    # Identifiers
    doi = Column(String(255), index=True)
    arxiv_id = Column(String(100), index=True)
    openalex_id = Column(String(100), index=True)
    scopus_id = Column(String(100))

    # Metadata
    title = Column(Text, nullable=False)
    abstract = Column(Text, default="")
    authors = Column(JSON, default=list)  # [{name, affiliation, orcid}]
    journal = Column(String(500), default="")
    year = Column(Integer, index=True)
    publication_date = Column(String(20))
    volume = Column(String(50))
    issue = Column(String(50))
    pages = Column(String(50))
    url = Column(Text)
    pdf_url = Column(Text)

    # Metrics
    citation_count = Column(Integer, default=0)
    reference_count = Column(Integer, default=0)

    # Classification
    keywords = Column(JSON, default=list)
    fields = Column(JSON, default=list)
    paper_type = Column(String(50))  # article, preprint, review, conference

    # Source tracking
    source = Column(String(100))  # which data source found this
    discovery_method = Column(String(50))  # search
    relevance_score = Column(Float)

    # Status
    is_included = Column(Boolean, default=True)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    session = relationship("ResearchSession", back_populates="papers")

    __table_args__ = (
        Index("ix_papers_title_year", "title", "year"),
    )


class PaperCitation(Base):
    __tablename__ = "paper_citations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    citing_paper_id = Column(Integer, ForeignKey("papers.id", ondelete="CASCADE"), nullable=False)
    cited_paper_id = Column(Integer, ForeignKey("papers.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("citing_paper_id", "cited_paper_id", name="uq_citation"),
    )


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False)
    analysis_type = Column(String(100), nullable=False)  # bibliometrics, topic_modeling, trend, network
    params = Column(JSON, default=dict)
    results = Column(JSON, default=dict)  # chart data, metrics, etc.
    chart_configs = Column(JSON, default=list)  # ECharts option configs
    ai_interpretation = Column(Text, default="")
    status = Column(String(50), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ResearchSession", back_populates="analysis_runs")


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False)
    parent_report_id = Column(Integer, ForeignKey("reports.id"), nullable=True)
    title = Column(String(500), nullable=False)
    content_markdown = Column(Text, default="")
    chart_configs = Column(JSON, default=list)
    version = Column(Integer, default=1)
    status = Column(String(50), default="draft")  # draft, generating, completed
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ResearchSession", back_populates="reports")
    parent = relationship("Report", remote_side=[id])


class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String(255), primary_key=True)
    value = Column(Text, nullable=False)  # encrypted for sensitive data
    is_encrypted = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
