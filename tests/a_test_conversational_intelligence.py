"""Multi-turn Conversational Intelligence & Workflow Regression Tests.

Validates:
1. Availability inquiry followed by 'yes place this' (The Critical Bugfix)
2. Price inquiry followed by 'how much?'
3. Product inquiry followed by 'can I get two?'
4. Product reference using 'it'
5. Product reference using 'this one'
6. Product variant inquiry
7. Ambiguous product reference
8. Product not found
9. Purchase workflow requiring final confirmation
10. Stock insufficient for requested quantity
11. Stock changing between availability check and order
12. Duplicate confirmation message idempotency
13. Context isolation between two customers
14. Conversation persistence across separate API requests
15. Complaint escalation during an active conversation
16. Refund request during an active conversation
17. Existing mock mode with no Claude API key
18. Existing commerce scenarios still working
"""

from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from agents.commerce.agent import ConversationalCommerceAgent
from agents.commerce.order_service import OrderService
from agents.inventory.service import SQLiteInventoryService
from api.main import app
from core.mocks import MockInventoryService
from core.schemas import AgentAction, ConversationStage, IncomingMessage, Intent, Product
from db.base import SessionLocal, init_db
from db.inventory_models import InventoryItemORM, ProductORM
from db.conversation_models import ConversationContextORM, ConversationORM, MessageORM
from db.order_models import OrderORM
from scripts.seed_db import seed_database


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    """Ensure database schema and catalog are seeded."""
    init_db()
    seed_database()


@pytest.fixture(autouse=True)
def clean_test_customers():
    """Ensure test customer records do not leak between test runs."""
    def _clean():
        with SessionLocal() as db:
            db.query(MessageORM).filter(
                MessageORM.message_id.like("api-msg-%")
                | MessageORM.message_id.like("reply-api-msg-%")
                | MessageORM.message_id.like("sc%")
                | MessageORM.message_id.like("dbg-%")
            ).delete(synchronize_session=False)
            db.query(ConversationContextORM).filter(
                ConversationContextORM.customer_id.like("test-buyer-%")
                | ConversationContextORM.customer_id.like("test_user_%")
                | ConversationContextORM.customer_id.like("cust-%")
            ).delete(synchronize_session=False)
            db.query(ConversationORM).filter(
                ConversationORM.customer_id.like("test-buyer-%")
                | ConversationORM.customer_id.like("test_user_%")
                | ConversationORM.customer_id.like("cust-%")
            ).delete(synchronize_session=False)
            db.query(OrderORM).filter(
                OrderORM.customer_id.like("test-buyer-%")
                | OrderORM.customer_id.like("test_user_%")
                | OrderORM.customer_id.like("cust-%")
            ).delete(synchronize_session=False)
            db.commit()
    _clean()
    yield
    _clean()


@pytest.fixture
def agent():
    return ConversationalCommerceAgent()


@pytest.fixture
def inventory():
    return SQLiteInventoryService()


@pytest.fixture
def order_svc():
    return OrderService()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client



# -----------------------------------------------------------------------------
# Scenario 1: Availability inquiry followed by "yes place this" (The Bugfix)
# -----------------------------------------------------------------------------
def test_scenario_1_availability_followed_by_yes_place_this(agent, inventory):
    """Customer asks if Rose Gold Hammered Bangle is in stock, then replies 'yes place this'."""
    cust_id = "test-buyer-sc1"

    # Turn 1: Availability check
    msg1 = IncomingMessage(
        message_id="sc1-m1",
        customer_id=cust_id,
        channel="instagram",
        text="is this in stock Rose Gold Hammered Bangle?",
        timestamp=datetime.utcnow(),
    )
    res1: AgentAction = agent.handle_message(msg1, inventory)
    assert res1.intent == Intent.stock_query
    assert res1.product_id == "prod-104"
    assert "Rose Gold Hammered Bangle" in res1.response_text

    # Read live catalog price & stock
    stock = inventory.get_stock("prod-104")
    assert stock is not None
    assert str(stock.quantity) in res1.response_text or "in stock" in res1.response_text.lower()

    # Turn 2: Purchase intent "yes place this"
    msg2 = IncomingMessage(
        message_id="sc1-m2",
        customer_id=cust_id,
        channel="instagram",
        text="yes place this",
        timestamp=datetime.utcnow(),
    )
    res2: AgentAction = agent.handle_message(msg2, inventory)

    # Must NOT return generic greeting
    assert "Welcome to Aura Jewels" not in res2.response_text
    assert res2.intent == Intent.purchase_intent
    assert res2.product_id == "prod-104"
    assert "Rose Gold Hammered Bangle" in (res2.active_product_name or res2.response_text)
    # Stage should advance towards purchase details or confirmation
    assert res2.conversation_stage in [
        ConversationStage.awaiting_purchase_details,
        ConversationStage.awaiting_order_confirmation,
    ]


