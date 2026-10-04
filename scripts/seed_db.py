"""Database Seeding Script for SellerPilot AI.

Populates SQLite with synthetic handmade jewelry catalog, live stock levels,
and initial inventory alerts from data/products.json.

Guaranteed idempotency: Can be executed repeatedly without generating duplicate records.
"""

from datetime import datetime
import json
import logging
from pathlib import Path
import sys

# Ensure repository root is on sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

# Configure UTF-8 output on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from db.base import Base, SessionLocal, engine
import db.conversation_models  # noqa: F401
from db.inventory_models import InventoryAlertORM, InventoryItemORM, ProductORM

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sellerpilot.seed")


def seed_database(db_session=None) -> dict[str, int]:
    """Seed the database with products and inventory records from data/products.json.

    Returns:
        dict containing counts of seeded items and alert metrics.
    """
    # 1. Initialize schema
    Base.metadata.create_all(bind=engine)

    db = db_session or SessionLocal()
    should_close = db_session is None

    try:
        data_file = root_dir / "data" / "products.json"
        if not data_file.exists():
            raise FileNotFoundError(f"Products data file not found at: {data_file}")

        with open(data_file, "r", encoding="utf-8") as f:
            products_data = json.load(f)

        low_stock_threshold = 3

        for item in products_data:
            prod_id = item["id"]

            # Upsert Product
            product = db.query(ProductORM).filter(ProductORM.id == prod_id).first()
            if not product:
                product = ProductORM(
                    id=prod_id,
                    name=item["name"],
                    price=item["price"],
                    category=item["category"],
                    material=item["material"],
                    description=item["description"],
                    sizes=item.get("sizes", []),
                    colors=item.get("colors", []),
                    image_path=item.get("image_path"),
                    created_at=datetime.utcnow(),
                )
                db.add(product)
            else:
                product.name = item["name"]
                product.price = item["price"]
                product.category = item["category"]
                product.material = item["material"]
                product.description = item["description"]
                product.sizes = item.get("sizes", [])
                product.colors = item.get("colors", [])
                product.image_path = item.get("image_path")

            db.flush()

            # Upsert Inventory Item
            inv_item = db.query(InventoryItemORM).filter(InventoryItemORM.product_id == prod_id).first()
            qty = item.get("quantity", 0)
            posted = item.get("posted_on_instagram", False)

            if not inv_item:
                inv_item = InventoryItemORM(
                    product_id=prod_id,
                    quantity=qty,
                    posted_on_instagram=posted,
                    low_stock_threshold=low_stock_threshold,
                    updated_at=datetime.utcnow(),
                )
                db.add(inv_item)
            else:
                inv_item.quantity = qty
                inv_item.posted_on_instagram = posted
                inv_item.low_stock_threshold = low_stock_threshold
                inv_item.updated_at = datetime.utcnow()

            db.flush()

            # Seed Initial Alerts
            if qty == 0 and posted:
                existing_alert = (
                    db.query(InventoryAlertORM)
                    .filter(
                        InventoryAlertORM.product_id == prod_id,
                        InventoryAlertORM.type == "posted_but_out_of_stock",
                        InventoryAlertORM.resolved == False,  # noqa: E712
                    )
                    .first()
                )
                if not existing_alert:
                    db.add(
                        InventoryAlertORM(
                            product_id=prod_id,
                            type="posted_but_out_of_stock",
                            message=f"{product.name} is featured in active Instagram reels/posts but is out of stock (qty: 0).",
                            resolved=False,
                            created_at=datetime.utcnow(),
                        )
                    )
            elif 0 < qty <= low_stock_threshold:
                existing_alert = (
                    db.query(InventoryAlertORM)
                    .filter(
                        InventoryAlertORM.product_id == prod_id,
                        InventoryAlertORM.type == "low_stock",
                        InventoryAlertORM.resolved == False,  # noqa: E712
                    )
                    .first()
                )
                if not existing_alert:
                    db.add(
                        InventoryAlertORM(
                            product_id=prod_id,
                            type="low_stock",
                            message=f"{product.name} has only {qty} units remaining in studio.",
                            resolved=False,
                            created_at=datetime.utcnow(),
                        )
                    )

        db.commit()

        # Compute summary metrics
        total_products = db.query(ProductORM).count()
        total_inventory = db.query(InventoryItemORM).count()
        low_stock = (
            db.query(InventoryItemORM)
            .filter(InventoryItemORM.quantity > 0, InventoryItemORM.quantity <= InventoryItemORM.low_stock_threshold)
            .count()
        )
        out_of_stock = db.query(InventoryItemORM).filter(InventoryItemORM.quantity == 0).count()
        posted_but_unavailable = (
            db.query(InventoryItemORM)
            .filter(InventoryItemORM.quantity == 0, InventoryItemORM.posted_on_instagram == True)  # noqa: E712
            .count()
        )

        return {
            "products": total_products,
            "inventory_records": total_inventory,
            "low_stock": low_stock,
            "out_of_stock": out_of_stock,
            "posted_but_unavailable": posted_but_unavailable,
        }

    finally:
        if should_close:
            db.close()


def main():
    summary = seed_database()
    print("Seed complete.\n")
    print(f"Products: {summary['products']}")
    print(f"Inventory records: {summary['inventory_records']}")
    print(f"Low stock: {summary['low_stock']}")
    print(f"Out of stock: {summary['out_of_stock']}")
    print(f"Posted but unavailable: {summary['posted_but_unavailable']}")


if __name__ == "__main__":
    main()
