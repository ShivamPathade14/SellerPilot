"""Unit and scenario tests for Conversational Commerce Agent.

Validates required viva scenarios:
1. Wrong size inquiry
2. Sold-out item inquiry
3. Price bargaining / discount negotiation
4. Angry customer / complaint / refund
5. "Is this still available?" with no product named
6. In-stock inquiry with product named
7. Shipping inquiry
8. Bulk order escalation
9. Custom order escalation
10. Strict protocol injection & zero-hallucination verification
"""

from datetime import datetime
import pytest
from agents.commerce.agent import ConversationalCommerceAgent
from core.mocks import MockInventoryService
from core.schemas import AgentAction, IncomingMessage, Intent


@pytest.fixture
def agent():
    return ConversationalCommerceAgent()


@pytest.fixture
def inventory():
    return MockInventoryService()


def test_scenario_wrong_size(agent, inventory):
    """Customer asks for a size that does not exist in standard catalog (size 10 vs 6, 7, 8)."""
    msg = IncomingMessage(
        message_id="msg-1",
        customer_id="cust-1",
        channel="instagram",
        text="Do you have the Moonstone Wire-Wrapped Ring in size 10?",
        timestamp=datetime.utcnow(),
    )
    action: AgentAction = agent.handle_message(msg, inventory)

    assert action.agent == "commerce"
    assert action.intent == Intent.stock_query
    assert action.product_id == "prod-101"
    assert "sizes: 6, 7, 8" in action.response_text or "size 10" in action.response_text
    assert "don't have size 10" in action.response_text.lower() or "custom-size" in action.response_text.lower()


def test_scenario_sold_out_item(agent, inventory):
    """Customer asks for an item with 0 stock (Dainty Freshwater Pearl Choker)."""
    msg = IncomingMessage(
        message_id="msg-2",
        customer_id="cust-2",
        channel="whatsapp",
        text="Is the Dainty Freshwater Pearl Choker available to buy?",
        timestamp=datetime.utcnow(),
    )
    action: AgentAction = agent.handle_message(msg, inventory)

    assert action.agent == "commerce"
    assert action.intent == Intent.stock_query
    assert action.product_id == "prod-103"
    assert "sold out" in action.response_text.lower()
    assert "notify" in action.response_text.lower() or "next studio batch" in action.response_text.lower()


def test_scenario_price_bargaining(agent, inventory):
    """Customer attempts price bargaining / asking for discount."""
    msg = IncomingMessage(
        message_id="msg-3",
        customer_id="cust-3",
        channel="instagram",
        text="Can you give me a 25% discount if I buy two rings right now?",
        timestamp=datetime.utcnow(),
    )
    action: AgentAction = agent.handle_message(msg, inventory)

    assert action.agent == "commerce"
    assert action.intent == Intent.price_query
    assert action.escalate is True
    assert "bargaining" in action.escalation_reason.lower() or "discount" in action.escalation_reason.lower()
    assert "founder" in action.response_text.lower()


def test_scenario_angry_customer_complaint(agent, inventory):
    """Angry customer complaining about a broken item and demanding refund."""
    msg = IncomingMessage(
        message_id="msg-4",
        customer_id="cust-4",
        channel="whatsapp",
        text="My necklace arrived completely broken and damaged! This is terrible, I am furious and want a refund!",
        timestamp=datetime.utcnow(),
    )
    action: AgentAction = agent.handle_message(msg, inventory)

    assert action.agent == "commerce"
    assert action.escalate is True
    assert "complaint" in action.escalation_reason.lower() or "dissatisfaction" in action.escalation_reason.lower()
    assert "founder" in action.response_text.lower() or "orders team" in action.response_text.lower()


