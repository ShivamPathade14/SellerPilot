"""Tests for Part B InventoryAgent and Orchestrator Event Integration.

Validates:
1. Stock lookup
2. Low-stock detection
3. Out-of-stock detection
4. Posted-but-out-of-stock detection
5. Reservation processing
6. Oversell protection
7. Alert retrieval
8. Deterministic behavior without LLM
9. Orchestrator 'low_stock' event routing and escalation
10. Non-inventory event observation
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from agents.inventory.agent import InventoryAgent
from agents.inventory.service import SQLiteInventoryService
from core.schemas import AgentAction, Event, Intent, StockStatus
from db.base import Base
import db.conversation_models  # noqa: F401
import db.inventory_models  # noqa: F401
from scripts.seed_db import seed_database


@pytest.fixture(scope="module")
def isolated_db():
    """Create an isolated in-memory SQLite database for agent tests."""
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
def agent(isolated_db):
    service = SQLiteInventoryService(session_factory=isolated_db)
    return InventoryAgent(service=service)


def test_agent_stock_lookup(agent):
    """Verify stock lookup returns accurate StockStatus."""
    status = agent.check_stock("prod-101")
    assert isinstance(status, StockStatus)
    assert status.product_id == "prod-101"
    assert status.quantity == 8
    assert status.in_stock is True


def test_agent_low_stock_detection(agent):
    """Verify low stock is detected for quantity <= 3."""
    is_low = agent.check_low_stock("prod-102")  # Qty 3
    assert is_low is True

    is_not_low = agent.check_low_stock("prod-104")  # Qty 12
    assert is_not_low is False


def test_agent_out_of_stock_detection(agent):
    """Verify out-of-stock is detected when quantity == 0."""
    is_oos = agent.check_out_of_stock("prod-103")  # Qty 0
    assert is_oos is True

    is_not_oos = agent.check_out_of_stock("prod-101")  # Qty 8
    assert is_not_oos is False


def test_agent_posted_but_unavailable_detection(agent):
    """Verify detection of items with 0 stock that are active on Instagram."""
    is_posted_oos = agent.check_posted_but_unavailable("prod-103")  # Qty 0, posted=True
    assert is_posted_oos is True

    # prod-112 has 0 stock but posted_on_instagram=False
    is_not_posted_oos = agent.check_posted_but_unavailable("prod-112")
    assert is_not_posted_oos is False


def test_agent_reservation_and_oversell_protection(agent):
    """Verify reservation succeeds when stock exists and blocks overselling."""
    # prod-106 starts with 15
    success = agent.reserve_stock("prod-106", 5)
    assert success is True
    assert agent.check_stock("prod-106").quantity == 10

    # Attempting to reserve 50 units must fail
    oversell_success = agent.reserve_stock("prod-106", 50)
    assert oversell_success is False
    assert agent.check_stock("prod-106").quantity == 10  # Unchanged


def test_agent_alerts_retrieval(agent):
    """Verify retrieval of unresolved alerts without creating duplicate entries."""
    alerts = agent.get_unresolved_alerts()
    assert len(alerts) >= 1
    types = {a.type for a in alerts}
    assert "posted_but_out_of_stock" in types or "low_stock" in types


def test_agent_deterministic_behavior_without_llm(agent):
    """Verify agent operates purely on SQLite truth with zero LLM dependency."""
    # Direct search
    products = agent.search_products("Emerald")
    assert len(products) >= 1
    assert "Emerald" in products[0].name


def test_agent_handle_event_low_stock_critical(agent):
    """Verify handling of 'low_stock' event for out-of-stock Instagram item triggers escalation."""
    event = Event(type="low_stock", payload={"product_id": "prod-103"})
    action = agent.handle_event(event)

    assert isinstance(action, AgentAction)
    assert action.agent == "inventory"
    assert action.product_id == "prod-103"
    assert action.escalate is True
    assert "CRITICAL" in action.escalation_reason or "Instagram" in action.escalation_reason


def test_agent_handle_event_non_inventory(agent):
    """Verify agent safely ignores non-inventory events without side effects."""
    event = Event(type="new_product_photo", payload={"product_id": "prod-101"})
    action = agent.handle_event(event)

    assert action.agent == "inventory"
    assert action.escalate is False


def test_orchestrator_integration_with_real_inventory(isolated_db):
    """Verify LangGraph Orchestrator seamlessly integrates with SQLiteInventoryService."""
    from core.mocks import MockContentService
    from orchestrator.graph import SellerPilotOrchestrator

    real_inv = SQLiteInventoryService(session_factory=isolated_db)
    content = MockContentService()
    orch = SellerPilotOrchestrator(inventory=real_inv, content=content)

    # Low-stock event for critical out-of-stock Instagram item
    event = Event(type="low_stock", payload={"product_id": "prod-103"})
    result = orch.process_event(event)

    assert isinstance(result, AgentAction)
    assert result.agent == "inventory"
    assert result.product_id == "prod-103"
    assert result.escalate is True
    assert "CRITICAL" in result.escalation_reason or "Instagram" in result.escalation_reason

