"""SellerPilot AI — Streamlit Copilot Dashboard.

Architectural Viva Notes:
1. Unified Copilot Interface: Multi-page sidebar navigation linking real-time multi-agent systems:
   - 🏠 Overview: Real-time inventory KPIs and active system health.
   - 💬 Customer Conversations: Interactive conversational commerce with LangGraph routing.
   - 📦 Inventory: Atomic stock reservations, positive-bounded adjustments, and alert feeds.
   - ✍️ Content Studio: Fact-grounded Instagram caption generation adhering to Aura Jewels brand voice.
   - 🧠 Agent Activity: End-to-end auditability and observability of multi-agent state transitions.
   - 🎬 Demo Mode: One-click live demonstration with state rollback guarantees.
2. Zero Logic Duplication: Consumes existing core services (SQLiteInventoryService, ContentAgent,
   SellerPilotOrchestrator) without reimplementing domain logic.
3. Offline & Mock Resilient: Fully functional in standalone local development (USE_MOCKS=True or no API key).
"""

from datetime import datetime
from pathlib import Path
import sys
import pandas as pd
import streamlit as st

# Ensure repository root is on sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from agents.commerce.agent import ConversationalCommerceAgent
from agents.content.agent import ContentAgent
from agents.content.brand_voice import BrandVoiceAnalyzer
from agents.inventory.agent import InventoryAgent
from agents.inventory.service import SQLiteInventoryService
from core.config import settings
from core.mocks import MockContentService, SAMPLE_PRODUCTS
from core.schemas import (
    AgentAction,
    CaptionRequest,
    CaptionResult,
    Event,
    IncomingMessage,
    InventoryAlert,
    Product,
)
from dashboard.components import (
    get_stock_badge,
    render_caption_result,
    render_chat_message,
    render_inventory_alert_card,
    render_kpi_card,
)
from dashboard.demo import render_demo_page
from db.base import init_db
from orchestrator.graph import SellerPilotOrchestrator
from scripts.seed_db import seed_database


# -----------------------------------------------------------------------------
# App Configuration & Styling
# -----------------------------------------------------------------------------

st.set_page_config(
    page_title="SellerPilot AI Copilot",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
)


# -----------------------------------------------------------------------------
# Service Initializers & Session State
# -----------------------------------------------------------------------------

@st.cache_resource
def init_services():
    """Initialize database and core singleton agent services."""
    init_db()
    inv_service = SQLiteInventoryService()

    # Ensure catalog is seeded
    products = inv_service.get_all_products_with_stock()
    if len(products) == 0:
        seed_database()

    content_agent = ContentAgent()
    orchestrator = SellerPilotOrchestrator(inventory=inv_service, content=content_agent)
    return inv_service, content_agent, orchestrator


inv_service, content_agent, orchestrator = init_services()

# Session State for Activity Log & Chat History
if "activity_log" not in st.session_state:
    st.session_state.activity_log = [
        {
            "timestamp": datetime.utcnow().strftime("%H:%M:%S"),
            "event": "system_startup",
            "agent": "Orchestrator",
            "intent": "system_init",
            "action": "initialize_pipeline",
            "result": "SellerPilot AI initialized with SQLite inventory & Content Agent.",
        }
    ]

if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {
            "sender": "customer",
            "text": "Do you have the Moonstone Wire-Wrapped Ring in size 7?",
            "action": None,
        },
        {
            "sender": "assistant",
            "text": "Yes! The Moonstone Wire-Wrapped Ring is available in stock (8 available), priced at ₹1,450. Hand-forged in Sterling Silver & Rainbow Moonstone. ✨ Would you like to place an order?",
            "action": AgentAction(
                agent="commerce",
                intent="stock_query",  # type: ignore
                product_id="prod-101",
                response_text="Yes! The Moonstone Wire-Wrapped Ring is available in stock (8 available)...",
                escalate=False,
                confidence=0.95,
            ),
        }
    ]


def log_activity(entry: dict):
    """Append a structured entry to the session activity log."""
    st.session_state.activity_log.insert(0, entry)


# -----------------------------------------------------------------------------
# Sidebar Navigation
# -----------------------------------------------------------------------------

st.sidebar.title("✨ SellerPilot AI")
st.sidebar.caption("Multi-Agent Copilot for D2C Sellers")

page = st.sidebar.radio(
    "Navigation",
    [
        "🏠 Overview",
        "💬 Customer Conversations",
        "📦 Inventory",
        "✍️ Content Studio",
        "🧠 Agent Activity",
        "🎬 Demo Mode",
    ],
)