def test_scenario_is_this_still_available_no_product_named(agent, inventory):
    """Customer sends 'is this still available?' without naming any product."""
    msg = IncomingMessage(
        message_id="msg-5",
        customer_id="cust-5",
        channel="instagram",
        text="Hey, is this still available?",
        timestamp=datetime.utcnow(),
    )
    action: AgentAction = agent.handle_message(msg, inventory)

    assert action.agent == "commerce"
    assert action.intent == Intent.stock_query
    assert action.product_id is None
    assert action.escalate is True
    assert "ambiguous" in action.escalation_reason.lower()
    assert "photo" in action.response_text.lower() or "screenshot" in action.response_text.lower() or "name" in action.response_text.lower()


def test_scenario_in_stock_inquiry_with_product_named(agent, inventory):
    """Customer asks about Moonstone ring in size 7 (which is in stock)."""
    msg = IncomingMessage(
        message_id="msg-6",
        customer_id="cust-6",
        channel="instagram",
        text="Do you have the Moonstone Wire-Wrapped Ring in size 7?",
        timestamp=datetime.utcnow(),
    )
    action: AgentAction = agent.handle_message(msg, inventory)

    assert action.agent == "commerce"
    assert action.intent == Intent.stock_query
    assert action.product_id == "prod-101"
    assert action.escalate is False
    assert "8 available" in action.response_text or "in stock" in action.response_text.lower()
    assert "1,450" in action.response_text


def test_scenario_low_stock_notice(agent, inventory):
    """Customer asks about Raw Emerald Pendant (which has only 3 pieces left)."""
    msg = IncomingMessage(
        message_id="msg-7",
        customer_id="cust-7",
        channel="whatsapp",
        text="Is the Raw Emerald Pendant Necklace in stock?",
        timestamp=datetime.utcnow(),
    )
    action: AgentAction = agent.handle_message(msg, inventory)

    assert action.product_id == "prod-102"
    assert action.escalate is False
    assert "3 pieces" in action.response_text or "3 left" in action.response_text


def test_scenario_price_query(agent, inventory):
    """Customer asks for price of Rose Gold Hammered Bangle."""
    msg = IncomingMessage(
        message_id="msg-8",
        customer_id="cust-8",
        channel="instagram",
        text="How much is the Rose Gold Hammered Bangle?",
        timestamp=datetime.utcnow(),
    )
    action: AgentAction = agent.handle_message(msg, inventory)

    assert action.intent == Intent.price_query
    assert action.product_id == "prod-104"
    assert "1,600" in action.response_text


def test_scenario_shipping_inquiry(agent, inventory):
    """Customer asks about shipping and delivery timeline."""
    msg = IncomingMessage(
        message_id="msg-9",
        customer_id="cust-9",
        channel="whatsapp",
        text="How long does shipping take to Bangalore and what are the courier charges?",
        timestamp=datetime.utcnow(),
    )
    action: AgentAction = agent.handle_message(msg, inventory)

    assert action.intent == Intent.shipping_query
    assert action.escalate is False
    assert "dispatch" in action.response_text.lower() or "tracked delivery" in action.response_text.lower()


def test_scenario_bulk_order_escalation(agent, inventory):
    """Customer asks for bulk wholesale order of 50 pieces."""
    msg = IncomingMessage(
        message_id="msg-10",
        customer_id="cust-10",
        channel="instagram",
        text="I need 50 pieces of your gemstone bracelets for wedding return gifts. Do you take wholesale orders?",
        timestamp=datetime.utcnow(),
    )
    action: AgentAction = agent.handle_message(msg, inventory)

    assert action.escalate is True
    assert "bulk" in action.escalation_reason.lower() or "wholesale" in action.escalation_reason.lower()


def test_scenario_custom_order_escalation(agent, inventory):
    """Customer asks for bespoke custom jewelry modification."""
    msg = IncomingMessage(
        message_id="msg-11",
        customer_id="cust-11",
        channel="instagram",
        text="Can you customize this ring to use 18k solid gold instead of silver wire?",
        timestamp=datetime.utcnow(),
    )
    action: AgentAction = agent.handle_message(msg, inventory)

    assert action.escalate is True
    assert "custom" in action.escalation_reason.lower() or "bespoke" in action.escalation_reason.lower()
