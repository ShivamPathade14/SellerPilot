"""SQLite Inventory Service Implementation for SellerPilot AI.

Architectural Viva Notes:
1. Strict Protocol Adherence: Conforms to core.interfaces.InventoryService typing.Protocol
   so it drops seamlessly into ConversationalCommerceAgent and SellerPilotOrchestrator
   without modifying Part A code.
2. Atomic Stock Reservation:
   - Evaluates quantity >= requested_quantity inside an isolated transaction.
   - Guarantees zero negative inventory.
   - Automatically generates low_stock or posted_but_out_of_stock alerts on depletion.
3. Deterministic Non-LLM Search:
   - Implements multi-word weighted relevance scoring across product name, category,
     material, and description to ensure fast, deterministic, reproducible catalog lookup.
"""

from datetime import datetime
import logging
from typing import Callable
from sqlalchemy.orm import Session
from core.interfaces import InventoryService
from core.schemas import InventoryAlert, Product, StockStatus
from db.base import SessionLocal
from db.inventory_models import InventoryAlertORM, InventoryItemORM, ProductORM

logger = logging.getLogger(__name__)


class SQLiteInventoryService(InventoryService):
    """Production SQLite-backed inventory service implementing InventoryService protocol."""

    def __init__(self, session_factory: Callable[[], Session] | None = None):
        self.session_factory = session_factory or SessionLocal

    def get_stock(self, product_id: str) -> StockStatus | None:
        """Fetch real-time stock status for a given product ID from SQLite."""
        with self.session_factory() as db:
            item = db.query(InventoryItemORM).filter(InventoryItemORM.product_id == product_id).first()
            if not item:
                return None

            quantity = item.quantity
            threshold = item.low_stock_threshold
            in_stock = quantity > 0
            low_stock = 0 < quantity <= threshold
            posted = item.posted_on_instagram

            return StockStatus(
                product_id=product_id,
                quantity=quantity,
                in_stock=in_stock,
                low_stock=low_stock,
                posted_on_instagram=posted,
            )

    def find_products(self, query: str) -> list[Product]:
        """Search products in catalog using deterministic multi-field weighted scoring."""
        query_lower = query.lower().strip()
        with self.session_factory() as db:
            products_orm = db.query(ProductORM).all()

            if not query_lower:
                return [self._to_pydantic_product(p) for p in products_orm]

            keywords = [kw for kw in query_lower.split() if len(kw) > 1]
            scored: list[tuple[float, ProductORM]] = []

            for p in products_orm:
                p_id_lower = p.id.lower()
                name_lower = p.name.lower()
                cat_lower = p.category.lower()
                mat_lower = p.material.lower()
                desc_lower = p.description.lower()
                all_text = f"{p_id_lower} {name_lower} {cat_lower} {mat_lower} {desc_lower}"

                score = 0.0
                if p_id_lower == query_lower:
                    score += 100.0  # Exact ID match
                elif query_lower in name_lower:
                    score += 50.0   # Exact phrase in name
                elif query_lower in all_text:
                    score += 25.0   # Exact phrase in other fields

                for kw in keywords:
                    if kw in name_lower:
                        score += 10.0
                    elif kw in cat_lower:
                        score += 5.0
                    elif kw in mat_lower:
                        score += 3.0
                    elif kw in desc_lower:
                        score += 1.0

                if score > 0.0:
                    scored.append((score, p))

            # Rank descending by relevance score
            scored.sort(key=lambda x: x[0], reverse=True)
            return [self._to_pydantic_product(p) for _, p in scored]

    def reserve(self, product_id: str, qty: int) -> bool:
        """Atomically reserve product quantity. Prevents negative stock and overselling."""
        if qty <= 0:
            return False

        with self.session_factory() as db:
            item = db.query(InventoryItemORM).filter(InventoryItemORM.product_id == product_id).first()
            if not item:
                logger.warning("Reservation failed: Product %s not found in inventory.", product_id)
                return False

            # Strict oversell guard: never allow quantity < requested_quantity
            if item.quantity < qty:
                logger.warning(
                    "Reservation failed: Attempted to reserve %d units of %s, but only %d available.",
                    qty,
                    product_id,
                    item.quantity,
                )
                # Record oversold alert
                product = db.query(ProductORM).filter(ProductORM.id == product_id).first()
                product_name = product.name if product else product_id
                oversold_alert = InventoryAlertORM(
                    product_id=product_id,
                    type="oversold",
                    message=(
                        f"Reservation failed for {product_name}: attempted {qty} units, "
                        f"only {item.quantity} in stock."
                    ),
                    resolved=False,
                    created_at=datetime.utcnow(),
                )
                db.add(oversold_alert)
                db.commit()
                return False

            # Decrement stock atomically
            new_quantity = item.quantity - qty
            item.quantity = new_quantity
            item.updated_at = datetime.utcnow()

            product = db.query(ProductORM).filter(ProductORM.id == product_id).first()
            product_name = product.name if product else product_id

            # Trigger automated alerts based on new stock level
            if new_quantity == 0 and item.posted_on_instagram:
                db.add(
                    InventoryAlertORM(
                        product_id=product_id,
                        type="posted_but_out_of_stock",
                        message=f"{product_name} just ran out of stock but is active on Instagram.",
                        resolved=False,
                        created_at=datetime.utcnow(),
                    )
                )
            elif 0 < new_quantity <= item.low_stock_threshold:
                db.add(
                    InventoryAlertORM(
                        product_id=product_id,
                        type="low_stock",
                        message=f"{product_name} is down to {new_quantity} units remaining.",
                        resolved=False,
                        created_at=datetime.utcnow(),
                    )
                )

            db.commit()
            return True

    def get_alerts(self) -> list[InventoryAlert]:
        """Fetch all active inventory alerts from database."""
        with self.session_factory() as db:
            alerts_orm = (
                db.query(InventoryAlertORM)
                .order_by(InventoryAlertORM.created_at.desc())
                .all()
            )

            results: list[InventoryAlert] = []
            seen_keys: set[tuple[str, str]] = set()

            for a in alerts_orm:
                key = (a.product_id, a.type)
                if key not in seen_keys:
                    seen_keys.add(key)
                    alert_type = a.type
                    if alert_type not in ("low_stock", "oversold", "posted_but_out_of_stock"):
                        alert_type = "low_stock"

                    results.append(
                        InventoryAlert(
                            product_id=a.product_id,
                            type=alert_type,  # type: ignore
                            message=a.message,
                            created_at=a.created_at,
                        )
                    )

            return results

    def adjust_stock(
        self, product_id: str, quantity_delta: int, reason: str = ""
    ) -> tuple[bool, StockStatus | None, int, str | None]:
        """Manually adjust stock by a delta. Rejects adjustments that cause negative inventory.

        Returns:
            tuple of (success, updated_stock_status, previous_quantity, error_message)
        """
        with self.session_factory() as db:
            item = db.query(InventoryItemORM).filter(InventoryItemORM.product_id == product_id).first()
            if not item:
                return False, None, 0, f"Product '{product_id}' not found in inventory."

            previous_quantity = item.quantity
            new_quantity = previous_quantity + quantity_delta

            if new_quantity < 0:
                return (
                    False,
                    None,
                    previous_quantity,
                    f"Invalid adjustment ({quantity_delta:+d}): resulting quantity would be negative ({new_quantity}).",
                )

            item.quantity = new_quantity
            item.updated_at = datetime.utcnow()

            product = db.query(ProductORM).filter(ProductORM.id == product_id).first()
            product_name = product.name if product else product_id

            # Alert transitions based on adjustment
            if new_quantity == 0 and item.posted_on_instagram:
                existing = (
                    db.query(InventoryAlertORM)
                    .filter(
                        InventoryAlertORM.product_id == product_id,
                        InventoryAlertORM.type == "posted_but_out_of_stock",
                        InventoryAlertORM.resolved == False,  # noqa: E712
                    )
                    .first()
                )
                if not existing:
                    db.add(
                        InventoryAlertORM(
                            product_id=product_id,
                            type="posted_but_out_of_stock",
                            message=f"{product_name} adjusted to 0 stock but active on Instagram. Reason: {reason or 'Manual adjustment'}",
                            resolved=False,
                            created_at=datetime.utcnow(),
                        )
                    )
            elif 0 < new_quantity <= item.low_stock_threshold:
                existing = (
                    db.query(InventoryAlertORM)
                    .filter(
                        InventoryAlertORM.product_id == product_id,
                        InventoryAlertORM.type == "low_stock",
                        InventoryAlertORM.resolved == False,  # noqa: E712
                    )
                    .first()
                )
                if not existing:
                    db.add(
                        InventoryAlertORM(
                            product_id=product_id,
                            type="low_stock",
                            message=f"{product_name} adjusted down to {new_quantity} units. Reason: {reason or 'Manual adjustment'}",
                            resolved=False,
                            created_at=datetime.utcnow(),
                        )
                    )
            elif new_quantity > item.low_stock_threshold:
                # Resolve low stock alerts if replenished
                active_alerts = (
                    db.query(InventoryAlertORM)
                    .filter(
                        InventoryAlertORM.product_id == product_id,
                        InventoryAlertORM.type.in_(["low_stock", "posted_but_out_of_stock", "oversold"]),
                        InventoryAlertORM.resolved == False,  # noqa: E712
                    )
                    .all()
                )
                for a in active_alerts:
                    a.resolved = True

            db.commit()

            status = StockStatus(
                product_id=product_id,
                quantity=new_quantity,
                in_stock=new_quantity > 0,
                low_stock=0 < new_quantity <= item.low_stock_threshold,
                posted_on_instagram=item.posted_on_instagram,
            )
            return True, status, previous_quantity, None

    def get_all_products_with_stock(self) -> list[dict]:
        """Fetch all products combined with live inventory and alert status for dashboard and APIs."""
        with self.session_factory() as db:
            products = db.query(ProductORM).order_by(ProductORM.id).all()
            results = []

            for p in products:
                item = p.inventory_item
                qty = item.quantity if item else 0
                threshold = item.low_stock_threshold if item else 3
                posted = item.posted_on_instagram if item else False

                in_stock = qty > 0
                low_stock = 0 < qty <= threshold

                # Determine alert status
                alert_status = None
                if qty == 0 and posted:
                    alert_status = "posted_but_out_of_stock"
                elif low_stock:
                    alert_status = "low_stock"
                elif qty == 0:
                    alert_status = "out_of_stock"

                results.append({
                    "product_id": p.id,
                    "name": p.name,
                    "price": p.price,
                    "category": p.category,
                    "material": p.material,
                    "description": p.description,
                    "sizes": p.sizes if isinstance(p.sizes, list) else [],
                    "colors": p.colors if isinstance(p.colors, list) else [],
                    "image_path": p.image_path,
                    "quantity": qty,
                    "in_stock": in_stock,
                    "low_stock": low_stock,
                    "posted_on_instagram": posted,
                    "alert_status": alert_status,
                })

            return results

    @staticmethod
    def _to_pydantic_product(orm: ProductORM) -> Product:
        """Convert a SQLAlchemy ProductORM instance to a Pydantic Product model."""
        return Product(
            id=orm.id,
            name=orm.name,
            price=orm.price,
            category=orm.category,
            material=orm.material,
            description=orm.description,
            sizes=orm.sizes if isinstance(orm.sizes, list) else [],
            colors=orm.colors if isinstance(orm.colors, list) else [],
            image_path=orm.image_path,
        )


# Backward-compatible alias for api/main.py lifespan dependency injection
InventoryServiceImplementation = SQLiteInventoryService

