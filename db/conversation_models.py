"""SQLAlchemy Conversation and Message ORM models.

Architectural Viva Notes:
1. Conversation State Persistence: Stores customer interactions across Instagram
   and WhatsApp to maintain multi-turn context and customer chat histories.
2. Webhook Idempotency: Uses unique indexing on message_id to prevent duplicate
   agent triggers when webhooks are retried by platforms.
3. Audit Trails: Records intent, confidence, escalation flags, and reasons directly
   alongside agent messages for analytics and supervisor review.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.base import Base


class ConversationORM(Base):
    """Represents a thread of conversation with a customer on a given channel."""
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)  # "instagram" or "whatsapp"
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    messages: Mapped[list["MessageORM"]] = relationship(
        "MessageORM", back_populates="conversation", cascade="all, delete-orphan", order_by="MessageORM.timestamp"
    )
    context: Mapped[Optional["ConversationContextORM"]] = relationship(
        "ConversationContextORM", back_populates="conversation", uselist=False, cascade="all, delete-orphan"
    )


class ConversationContextORM(Base):
    """Persistent operational state and active context for a conversation."""
    __tablename__ = "conversation_contexts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("conversations.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    customer_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    active_product_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    active_product_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    previous_intent: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    conversation_stage: Mapped[str] = mapped_column(String(64), default="discovery", nullable=False)
    pending_action: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    requested_quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    selected_size: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    selected_color: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    shipping_city: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    last_agent_question: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    context_metadata: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    conversation: Mapped["ConversationORM"] = relationship("ConversationORM", back_populates="context")



class MessageORM(Base):
    """Represents an individual message exchanged within a conversation."""
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    sender: Mapped[str] = mapped_column(String(32), nullable=False)  # "customer" or "agent"
    text: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    product_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    escalation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    conversation: Mapped["ConversationORM"] = relationship("ConversationORM", back_populates="messages")
