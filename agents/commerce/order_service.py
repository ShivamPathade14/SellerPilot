"""Order Service for SellerPilot AI.

Architectural Viva Notes:
1. Atomic Stock Reservation + Grounded Order Creation:
   An order is persisted only if stock reservation succeeds in the inventory service.
2. Idempotent Order Confirmation:
   Guarantees duplicate incoming confirmation messages do not create duplicate orders
   or double-reserve inventory.
3. Clean Separation: Provides core order management without external payment APIs.
"""

from datetime import datetime
import logging
from typing import Callable, Optional
import uuid
from sqlalchemy.orm import Session
from core.interfaces import InventoryService
from db.base import SessionLocal
from db.order_models import OrderORM

logger = logging.getLogger(__name__)


class OrderService:
    """Service handling order creation, verification, and retrieval."""

    def __init__(self, session_factory: Callable[[], Session] | None = None):
        self.session_factory = session_factory or SessionLocal

    def create_order(
        self,
        customer_id: str,
        channel: str,
        product_id: str,
        product_name: str,
        quantity: int,
        unit_price: float,
        inventory_service: InventoryService,
        size: str | None = None,
        color: str | None = None,
        confirmation_message_id: str | None = None,
        conversation_id: int | None = None,
    ) -> tuple[bool, Optional[OrderORM], Optional[str]]:
        """Create a new order after verifying availability and atomically reserving stock.

        Returns:
            (success: bool, order: OrderORM | None, error_or_notice: str | None)
        """
        if quantity <= 0:
            return False, None, "Invalid quantity: must be at least 1."

        with self.session_factory() as db:
            # 1. Idempotency Check: prevent duplicate orders on message retry
            if confirmation_message_id:
                existing = (
                    db.query(OrderORM)
                    .filter(OrderORM.confirmation_message_id == confirmation_message_id)
                    .first()
                )
                if existing:
                    logger.info("Order for message %s already exists: %s", confirmation_message_id, existing.order_id)
                    return True, existing, "Order already created (idempotent duplicate)."

            # 2. Check live stock before reserving
            stock = inventory_service.get_stock(product_id)
            if not stock or stock.quantity < quantity:
                available = stock.quantity if stock else 0
                return False, None, f"Insufficient stock: requested {quantity}, but only {available} available."

            # 3. Atomically reserve stock
            reserved = inventory_service.reserve(product_id, quantity)
            if not reserved:
                return False, None, "Stock reservation failed. Product may have just sold out."

            # 4. Generate order ID and persist order
            order_id = f"ORD-{int(datetime.utcnow().timestamp())}-{uuid.uuid4().hex[:4].upper()}"
            total_amount = float(quantity * unit_price)

            order = OrderORM(
                order_id=order_id,
                conversation_id=conversation_id,
                customer_id=customer_id,
                channel=channel,
                product_id=product_id,
                product_name=product_name,
                quantity=quantity,
                unit_price=unit_price,
                total_amount=total_amount,
                size=size,
                color=color,
                status="confirmed",
                confirmation_message_id=confirmation_message_id,
                created_at=datetime.utcnow(),
            )
            db.add(order)
            db.commit()
            db.refresh(order)

            logger.info("Order %s successfully created for customer %s (%s x %d)", order_id, customer_id, product_name, quantity)
            return True, order, None

    def get_order_by_id(self, order_id: str) -> Optional[OrderORM]:
        """Fetch order by public order ID."""
        with self.session_factory() as db:
            return db.query(OrderORM).filter(OrderORM.order_id == order_id).first()

    def get_order_by_confirmation_message(self, message_id: str) -> Optional[OrderORM]:
        """Fetch order by confirmation message ID for idempotency."""
        with self.session_factory() as db:
            return db.query(OrderORM).filter(OrderORM.confirmation_message_id == message_id).first()

    def get_orders_for_customer(self, customer_id: str) -> list[OrderORM]:
        """Fetch all orders placed by a customer."""
        with self.session_factory() as db:
            return (
                db.query(OrderORM)
                .filter(OrderORM.customer_id == customer_id)
                .order_by(OrderORM.created_at.desc())
                .all()
            )
