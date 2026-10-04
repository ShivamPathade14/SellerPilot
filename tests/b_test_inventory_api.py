"""Integration tests for FastAPI Inventory Endpoints and Commerce Agent Integration.

Validates:
1. GET /inventory
2. GET /inventory/{product_id}
3. GET /inventory/alerts (and repeatability without duplicate alerts)
4. POST /inventory/{product_id}/reserve (success, oversell 409, invalid 400, 404)
5. POST /inventory/{product_id}/adjust (restock 200, negative rejection 409, invalid 400, 404)
6. Commerce Agent integration with real SQLiteInventoryService (in-stock, out-of-stock, low-stock)
"""

from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from agents.commerce.agent import ConversationalCommerceAgent
from agents.inventory.service import SQLiteInventoryService
from api.main import app
from core.schemas import AgentAction, IncomingMessage, Intent
from db.base import Base
import db.conversation_models  # noqa: F401
import db.inventory_models  # noqa: F401
from scripts.seed_db import seed_database


@pytest.fixture(scope="module")
def api_test_db():
    """Create an isolated test database for API tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    seed_database(db_session=TestingSessionLocal())

    yield TestingSessionLocal
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(api_test_db):
    """TestClient wired with the isolated SQLite inventory service using dependency overrides."""
    from api.routes_inventory import get_inventory_service
    test_inv_service = SQLiteInventoryService(session_factory=api_test_db)
    app.dependency_overrides[get_inventory_service] = lambda: test_inv_service

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.pop(get_inventory_service, None)


# 1. GET /inventory
def test_get_all_inventory_endpoint(client):
    response = client.get("/inventory")
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 15

    # Check dashboard fields
    first = items[0]
    for field in [
        "product_id", "name", "price", "category", "quantity",
        "in_stock", "low_stock", "posted_on_instagram", "alert_status",
    ]:
        assert field in first


# 2. GET /inventory/{id}
def test_get_product_stock_endpoint(client):
    response = client.get("/inventory/prod-101")
    assert response.status_code == 200
    data = response.json()
    assert data["product"]["id"] == "prod-101"
    assert data["stock"]["quantity"] >= 0
    assert data["stock"]["in_stock"] is True


def test_get_product_stock_not_found(client):
    response = client.get("/inventory/prod-nonexistent-999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# 3. GET /inventory/alerts
def test_get_inventory_alerts_endpoint(client):
    res1 = client.get("/inventory/alerts")
    assert res1.status_code == 200
    alerts1 = res1.json()
    assert len(alerts1) >= 1

    # Calling repeatedly must NOT create duplicate alerts
    res2 = client.get("/inventory/alerts")
    assert res2.status_code == 200
    alerts2 = res2.json()
    assert len(alerts1) == len(alerts2)


# 4. POST /inventory/{id}/reserve
def test_post_reserve_success(client):
    # Reserve 1 unit of prod-104 (starts with 12)
    response = client.post("/inventory/prod-104/reserve", json={"quantity": 1})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["product_id"] == "prod-104"
    assert data["requested_quantity"] == 1
    assert data["remaining_quantity"] == 11


def test_post_reserve_oversell_conflict(client):
    # Attempting to reserve 500 units returns 409 Conflict
    response = client.post("/inventory/prod-104/reserve", json={"quantity": 500})
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["success"] is False
    assert detail["alert_generated"] == "oversold"


def test_post_reserve_invalid_quantity(client):
    # Zero or negative quantity returns 400 or 422
    response = client.post("/inventory/prod-104/reserve", json={"quantity": 0})
    assert response.status_code in (400, 422)


def test_post_reserve_not_found(client):
    response = client.post("/inventory/prod-missing-999/reserve", json={"quantity": 1})
    assert response.status_code == 404


# 5. POST /inventory/{id}/adjust
def test_post_adjust_success(client):
    # Restock prod-105 by +10
    response = client.post(
        "/inventory/prod-105/adjust",
        json={"quantity_delta": 10, "reason": "Restock from artisan workshop"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["quantity_delta"] == 10
    assert data["new_quantity"] > data["previous_quantity"]


def test_post_adjust_negative_rejection_conflict(client):
    # Attempting to adjust stock below zero returns 409 Conflict
    response = client.post(
        "/inventory/prod-105/adjust",
        json={"quantity_delta": -9999, "reason": "Accidental deletion"},
    )
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["success"] is False
    assert "negative" in detail["message"].lower()


def test_post_adjust_zero_delta_invalid(client):
    response = client.post(
        "/inventory/prod-105/adjust",
        json={"quantity_delta": 0, "reason": "No-op"},
    )
    assert response.status_code == 400


def test_post_adjust_not_found(client):
    response = client.post(
        "/inventory/prod-missing-999/adjust",
        json={"quantity_delta": 5, "reason": "Ghost product"},
    )
    assert response.status_code == 404


# 6. Commerce Agent + Real SQLiteInventoryService Integration
def test_commerce_agent_real_inventory_integration(api_test_db):
    real_inv = SQLiteInventoryService(session_factory=api_test_db)
    agent = ConversationalCommerceAgent()

    # Scenario: Available product
    msg_available = IncomingMessage(
        message_id="integ-1",
        customer_id="cust-1",
        channel="instagram",
        text="Do you have the Moonstone Wire-Wrapped Ring in size 7?",
        timestamp=datetime.utcnow(),
    )
    action: AgentAction = agent.handle_message(msg_available, real_inv)
    assert action.agent == "commerce"
    assert action.intent == Intent.stock_query
    assert action.product_id == "prod-101"
    assert action.escalate is False
    assert "in stock" in action.response_text.lower() or "available" in action.response_text.lower()

    # Scenario: Out-of-stock product (prod-103 Dainty Freshwater Pearl Choker has 0 stock)
    msg_oos = IncomingMessage(
        message_id="integ-2",
        customer_id="cust-2",
        channel="whatsapp",
        text="Is the Dainty Freshwater Pearl Choker available to buy?",
        timestamp=datetime.utcnow(),
    )
    action_oos: AgentAction = agent.handle_message(msg_oos, real_inv)
    assert action_oos.product_id == "prod-103"
    assert "sold out" in action_oos.response_text.lower()
    # Commerce Agent must NEVER claim out-of-stock product is available
    assert "available in stock" not in action_oos.response_text.lower()

    # Scenario: Low-stock product (prod-102 Raw Emerald has 3 units)
    msg_low = IncomingMessage(
        message_id="integ-3",
        customer_id="cust-3",
        channel="instagram",
        text="Is the Raw Emerald Pendant Necklace in stock?",
        timestamp=datetime.utcnow(),
    )
    action_low: AgentAction = agent.handle_message(msg_low, real_inv)
    assert action_low.product_id == "prod-102"
    assert action_low.escalate is False
    assert "3 pieces" in action_low.response_text or "3 left" in action_low.response_text or "in stock" in action_low.response_text.lower()
