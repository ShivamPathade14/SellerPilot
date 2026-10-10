"""SQLAlchemy Order ORM models for SellerPilot AI.

Architectural Viva Notes:
1. Grounded Persistence: An order is recorded only after atomic stock reservation
   and explicit final customer confirmation.
2. Idempotency: Uses confirmation_message_id with a unique constraint to prevent
   duplicate order records or double-reservation on retried webhooks.
3. Separation of Concerns: Stores orders without coupling to third-party payment gateways.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base


class OrderORM(Base):
    """Represents a confirmed customer purchase order."""
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    conversation_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    customer_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    product_id: Mapped[str] = mapped_column(String(64), ForeignKey("products.id"), nullable=False, index=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)
    size: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="confirmed", nullable=False)
    confirmation_message_id: Mapped[Optional[str]] = mapped_column(
        String(128), unique=True, index=True, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