# -----------------------------------------------------------------------------
# Scenario 2: Price inquiry followed by "how much?"
# -----------------------------------------------------------------------------
def test_scenario_2_price_inquiry_followed_by_how_much(agent, inventory):
    cust_id = "test-buyer-sc2"

    # Turn 1: Mention Moonstone Wire-Wrapped Ring
    msg1 = IncomingMessage(
        message_id="sc2-m1",
        customer_id=cust_id,
        channel="instagram",
        text="Do you have the Moonstone Wire-Wrapped Ring?",
        timestamp=datetime.utcnow(),
    )
    agent.handle_message(msg1, inventory)

    # Turn 2: "how much?"
    msg2 = IncomingMessage(
        message_id="sc2-m2",
        customer_id=cust_id,
        channel="instagram",
        text="how much?",
        timestamp=datetime.utcnow(),
    )
    res2: AgentAction = agent.handle_message(msg2, inventory)

    assert res2.intent == Intent.price_query
    assert res2.product_id == "prod-101"
    # Verify price from database is mentioned
    prod = inventory.find_products("prod-101")[0]
    expected_price_str = f"{prod.price:,.0f}"
    assert expected_price_str in res2.response_text or str(int(prod.price)) in res2.response_text


# -----------------------------------------------------------------------------
# Scenario 3: Product inquiry followed by "can I get two?"
# -----------------------------------------------------------------------------
def test_scenario_3_product_inquiry_followed_by_quantity_change(agent, inventory):
    cust_id = "test-buyer-sc3"

    msg1 = IncomingMessage(
        message_id="sc3-m1",
        customer_id=cust_id,
        channel="instagram",
        text="Is the Rose Gold Hammered Bangle available?",
        timestamp=datetime.utcnow(),
    )
    agent.handle_message(msg1, inventory)

    msg2 = IncomingMessage(
        message_id="sc3-m2",
        customer_id=cust_id,
        channel="instagram",
        text="can I get two?",
        timestamp=datetime.utcnow(),
    )
    res2: AgentAction = agent.handle_message(msg2, inventory)

    assert res2.intent == Intent.quantity_change
    assert res2.requested_quantity == 2
    assert res2.product_id == "prod-104"
    # Total for 2 pieces
    prod = inventory.find_products("prod-104")[0]
    expected_total = prod.price * 2
    assert f"{expected_total:,.0f}" in res2.response_text or str(int(expected_total)) in res2.response_text


# -----------------------------------------------------------------------------
# Scenario 4: Product reference using "it"
# -----------------------------------------------------------------------------
def test_scenario_4_product_reference_using_it(agent, inventory):
    cust_id = "test-buyer-sc4"

    msg1 = IncomingMessage(
        message_id="sc4-m1",
        customer_id=cust_id,
        channel="whatsapp",
        text="Is the Amethyst Cluster Studs available?",
        timestamp=datetime.utcnow(),
    )
    agent.handle_message(msg1, inventory)

    msg2 = IncomingMessage(
        message_id="sc4-m2",
        customer_id=cust_id,
        channel="whatsapp",
        text="how much is it?",
        timestamp=datetime.utcnow(),
    )
    res2: AgentAction = agent.handle_message(msg2, inventory)

    assert res2.intent == Intent.price_query
    assert res2.product_id == "prod-106"
    assert "Amethyst Cluster Studs" in (res2.active_product_name or res2.response_text)


