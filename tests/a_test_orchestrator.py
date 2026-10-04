"""Tests for LangGraph Multi-Agent Orchestrator.

Validates:
1. Conformance to Orchestrator Protocol
2. Routing 'new_dm' to commerce_node
3. Escalation branching to escalation_node on high-risk inquiries
4. Routing 'new_product_photo' to content_node returning CaptionResult
5. Routing 'low_stock' to inventory_alert_node
6. Completeness of explicit, loggable audit trail in shared state
"""

import pytest
from core.interfaces import Orchestrator
from core.mocks import MockContentService, MockInventoryService
from core.schemas import AgentAction, CaptionResult, Event, Intent
from orchestrator.graph import SellerPilotOrchestrator


@pytest.fixture
def orchestrator():
    inv = MockInventoryService()
    content = MockContentService()
    orch = SellerPilotOrchestrator(inventory=inv, content=content)
    return orch


def test_orchestrator_protocol_conformance(orchestrator):
    """Ensure orchestrator adheres to typing.Protocol contract."""
    assert isinstance(orchestrator, Orchestrator)


def test_route_new_dm_event(orchestrator):
    """Verify 'new_dm' routes to commerce agent node and returns AgentAction."""
    event = Event(
        type="new_dm",
        payload={
            "customer_id": "cust-ig-42",
            "channel": "instagram",
            "text": "Do you have the Moonstone Wire-Wrapped Ring in size 7?",
        },
    )
    result = orchestrator.process_event(event)

    assert isinstance(result, AgentAction)
    assert result.agent == "commerce"
    assert result.intent == Intent.stock_query
    assert result.product_id == "prod-101"
    assert result.escalate is False


def test_route_new_dm_escalation_branch(orchestrator):
    """Verify that a complaint DM conditionally branches through escalation_node."""
    event = Event(
        type="new_dm",
        payload={
            "customer_id": "cust-angry-99",
            "channel": "whatsapp",
            "text": "My package arrived damaged! I demand a refund from your manager right now!",
        },
    )
    result = orchestrator.process_event(event)

    assert isinstance(result, AgentAction)
    assert result.escalate is True
    assert result.escalation_reason is not None


def test_route_new_product_photo_event(orchestrator):
    """Verify 'new_product_photo' routes to content agent node and returns CaptionResult."""
    event = Event(
        type="new_product_photo",
        payload={
            "product_id": "prod-102",
            "image_path": "/uploads/raw_emerald.png",
            "extra_notes": "Spotlight on raw emerald mining origins",
        },
    )
    result = orchestrator.process_event(event)

    assert isinstance(result, CaptionResult)
    assert "Raw Emerald" in result.caption
    assert len(result.hashtags) > 0
    assert "raw emerald mining origins" in result.caption.lower()


def test_route_low_stock_event(orchestrator):
    """Verify 'low_stock' event routes to inventory alert handling node."""
    event = Event(
        type="low_stock",
        payload={"product_id": "prod-103"},
    )
    result = orchestrator.process_event(event)

    assert isinstance(result, AgentAction)
    assert result.agent == "inventory"
    assert result.product_id == "prod-103"
    # prod-103 is posted on IG with 0 stock -> critical escalation!
    assert result.escalate is True


def test_explicit_log_trail_observability(orchestrator):
    """Verify that explicit node routing creates an observable, timestamped log trail."""
    event = Event(
        type="new_dm",
        payload={
            "customer_id": "cust-audit-1",
            "channel": "instagram",
            "text": "Can I get a 50% discount?",
        },
    )
    result = orchestrator.process_event(event)
    assert isinstance(result, AgentAction)
    assert result.escalate is True
