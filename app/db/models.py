"""SQLAlchemy ORM models for the EVA application.

All models use the SQLAlchemy 2.x ``Mapped`` / ``mapped_column()`` syntax.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.config import get_settings
from app.db.session import Base


class TimestampMixin:
    """Mixin that adds ``created_at`` and ``updated_at`` timestamp columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    phone: Mapped[str | None] = mapped_column(String(50))
    company: Mapped[str | None] = mapped_column(String(255))
    plan_tier: Mapped[str] = mapped_column(String(50), default="free")
    is_active: Mapped[bool] = mapped_column(default=True)

    # Relationships
    subscriptions: Mapped[list["Subscription"]] = relationship(
        back_populates="customer",
        cascade="all, delete-orphan",
    )
    billing_records: Mapped[list["BillingRecord"]] = relationship(
        back_populates="customer",
        cascade="all, delete-orphan",
    )
    support_tickets: Mapped[list["SupportTicket"]] = relationship(
        back_populates="customer",
        cascade="all, delete-orphan",
    )
    usage_analytics: Mapped[list["UsageAnalytic"]] = relationship(
        back_populates="customer",
        cascade="all, delete-orphan",
    )
    crm_notes: Mapped[list["CRMNote"]] = relationship(
        back_populates="customer",
        cascade="all, delete-orphan",
    )
    conversation_sessions: Mapped[list["ConversationSession"]] = relationship(
        back_populates="customer",
        cascade="all, delete-orphan",
    )


class Subscription(TimestampMixin, Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"),
    )
    plan_name: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50))
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    monthly_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0)

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="subscriptions")
    billing_records: Mapped[list["BillingRecord"]] = relationship(
        back_populates="subscription",
        cascade="all, delete-orphan",
    )


class BillingRecord(TimestampMixin, Base):
    __tablename__ = "billing_records"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"),
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
    )
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    description: Mapped[str | None] = mapped_column(Text)

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="billing_records")
    subscription: Mapped["Subscription | None"] = relationship(
        back_populates="billing_records",
    )


class SupportTicket(TimestampMixin, Base):
    __tablename__ = "support_tickets"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"),
    )
    title: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(50))
    priority: Mapped[str] = mapped_column(String(20))
    assigned_to: Mapped[str | None] = mapped_column(String(255))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="support_tickets")


class UsageAnalytic(TimestampMixin, Base):
    __tablename__ = "usage_analytics"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"),
    )
    metric_name: Mapped[str] = mapped_column(String(100))
    metric_value: Mapped[float] = mapped_column(Float)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="usage_analytics")


class CRMNote(TimestampMixin, Base):
    __tablename__ = "crm_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"),
    )
    content: Mapped[str] = mapped_column(Text)
    note_type: Mapped[str | None] = mapped_column(String(50))
    author: Mapped[str | None] = mapped_column(String(255))

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="crm_notes")


class ConversationSession(TimestampMixin, Base):
    __tablename__ = "conversation_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"),
    )
    title: Mapped[str | None] = mapped_column(String(500))
    session_status: Mapped[str] = mapped_column(String(50))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    language: Mapped[str] = mapped_column(String(10), default="en")
    summary: Mapped[str | None] = mapped_column(Text)
    tools_used: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="conversation_sessions")
    messages: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class ConversationMessage(TimestampMixin, Base):
    __tablename__ = "conversation_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversation_sessions.id", ondelete="CASCADE"),
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True,
    )
    tool_calls: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    token_count: Mapped[int | None] = mapped_column(nullable=True)

    # Relationships
    session: Mapped["ConversationSession"] = relationship(back_populates="messages")

    __table_args__ = (
        CheckConstraint(
            "role IN ('user','assistant','system')",
            name="ck_conversation_messages_role",
        ),
    )


class KnowledgeDocument(TimestampMixin, Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    collection: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text)
    source_ref: Mapped[str | None] = mapped_column(String(500))
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True,
    )
    embedding: Mapped[list[float]] = mapped_column(
        Vector(get_settings().embedding_dim),
    )

    __table_args__ = (
        CheckConstraint(
            "collection IN ('documentation', 'policies', "
            "'knowledge_articles', 'troubleshooting_guides')",
            name="ck_knowledge_documents_collection",
        ),
    )


# Explicit table-level indexes (HNSW vector index is created in migration 2)
Index("ix_support_tickets_status", SupportTicket.status)
Index("ix_billing_records_due_date", BillingRecord.due_date)
Index("ix_conversation_sessions_customer_id", ConversationSession.customer_id)
