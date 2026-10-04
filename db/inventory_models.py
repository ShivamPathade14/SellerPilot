"""SQLAlchemy Inventory Models for Part B.

Architectural Viva Notes:
1. Shared Metadata Integration: Builds directly on db.base.Base, ensuring unified schema
   management alongside conversation_models.py without duplicate metadata bases.
2. Normalized Inventory Architecture:
   - ProductORM: Canonical product catalog (pricing, category, material, sizes/colors).
   - InventoryItemORM: Live stock tracking (quantity, posted_on_instagram, low_stock_threshold).
   - InventoryAlertORM: Automated event and anomaly records (low_stock, oversold, posted_but_out_of_stock).
3. SQLite Optimization: Uses JSON column types for lists (sizes, colors) and indexed foreign keys
   with CASCADE deletes for clean referential integrity.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.base import Base


class ProductORM(Base):
    """Product catalog ORM entity representing handmade jewelry pieces."""
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    material: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    sizes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    colors: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    image_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    inventory_item: Mapped[Optional["InventoryItemORM"]] = relationship(
        "InventoryItemORM", back_populates="product", uselist=False, cascade="all, delete-orphan"
    )
    alerts: Mapped[list["InventoryAlertORM"]] = relationship(
        "InventoryAlertORM", back_populates="product", cascade="all, delete-orphan", order_by="desc(InventoryAlertORM.created_at)"
    )


class InventoryItemORM(Base):
    """Real-time inventory levels and channel synchronization flags."""
    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("products.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    posted_on_instagram: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relationships
    product: Mapped["ProductORM"] = relationship("ProductORM", back_populates="inventory_item")


class InventoryAlertORM(Base):
    """Inventory alerts generated for low-stock, out-of-stock, and oversold events."""
    __tablename__ = "inventory_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False)  # "low_stock", "oversold", "posted_but_out_of_stock"
    message: Mapped[str] = mapped_column(Text, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    product: Mapped["ProductORM"] = relationship("ProductORM", back_populates="alerts")
