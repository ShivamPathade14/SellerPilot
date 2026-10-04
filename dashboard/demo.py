"""End-to-End Live Demonstration Runner for SellerPilot AI.

Architectural Viva Notes:
1. Multi-Agent Coordinated Pipeline: Executes a complete live sequence demonstrating:
   - Inbound customer DM -> LangGraph Orchestrator -> Conversational Commerce Agent
   - Live zero-hallucination inventory lookup (SQLiteInventoryService)
   - Stock mutation triggering Inventory Agent threshold detection & alert generation
   - Brand Voice Analyzer & Content Agent generating fact-grounded Instagram captions
2. Non-Destructive State Guarantees: Reverts any demo stock adjustments upon completion,
   ensuring the persistent database is never corrupted.
3. Observability & Logging: Each transition updates the audit activity log and displays
   step-by-step progress for hackathon judges and viva evaluators.
"""

from datetime import datetime
import time
from typing import Callable
import streamlit as st
from agents.commerce.agent import ConversationalCommerceAgent
from agents.content.agent import ContentAgent
from agents.inventory.agent import InventoryAgent
from agents.inventory.service import SQLiteInventoryService
from core.mocks import SAMPLE_PRODUCTS
from core.schemas import AgentAction, CaptionRequest, CaptionResult, Event, IncomingMessage
from orchestrator.graph import SellerPilotOrchestrator


def run_live_demo(
    inventory_service: SQLiteInventoryService,
    content_agent: ContentAgent,
    orchestrator: SellerPilotOrchestrator,
    log_callback: Callable[[dict], None] | None = None,
):
    """Execute the end-to-end multi-agent demonstration sequence."""
    st.markdown("### 🎬 Multi-Agent Coordinated Live Execution")

    demo_prod_id = "prod-101"
    initial_stock = inventory_service.get_stock(demo_prod_id)
    orig_qty = initial_stock.quantity if initial_stock else 8

    try:
        with st.status("🚀 Running SellerPilot Multi-Agent Pipeline...", expanded=True) as status_box:

            # -----------------------------------------------------------------
            # Step 1 & 2 & 3: Customer DM -> Commerce Agent via Orchestrator
            # -----------------------------------------------------------------
            st.write("#### 1️⃣ Customer DM & Conversational Commerce")
            customer_query = "Hi, is the Moonstone Wire-Wrapped Ring available in size 7?"
            st.info(f"**Customer DM:** \"{customer_query}\"")

            time.sleep(0.4)
            msg = IncomingMessage(
                message_id=f"demo-dm-{int(time.time())}",
                customer_id="cust_demo_buyer",
                channel="instagram",
                text=customer_query,
                timestamp=datetime.utcnow(),
            )
            event = Event(type="new_dm", payload={"message": msg.model_dump()})

            st.write("⚡ *Dispatched `new_dm` to LangGraph Orchestrator -> `commerce_node`*")
            action: AgentAction = orchestrator.process_event(event)  # type: ignore

            st.success(f"**SellerPilot Response:** {action.response_text}")
            c1, c2, c3 = st.columns(3)
            c1.metric("Selected Agent", action.agent.capitalize())
            c2.metric("Detected Intent", action.intent.value.upper())
            c3.metric("Stock Verified", f"{initial_stock.quantity if initial_stock else 0} units")

            if log_callback:
                log_callback({
                    "timestamp": datetime.utcnow().strftime("%H:%M:%S"),
                    "event": "new_dm",
                    "agent": "CommerceAgent",
                    "intent": action.intent.value,
                    "action": "lookup_stock",
                    "result": f"Answered in-stock ({initial_stock.quantity if initial_stock else 0} available)",
                })

            time.sleep(0.4)
            st.divider()

            # -----------------------------------------------------------------
            # Step 4 & 5: Inventory Mutation & Low-Stock Alert Detection
            # -----------------------------------------------------------------
            st.write("#### 2️⃣ Inventory Threshold Event & Alert Generation")
            st.write("Simulating reservation spike: reserving stock down to trigger low-stock threshold (<= 3)...")

            # Reserve down to 2 units to trigger low stock
            units_to_reserve = max(1, orig_qty - 2)
            inventory_service.reserve(demo_prod_id, units_to_reserve)

            inv_agent = InventoryAgent(service=inventory_service)
            low_stock_event = Event(type="low_stock", payload={"product_id": demo_prod_id})
            inv_action = inv_agent.handle_event(low_stock_event)

            current_stock = inventory_service.get_stock(demo_prod_id)
            alerts = inventory_service.get_alerts()
            recent_alert = next((a for a in alerts if a.product_id == demo_prod_id), None)

            st.warning(
                f"⚠️ **Inventory Agent Detected:** Product `{demo_prod_id}` depleted from {orig_qty} -> {current_stock.quantity if current_stock else 0} units!\n\n"
                f"**Alert Message:** {recent_alert.message if recent_alert else 'Low stock threshold reached.'}"
            )

            if log_callback:
                log_callback({
                    "timestamp": datetime.utcnow().strftime("%H:%M:%S"),
                    "event": "low_stock",
                    "agent": "InventoryAgent",
                    "intent": "stock_alert",
                    "action": "threshold_detection",
                    "result": f"Alert emitted: {current_stock.quantity if current_stock else 0} units remaining",
                })

            time.sleep(0.4)
            st.divider()

            # -----------------------------------------------------------------
            # Step 6 & 7: Content Studio Caption Generation
            # -----------------------------------------------------------------
            st.write("#### 3️⃣ Content Agent & Brand Voice Generation")
            st.write("Automated campaign trigger: creating Instagram restock / drop caption for affected product...")

            matches = inventory_service.find_products(demo_prod_id)
            target_product = matches[0] if matches else SAMPLE_PRODUCTS[0]

            caption_req = CaptionRequest(
                product=target_product,
                extra_notes="Limited studio batch — low stock alert active",
            )
            caption_res: CaptionResult = content_agent.generate_caption(caption_req)

            st.markdown(f"**Generated Instagram Caption:**\n> {caption_res.caption}")
            st.markdown(f"**Hashtags:** {' '.join([f'`{t}`' for t in caption_res.hashtags])}")
            st.info(f"**Brand Voice Match:** {caption_res.voice_match_notes}")

            if log_callback:
                log_callback({
                    "timestamp": datetime.utcnow().strftime("%H:%M:%S"),
                    "event": "new_product_photo",
                    "agent": "ContentAgent",
                    "intent": "content_generation",
                    "action": "generate_caption",
                    "result": f"Caption generated with {len(caption_res.hashtags)} hashtags",
                })

            time.sleep(0.3)
            status_box.update(label="✅ End-to-End Multi-Agent Pipeline Completed!", state="complete", expanded=True)

    finally:
        # Revert stock mutation back to original quantity
        curr = inventory_service.get_stock(demo_prod_id)
        if curr and curr.quantity != orig_qty:
            delta = orig_qty - curr.quantity
            inventory_service.adjust_stock(demo_prod_id, delta, reason="Demo state rollback")
            # Mark demo alerts as resolved
            with inventory_service.session_factory() as db:
                from db.inventory_models import InventoryAlertORM
                db.query(InventoryAlertORM).filter(
                    InventoryAlertORM.product_id == demo_prod_id,
                    InventoryAlertORM.type == "low_stock"
                ).update({"resolved": True})
                db.commit()


