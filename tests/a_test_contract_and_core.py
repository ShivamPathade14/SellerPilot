"""Tests for frozen Pydantic contract and core service abstractions."""

import pytest
from core.interfaces import ContentService, InventoryService
from core.llm import claude_client
from core.mocks import MockContentService, MockInventoryService
from core.schemas import (
    AgentAction,
    CaptionRequest,
    CaptionResult,
    Event,
    IncomingMessage,
    Intent,
    InventoryAlert,
    Product,
    StockStatus,
)


def test_product_schema_validation():
    p = Product(
        id="prod-999",
        name="Test Ring",
        price=1200.0,
        category="Rings",
        material="Silver",
        description="A handcrafted ring",
        sizes=["6", "7"],
        colors=["Silver"],
    )
    assert p.id == "prod-999"
    assert p.price == 1200.0
    assert len(p.sizes) == 2


def test_agent_action_validation():
    action = AgentAction(
        agent="commerce",
        intent=Intent.stock_query,
        product_id="prod-101",
        response_text="Yes, we have 8 in stock! ✨",
        confidence=0.95,
    )
    assert action.agent == "commerce"
    assert action.intent == Intent.stock_query
    assert action.escalate is False
    assert action.confidence == 0.95


def test_protocol_conformance():
    inv_service = MockInventoryService()
    content_service = MockContentService()

    assert isinstance(inv_service, InventoryService)
    assert isinstance(content_service, ContentService)


def test_mock_inventory_service_operations():
    inv = MockInventoryService()

    # Search
    rings = inv.find_products("ring")
    assert len(rings) >= 1
    assert any("Ring" in r.name for r in rings)

    # Stock check
    stock = inv.get_stock("prod-101")
    assert stock is not None
    assert stock.in_stock is True
    assert stock.quantity == 8

    # Reservation success
    success = inv.reserve("prod-101", 2)
    assert success is True
    updated_stock = inv.get_stock("prod-101")
    assert updated_stock.quantity == 6

    # Out of stock reservation failure
    oos_success = inv.reserve("prod-103", 1)
    assert oos_success is False

    # Alerts check
    alerts = inv.get_alerts()
    assert len(alerts) >= 1
    assert any(a.product_id == "prod-103" for a in alerts)


def test_mock_content_service_generation():
    content = MockContentService()
    inv = MockInventoryService()
    product = inv.find_products("emerald")[0]

    req = CaptionRequest(product=product, extra_notes="Limited edition launch")
    res = content.generate_caption(req)

    assert isinstance(res, CaptionResult)
    assert "Raw Emerald" in res.caption
    assert len(res.hashtags) > 0
    assert "Limited edition launch" in res.caption


def test_claude_client_structured_mock_fallback():
    # Test intent classification structured output in mock mode
    action = claude_client.generate_structured_output(
        prompt="Do you have the Moonstone ring in size 7?",
        response_model=AgentAction,
    )
    assert isinstance(action, AgentAction)
    assert action.agent == "commerce"
    assert action.intent == Intent.stock_query
    assert action.escalate is False

    # Test refund escalation
    refund_action = claude_client.generate_structured_output(
        prompt="The ring broke and I want an immediate refund from your manager!",
        response_model=AgentAction,
    )
    assert refund_action.escalate is True
    assert refund_action.escalation_reason is not None