st.sidebar.divider()
st.sidebar.markdown(f"**Mode:** `{'Mock (Offline)' if settings.USE_MOCKS else 'Live Claude API'}`")
st.sidebar.markdown(f"**Database:** `{settings.DATABASE_URL}`")


# -----------------------------------------------------------------------------
# PAGE 1: 🏠 Overview
# -----------------------------------------------------------------------------

if page == "🏠 Overview":
    st.title("🏠 Store & Agent Overview")
    st.caption("Live monitoring of product inventory, active alerts, and autonomous agent operations.")

    # Fetch live inventory metrics
    inventory_items = inv_service.get_all_products_with_stock()
    alerts = inv_service.get_alerts()

    total_products = len(inventory_items)
    in_stock_count = sum(1 for item in inventory_items if item["in_stock"])
    low_stock_count = sum(1 for item in inventory_items if item["low_stock"])
    out_of_stock_count = sum(1 for item in inventory_items if not item["in_stock"])
    active_alerts_count = len(alerts)

    # 1. KPI Cards
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        render_kpi_card("Total Products", total_products, icon="📦")
    with col2:
        render_kpi_card("In Stock", in_stock_count, icon="🟢")
    with col3:
        render_kpi_card("Low Stock", low_stock_count, icon="🟡")
    with col4:
        render_kpi_card("Out of Stock", out_of_stock_count, icon="🔴")
    with col5:
        render_kpi_card("Active Alerts", active_alerts_count, icon="🚨")

    st.divider()

    # 2. Inventory Health Breakdown
    st.markdown("### 📊 Inventory Health")
    c1, c2, c3 = st.columns(3)
    healthy_pct = (in_stock_count - low_stock_count) / max(1, total_products) * 100
    low_stock_pct = low_stock_count / max(1, total_products) * 100
    oos_pct = out_of_stock_count / max(1, total_products) * 100

    c1.metric("Healthy Stock", f"{in_stock_count - low_stock_count} items", f"{healthy_pct:.1f}%")
    c2.metric("Low Stock Watchlist", f"{low_stock_count} items", f"{low_stock_pct:.1f}%")
    c3.metric("Depleted Stock", f"{out_of_stock_count} items", f"{oos_pct:.1f}%")

    st.divider()

    # 3. Recent Agent Activity
    st.markdown("### 🧠 Recent Agent Operations")
    if st.session_state.activity_log:
        recent_entries = st.session_state.activity_log[:5]
        for entry in recent_entries:
            st.info(
                f"**[{entry['timestamp']}] {entry['event']}** — Agent `{entry['agent']}` | "
                f"Action: `{entry['action']}` | Result: {entry['result']}"
            )
    else:
        st.write("No agent operations recorded yet.")


# -----------------------------------------------------------------------------
# PAGE 2: 💬 Customer Conversations
# -----------------------------------------------------------------------------

elif page == "💬 Customer Conversations":
    st.title("💬 Customer Conversations")
    st.caption("Conversational Commerce Agent answering inbound Instagram and WhatsApp customer queries.")

    # Quick scenario selector for demoing
    st.markdown("##### ⚡ Quick Viva Scenarios")
    quick_cols = st.columns(4)
    quick_query = None
    if quick_cols[0].button("💍 In-Stock Size 7 Ring"):
        quick_query = "Do you have the Moonstone Wire-Wrapped Ring in size 7?"
    if quick_cols[1].button("💰 Rose Gold Bangle Price"):
        quick_query = "How much is the Rose Gold Hammered Bangle?"
    if quick_cols[2].button("🚫 Freshwater Pearl (Sold Out)"):
        quick_query = "Is the Dainty Freshwater Pearl Choker in stock to order?"
    if quick_cols[3].button("🚨 30% Bargain (Escalation)"):
        quick_query = "Can you give me 30% discount if I buy two right now?"

    st.divider()

    # Display Chat History
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.chat_history:
            render_chat_message(
                sender=msg["sender"],
                text=msg["text"],
                action=msg.get("action"),
            )

    # Chat Input Box
    user_input = st.chat_input("Type a customer DM (e.g. 'Do you have the Raw Emerald Necklace in stock?')...")
    query_to_process = quick_query or user_input

    if query_to_process:
        # Add customer message to history
        st.session_state.chat_history.append({
            "sender": "customer",
            "text": query_to_process,
            "action": None,
        })

        # Process through LangGraph Orchestrator
        msg_obj = IncomingMessage(
            message_id=f"chat-{int(datetime.utcnow().timestamp() * 1000)}",
            customer_id="cust_store_guest",
            channel="instagram",
            text=query_to_process,
            timestamp=datetime.utcnow(),
        )
        event = Event(type="new_dm", payload={"message": msg_obj.model_dump()})
        action_res: AgentAction = orchestrator.process_event(event)  # type: ignore

        # Add assistant response to history
        st.session_state.chat_history.append({
            "sender": "assistant",
            "text": action_res.response_text,
            "action": action_res,
        })

        # Log activity
        log_activity({
            "timestamp": datetime.utcnow().strftime("%H:%M:%S"),
            "event": "new_dm",
            "agent": "CommerceAgent",
            "intent": action_res.intent.value,
            "action": "handle_dm",
            "result": f"Escalate={action_res.escalate} | Confidence={action_res.confidence:.2f}",
        })
        st.rerun()


