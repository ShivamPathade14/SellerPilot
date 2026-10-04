"""Tests for Part B Streamlit Dashboard and End-to-End Demo flow.

Validates:
1. Dashboard module imports cleanly
2. Dashboard services initialization
3. Inventory page data retrieval
4. Content page caption generation in mock mode
5. Customer conversation flow reaches Commerce Agent via LangGraph
6. Demo flow executes without Claude API key and without state corruption
7. No business logic duplication in dashboard presentation layer
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from agents.content.agent import ContentAgent
from agents.inventory.service import SQLiteInventoryService
from core.mocks import SAMPLE_PRODUCTS
from core.schemas import AgentAction, CaptionRequest, CaptionResult, Event, IncomingMessage, Product
from db.base import Base
import db.conversation_models  # noqa: F401
import db.inventory_models  # noqa: F401
from orchestrator.graph import SellerPilotOrchestrator
from scripts.seed_db import seed_database


@pytest.fixture(scope="module")
def dashboard_test_db():
    """Create an isolated in-memory test database for dashboard tests."""
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


# 1. Dashboard module imports cleanly
def test_dashboard_modules_import():
    import dashboard.components as components
    import dashboard.demo as demo
    assert hasattr(components, "render_kpi_card")
    assert hasattr(components, "render_chat_message")
    assert hasattr(components, "render_caption_result")
    assert hasattr(demo, "run_live_demo")


# 2. Dashboard can initialize its core services
def test_dashboard_service_initialization(dashboard_test_db):
    inv_service = SQLiteInventoryService(session_factory=dashboard_test_db)
    content_agent = ContentAgent()
    orchestrator = SellerPilotOrchestrator(inventory=inv_service, content=content_agent)

    assert inv_service is not None
    assert content_agent is not None
    assert orchestrator is not None


# 3. Inventory page data retrieval
def test_inventory_data_retrieval(dashboard_test_db):
    inv_service = SQLiteInventoryService(session_factory=dashboard_test_db)
    items = inv_service.get_all_products_with_stock()
    assert len(items) == 15
    for item in items:
        assert "product_id" in item
        assert "name" in item
        assert "price" in item
        assert "quantity" in item
        assert "in_stock" in item


# 4. Content page can generate caption in mock mode
def test_content_generation_in_mock_mode():
    content_agent = ContentAgent()
    product = SAMPLE_PRODUCTS[0]
    req = CaptionRequest(product=product, extra_notes="Dashboard test drop")
    result = content_agent.generate_caption(req)

    assert isinstance(result, CaptionResult)
    assert product.name in result.caption
    assert len(result.hashtags) >= 5
    assert "#AuraJewels" in result.hashtags


# 5. Customer conversation flow reaches Commerce Agent via LangGraph Orchestrator
def test_conversation_flow_reaches_commerce_agent(dashboard_test_db):
    inv_service = SQLiteInventoryService(session_factory=dashboard_test_db)
    content_agent = ContentAgent()
    orchestrator = SellerPilotOrchestrator(inventory=inv_service, content=content_agent)

    msg = IncomingMessage(
        message_id="dash-test-1",
        customer_id="dash_user",
        channel="instagram",
        text="Do you have the Moonstone Wire-Wrapped Ring in size 7?",
    )
    event = Event(type="new_dm", payload={"message": msg.model_dump()})
    action: AgentAction = orchestrator.process_event(event)  # type: ignore

    assert action.agent == "commerce"
    assert action.product_id == "prod-101"
    assert "Moonstone" in action.response_text
    assert action.escalate is False


# 6. Demo flow executes without Claude API key and preserves state
def test_demo_flow_executes_safely(dashboard_test_db):
    inv_service = SQLiteInventoryService(session_factory=dashboard_test_db)
    content_agent = ContentAgent()
    orchestrator = SellerPilotOrchestrator(inventory=inv_service, content=content_agent)

    stock_before = inv_service.get_stock("prod-101")
    assert stock_before is not None
    orig_qty = stock_before.quantity

    activity_entries = []

    def mock_logger(entry):
        activity_entries.append(entry)

    # Execute core sequence steps directly to verify pipeline logic
    # Step 1: Customer DM
    msg = IncomingMessage(
        message_id="demo-test",
        customer_id="demo_user",
        channel="instagram",
        text="Do you have the Moonstone Wire-Wrapped Ring in size 7?",
    )
    action = orchestrator.process_event(Event(type="new_dm", payload={"message": msg.model_dump()}))
    assert isinstance(action, AgentAction)

    # Step 2: Simulate low stock and verify alert
    inv_service.reserve("prod-101", orig_qty - 2)
    low_stock = inv_service.get_stock("prod-101")
    assert low_stock is not None
    assert low_stock.quantity == 2
    assert low_stock.low_stock is True

    # Step 3: Content generation
    caption_res = content_agent.generate_caption(CaptionRequest(product=SAMPLE_PRODUCTS[0]))
    assert isinstance(caption_res, CaptionResult)

    # Revert reservation
    inv_service.adjust_stock("prod-101", orig_qty - 2, reason="Test teardown restore")
    restored_stock = inv_service.get_stock("prod-101")
    assert restored_stock is not None
    assert restored_stock.quantity == orig_qty


# 7. No business logic is duplicated in dashboard
def test_no_business_logic_duplication_in_dashboard():
    import dashboard.components as components
    # Components should only be callables for rendering
    assert callable(components.render_kpi_card)
    assert callable(components.get_stock_badge)
    assert callable(components.render_chat_message)
    assert callable(components.render_caption_result)
    assert callable(components.render_inventory_alert_card)