# -----------------------------------------------------------------------------
# Scenario 5: Product reference using "this one"
# -----------------------------------------------------------------------------
def test_scenario_5_product_reference_using_this_one(agent, inventory):
    cust_id = "test-buyer-sc5"

    msg1 = IncomingMessage(
        message_id="sc5-m1",
        customer_id=cust_id,
        channel="instagram",
        text="Tell me about Raw Emerald Pendant Necklace",
        timestamp=datetime.utcnow(),
    )
    agent.handle_message(msg1, inventory)

    msg2 = IncomingMessage(
        message_id="sc5-m2",
        customer_id=cust_id,
        channel="instagram",
        text="okay, I'll take this one",
        timestamp=datetime.utcnow(),
    )
    res2: AgentAction = agent.handle_message(msg2, inventory)

    assert res2.intent == Intent.purchase_intent
    assert res2.product_id == "prod-102"
    assert "Raw Emerald Pendant Necklace" in (res2.active_product_name or res2.response_text)


# -----------------------------------------------------------------------------
# Scenario 6: Product variant inquiry
# -----------------------------------------------------------------------------
def test_scenario_6_product_variant_inquiry(agent, inventory):
    cust_id = "test-buyer-sc6"

    msg1 = IncomingMessage(
        message_id="sc6-m1",
        customer_id=cust_id,
        channel="instagram",
        text="Is the Rose Gold Hammered Bangle in stock?",
        timestamp=datetime.utcnow(),
    )
    agent.handle_message(msg1, inventory)

    msg2 = IncomingMessage(
        message_id="sc6-m2",
        customer_id=cust_id,
        channel="instagram",
        text="what about silver?",
        timestamp=datetime.utcnow(),
    )
    res2: AgentAction = agent.handle_message(msg2, inventory)

    assert res2.intent == Intent.variant_query
    assert res2.product_id == "prod-104"
    # Must correctly note material is Rose Gold Vermeil, not silver
    assert "Rose Gold" in res2.response_text


# -----------------------------------------------------------------------------
# Scenario 7: Ambiguous product reference
# -----------------------------------------------------------------------------
def test_scenario_7_ambiguous_product_reference(agent, inventory):
    cust_id = "test-buyer-sc7"

    # Multiple earrings exist in catalog (Sunburst Labradorite Drops, Amethyst Cluster Studs, etc.)
    msg = IncomingMessage(
        message_id="sc7-m1",
        customer_id=cust_id,
        channel="instagram",
        text="Show me earrings",
        timestamp=datetime.utcnow(),
    )
    res: AgentAction = agent.handle_message(msg, inventory)

    # Should ask customer which earring piece they mean
    assert res.intent in [Intent.product_search, Intent.other]
    assert "which" in res.response_text.lower() or "few" in res.response_text.lower() or "options" in res.response_text.lower()


# -----------------------------------------------------------------------------
# Scenario 8: Product not found
# -----------------------------------------------------------------------------
def test_scenario_8_product_not_found(agent, inventory):
    cust_id = "test-buyer-sc8"

    msg = IncomingMessage(
        message_id="sc8-m1",
        customer_id=cust_id,
        channel="instagram",
        text="Do you sell Titanium Smartwatches with GPS?",
        timestamp=datetime.utcnow(),
    )
    res: AgentAction = agent.handle_message(msg, inventory)

    assert res.product_id is None
    # Never claim product exists
    assert "Titanium Smartwatch" not in res.response_text