# -----------------------------------------------------------------------------
# PAGE 3: 📦 Inventory
# -----------------------------------------------------------------------------

elif page == "📦 Inventory":
    st.title("📦 Inventory Management")
    st.caption("Live SQLite inventory truth, atomic stock reservations, and threshold alerts.")

    items = inv_service.get_all_products_with_stock()
    alerts = inv_service.get_alerts()

    # 1. Product Stock Table
    st.markdown("### 📋 Catalog & Live Stock Status")
    table_data = []
    for item in items:
        status_label = get_stock_badge(item["quantity"], item["low_stock"])
        table_data.append({
            "ID": item["product_id"],
            "Product": item["name"],
            "Category": item["category"],
            "Price (₹)": f"₹{item['price']:,.0f}",
            "Stock": item["quantity"],
            "Status": status_label,
            "On Instagram": "📸 Yes" if item["posted_on_instagram"] else "No",
        })

    df = pd.DataFrame(table_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    # 2. Interactive Actions: Reserve & Adjust
    col_res, col_adj = st.columns(2)

    with col_res:
        st.markdown("### 🔒 Reserve Stock")
        st.caption("Atomically hold stock for customer orders. Blocks overselling.")
        product_options = {item["name"]: item["product_id"] for item in items}
        selected_prod_name = st.selectbox("Select Product to Reserve", list(product_options.keys()), key="res_prod")
        reserve_qty = st.number_input("Quantity to Reserve", min_value=1, max_value=100, value=1, key="res_qty")

        if st.button("Reserve Stock", type="primary", use_container_width=True):
            target_id = product_options[selected_prod_name]
            stock_info = inv_service.get_stock(target_id)
            current_q = stock_info.quantity if stock_info else 0

            success = inv_service.reserve(target_id, reserve_qty)
            if success:
                updated_stock = inv_service.get_stock(target_id)
                new_q = updated_stock.quantity if updated_stock else 0
                st.success(f"Successfully reserved {reserve_qty} unit(s) of '{selected_prod_name}'! Remaining stock: {new_q}.")
                log_activity({
                    "timestamp": datetime.utcnow().strftime("%H:%M:%S"),
                    "event": "stock_reservation",
                    "agent": "InventoryService",
                    "intent": "reserve",
                    "action": "reserve_stock",
                    "result": f"Reserved {reserve_qty} of {target_id} ({current_q} -> {new_q})",
                })
                st.rerun()
            else:
                st.error(f"Reservation failed! Requested {reserve_qty} unit(s), but only {current_q} in stock.")
                log_activity({
                    "timestamp": datetime.utcnow().strftime("%H:%M:%S"),
                    "event": "reservation_rejected",
                    "agent": "InventoryService",
                    "intent": "reserve",
                    "action": "reserve_stock",
                    "result": f"Oversell blocked: requested {reserve_qty}, available {current_q}",
                })

    with col_adj:
        st.markdown("### ⚖️ Adjust Stock")
        st.caption("Manual stock updates for restocks or damaged goods. Never allows negative inventory.")
        selected_adj_prod = st.selectbox("Select Product to Adjust", list(product_options.keys()), key="adj_prod")
        adj_delta = st.number_input("Stock Adjustment Delta (+/-)", value=5, step=1, key="adj_delta")
        adj_reason = st.text_input("Operational Reason", value="Studio artisan restock", key="adj_reason")

        if st.button("Apply Stock Adjustment", use_container_width=True):
            target_id = product_options[selected_adj_prod]
            success, updated_stock, prev_q, err_msg = inv_service.adjust_stock(
                product_id=target_id,
                quantity_delta=adj_delta,
                reason=adj_reason,
            )
            if success and updated_stock:
                st.success(f"Stock adjusted by {adj_delta:+d} ({prev_q} -> {updated_stock.quantity}). Reason: {adj_reason}")
                log_activity({
                    "timestamp": datetime.utcnow().strftime("%H:%M:%S"),
                    "event": "stock_adjustment",
                    "agent": "InventoryService",
                    "intent": "adjust",
                    "action": "adjust_stock",
                    "result": f"Adjusted {target_id} ({prev_q} -> {updated_stock.quantity})",
                })
                st.rerun()
            else:
                st.error(f"Adjustment rejected: {err_msg}")

    st.divider()

    # 3. Active Inventory Alerts
    st.markdown("### 🚨 Active Inventory Alerts")
    if alerts:
        for alert in alerts:
            render_inventory_alert_card(alert)
    else:
        st.success("No active inventory alerts. All product inventory is healthy! ✨")


# -----------------------------------------------------------------------------
# PAGE 4: ✍️ Content Studio
# -----------------------------------------------------------------------------

elif page == "✍️ Content Studio":
    st.title("✍️ Content Studio & Brand Voice")
    st.caption("AI-generated social media captions strictly grounded in catalog facts and Aura Jewels brand voice.")

    all_products = inv_service.find_products("")
    product_map = {p.name: p for p in all_products}

    col_input, col_voice = st.columns([3, 2])

    with col_input:
        st.markdown("### 📝 Caption Generator")
        selected_name = st.selectbox("Select Catalog Product", list(product_map.keys()))
        selected_prod: Product = product_map[selected_name]

        st.caption(f"**Material:** {selected_prod.material} | **Price:** ₹{selected_prod.price:,.0f} | **Category:** {selected_prod.category}")

        img_path = st.text_input("Optional Local Image Path", value=selected_prod.image_path or "")
        notes = st.text_area("Additional Campaign Notes / Highlights", value="Exclusive artisan batch drop")

        if st.button("✨ Generate Instagram Caption", type="primary", use_container_width=True):
            req = CaptionRequest(
                product=selected_prod,
                image_path=img_path if img_path else None,
                extra_notes=notes if notes else None,
            )
            caption_result: CaptionResult = content_agent.generate_caption(req)

            st.divider()
            render_caption_result(caption_result)

            log_activity({
                "timestamp": datetime.utcnow().strftime("%H:%M:%S"),
                "event": "caption_generated",
                "agent": "ContentAgent",
                "intent": "content_generation",
                "action": "generate_caption",
                "result": f"Generated caption for {selected_prod.id} with {len(caption_result.hashtags)} hashtags",
            })

    with col_voice:
        st.markdown("### 🎨 Learned Brand Voice")
        analyzer = BrandVoiceAnalyzer()
        profile = analyzer.get_profile()

        st.markdown("**Tone Descriptors:**")
        st.write(", ".join([f"`{t}`" for t in profile.tone_descriptors]))

        st.markdown("**Emoji Usage Style:**")
        st.info(profile.emoji_style)

        st.markdown("**Signature Brand Hashtags:**")
        st.write(" ".join([f"`{h}`" for h in profile.hashtags[:8]]))

        st.markdown("**Sample Captions Reference:**")
        for idx, sample in enumerate(profile.sample_captions[:2], 1):
            with st.expander(f"Sample Post {idx}", expanded=False):
                st.caption(sample)


# -----------------------------------------------------------------------------
# PAGE 5: 🧠 Agent Activity
# -----------------------------------------------------------------------------

elif page == "🧠 Agent Activity":
    st.title("🧠 Agent Activity & Audit Trail")
    st.caption("Complete, structured trace of multi-agent routing decisions, stock queries, and content generation.")

    col_filter, col_clear = st.columns([4, 1])
    with col_filter:
        agent_filter = st.selectbox(
            "Filter by Agent",
            ["All Agents", "CommerceAgent", "InventoryAgent", "ContentAgent", "InventoryService", "Orchestrator"],
        )
    with col_clear:
        st.write("")
        st.write("")
        if st.button("Clear Log"):
            st.session_state.activity_log = []
            st.rerun()

    logs = st.session_state.activity_log
    if agent_filter != "All Agents":
        logs = [l for l in logs if l.get("agent") == agent_filter]

    if logs:
        activity_df = pd.DataFrame(logs)
        st.dataframe(activity_df, use_container_width=True, hide_index=True)
    else:
        st.write("No matching agent activity recorded.")


# -----------------------------------------------------------------------------
# PAGE 6: 🎬 Demo Mode
# -----------------------------------------------------------------------------

elif page == "🎬 Demo Mode":
    render_demo_page(
        inventory_service=inv_service,
        content_agent=content_agent,
        orchestrator=orchestrator,
        log_callback=log_activity,
    )
