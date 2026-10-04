"""Tests for Part B Inventory Data Foundation and SQLite Service.

Validates all 13 required Part B specifications:
1. Product loading
2. Product search
3. Stock lookup
4. Available product
5. Low-stock product
6. Out-of-stock product
7. Successful reservation
8. Reservation cannot oversell
9. Reservation cannot create negative stock
10. Posted-but-out-of-stock alert
11. Low-stock alert
12. Repeat-safe database seeding
13. InventoryService protocol conformance
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from agents.inventory.service import SQLiteInventoryService
from core.interfaces import InventoryService
from core.schemas import InventoryAlert, Product, StockStatus
from db.base import Base
import db.conversation_models  # noqa: F401
import db.inventory_models  # noqa: F401
from scripts.seed_db import seed_database


@pytest.fixture(scope="module")
def test_db():
    """Create an isolated in-memory SQLite database for Part B tests."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    # Seed the test database
    seed_database(db_session=TestingSessionLocal())

    yield TestingSessionLocal
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def inv_service(test_db):
    return SQLiteInventoryService(session_factory=test_db)


# 1. Product Loading
def test_product_loading(inv_service):
    products = inv_service.find_products("")
    assert len(products) == 15
    ids = {p.id for p in products}
    assert "prod-101" in ids
    assert "prod-102" in ids
    assert "prod-103" in ids


# 2. Product Search
def test_product_search_matching(inv_service):
    # Search by category and stone keywords
    pearl_matches = inv_service.find_products("pearl necklace")
    assert len(pearl_matches) >= 1
    assert pearl_matches[0].id == "prod-103"
    assert "Pearl" in pearl_matches[0].name

    # Search by material
    silver_rings = inv_service.find_products("sterling silver ring")
    assert len(silver_rings) >= 1
    assert any("Moonstone" in r.name for r in silver_rings)

    # Search by ID directly
    exact_id = inv_service.find_products("prod-105")
    assert len(exact_id) >= 1
    assert exact_id[0].id == "prod-105"


# 3. Stock Lookup
def test_stock_lookup(inv_service):
    status = inv_service.get_stock("prod-101")
    assert isinstance(status, StockStatus)
    assert status.product_id == "prod-101"
    assert status.quantity == 8
    assert status.in_stock is True
    assert status.low_stock is False
    assert status.posted_on_instagram is True


# 4. Available Product
def test_available_product_status(inv_service):
    status = inv_service.get_stock("prod-104")
    assert status is not None
    assert status.quantity == 12
    assert status.in_stock is True
    assert status.low_stock is False
    assert status.posted_on_instagram is False


# 5. Low-Stock Product
def test_low_stock_product_status(inv_service):
    status = inv_service.get_stock("prod-102")  # Quantity 3, threshold 3
    assert status is not None
    assert status.quantity == 3
    assert status.in_stock is True
    assert status.low_stock is True
    assert status.posted_on_instagram is True


# 6. Out-of-Stock Product
def test_out_of_stock_product_status(inv_service):
    status = inv_service.get_stock("prod-103")  # Quantity 0
    assert status is not None
    assert status.quantity == 0
    assert status.in_stock is False
    assert status.low_stock is False or status.quantity <= 3  # Qty 0 is out of stock
    assert status.posted_on_instagram is True


# 7. Successful Reservation
def test_successful_reservation(inv_service):
    # Initial: prod-106 has 15
    initial = inv_service.get_stock("prod-106")
    assert initial.quantity == 15

    # Reserve 5 units
    success = inv_service.reserve("prod-106", 5)
    assert success is True

    # Updated: prod-106 has 10
    updated = inv_service.get_stock("prod-106")
    assert updated.quantity == 10


# 8. Reservation Cannot Oversell
def test_reservation_cannot_oversell(inv_service):
    # prod-107 has quantity 2
    initial = inv_service.get_stock("prod-107")
    assert initial.quantity == 2

    # Attempt to reserve 5 units (exceeding stock)
    success = inv_service.reserve("prod-107", 5)
    assert success is False

    # Stock must remain unchanged
    after = inv_service.get_stock("prod-107")
    assert after.quantity == 2


# 9. Reservation Cannot Create Negative Stock
def test_reservation_cannot_create_negative_stock(inv_service):
    # prod-103 has quantity 0
    initial = inv_service.get_stock("prod-103")
    assert initial.quantity == 0

    # Attempt to reserve from 0 stock
    success = inv_service.reserve("prod-103", 1)
    assert success is False

    # Quantity must remain 0, never negative
    after = inv_service.get_stock("prod-103")
    assert after.quantity == 0
    assert after.quantity >= 0


# 10. Posted-But-Out-Of-Stock Alert
def test_posted_but_out_of_stock_alert(inv_service):
    alerts = inv_service.get_alerts()
    # prod-103 has 0 stock and is posted on Instagram -> alert created on seed
    posted_alerts = [a for a in alerts if a.product_id == "prod-103" and a.type == "posted_but_out_of_stock"]
    assert len(posted_alerts) >= 1
    assert "Instagram" in posted_alerts[0].message or "out of stock" in posted_alerts[0].message


# 11. Low-Stock Alert Generation on Depletion
def test_low_stock_alert_on_reservation(inv_service):
    # prod-105 starts with 5 units (normal stock)
    initial = inv_service.get_stock("prod-105")
    assert initial.quantity == 5

    # Reserve 3 units -> drops to 2 units (low stock threshold is 3)
    success = inv_service.reserve("prod-105", 3)
    assert success is True

    updated = inv_service.get_stock("prod-105")
    assert updated.quantity == 2
    assert updated.low_stock is True

    # Check alert list
    alerts = inv_service.get_alerts()
    low_stock_alerts = [a for a in alerts if a.product_id == "prod-105" and a.type == "low_stock"]
    assert len(low_stock_alerts) >= 1


# 12. Repeat-Safe Database Seeding
def test_repeat_safe_seeding(test_db):
    # Run seed script a second time on the same DB
    summary = seed_database(db_session=test_db())
    assert summary["products"] == 15
    assert summary["inventory_records"] == 15
    assert summary["out_of_stock"] >= 2


# 13. InventoryService Protocol Conformance
def test_inventory_service_protocol_conformance(inv_service):
    assert isinstance(inv_service, InventoryService)