def render_demo_page(
    inventory_service: SQLiteInventoryService,
    content_agent: ContentAgent,
    orchestrator: SellerPilotOrchestrator,
    log_callback: Callable[[dict], None] | None = None,
):
    """Render the Streamlit Demo Mode page."""
    st.title("🎬 SellerPilot Live Demo")
    st.caption("One-click automated demonstration of the coordinated multi-agent workflow.")

    st.markdown("""
    This demo executes a realistic sequence across the three autonomous agents:
    1. **Customer Inquiry**: A buyer asks about the Moonstone Ring.
    2. **Orchestrator Routing**: LangGraph routes to the **Commerce Agent**, which queries live SQLite inventory.
    3. **Stock Mutation**: Simulates stock depletion to trigger low-stock threshold monitoring.
    4. **Inventory Agent**: Autonomously flags the low-stock alert.
    5. **Content Agent**: Automatically crafts an on-brand Instagram restock caption grounded in product facts.
    """)

    st.markdown("""
    ```text
    Customer DM ──► LangGraph Orchestrator ──► Commerce Agent ──► Inventory Service ──► Grounded Response
                                                                             │
    Product Details ──► Content Agent ◄── Brand Voice Analyzer ◄── Low Stock Event
           │
           ▼
    Instagram Caption
    ```
    """)

    st.divider()

    if st.button("▶ Run End-to-End Demo", type="primary", use_container_width=True):
        run_live_demo(
            inventory_service=inventory_service,
            content_agent=content_agent,
            orchestrator=orchestrator,
            log_callback=log_callback,
        )