# -----------------------------------------------------------------------------
# Scenario 9: Purchase workflow requiring final confirmation
# -----------------------------------------------------------------------------
def test_scenario_9_purchase_workflow_full_flow(agent, inventory, order_svc):
    cust_id = "test-buyer-sc9"

    # Turn 1: Availability
    msg1 = IncomingMessage(
        message_id="sc9-m1",
        customer_id=cust_id,
        channel="instagram",
        text="is this in stock Rose Gold Hammered Bangle?",
        timestamp=datetime.utcnow(),
    )
    res1 = agent.handle_message(msg1, inventory, order_service=order_svc)
    assert res1.conversation_stage == ConversationStage.availability_verified

    # Turn 2: Purchase intent
    msg2 = IncomingMessage(
        message_id="sc9-m2",
        customer_id=cust_id,
        channel="instagram",
        text="yes place this",
        timestamp=datetime.utcnow(),
    )
    res2 = agent.handle_message(msg2, inventory, order_service=order_svc)
    assert res2.conversation_stage == ConversationStage.awaiting_purchase_details

    # Turn 3: Size selection
    msg3 = IncomingMessage(
        message_id="sc9-m3",
        customer_id=cust_id,
        channel="instagram",
        text="Medium",
        timestamp=datetime.utcnow(),
    )
    res3 = agent.handle_message(msg3, inventory, order_service=order_svc)
    assert res3.conversation_stage == ConversationStage.awaiting_order_confirmation
    assert "confirm" in res3.response_text.lower()

    # Turn 4: Final confirmation
    msg4 = IncomingMessage(
        message_id="sc9-m4",
        customer_id=cust_id,
        channel="instagram",
        text="yes confirm",
        timestamp=datetime.utcnow(),
    )
    res4 = agent.handle_message(msg4, inventory, order_service=order_svc)
    assert res4.conversation_stage == ConversationStage.order_created
    assert res4.order_id is not None
    assert "confirmed" in res4.response_text.lower()

    # Verify order is persisted in DB
    order = order_svc.get_order_by_id(res4.order_id)
    assert order is not None
    assert order.product_id == "prod-104"
    assert order.customer_id == cust_id


# -----------------------------------------------------------------------------
# Scenario 10: Stock insufficient for requested quantity
# -----------------------------------------------------------------------------
def test_scenario_10_stock_insufficient(agent, inventory):
    cust_id = "test-buyer-sc10"

    msg1 = IncomingMessage(
        message_id="sc10-m1",
        customer_id=cust_id,
        channel="instagram",
        text="Is the Rose Gold Hammered Bangle in stock?",
        timestamp=datetime.utcnow(),
    )
    agent.handle_message(msg1, inventory)

    msg2 = IncomingMessage(
        message_id="sc10-m2",
        customer_id=cust_id,
        channel="instagram",
        text="can I get 15 pieces?",
        timestamp=datetime.utcnow(),
    )
    res2: AgentAction = agent.handle_message(msg2, inventory)

    assert "only" in res2.response_text.lower() or "remaining" in res2.response_text.lower()


# -----------------------------------------------------------------------------
# Scenario 11: Stock changing between availability check and order
# -----------------------------------------------------------------------------
def test_scenario_11_stock_changing_between_inquiry_and_order(agent, inventory, order_svc):
    cust_id = "test-buyer-sc11"

    # Setup a product with 1 unit in stock
    with SessionLocal() as db:
        item = db.query(InventoryItemORM).filter(InventoryItemORM.product_id == "prod-105").first()
        if item:
            item.quantity = 1
            db.commit()

    # Turn 1: Availability check
    msg1 = IncomingMessage(
        message_id="sc11-m1",
        customer_id=cust_id,
        channel="instagram",
        text="Is Sunburst Labradorite Drops available?",
        timestamp=datetime.utcnow(),
    )
    agent.handle_message(msg1, inventory, order_service=order_svc)

    # Now stock changes to 0 before customer confirms!
    with SessionLocal() as db:
        item = db.query(InventoryItemORM).filter(InventoryItemORM.product_id == "prod-105").first()
        if item:
            item.quantity = 0
            db.commit()

    # Turn 2: Customer tries to place order
    msg2 = IncomingMessage(
        message_id="sc11-m2",
        customer_id=cust_id,
        channel="instagram",
        text="yes place this",
        timestamp=datetime.utcnow(),
    )
    res2 = agent.handle_message(msg2, inventory, order_service=order_svc)

    # Must explain out of stock honestly
    assert "sold out" in res2.response_text.lower() or "out of stock" in res2.response_text.lower()


