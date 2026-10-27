import uuid
from datetime import datetime, timezone
from typing import Any
from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


EmbeddingColumnType = Vector(settings.GEMINI_EMBEDDING_DIM).with_variant(JSON(), "sqlite")


class ClaimRecord(Base):
    """
    Claim Memory – Versioned Evidence Database (Phần VII.2).
    Stores canonicalized claims, semantic embeddings (pgvector), versioned verdicts,
    and timestamps so claims can be reused while respecting temporal validity.
    """

    __tablename__ = "claim_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    normalized_claim: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    claim_type: Mapped[str] = mapped_column(String(40), nullable=False, default="FACTUAL_CLAIM")
    topic_category: Mapped[str] = mapped_column(String(80), nullable=False, default="Tổng hợp", index=True)

    # 768-dim vector in PostgreSQL pgvector (JSON fallback on SQLite)
    embedding: Mapped[Any] = mapped_column(EmbeddingColumnType, nullable=True)

    verdict: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    evidence_completeness: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    missing_information: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    limitations: Mapped[str] = mapped_column(Text, nullable=False, default="")
    suggested_correction: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    evidences: Mapped[list["EvidenceRecord"]] = relationship(
        "EvidenceRecord",
        back_populates="claim",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class EvidenceRecord(Base):
    """Validated evidence item linked to a specific ClaimRecord version."""

    __tablename__ = "evidence_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    claim_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("claim_records.id", ondelete="CASCADE"), nullable=False, index=True
    )
    claim_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    publisher: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    published_date: Mapped[str | None] = mapped_column(String(64), nullable=True)

    tier: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    tier_label: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    stance: Mapped[str] = mapped_column(String(32), nullable=False, default="CONTEXTUAL")
    snippet: Mapped[str] = mapped_column(Text, nullable=False, default="")

    scores: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False, default=dict)
    citation_validated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    validation_note: Mapped[str] = mapped_column(Text, nullable=False, default="")

    claim: Mapped["ClaimRecord"] = relationship("ClaimRecord", back_populates="evidences")


class DocumentJob(Base):
    """Stores document/URL/text verification sessions and exportable payloads."""

    __tablename__ = "document_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING", index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="TEXT")
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FeedbackReport(Base):
    """User-submitted dispute or error report per IFCN correction principles (Phần IX)."""

    __tablename__ = "feedback_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    reported_verdict: Mapped[str] = mapped_column(String(40), nullable=False)
    suggested_verdict: Mapped[str | None] = mapped_column(String(40), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