# -----------------------------------------------------------------------------
# Scenario 12: Duplicate confirmation message idempotency
# -----------------------------------------------------------------------------
def test_scenario_12_duplicate_confirmation_message_idempotency(agent, inventory, order_svc):
    cust_id = "test-buyer-sc12"

    # Setup context at awaiting_order_confirmation
    ctx = agent.context_manager.get_or_create(cust_id, "instagram")
    ctx.active_product_id = "prod-101"
    ctx.active_product_name = "Moonstone Wire-Wrapped Ring"
    ctx.conversation_stage = ConversationStage.awaiting_order_confirmation
    ctx.pending_action = "awaiting_order_confirmation"
    ctx.requested_quantity = 1
    agent.context_manager.save(ctx)

    # Turn 1: Confirm message
    msg_confirm = IncomingMessage(
        message_id="m-confirm-unique-12",
        customer_id=cust_id,
        channel="instagram",
        text="yes confirm",
        timestamp=datetime.utcnow(),
    )
    res1 = agent.handle_message(msg_confirm, inventory, context=ctx, order_service=order_svc)
    assert res1.order_id is not None
    first_order_id = res1.order_id

    # Turn 2: Duplicate retry of same message
    res2 = agent.handle_message(msg_confirm, inventory, context=ctx, order_service=order_svc)
    assert res2.order_id == first_order_id
    assert "already" in res2.response_text.lower()


# -----------------------------------------------------------------------------
# Scenario 13: Context isolation between two customers
# -----------------------------------------------------------------------------
def test_scenario_13_context_isolation_between_customers(agent, inventory):
    # Customer A talks about Moonstone Ring
    msg_a1 = IncomingMessage(
        message_id="a-1",
        customer_id="cust-alpha",
        channel="instagram",
        text="Is the Moonstone Wire-Wrapped Ring in stock?",
        timestamp=datetime.utcnow(),
    )
    agent.handle_message(msg_a1, inventory)

    # Customer B talks about Emerald Necklace
    msg_b1 = IncomingMessage(
        message_id="b-1",
        customer_id="cust-beta",
        channel="instagram",
        text="Is the Raw Emerald Pendant Necklace in stock?",
        timestamp=datetime.utcnow(),
    )
    agent.handle_message(msg_b1, inventory)

    # Customer A asks "how much?"
    msg_a2 = IncomingMessage(
        message_id="a-2",
        customer_id="cust-alpha",
        channel="instagram",
        text="how much?",
        timestamp=datetime.utcnow(),
    )
    res_a2 = agent.handle_message(msg_a2, inventory)
    assert res_a2.product_id == "prod-101"
    assert "Moonstone" in (res_a2.active_product_name or res_a2.response_text)

    # Customer B asks "how much?"
    msg_b2 = IncomingMessage(
        message_id="b-2",
        customer_id="cust-beta",
        channel="instagram",
        text="how much?",
        timestamp=datetime.utcnow(),
    )
    res_b2 = agent.handle_message(msg_b2, inventory)
    assert res_b2.product_id == "prod-102"
    assert "Emerald" in (res_b2.active_product_name or res_b2.response_text)


# -----------------------------------------------------------------------------
# Scenario 14: Conversation persistence across separate API requests
# -----------------------------------------------------------------------------
def test_scenario_14_api_persistence_across_separate_requests(client):
    cust_id = "test-buyer-sc14"

    # API Request 1: Inquire about Bangle
    payload1 = {
        "message_id": "sc14-api-1",
        "customer_id": cust_id,
        "channel": "instagram",
        "text": "is this in stock Rose Gold Hammered Bangle?",
    }
    r1 = client.post("/webhook/message", json=payload1)
    assert r1.status_code == 200
    action1 = r1.json()["action"]
    assert action1["intent"] == "stock_query"
    assert action1["product_id"] == "prod-104"

    # API Request 2: "yes place this"
    payload2 = {
        "message_id": "sc14-api-2",
        "customer_id": cust_id,
        "channel": "instagram",
        "text": "yes place this",
    }
    r2 = client.post("/webhook/message", json=payload2)
    assert r2.status_code == 200
    action2 = r2.json()["action"]
    assert action2["intent"] == "purchase_intent"
    assert action2["product_id"] == "prod-104"
    assert "Welcome to Aura Jewels" not in action2["response_text"]


# -----------------------------------------------------------------------------
# Scenario 15: Complaint escalation during an active conversation
# -----------------------------------------------------------------------------
def test_scenario_15_complaint_escalation_during_active_conversation(agent, inventory):
    cust_id = "test-buyer-sc15"

    msg1 = IncomingMessage(
        message_id="sc15-1",
        customer_id=cust_id,
        channel="instagram",
        text="Do you have the Moonstone Wire-Wrapped Ring?",
        timestamp=datetime.utcnow(),
    )
    agent.handle_message(msg1, inventory)

    msg2 = IncomingMessage(
        message_id="sc15-2",
        customer_id=cust_id,
        channel="instagram",
        text="Your previous parcel arrived damaged and broken! This is terrible quality!",
        timestamp=datetime.utcnow(),
    )
    res2: AgentAction = agent.handle_message(msg2, inventory)

    assert res2.escalate is True
    assert "complaint" in (res2.escalation_reason or "").lower() or "dissatisfaction" in (res2.escalation_reason or "").lower()
    assert res2.conversation_stage == ConversationStage.escalated


# -----------------------------------------------------------------------------
# Scenario 16: Refund request during an active conversation
# -----------------------------------------------------------------------------
def test_scenario_16_refund_request_during_active_conversation(agent, inventory):
    cust_id = "test-buyer-sc16"

    msg1 = IncomingMessage(
        message_id="sc16-1",
        customer_id=cust_id,
        channel="instagram",
        text="I want a refund for my order right now!",
        timestamp=datetime.utcnow(),
    )
    res1: AgentAction = agent.handle_message(msg1, inventory)

    assert res1.escalate is True
    assert "refund" in (res1.escalation_reason or "").lower()
    assert res1.conversation_stage == ConversationStage.escalated


# -----------------------------------------------------------------------------
# Scenario 17: Existing mock mode with no Claude API key
# -----------------------------------------------------------------------------
def test_scenario_17_mock_mode_without_api_key(agent, inventory):
    msg = IncomingMessage(
        message_id="sc17-1",
        customer_id="cust-offline",
        channel="instagram",
        text="Is the Rose Gold Hammered Bangle in stock?",
        timestamp=datetime.utcnow(),
    )
    res = agent.handle_message(msg, inventory)
    assert isinstance(res, AgentAction)
    assert res.intent == Intent.stock_query


# -----------------------------------------------------------------------------
# Scenario 18: Existing commerce scenarios still working
# -----------------------------------------------------------------------------
def test_scenario_18_existing_scenarios_preserved(agent, inventory):
    # Wrong size
    msg_size = IncomingMessage(
        message_id="sc18-size",
        customer_id="cust-size",
        channel="instagram",
        text="Do you have the Moonstone Wire-Wrapped Ring in size 10?",
        timestamp=datetime.utcnow(),
    )
    res_size = agent.handle_message(msg_size, inventory)
    assert "custom-size" in res_size.response_text.lower() or "don't have size 10" in res_size.response_text.lower()

    # Bargaining
    msg_bargain = IncomingMessage(
        message_id="sc18-bargain",
        customer_id="cust-bargain",
        channel="instagram",
        text="Can I get a discount or lower price?",
        timestamp=datetime.utcnow(),
    )
    res_bargain = agent.handle_message(msg_bargain, inventory)
    assert res_bargain.escalate is True

    # Shipping
    msg_ship = IncomingMessage(
        message_id="sc18-ship",
        customer_id="cust-ship",
        channel="instagram",
        text="How long does delivery and shipping take?",
        timestamp=datetime.utcnow(),
    )
    res_ship = agent.handle_message(msg_ship, inventory)
    assert res_ship.intent == Intent.shipping_query
    assert res_ship.escalate is False
